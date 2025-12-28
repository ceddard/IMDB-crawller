"""
IMDb Crawler Pipeline

Orchestrates data fetching, transformation, and collection.
Handles pagination, error recovery, and backoff management.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from service.config import Config

from service import (
    GraphQLClient,
    TitleNode,
    ProgressManager,
    ErrorHandler,
    validate_graphql_response,
)
from service.exceptions import NetworkError, HTTPStatusError

logger = logging.getLogger(__name__)


def find_title_list(data: Any) -> Optional[List[Any]]:
    """Recursively find the title list in the GraphQL response."""
    if isinstance(data, dict):
        advanced_search = data.get("data", {}).get("advancedTitleSearch")
        if advanced_search and "edges" in advanced_search:
            return advanced_search["edges"]
        for value in data.values():
            result = find_title_list(value)
            if result:
                return result
    elif isinstance(data, list):
        for value in data:
            result = find_title_list(value)
            if result:
                return result
    return None


def find_page_info(data: Any) -> Optional[Dict[str, Any]]:
    """Recursively find the pageInfo block in the GraphQL response."""
    if isinstance(data, dict):
        if "pageInfo" in data and isinstance(data["pageInfo"], dict):
            return data["pageInfo"]
        for value in data.values():
            res = find_page_info(value)
            if res:
                return res
    elif isinstance(data, list):
        for value in data:
            res = find_page_info(value)
            if res:
                return res
    return None


def find_cursor(data: Any) -> Optional[str]:
    """Recursively find the pagination cursor in the GraphQL response."""
    if isinstance(data, dict):
        page_info = data.get("pageInfo")
        if page_info and "endCursor" in page_info:
            return page_info["endCursor"]
        for value in data.values():
            cursor = find_cursor(value)
            if cursor:
                return cursor
    elif isinstance(data, list):
        for value in data:
            cursor = find_cursor(value)
            if cursor:
                return cursor
    return None


async def run_crawl_pipeline(
    config: "Config",
    per_page: int = 100,
    max_pages: int | str = "all",
    worker_count: Optional[int] = None,
    resume: bool = True,
    streaming: bool = False,
    stream_handler: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """
    Main crawl pipeline orchestrator.
    
    Args:
        config: Application configuration
        per_page: Items per page (1-10000, recommended 100)
        max_pages: Max pages to fetch (int or 'all'/'unlimited')
        worker_count: Thread workers for transformation (1-24)
        resume: Resume from saved progress if available
        streaming: Enable streaming output (save incrementally)
        stream_handler: StreamingOutputHandler instance (if streaming=True)
        
    Returns:
        List of Bronze records (or empty if streaming)
    """
    graphql_client = GraphQLClient(config, per_page=per_page)
    progress_mgr = ProgressManager()
    error_handler = ErrorHandler()
    
    if worker_count is None:
        worker_count = 24
    else:
        worker_count = max(1, min(24, worker_count))
    
    unlimited = False
    if isinstance(max_pages, int):
        unlimited = max_pages <= 0
    else:
        unlimited = str(max_pages).strip().lower() in {"0", "all", "unlimited"}
    
    collected: List[Dict[str, Any]] = []
    page_no = 0
    after: Optional[str] = None
    
    if resume:
        state = progress_mgr.load()
        if state:
            after = state.get("cursor")
            page_no = state.get("page_no", 0)
    
    logger.info(f"Starting crawl pipeline: per_page={per_page}, max_pages={max_pages}, workers={worker_count}")
    logger.info(f"HTTP/2 settings: connections={graphql_client.http_pool_connections}, keepalive={graphql_client.http_pool_maxsize}, timeout={graphql_client.http_timeout}s")
    
    try:
        async with graphql_client._create_async_client() as aclient:
            loop = asyncio.get_running_loop()
            next_task: Optional[asyncio.Task] = None
            next_req_started_at: Optional[float] = None
            consecutive_errors = 0
            max_consecutive_errors = 5
            
            while True:
                logger.info(f"Requesting page {page_no + 1} (cursor present={bool(after)})")
                
                try:
                    if next_task is None:
                        resp, t_req_ms = await graphql_client.fetch_page(aclient, after)
                    else:
                        resp, t_req_ms = await next_task
                    
                    if error_handler.is_rate_limited(resp):
                        logger.error(f"Rate limited! HTTP {resp.status_code}. Pausing for 60s...")
                        await asyncio.sleep(60)
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            logger.error(f"Too many errors ({consecutive_errors}), stopping")
                            break
                        continue
                    
                    resp.raise_for_status()
                    data = resp.json()
                    
                    if not validate_graphql_response(data):
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            break
                        continue
                    
                    consecutive_errors = 0
                    
                except httpx.HTTPStatusError as e:
                    raise HTTPStatusError(e.response.status_code, f"HTTP {e.response.status_code}: {e}")
                except (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError) as e:
                    raise NetworkError(f"Network error: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error: {e}", exc_info=True)
                    break
                
                items = find_title_list(data)
                if not items:
                    logger.warning("No items found in response")
                    break
                
                page_info = find_page_info(data) or {}
                has_next = page_info.get("hasNextPage")
                after = find_cursor(data)
                pages_done = page_no + 1
                remaining = 0 if unlimited else max(0, (max_pages if isinstance(max_pages, int) else 0) - pages_done)
                
                t_map_start = datetime.now(timezone.utc).timestamp()
                with ThreadPoolExecutor(max_workers=worker_count) as executor:
                    transform_tasks = [
                        loop.run_in_executor(
                            executor,
                            TitleNode.transform,
                            item.get("node", item),
                            page_no
                        )
                        for item in items
                    ]
                    try:
                        records = await asyncio.gather(*transform_tasks, return_exceptions=False)
                    except Exception as ex:
                        logger.error(f"Transform failed: {ex}")
                        records = [TitleNode.transform(item.get("node", item), page_no) for item in items]
                
                t_map_ms = (datetime.now(timezone.utc).timestamp() - t_map_start) * 1000
                
                if streaming and stream_handler:
                    stream_handler.add_records(records, page_no)
                    total_records = stream_handler.record_count
                else:
                    collected.extend(records)
                    total_records = len(collected)
                
                if pages_done % 10 == 0:
                    if streaming:
                        progress_mgr.save(after, pages_done, [])
                    else:
                        progress_mgr.save(after, pages_done, collected)
                
                logger.info(
                    f"Processed page {pages_done} items={len(items)} total={total_records} "
                    f"remaining={remaining} has_next={has_next} "
                    f"t_request_ms={t_req_ms:.1f} t_map_ms={t_map_ms:.1f} delay_ms={graphql_client.current_delay_sec*1000:.0f}"
                )
                
                if not after:
                    logger.info(f"No more pages (no cursor). Completed {pages_done} pages")
                    break
                if has_next is False:
                    logger.info(f"hasNextPage=False. Completed {pages_done} pages")
                    break
                if not unlimited and pages_done >= max_pages:
                    logger.info(f"Reached max_pages={max_pages}")
                    break
                
                graphql_client.update_backoff(t_req_ms)
                await graphql_client.apply_backoff()
                
                if graphql_client.should_pipeline(t_req_ms):
                    next_req_started_at = datetime.now(timezone.utc).timestamp()
                    next_task = asyncio.create_task(graphql_client.fetch_page(aclient, after))
                else:
                    next_task = None
                    next_req_started_at = None
                
                page_no += 1
            
            if next_task and not next_task.done():
                next_task.cancel()
                try:
                    await next_task
                except asyncio.CancelledError:
                    logger.debug("Pending request cancelled")
            
            if not streaming:
                if collected:
                    progress_mgr.save(after, page_no, collected)
                    logger.info(f"Final save: {len(collected)} total records")
            else:
                logger.info(f"Streaming complete: {stream_handler.record_count if stream_handler else 0} records")
    
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        if not streaming and collected:
            progress_mgr.save(after, page_no, collected)
            logger.info(f"Progress saved: {len(collected)} records")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        if not streaming and collected:
            progress_mgr.save(after, page_no, collected)
    
    return collected if not streaming else []
