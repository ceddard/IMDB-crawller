"""S3 upload functionality."""

import logging
import os
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)


class S3Uploader:
    """Handles uploading files to AWS S3."""
    
    def __init__(self, bucket: Optional[str] = None, prefix: str = "imdb/bronze/", region: str = "us-east-1"):
        """Initialize S3 uploader.
        
        Args:
            bucket: S3 bucket name
            prefix: S3 key prefix
            region: AWS region
        """
        self.bucket = bucket
        self.prefix = prefix
        self.region = region
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
        
        s3_key = f"{self.prefix.rstrip('/')}/{os.path.basename(file_path)}"
        
        try:
            s3 = boto3.client("s3", region_name=self.region)
            file_size = os.path.getsize(file_path)
            logger.info(f"Uploading {file_path} ({file_size} bytes) to s3://{self.bucket}/{s3_key}")
            
            s3.upload_file(file_path, self.bucket, s3_key)
            
            logger.info(f"Successfully uploaded to S3: s3://{self.bucket}/{s3_key}")
            return True
        except (BotoCoreError, ClientError) as e:
            logger.error(f"S3 upload failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during S3 upload: {e}", exc_info=True)
            return False
