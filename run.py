"""
IMDb Crawler Pipeline - Main Entry Point

Simple orchestrator that delegates all functionality to the service layer.
Supports both batch and streaming modes.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone

from dotenv import load_dotenv

from service import (
    Config,
    OutputHandler,
    run_crawl_pipeline,
)
from service.streaming_output import StreamingOutputHandler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

load_dotenv()


async def main():
    """Main entry point - ALWAYS uses streaming to avoid OOM."""
    config = Config()
    logger.info(f"Configuration: {config}")
    run_start_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    
    # ALWAYS use streaming mode to prevent memory exhaustion
    logger.info("🌊 Running in STREAMING mode (memory-safe incremental save)")
    
    with StreamingOutputHandler(
        output_file=config.output_file,
        s3_bucket=config.s3_bucket,
        s3_prefix=config.s3_prefix,
        buffer_size=50,  # Flush every 50 records
        run_start_ts=run_start_ts
    ) as stream_handler:
        await run_crawl_pipeline(
            config=config,
            per_page=config.per_page,
            max_pages=config.max_pages,
            worker_count=config.worker_count,
            resume=config.resume,
            streaming=True,
            stream_handler=stream_handler
        )
        
        logger.info(f"✅ Crawl complete: {stream_handler.record_count} records streamed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nShutdown requested by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        exit(1)
