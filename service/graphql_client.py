"""GraphQL client with HTTP/2 pooling and pipelined requests."""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from service.config import Config

logger = logging.getLogger(__name__)


class GraphQLClient:
    """GraphQL client for IMDb API with pipelined requests and adaptive backoff."""
    
    ENDPOINT = "https://caching.graphql.imdb.com/"
    SHA = "9fc7c8867ff66c1e1aa0f39d0fd4869c64db97cddda14fea1c048ca4b568f06a"
    
    def __init__(self, config: "Config", per_page: int = 100):
        """Initialize GraphQL client.
        
        Args:
            config: Application configuration
            per_page: Items per page (1-10000, recommended 100)
        """
        self.config = config
        self.per_page = max(1, min(10000, per_page))
        
        self.http_pool_connections = config.http_pool_connections
        self.http_pool_maxsize = config.http_pool_maxsize
        self.http_timeout = config.http_timeout
        
        self.base_delay_ms = config.page_delay_ms
        self.base_delay_sec = max(0.0, self.base_delay_ms / 1000.0)
        self.current_delay_sec = self.base_delay_sec
        
        self.backoff_threshold_ms = config.backoff_threshold_ms
        self.backoff_step_ms = config.backoff_step_ms
        self.backoff_max_ms = config.backoff_max_ms
        self.backoff_step_sec = max(0.0, self.backoff_step_ms / 1000.0)
        self.backoff_max_sec = max(0.0, self.backoff_max_ms / 1000.0)
    
    def _create_async_client(self) -> httpx.AsyncClient:
        """Create HTTP/2 async client with connection pooling."""
        headers = {
            "accept": "application/graphql+json, application/json",
            "content-type": "application/json",
            "accept-encoding": "gzip",
            "user-agent": self.config.user_agent
        }
        limits = httpx.Limits(
            max_connections=self.http_pool_connections,
            max_keepalive_connections=self.http_pool_maxsize,
        )
        return httpx.AsyncClient(
            http2=True,
            headers=headers,
            limits=limits,
            timeout=self.http_timeout
        )
    
    def _build_payload(self, after: Optional[str]) -> Dict[str, Any]:
        """Build GraphQL query payload.
        
        Args:
            after: Pagination cursor
            
        Returns:
            GraphQL request payload
        """
        variables = {
            "first": self.per_page,
            "after": after,
            "locale": self.config.locale,
            "sortBy": self.config.graphql_sortby,
            "sortOrder": self.config.graphql_sortorder,
            "titleTypeConstraint": {
                "anyTitleTypeIds": ["movie", "tvSeries", "short", "tvMiniSeries", "tvMovie", "tvEpisode"],
                "excludeTitleTypeIds": []
            }
        }
        return {
            "operationName": "AdvancedTitleSearch",
            "variables": variables,
            "extensions": {"persistedQuery": {"sha256Hash": self.SHA, "version": 1}}
        }
    
    async def fetch_page(self, client: httpx.AsyncClient, after: Optional[str]) -> tuple[httpx.Response, float]:
        """Fetch a single page.
        
        Args:
            client: Async HTTP client
            after: Pagination cursor
            
        Returns:
            Tuple of (response, request_time_ms)
        """
        t_start = time.perf_counter()
        payload = self._build_payload(after)
        response = await client.post(self.ENDPOINT, json=payload)
        t_ms = (time.perf_counter() - t_start) * 1000
        return response, t_ms
    
    def update_backoff(self, t_request_ms: float) -> None:
        """Update adaptive backoff based on request latency.
        
        Args:
            t_request_ms: Request time in milliseconds
        """
        if self.backoff_threshold_ms > 0:
            if t_request_ms > self.backoff_threshold_ms:
                self.current_delay_sec = min(self.backoff_max_sec, self.current_delay_sec + self.backoff_step_sec)
            elif self.current_delay_sec > self.base_delay_sec and t_request_ms < (0.5 * self.backoff_threshold_ms):
                self.current_delay_sec = max(self.base_delay_sec, self.current_delay_sec - (self.backoff_step_sec / 2.0))
    
    async def apply_backoff(self) -> None:
        """Apply backoff delay before next request."""
        if self.current_delay_sec > 0:
            await asyncio.sleep(self.current_delay_sec)
    
    def should_pipeline(self, t_request_ms: float) -> bool:
        """Determine if next request should be pipelined.
        
        Args:
            t_request_ms: Request time in milliseconds
            
        Returns:
            True if safe to pipeline, False otherwise
        """
        return t_request_ms <= self.backoff_threshold_ms
