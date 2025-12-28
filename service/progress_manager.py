"""Progress state management for crawl resumption."""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ProgressManager:
    """Manages saving and loading crawl progress state."""
    
    def __init__(self, state_file: str = ".crawl_state.json"):
        """Initialize progress manager.
        
        Args:
            state_file: Path to state file for persistence
        """
        self.state_file = state_file
    
    def save(self, cursor: Optional[str], page_no: int, records: List[Dict[str, Any]]) -> None:
        """Save crawl progress state to file.
        
        Args:
            cursor: Pagination cursor for next page
            page_no: Current page number
            records: Collected records so far
        """
        try:
            state = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "cursor": cursor,
                "page_no": page_no,
                "records_count": len(records),
                "sample_record": records[-1] if records else None
            }
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2, default=str)
            logger.debug(f"Progress saved: {page_no} pages, {len(records)} records")
        except Exception as e:
            logger.warning(f"Failed to save progress: {e}")
    
    def load(self) -> Optional[Dict[str, Any]]:
        """Load previous crawl progress state.
        
        Returns:
            State dict with cursor, page_no, records_count if exists, None otherwise
        """
        if not os.path.exists(self.state_file):
            return None
        
        try:
            with open(self.state_file, "r") as f:
                state = json.load(f)
            logger.info(
                f"Loaded progress: page {state.get('page_no', 0)}, "
                f"{state.get('records_count', 0)} records, "
                f"cursor={bool(state.get('cursor'))}"
            )
            return state
        except Exception as e:
            logger.warning(f"Failed to load progress: {e}")
            return None
    
    def clear(self) -> None:
        """Clear saved progress state."""
        if os.path.exists(self.state_file):
            try:
                os.remove(self.state_file)
                logger.info("Progress state cleared")
            except Exception as e:
                logger.warning(f"Failed to clear progress: {e}")
