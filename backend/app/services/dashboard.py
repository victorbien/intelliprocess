"""Dashboard statistics and admin seed-data service (Module 4).

Implements:
- compute_stats()       — FR-AP-009, AC-3.9.x  (invoice processing summary)
- default_seed_data()   — AC-5.1.4             (sample PO / GR data set)

Statistics are computed on demand from the invoice table (refresh-on-load,
not real-time — AC-3.9.2). Invoice volume is low in the MVP, so a table scan
is acceptable; see ``DynamoClient.scan_all`` for the production note.

All DynamoDB ``Decimal`` values are coerced to ``float``/``int`` before use.
"""

import logging
from typing import Any

from app.models.enums import InvoiceStatus

logger = logging.getLogger(__name__)

# Statuses that count as an automatic (SYSTEM) approval for the auto-approval rate.
_AUTO_APPROVED_APPROVER = "SYSTEM"

# Maximum number of recent-activity rows returned on the dashboard.
_RECENT_ACTIVITY_LIMIT = 10


def compute_stats(invoice_items: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate invoice records into dashboard statistics.

    Args:
        invoice_items: Raw invoice records fetched from the invoice table.

    Returns:
        A dict with keys: ``totalInvoices``, ``statusCounts``,
        ``autoApprovalRate``, ``avgProcessingTimeSec``, ``recentActivity``.

    The function never raises on individual malformed records — it defends
    against missing fields so a single bad row cannot break the dashboard.
    """
    total = len(invoice_items)

    # Initialise status counts with every known status at zero so the frontend
    # always receives a complete, stable shape (AC-3.9.1).
    status_counts: dict[str, int] = {status.value.lower(): 0 for status in InvoiceStatus}

    processing_times_ms: list[float] = []
    auto_approved = 0

    for item in invoice_items:
        status = str(item.get("status") or "").upper()
        key = status.lower()
        if not key:
            # Missing/blank status — bucket under "unknown" so counts stay complete.
            key = "unknown"
            logger.warning(
                "Dashboard encountered invoice with no status",
                extra={"documentId": item.get("documentId")},
            )
            status_counts[key] = status_counts.get(key, 0) + 1
        elif key in status_counts:
            status_counts[key] += 1
        else:
            # Unknown status — record it verbatim rather than dropping the count.
            status_counts[key] = status_counts.get(key, 0) + 1
            logger.warning(
                "Dashboard encountered unknown invoice status",
                extra={"status": status, "documentId": item.get("documentId")},
            )

        duration = _to_float(item.get("processingDurationMs"))
        if duration is not None and duration > 0:
            processing_times_ms.append(duration)

        if status == InvoiceStatus.APPROVED.value and _approved_by_system(item):
            auto_approved += 1

    # Auto-approval rate = auto-approved / total processed, as a percentage.
    auto_approval_rate = round((auto_approved / total) * 100, 1) if total else 0.0

    avg_processing_time_sec = (
        round(sum(processing_times_ms) / len(processing_times_ms) / 1000, 1)
        if processing_times_ms
        else 0.0
    )

    recent_activity = _build_recent_activity(invoice_items)

    logger.info(
        "Dashboard stats computed",
        extra={
            "totalInvoices": total,
            "autoApprovalRate": auto_approval_rate,
            "avgProcessingTimeSec": avg_processing_time_sec,
        },
    )

    return {
        "totalInvoices": total,
        "statusCounts": status_counts,
        "autoApprovalRate": auto_approval_rate,
        "avgProcessingTimeSec": avg_processing_time_sec,
        "recentActivity": recent_activity,
    }


def _approved_by_system(item: dict[str, Any]) -> bool:
    """Return True if the invoice was auto-approved by the rules engine."""
    decision = item.get("approvalDecision") or {}
    approver = str(decision.get("approver", "")).upper()
    return approver == _AUTO_APPROVED_APPROVER


def _build_recent_activity(invoice_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build the recent-activity feed, most recent first.

    Uses ``updatedAt`` (falling back to ``uploadedAt``) as the activity time and
    derives a human-readable action label from the invoice status and any
    escalation reason.
    """
    sortable = sorted(
        invoice_items,
        key=lambda i: str(i.get("updatedAt") or i.get("uploadedAt") or ""),
        reverse=True,
    )

    activity: list[dict[str, Any]] = []
    for item in sortable[:_RECENT_ACTIVITY_LIMIT]:
        decision = item.get("approvalDecision") or {}
        activity.append(
            {
                "documentId": item.get("documentId", ""),
                "fileName": item.get("fileName", ""),
                "action": _action_label(item, decision),
                "timestamp": str(item.get("updatedAt") or item.get("uploadedAt") or ""),
                "actor": str(decision.get("approver") or "SYSTEM"),
            }
        )
    return activity


def _action_label(item: dict[str, Any], decision: dict[str, Any]) -> str:
    """Derive a friendly action label for a recent-activity row."""
    status = str(item.get("status") or "").upper()

    if status == InvoiceStatus.APPROVED.value:
        approver = str(decision.get("approver", "")).upper()
        return "Auto-approved" if approver == _AUTO_APPROVED_APPROVER else "Manually approved"
    if status == InvoiceStatus.ESCALATED.value:
        reason = decision.get("reason")
        return f"Escalated - {reason}" if reason else "Escalated"
    if status == InvoiceStatus.REJECTED.value:
        return "Rejected"
    if status == InvoiceStatus.PROCESSING.value:
        return "Processing"
    if status == InvoiceStatus.EXTRACTED.value:
        return "Extracted"
    if status == InvoiceStatus.ERROR.value:
        return "Processing error"
    return "Uploaded"


def default_seed_data() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return the default sample Purchase Orders and Goods Receipts (AC-5.1.4).

    The records mirror the shapes expected by ``services.matcher`` and the
    ``dev_mock`` seed so that seeded invoices match cleanly during a demo.

    Returns:
        Tuple of ``(purchase_orders, goods_receipts)`` as DynamoDB-ready dicts.
        Numeric fields are plain ``str`` values; callers convert to ``Decimal``
        before writing to DynamoDB.
    """
    purchase_orders = [
        {
            "poNumber": "PO-2024-0456",
            "vendorName": "Acme Office Supplies Inc.",
            "vendorId": "VENDOR-001",
            "createdDate": "2026-07-01",
            "totalAmount": "658.80",
            "currency": "USD",
            "status": "OPEN",
            "department": "Administration",
        },
        {
            "poNumber": "PO-2024-0457",
            "vendorName": "TechParts Global Ltd.",
            "vendorId": "VENDOR-002",
            "createdDate": "2026-07-05",
            "totalAmount": "15000.00",
            "currency": "USD",
            "status": "OPEN",
            "department": "Engineering",
        },
        {
            "poNumber": "PO-2024-0458",
            "vendorName": "BrightSpark Electric Co.",
            "vendorId": "VENDOR-003",
            "createdDate": "2026-07-08",
            "totalAmount": "3200.00",
            "currency": "USD",
            "status": "OPEN",
            "department": "Facilities",
        },
        {
            "poNumber": "PO-2024-0459",
            "vendorName": "Global Freight Partners LLC",
            "vendorId": "VENDOR-004",
            "createdDate": "2026-07-10",
            "totalAmount": "8750.00",
            "currency": "USD",
            "status": "OPEN",
            "department": "Logistics",
        },
        {
            "poNumber": "PO-2024-0460",
            "vendorName": "Summit Software Solutions",
            "vendorId": "VENDOR-005",
            "createdDate": "2026-07-12",
            "totalAmount": "4990.00",
            "currency": "USD",
            "status": "OPEN",
            "department": "IT",
        },
    ]

    goods_receipts = [
        {
            "grId": "GR-2024-0789",
            "poNumber": "PO-2024-0456",
            "receivedDate": "2026-07-15",
            "totalQuantityReceived": "15",
            "status": "COMPLETE",
        },
        {
            "grId": "GR-2024-0790",
            "poNumber": "PO-2024-0457",
            "receivedDate": "2026-07-18",
            "totalQuantityReceived": "10",
            "status": "COMPLETE",
        },
        {
            "grId": "GR-2024-0791",
            "poNumber": "PO-2024-0458",
            "receivedDate": "2026-07-20",
            "totalQuantityReceived": "40",
            "status": "COMPLETE",
        },
        {
            "grId": "GR-2024-0792",
            "poNumber": "PO-2024-0459",
            "receivedDate": "2026-07-22",
            "totalQuantityReceived": "5",
            "status": "COMPLETE",
        },
        {
            "grId": "GR-2024-0793",
            "poNumber": "PO-2024-0460",
            "receivedDate": "2026-07-24",
            "totalQuantityReceived": "1",
            "status": "COMPLETE",
        },
    ]

    return purchase_orders, goods_receipts


# ── Helpers ────────────────────────────────────────────────────────────────────


def _to_float(value: Any) -> float | None:
    """Coerce a DynamoDB Decimal/str/int/float to float. Returns None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
