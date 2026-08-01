"""Invoice processing orchestrator — full pipeline coordination.

Triggered by S3 ObjectCreated events on the ``invoices/`` prefix.
Implements the sequential pipeline from technical-design.md §3.3:

    UPLOADED → PROCESSING → EXTRACTED → APPROVED | ESCALATED | ERROR

Steps
-----
1.  Idempotency guard — skip if status is not UPLOADED.
2.  Mark status PROCESSING.
3.  Call extraction service (BDA / mock).
4.  Persist extraction result; mark EXTRACTED.
5.  Run PO match → GR match → three-way match.
6.  Evaluate approval rules.
7.  Persist match + decision; mark APPROVED or ESCALATED.
8.  On any unhandled exception: mark ERROR.

All timing is recorded so the dashboard can show average processing time
(FR-AP-009 / AC-3.9.x).
"""

import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from botocore.exceptions import ClientError

from app.config import settings
from app.models.enums import InvoiceStatus
from app.services.dynamo import DynamoClient
from app.services.extraction import ExtractionError, extract_invoice
from app.services.matcher import match_goods_receipt, match_purchase_order, three_way_match
from app.services.rules import evaluate_approval_rules

logger = logging.getLogger(__name__)

# ── Service client ────────────────────────────────────────────────────────────

_invoice_db = DynamoClient(settings.INVOICE_TABLE)


# ── Public API ────────────────────────────────────────────────────────────────

def process_invoice(bucket: str, s3_key: str) -> None:
    """Orchestrate the full invoice processing pipeline for one document.

    Extracts the document ID from the S3 key, then runs extraction →
    matching → rules → status update.

    Parameters
    ----------
    bucket:
        S3 bucket name.
    s3_key:
        Object key, expected format ``invoices/<document_id>/<filename>``.
    """
    document_id = _extract_document_id(s3_key)
    if not document_id:
        logger.error(
            "Cannot derive documentId from S3 key — skipping",
            extra={"s3Key": s3_key},
        )
        return

    log_ctx = {"documentId": document_id, "s3Key": s3_key}

    # ── 1. Idempotency guard ───────────────────────────────────────────────────
    item = _invoice_db.get_item({"documentId": document_id})
    if not item:
        logger.warning("Invoice metadata not found — skipping", extra=log_ctx)
        return

    current_status = item.get("status", "")
    if current_status != InvoiceStatus.UPLOADED:
        logger.info(
            "Invoice already processed — skipping (idempotency)",
            extra={**log_ctx, "currentStatus": current_status},
        )
        return

    logger.info("Starting invoice processing pipeline", extra=log_ctx)

    # ── 2. Mark PROCESSING ────────────────────────────────────────────────────
    try:
        _invoice_db.update_status(
            document_id=document_id,
            new_status=InvoiceStatus.PROCESSING,
            expected_current=InvoiceStatus.UPLOADED,
        )
    except ClientError:
        # Another invocation already claimed this invoice
        logger.warning(
            "Status transition UPLOADED→PROCESSING rejected — "
            "concurrent processing detected, skipping",
            extra=log_ctx,
        )
        return

    try:
        _run_pipeline(document_id=document_id, bucket=bucket, s3_key=s3_key, log_ctx=log_ctx)
    except Exception as exc:
        logger.error(
            "Invoice processing pipeline failed",
            extra={**log_ctx, "error": str(exc)},
            exc_info=True,
        )
        _mark_error(document_id, str(exc))


# ── Pipeline internals ────────────────────────────────────────────────────────

