"""Output handling: JSONL gzip and S3 upload."""

import gzip
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from service.s3_uploader import S3Uploader

logger = logging.getLogger(__name__)


class OutputHandler:
    """Handles saving and uploading crawled data."""
    
    def __init__(self, s3_bucket: Optional[str] = None, s3_prefix: str = "imdb/bronze/"):
        """Initialize output handler.
        
        Args:
            s3_bucket: Optional S3 bucket for uploads
            s3_prefix: S3 key prefix
        """
        self.s3_uploader = S3Uploader(bucket=s3_bucket, prefix=s3_prefix)
    
    @staticmethod
    def _generate_output_file(custom_path: Optional[str] = None) -> str:
        """Generate output file path.
        
        Args:
            custom_path: Custom output path (if provided via env/config)
            
        Returns:
            Output file path
        """
        if custom_path:
            return custom_path
        
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        return f"imdb_bronze_{timestamp}.jsonl.gz"
    
    @staticmethod
    def save_jsonl_gzip(output_file: str, records: List[Dict[str, Any]]) -> bool:
        """Save records to JSONL gzip file.
        
        Args:
            output_file: Output file path
            records: Records to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with gzip.open(output_file, "wt", encoding="utf-8") as f:
                for record in records:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            
            logger.info(f"Saved JSONL gzip: {output_file} ({len(records)} records)")
            
            if not os.path.exists(output_file):
                logger.error(f"Output file not created: {output_file}")
                return False
            
            file_size = os.path.getsize(output_file)
            logger.info(f"Output file verified: {file_size} bytes")
            return True
        
        except IOError as e:
            logger.error(f"Failed to write output file: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during save: {e}", exc_info=True)
            return False
    
    def save_and_upload(
        self,
        records: List[Dict[str, Any]],
        output_file: Optional[str] = None
    ) -> tuple[bool, str]:
        """Save records and optionally upload to S3.
        
        Args:
            records: Records to save
            output_file: Custom output file path
            
        Returns:
            Tuple of (success: bool, file_path: str)
        """
        output_file = self._generate_output_file(output_file)
        
        if not self.save_jsonl_gzip(output_file, records):
            return False, output_file
        
        if self.s3_uploader.enabled:
            if self.s3_uploader.upload(output_file):
                logger.info("S3 upload successful")
            else:
                logger.warning("S3 upload failed, but local file preserved")
        
        return True, output_file
