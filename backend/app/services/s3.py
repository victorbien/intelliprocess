"""S3 service — document storage and presigned URL generation."""

import logging
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.config import settings
from app.models.enums import MAX_FILE_SIZE_BYTES, PRESIGNED_URL_EXPIRY_SECONDS

logger = logging.getLogger(__name__)


class S3Client:
    """Wrapper around S3 operations with presigned URL support.

    The boto3 client is created lazily on first use so importing this module
    does not require a configured AWS environment at startup.
    """

    def __init__(self, bucket: str | None = None):
        self._bucket = bucket  # Resolved lazily from settings if None
        self._client_obj = None  # Initialized lazily

    def _get_client(self):
        """Return the boto3 S3 client, initializing it on first call."""
        if self._client_obj is None:
            resolved_bucket = self._bucket or settings.DOCUMENT_BUCKET
            if not resolved_bucket:
                raise RuntimeError(
                    "S3 bucket name is not configured. Check DOCUMENT_BUCKET environment variable."
                )
            self._bucket = resolved_bucket
            self._client_obj = boto3.client("s3", region_name=settings.AWS_REGION)
        return self._client_obj

    @property
    def bucket(self) -> str:
        return self._bucket or settings.DOCUMENT_BUCKET

    def generate_presigned_post(
        self,
        key: str,
        content_type: str,
        max_size: int = MAX_FILE_SIZE_BYTES,
        expires_in: int = PRESIGNED_URL_EXPIRY_SECONDS,
    ) -> dict[str, Any]:
        """Generate a presigned POST URL for direct browser upload to S3.

        Args:
            key: S3 object key (e.g., "invoices/incoming/filename.pdf").
            content_type: Expected Content-Type of the upload.
            max_size: Maximum allowed file size in bytes.
            expires_in: URL expiration in seconds.

        Returns:
            Dict with "url" and "fields" for the presigned POST form.

        Raises:
            ClientError: If S3 presigning fails.
        """
        try:
            presigned = self._get_client().generate_presigned_post(
                Bucket=self._bucket,
                Key=key,
                Fields={"Content-Type": content_type},
                Conditions=[
                    {"Content-Type": content_type},
                    ["content-length-range", 1, max_size],
                ],
                ExpiresIn=expires_in,
            )
            logger.info(
                "Generated presigned POST URL",
                extra={"bucket": self._bucket, "key": key, "expiresIn": expires_in},
            )
            return presigned
        except ClientError as e:
            logger.error(
                "Failed to generate presigned POST",
                extra={"bucket": self._bucket, "key": key, "error": str(e)},
            )
            raise

    def generate_presigned_get(
        self,
        key: str,
        expires_in: int = 3600,
    ) -> str:
        """Generate a presigned GET URL for downloading/viewing a document.

        Args:
            key: S3 object key.
            expires_in: URL expiration in seconds (default 1 hour).

        Returns:
            Presigned URL string.
        """
        try:
            url = self._get_client().generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in,
            )
            return url
        except ClientError as e:
            logger.error(
                "Failed to generate presigned GET",
                extra={"bucket": self._bucket, "key": key, "error": str(e)},
            )
            raise