def _run_pipeline(
    document_id: str,
    bucket: str,
    s3_key: str,
    log_ctx: dict,
) -> None:
    """Execute the extraction → matching → rules pipeline."""
    start_time = time.monotonic()

    # ── 3. Extract invoice fields ─────────────────────────────────────────────
    try:
        extraction = extract_invoice(bucket=bucket, s3_key=s3_key)
    except ExtractionError as exc:
        logger.error("Extraction failed", extra={**log_ctx, "reason": str(exc)})
        _mark_error(document_id, f"Extraction failed: {exc}")
        return

    total_amount_raw = extraction.get("totalAmount", 0)
    logger.info(
        "Extraction complete",
        extra={
            **log_ctx,
            "overallConfidence": extraction.get("overallConfidence"),
            "vendor": extraction.get("vendorName"),
            "totalAmount": f"{float(total_amount_raw):.2f}",
        },
    )

    # ── 4. Persist extraction + mark EXTRACTED atomically ─────────────────────
    # Both the extraction data and status transition are written in one
    # update_item call so a crash between the two can never leave the record
    # in an inconsistent state (AC-3.1.3).
    confidence: dict = extraction.get("confidence", {})
    overall_conf: float = extraction.get("overallConfidence", 0.0)
    extraction_record = {
        k: v for k, v in extraction.items()
        if k not in ("confidence", "overallConfidence")
    }

    _invoice_db.update_status(
        document_id=document_id,
        new_status=InvoiceStatus.EXTRACTED,
        expected_current=InvoiceStatus.PROCESSING,
        extraction=_to_dynamo(extraction_record),
        confidence=_to_dynamo(confidence),
        overallConfidence=Decimal(str(round(overall_conf, 4))),
    )

    # ── 5. PO + GR matching ───────────────────────────────────────────────────
    po_number = extraction.get("poReference")
    vendor_name = extraction.get("vendorName", "")
    total_amount = float(extraction.get("totalAmount", 0))

    line_items = extraction.get("lineItems") or []
    invoiced_qty = sum(float(item.get("quantity", 0)) for item in line_items)

    po_result = match_purchase_order(
        po_number=po_number,
        vendor_name=vendor_name,
        invoice_amount=total_amount,
    )

    # Use the matched PO ID if we found one (more reliable for GR lookup)
    gr_po_number = po_result.get("poId") or po_number

    gr_result = match_goods_receipt(
        po_number=gr_po_number,
        invoiced_quantity=invoiced_qty,
    )

    match_result = three_way_match(po_result=po_result, gr_result=gr_result)

    # ── 6. Apply approval rules ───────────────────────────────────────────────
    decision = evaluate_approval_rules(
        total_amount=total_amount,
        overall_confidence=float(extraction.get("overallConfidence", 0)),
        vendor_name=vendor_name,
        three_way_match_status=match_result["status"],
        discrepancies=match_result.get("discrepancies", []),
    )

    # ── 7. Persist match + decision; final status update ─────────────────────
    elapsed_ms = int((time.monotonic() - start_time) * 1000)
    now = datetime.now(timezone.utc).isoformat()

    approval_record: dict[str, Any] = {
        "decision":     decision["decision"],
        "reason":       decision["reason"],
        "escalateTo":   decision.get("escalateTo"),
        "rulesResults": decision["rulesResults"],
    }

    if decision["decision"] == "APPROVE":
        approval_record["approver"]   = "SYSTEM"
        approval_record["approvedAt"] = now
        new_status = InvoiceStatus.APPROVED

        _invoice_db.update_status(
            document_id=document_id,
            new_status=new_status,
            expected_current=InvoiceStatus.EXTRACTED,
            matchResult=_to_dynamo(match_result),
            approvalDecision=_to_dynamo(approval_record),
            processingDurationMs=Decimal(str(elapsed_ms)),
        )
    else:
        new_status = InvoiceStatus.ESCALATED

        _invoice_db.update_status(
            document_id=document_id,
            new_status=new_status,
            expected_current=InvoiceStatus.EXTRACTED,
            matchResult=_to_dynamo(match_result),
            approvalDecision=_to_dynamo(approval_record),
            processingDurationMs=Decimal(str(elapsed_ms)),
        )

    logger.info(
        "Invoice processing complete",
        extra={
            **log_ctx,
            "finalStatus": new_status,
            "decision": decision["decision"],
            "escalateTo": decision.get("escalateTo"),
            "elapsedMs": elapsed_ms,
        },
    )


def _mark_error(document_id: str, error_detail: str) -> None:
    """Transition invoice to ERROR status with the error description."""
    try:
        _invoice_db.update_status(
            document_id=document_id,
            new_status=InvoiceStatus.ERROR,
            errorDetails=error_detail[:1000],  # Truncate very long error strings
        )
    except Exception as exc:
        logger.error(
            "Failed to mark invoice as ERROR",
            extra={"documentId": document_id, "secondaryError": str(exc)},
        )


# ── Utilities ──────────────────────────────────────────────────────────────────

def _extract_document_id(s3_key: str) -> str | None:
    """Parse document ID from S3 key ``invoices/<doc_id>/<filename>``."""
    parts = s3_key.strip("/").split("/")
    if len(parts) >= 2:
        return parts[1]
    return None


def _to_dynamo(obj: Any) -> Any:
    """Recursively convert floats to Decimal for DynamoDB storage."""
    if isinstance(obj, float):
        return Decimal(str(round(obj, 6)))
    if isinstance(obj, dict):
        return {k: _to_dynamo(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_dynamo(v) for v in obj]
    return obj
