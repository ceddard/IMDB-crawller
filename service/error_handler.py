"""Error handling, retry logic, and rate limit detection."""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ErrorHandler:
    """Handles different types of errors with appropriate logging and recovery strategies."""
    
    @staticmethod
    def is_rate_limited(response: httpx.Response) -> bool:
        """Detect rate limiting from response status/headers.
        
        Returns:
            True if rate limited, False otherwise
        """
        if response.status_code in (429, 503, 502):
            logger.warning(f"Rate limited: HTTP {response.status_code}")
            return True
        
        retry_after = response.headers.get("retry-after")
        if retry_after:
            logger.warning(f"Server sent Retry-After header: {retry_after}")
            return True
        
        return False
    
    @staticmethod
    def is_transient_error(error: Exception) -> bool:
        """Check if error is transient (can be retried).
        
        Returns:
            True if transient, False if permanent
        """
        return isinstance(error, (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError))
    
    @staticmethod
    def log_error(error: Exception, context: str = "") -> None:
        """Log error with appropriate level based on type.
        
        Args:
            error: The exception that occurred
            context: Additional context about where error occurred
        """
        if isinstance(error, httpx.HTTPStatusError):
            logger.error(f"HTTP {error.response.status_code} error{f' ({context})' if context else ''}: {error}")
        elif isinstance(error, (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError)):
            logger.warning(f"Network error{f' ({context})' if context else ''}: {error}")
        else:
            logger.error(f"Unexpected error{f' ({context})' if context else ''}: {error}", exc_info=True)


def is_rate_limited(response: httpx.Response) -> bool:
    """Convenience function for rate limit detection."""
    return ErrorHandler.is_rate_limited(response)


def validate_graphql_response(data: Any) -> bool:
    """Validate that response contains expected GraphQL structure.
    
    Args:
        data: Response data to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(data, dict):
        logger.error(f"Response is not a dict: {type(data)}")
        return False
    
    if "errors" in data and data["errors"]:
        logger.error(f"GraphQL errors: {data['errors']}")
        return False
    
    if "data" not in data:
        logger.error("No 'data' field in GraphQL response")
        return False
    
    return True
