"""Configuration parsing and validation."""

import logging
import os
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)


class Config:
    """Application configuration with validation."""
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        # Pipeline config
        self.per_page = self._parse_per_page()
        self.max_pages = self._parse_max_pages()
        self.worker_count = self._parse_worker_count()
        self.resume = os.getenv("RESUME", "true").lower() in {"true", "1", "yes"}
        
        # Output config
        self.output_file = os.getenv("OUT_JSONL", None)
        self.s3_bucket = os.getenv("S3_BUCKET", None)
        self.s3_prefix = os.getenv("S3_PREFIX", "imdb/bronze/")
        
        # HTTP config
        self.http_pool_connections = int(os.getenv("HTTP_POOL_CONNECTIONS", "40"))
        self.http_pool_maxsize = int(os.getenv("HTTP_POOL_MAXSIZE", "100"))
        self.http_timeout = float(os.getenv("HTTP_TIMEOUT", "30"))
        self.user_agent = os.getenv("USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        
        # Backoff config
        self.page_delay_ms = float(os.getenv("PAGE_DELAY_MS", "150"))
        self.backoff_threshold_ms = float(os.getenv("BACKOFF_THRESHOLD_MS", "2000"))
        self.backoff_step_ms = float(os.getenv("BACKOFF_STEP_MS", "200"))
        self.backoff_max_ms = float(os.getenv("BACKOFF_MAX_MS", "1200"))
        
        # GraphQL query config
        self.locale = os.getenv("LOCALE", "pt-BR")
        self.graphql_sortby = os.getenv("GRAPHQL_SORTBY", "POPULARITY")
        self.graphql_sortorder = os.getenv("GRAPHQL_SORTORDER", "ASC")
        self.title_types = self._parse_title_types()
    
    @staticmethod
    def _parse_per_page() -> int:
        """Parse and validate PER_PAGE environment variable.
        
        Returns:
            Valid per_page value (1-10000, default 100)
        """
        per_page_env = os.getenv("PER_PAGE", "1000")
        try:
            per_page = int(per_page_env)
            if per_page < 1 or per_page > 10000:
                logger.warning(f"PER_PAGE {per_page} out of range [1-10000], using 100")
                return 100
            return per_page
        except ValueError:
            logger.warning(f"Invalid PER_PAGE: {per_page_env}, using 100")
            return 100
    
    @staticmethod
    def _parse_max_pages() -> Union[int, str]:
        """Parse MAX_PAGES environment variable.
        
        Returns:
            Integer or string ('all', 'unlimited', '0')
        """
        max_pages_env = os.getenv("MAX_PAGES", "all")
        try:
            return int(max_pages_env)
        except (TypeError, ValueError):
            return max_pages_env
    
    @staticmethod
    def _parse_worker_count() -> Optional[int]:
        """Parse and validate WORKER_COUNT environment variable.
        
        Returns:
            Valid worker count (1-24) or None for default (24)
        """
        worker_count_env = os.getenv("WORKER_COUNT", "24")
        try:
            return max(1, min(int(worker_count_env), 24))
        except ValueError:
            logger.warning(f"Invalid WORKER_COUNT: {worker_count_env}, using default")
            return None

    @staticmethod
    def _parse_title_types() -> list[str]:
        """Parse TITLE_TYPES env (comma-separated) with safe defaults."""
        default_types = [
            "movie",
            "tvSeries",
            "short",
            "tvEpisode",
            "tvMiniSeries",
            "tvMovie",
            "tvShort",
            "tvSpecial",
            "musicVideo",
            "podcastEpisode",
            "video",
            "videoGame",
            "podcastSeries",
        ]

        raw = os.getenv("TITLE_TYPES")
        if not raw:
            return default_types

        parsed = [t.strip() for t in raw.split(",") if t.strip()]
        return parsed or default_types
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for logging."""
        return {
            "per_page": self.per_page,
            "max_pages": self.max_pages,
            "worker_count": self.worker_count,
            "resume": self.resume,
            "output_file": self.output_file,
            "s3_bucket": self.s3_bucket,
        }
    
    def __str__(self) -> str:
        """String representation of config."""
        return f"Config(per_page={self.per_page}, max_pages={self.max_pages}, workers={self.worker_count or 24})"
