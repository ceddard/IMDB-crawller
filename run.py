"""
IMDb Crawler Pipeline - Main Entry Point

Simple orchestrator that delegates all functionality to the service layer.
"""

import asyncio
import logging

from dotenv import load_dotenv

from service import (
    Config,
    OutputHandler,
    run_crawl_pipeline,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

load_dotenv()


async def main():
    """Main entry point - simplified orchestration."""
    config = Config()
    logger.info(f"Configuration: {config}")
    
    records = await run_crawl_pipeline(
        config=config,
        per_page=config.per_page,
        max_pages=config.max_pages,
        worker_count=config.worker_count,
        resume=config.resume
    )
    
    if not records:
        logger.warning("No records collected")
        return
    
    logger.info(f"Crawl complete: {len(records)} records")
    
    output_handler = OutputHandler(
        s3_bucket=config.s3_bucket,
        s3_prefix=config.s3_prefix
    )
    success, output_file = output_handler.save_and_upload(records, config.output_file)
    
    if success:
        logger.info(f"Data saved to {output_file}")
    else:
        logger.error("Failed to save data")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nShutdown requested by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        exit(1)
