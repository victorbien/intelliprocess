"""InvoiceProcessor Lambda handler — S3 event–driven document ingestion.

Triggered by ``s3:ObjectCreated:*`` events on the ``invoices/`` prefix.
Parses the S3 event, validates the object metadata, and delegates to
:func:`app.services.processor.process_invoice` for full pipeline execution.

Design reference: docs/07-component-design.md §2.1 — Document Ingestion.
"""

import json
import logging
import urllib.parse
from typing import Any

from app.config import settings
from app.models.enums import INVOICE_CONTENT_TYPES, MAX_FILE_SIZE_BYTES, S3Stage
from app.services.processor import process_invoice

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)


# ── Constants ────────────────────────────────────────────────────────────────

# Minimum valid S3 key parts: invoices/<stage>/<document_id>/<filename>
_MIN_KEY_PARTS = 4


# ── Lambda entry point ────────────────────────────────────────────────────────

def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda handler for S3 ObjectCreated events.

    Parameters
    ----------
    event:
        S3 event notification payload containing one or more Records.
    context:
        Lambda execution context (unused but required by the runtime).

    Returns
    -------
    dict with summary of processing results per record.
    """
    records = event.get("Records", [])
    if not records:
        logger.warning("Received event with no Records — ignoring")
        return {"statusCode": 200, "body": "No records to process."}

    logger.info(
        "InvoiceProcessor invoked",
        extra={"recordCount": len(records), "requestId": _get_request_id(context)},
    )

    results: list[dict[str, str]] = []

    for record in records:
        result = _process_record(record)
        results.append(result)

    # Summary response (not used by S3 event source, but aids debugging)
    processed = sum(1 for r in results if r["status"] == "processed")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    failed = sum(1 for r in results if r["status"] == "failed")

    logger.info(
        "InvoiceProcessor batch complete",
        extra={"processed": processed, "skipped": skipped, "failed": failed},
    )

    return {
        "statusCode": 200,
        "body": json.dumps({
            "processed": processed,
            "skipped": skipped,
            "failed": failed,
            "results": results,
        }),
    }


# ── Record-level processing ──────────────────────────────────────────────────

def _process_record(record: dict[str, Any]) -> dict[str, str]:
    """Process a single S3 event record.

    Validates the record structure, object metadata (content type, size),
    and delegates to the processing pipeline.

    Returns a dict with 'key', 'status' ('processed' | 'skipped' | 'failed'),
    and optional 'reason'.
    """
    # ── Parse S3 event fields ─────────────────────────────────────────────────
    try:
        s3_info = record.get("s3", {})
        bucket_info = s3_info.get("bucket", {})
        object_info = s3_info.get("object", {})

        bucket_name = bucket_info.get("name", "")
        raw_key = object_info.get("key", "")
        # S3 event keys are URL-encoded
        s3_key = urllib.parse.unquote_plus(raw_key)
        object_size = object_info.get("size", 0)

    except (KeyError, TypeError) as exc:
        logger.error(
            "Malformed S3 event record",
            extra={"error": str(exc), "record": _safe_serialize(record)},
        )
        return {"key": "unknown", "status": "failed", "reason": f"Malformed record: {exc}"}

    log_ctx = {"bucket": bucket_name, "s3Key": s3_key, "objectSize": object_size}

    # ── Validate event source ─────────────────────────────────────────────────
    event_name = record.get("eventName", "")
    if not event_name.startswith("ObjectCreated"):
        logger.info("Non-create event — skipping", extra={**log_ctx, "eventName": event_name})
        return {"key": s3_key, "status": "skipped", "reason": f"Event type: {event_name}"}

    # ── Validate S3 key structure ─────────────────────────────────────────────
    key_parts = s3_key.strip("/").split("/")
    if len(key_parts) < _MIN_KEY_PARTS:
        logger.warning(
            "S3 key does not match expected format invoices/<stage>/<id>/<file>",
            extra=log_ctx,
        )
        return {"key": s3_key, "status": "skipped", "reason": "Invalid key structure"}

    prefix = key_parts[0]
    if prefix != "invoices":
        logger.info("Object not under invoices/ prefix — skipping", extra=log_ctx)
        return {"key": s3_key, "status": "skipped", "reason": "Not an invoice prefix"}

    # Only process brand-new uploads in the "incoming" stage. When the pipeline
    # moves an object to processed/ or failed/, S3 emits another ObjectCreated
    # event; ignoring non-incoming stages prevents reprocessing loops.
    stage = key_parts[1]
    if stage != S3Stage.INCOMING:
        logger.info(
            "Object not in incoming stage — skipping",
            extra={**log_ctx, "stage": stage},
        )
        return {"key": s3_key, "status": "skipped", "reason": f"Stage: {stage}"}

    # ── Validate file size ────────────────────────────────────────────────────
    if object_size > MAX_FILE_SIZE_BYTES:
        logger.warning(
            "Object exceeds maximum allowed size",
            extra={**log_ctx, "maxSize": MAX_FILE_SIZE_BYTES},
        )
        return {
            "key": s3_key,
            "status": "failed",
            "reason": f"File size {object_size} exceeds limit {MAX_FILE_SIZE_BYTES}",
        }

    if object_size == 0:
        logger.warning("Zero-byte object — skipping", extra=log_ctx)
        return {"key": s3_key, "status": "skipped", "reason": "Zero-byte object"}

    # ── Validate content type (from key extension) ────────────────────────────
    filename = key_parts[-1]
    content_type = _infer_content_type(filename)
    if content_type and content_type not in INVOICE_CONTENT_TYPES:
        logger.warning(
            "Unsupported file type for invoice processing",
            extra={**log_ctx, "contentType": content_type, "fileName": filename},
        )
        return {
            "key": s3_key,
            "status": "failed",
            "reason": f"Unsupported content type: {content_type}",
        }

    # ── Dispatch to processor ─────────────────────────────────────────────────
    logger.info("Dispatching to invoice processor", extra=log_ctx)

    try:
        process_invoice(bucket=bucket_name, s3_key=s3_key)
        return {"key": s3_key, "status": "processed"}
    except Exception as exc:
        # process_invoice internally handles errors and marks status=ERROR,
        # but if something catastrophic escapes, catch it here to prevent
        # Lambda retry storms.
        logger.error(
            "Unhandled exception from process_invoice",
            extra={**log_ctx, "error": str(exc)},
            exc_info=True,
        )
        return {"key": s3_key, "status": "failed", "reason": str(exc)[:500]}


# ── Helpers ───────────────────────────────────────────────────────────────────

_EXTENSION_MAP = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def _infer_content_type(filename: str) -> str | None:
    """Infer content type from file extension. Returns None if unknown."""
    lower = filename.lower()
    for ext, ct in _EXTENSION_MAP.items():
        if lower.endswith(ext):
            return ct
    return None


def _get_request_id(context: Any) -> str:
    """Safely extract the Lambda request ID from the context object."""
    try:
        return context.aws_request_id
    except AttributeError:
        return "local"


def _safe_serialize(obj: Any) -> str:
    """Serialize an object for logging, truncating to prevent oversized logs."""
    try:
        serialized = json.dumps(obj, default=str)
        return serialized[:2000]
    except (TypeError, ValueError):
        return str(obj)[:2000]
