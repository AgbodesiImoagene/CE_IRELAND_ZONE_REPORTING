"""S3/MinIO utilities for file storage."""

from __future__ import annotations

import logging
from io import BytesIO
from typing import Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from app.core.config import settings

logger = logging.getLogger(__name__)


class S3Client:
    """S3/MinIO client wrapper."""

    def __init__(self):
        """Initialize S3 client."""
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
        )
        self.bucket = settings.s3_bucket

    def upload_file(
        self, file_content: bytes, key: str, content_type: Optional[str] = None
    ) -> str:
        """
        Upload file to S3/MinIO.

        Args:
            file_content: File content as bytes
            key: S3 object key (path)
            content_type: Optional content type

        Returns:
            S3 object key
        """
        try:
            extra_args = {}
            if content_type:
                extra_args["ContentType"] = content_type

            self.client.upload_fileobj(
                BytesIO(file_content),
                self.bucket,
                key,
                ExtraArgs=extra_args,
            )
            return key
        except (ClientError, NoCredentialsError) as e:
            logger.error(f"Failed to upload file to S3: {e}")
            raise

    def download_file(self, key: str) -> bytes:
        """
        Download file from S3/MinIO.

        Args:
            key: S3 object key

        Returns:
            File content as bytes
        """
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read()
        except ClientError as e:
            logger.error(f"Failed to download file from S3: {e}")
            raise

    def delete_file(self, key: str) -> None:
        """
        Delete file from S3/MinIO.

        Args:
            key: S3 object key
        """
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except ClientError as e:
            logger.error(f"Failed to delete file from S3: {e}")
            # Don't raise - deletion failures are not critical

    def get_presigned_url(self, key: str, expiration: int = 3600) -> str:
        """
        Generate presigned URL for file access.

        Args:
            key: S3 object key
            expiration: URL expiration time in seconds

        Returns:
            Presigned URL
        """
        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expiration,
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise

