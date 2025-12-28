"""S3 upload functionality."""

import json
import logging
import os
from typing import Optional
from datetime import datetime, timezone

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from service.exceptions import S3UploadError

logger = logging.getLogger(__name__)


class S3Uploader:
    """Handles uploading files to AWS S3."""
    
    def __init__(self, bucket: Optional[str] = None, prefix: str = "imdb/bronze/", region: str = "us-east-1", run_timestamp: Optional[str] = None):
        """Initialize S3 uploader.
        
        Args:
            bucket: S3 bucket name
            prefix: S3 key prefix
            region: AWS region
            run_timestamp: Run timestamp for partitioning
        """
        self.bucket = bucket
        self.prefix = prefix
        self.region = region
        self.run_timestamp = run_timestamp
        self.enabled = bool(self.bucket)
    
    def upload(self, file_path: str) -> bool:
        """Upload file to S3.
        
        Args:
            file_path: Local file path to upload
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            logger.debug("S3 upload disabled (no bucket configured)")
            return False
        
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return False
        
        try:
            s3 = boto3.client("s3", region_name=self.region)
            basename = os.path.basename(file_path)
            s3_key = (
                f"{self.prefix.rstrip('/')}/"
                f"run={self.run_timestamp}/"
                f"{basename}"
            )

            with open(file_path, "rb") as f:
                s3.upload_fileobj(f, self.bucket, s3_key)

            logger.info(f"Uploaded batch JSONL file to S3: {s3_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to upload JSONL file to S3: {e}")
            return False
