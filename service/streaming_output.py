"""Streaming output handler for real-time data saving."""

import gzip
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from service.s3_uploader import S3Uploader

logger = logging.getLogger(__name__)


class StreamingOutputHandler:
    """Handles streaming output to JSONL gzip file and S3."""
    
    def __init__(
        self,
        output_file: Optional[str] = None,
        s3_bucket: Optional[str] = None,
        s3_prefix: str = "imdb/bronze/",
        buffer_size: int = 100,
        run_start_ts: Optional[str] = None
    ):
        """Initialize streaming output handler.
        
        Args:
            output_file: Output file path (auto-generated if not provided)
            s3_bucket: Optional S3 bucket for uploads
            s3_prefix: S3 key prefix
            buffer_size: How many records to buffer before flushing (if using S3)
        """
        self.run_start_ts = run_start_ts or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        self.output_file = output_file or self._generate_output_file()
        self.s3_uploader = S3Uploader(bucket=s3_bucket, prefix=s3_prefix)
        self.buffer_size = buffer_size
        self.record_count = 0
        self.file_handle = None
        self.buffer = []
        
    def _generate_output_file(self) -> str:
        """Generate output file path using the pipeline start timestamp."""
        return f"imdb_data_{self.run_start_ts}.jsonl.gz"
    
    def _open_file(self):
        """Open gzip file for appending."""
        if self.file_handle is None:
            # Open in append mode if file exists, otherwise create new
            mode = 'ab' if os.path.exists(self.output_file) else 'wb'
            self.file_handle = gzip.open(self.output_file, mode)
            logger.info(f"Opened output file: {self.output_file}")
    
    def add_record(self, record: Dict[str, Any]) -> None:
        """Add a single record to the stream.
        
        Args:
            record: Record to add
        """
        self._open_file()
        self.buffer.append(record)
        self.record_count += 1
        
        # Flush buffer if it reaches the threshold
        if len(self.buffer) >= self.buffer_size:
            self.flush()
    
    def add_records(self, records: list) -> None:
        """Add multiple records to the stream.
        
        Args:
            records: Records to add
        """
        for record in records:
            self.add_record(record)
    
    def flush(self) -> None:
        """Flush buffered records to file."""
        if not self.buffer or self.file_handle is None:
            return
        
        try:
            for record in self.buffer:
                line = json.dumps(record, default=str)
                self.file_handle.write((line + '\n').encode('utf-8'))
            
            self.file_handle.flush()
            os.fsync(self.file_handle.fileno())  # Force disk sync
            
            logger.debug(f"Flushed {len(self.buffer)} records to {self.output_file}")
            self.buffer.clear()
        except Exception as e:
            logger.error(f"Error flushing records: {e}", exc_info=True)
            raise
    
    def close(self) -> bool:
        """Close file and optionally upload to S3.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Flush remaining records
            if self.buffer:
                self.flush()
            
            # Close file
            if self.file_handle:
                self.file_handle.close()
                self.file_handle = None
                logger.info(f"Closed output file: {self.output_file} ({self.record_count} records)")
            
            # Verify file size
            if os.path.exists(self.output_file):
                file_size = os.path.getsize(self.output_file)
                logger.info(f"Output file size: {file_size:,} bytes ({self.record_count} records)")
            
            return True
        except Exception as e:
            logger.error(f"Error closing file: {e}", exc_info=True)
            return False
    
    def upload_to_s3(self) -> bool:
        """Upload completed file to S3.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.s3_uploader.enabled:
            logger.warning("S3 upload not configured")
            return False
        
        try:
            success = self.s3_uploader.upload(self.output_file)
            if success:
                logger.info(f"✅ Uploaded to S3: s3://{self.s3_uploader.bucket}/{self.s3_uploader.prefix}")
            return success
        except Exception as e:
            logger.error(f"Error uploading to S3: {e}", exc_info=True)
            return False
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        if exc_type is None:
            self.upload_to_s3()
