"""S3 service — document storage and presigned URL generation."""

import logging
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.config import settings
from app.models.enums import MAX_FILE_SIZE_BYTES, PRESIGNED_URL_EXPIRY_SECONDS, S3Stage

logger = logging.getLogger(__name__)

# The set of stage folder names, used to detect and rewrite the stage segment
# of a transaction document key.
_STAGE_VALUES = frozenset(s.value for s in S3Stage)


def build_stage_key(document_type: str, stage: str, *parts: str) -> str:
    """Build a staged object key: ``<document_type>/<stage>/<parts...>``.

    Example: ``build_stage_key("invoices", "incoming", doc_id, filename)``
    -> ``invoices/incoming/<doc_id>/<filename>``.
    """
    segments = [document_type.strip("/"), stage.strip("/"), *[p.strip("/") for p in parts]]
    return "/".join(s for s in segments if s)


def restage_key(key: str, new_stage: str) -> str:
    """Return ``key`` with its stage segment (2nd path component) swapped.

    Assumes the key follows ``<document_type>/<stage>/<rest...>``. If the key
    does not carry a recognised stage segment, the key is returned unchanged so
    callers never crash on unexpected shapes.
    """
    parts = key.split("/")
    if len(parts) >= 3 and parts[1] in _STAGE_VALUES:
        parts[1] = new_stage
        return "/".join(parts)
    return key


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

    def upload_bytes(self, key: str, data: bytes, content_type: str) -> str:
        """Upload raw bytes to S3 (server-side). Returns the object key.

        Used for synchronous server-side ingestion (e.g. admin PO/GR upload +
        immediate BDA extraction), as opposed to browser presigned uploads.
        """
        try:
            client = self._get_client()
            client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
            logger.info(
                "Uploaded object to S3",
                extra={"bucket": self._bucket, "key": key, "size": len(data)},
            )
            return key
        except ClientError as e:
            logger.error(
                "Failed to upload object to S3",
                extra={"bucket": self._bucket, "key": key, "error": str(e)},
            )
            raise

    def move_object(self, source_key: str, dest_key: str) -> str:
        """Move an object within the bucket (server-side copy + delete).

        Used to advance a transaction document through its processing-stage
        folders, e.g. ``invoices/incoming/...`` -> ``invoices/processed/...``.

        No-ops when ``source_key == dest_key``. If the source object does not
        exist (e.g. it was already moved by a previous, partially-completed
        run), the copy raises and is surfaced to the caller.

        Returns the destination key on success.
        """
        if source_key == dest_key:
            return dest_key

        try:
            client = self._get_client()
            client.copy_object(
                Bucket=self._bucket,
                CopySource={"Bucket": self._bucket, "Key": source_key},
                Key=dest_key,
            )
            client.delete_object(Bucket=self._bucket, Key=source_key)
            logger.info(
                "Moved S3 object",
                extra={"bucket": self._bucket, "from": source_key, "to": dest_key},
            )
            return dest_key
        except ClientError as e:
            logger.error(
                "Failed to move S3 object",
                extra={
                    "bucket": self._bucket,
                    "from": source_key,
                    "to": dest_key,
                    "error": str(e),
                },
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
