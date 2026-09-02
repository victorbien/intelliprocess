"""Dashboard and admin endpoints (Module 4).

Exposes four routers (mounted at distinct prefixes in ``main.py``):

- ``router``     — GET  /dashboard/stats          (FR-AP-009, AC-3.9.x)
- ``admin_router`` — POST /admin/seed-data         (AC-5.1.4)
- ``po_router``  — POST /purchase-orders/upload    (AC-5.1.1, AC-5.1.3)
- ``gr_router``  — POST /goods-receipts/upload     (AC-5.1.2, AC-5.1.3)

The ``POST /documents/sync`` endpoint (FR-CROSS-001) lives in ``documents.py``
so it mounts under the ``/documents`` prefix.

All endpoints enforce role-based access, emit structured logs, and surface
user-facing errors via ``AppError`` (never leaking internal details).
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends

from app.config import settings
from app.middleware import AppError, CurrentUser, require_role
from app.models.enums import UserRole
from app.models.schemas import (
    ApiResponse,
    ApprovalSettings,
    DashboardStatsResponse,
    GoodsReceiptUploadRequest,
    GoodsReceiptUploadResponse,
    PurchaseOrderUploadRequest,
    PurchaseOrderUploadResponse,
    SeedDataRequest,
    SeedDataResponse,
)
from app.services.dashboard import compute_stats, default_seed_data
from app.services.dynamo import DynamoClient
from app.services.settings_store import get_approval_settings, put_approval_settings

logger = logging.getLogger(__name__)

router = APIRouter()
admin_router = APIRouter()
po_router = APIRouter()
gr_router = APIRouter()

# Service instances (initialized once, reused across requests).
_invoice_db = DynamoClient(settings.INVOICE_TABLE)
_po_db = DynamoClient(settings.PO_TABLE)
_gr_db = DynamoClient(settings.GR_TABLE)

# Attributes needed to compute dashboard statistics (keeps the scan lean).
# ``extraction`` and ``matchResult`` are nested maps projected by their
# top-level attribute name so compute_stats can aggregate by supplier,
# amount, and three-way match outcome.
_STATS_PROJECTION = (
    "documentId, fileName, #s, uploadedAt, updatedAt, "
    "approvalDecision, processingDurationMs, extraction, matchResult"
)
_STATS_ATTR_NAMES = {"#s": "status"}


# ── GET /dashboard/stats ──────────────────────────────────────────────────────


@router.get(
    "/stats",
    response_model=ApiResponse[DashboardStatsResponse],
)
async def get_dashboard_stats(
    user: Annotated[
        CurrentUser,
        Depends(require_role(UserRole.FINANCE_MANAGER, UserRole.ADMIN)),
    ],
):
    """Return invoice processing summary statistics (FR-AP-009, AC-3.9.x).

    Counts reflect the current state of all invoices at page-load time
    (not real-time). Only Finance Managers and Admins may view stats.
    """
    logger.info("Dashboard stats requested", extra={"userId": user.user_id})

    try:
        items = _invoice_db.scan_all(
            projection=_STATS_PROJECTION,
            attr_names=_STATS_ATTR_NAMES,
        )
    except (ClientError, BotoCoreError) as exc:
        logger.error("Dashboard stats scan failed", extra={"error": str(exc)})
        raise AppError(
            "An error occurred while retrieving dashboard statistics. Please try again.",
            status_code=500,
        )

    stats = compute_stats(items)

    return ApiResponse(data=DashboardStatsResponse(**stats))


# ── POST /admin/seed-data ─────────────────────────────────────────────────────


@admin_router.post(
    "/seed-data",
    response_model=ApiResponse[SeedDataResponse],
)
async def seed_data(
    body: SeedDataRequest,
    user: Annotated[CurrentUser, Depends(require_role(UserRole.ADMIN))],
):
    """Load sample Purchase Orders and Goods Receipts into DynamoDB (AC-5.1.4).

    Admin-only. Returns the counts created. Idempotent: re-running overwrites
    the same sample records (``put_item`` by primary key).
    """
    logger.info(
        "Seed data requested",
        extra={"userId": user.user_id, "dataSet": body.data_set},
    )

    if body.data_set != "default":
        raise AppError(
            f"Unknown data set '{body.data_set}'. Only 'default' is supported.",
            status_code=400,
        )

    purchase_orders, goods_receipts = default_seed_data()

    try:
        po_count = _write_records(_po_db, purchase_orders, numeric_fields=("totalAmount",))
        gr_count = _write_records(
            _gr_db, goods_receipts, numeric_fields=("totalQuantityReceived",)
        )
    except (ClientError, BotoCoreError) as exc:
        logger.error("Seed data write failed", extra={"error": str(exc)})
        raise AppError(
            "An error occurred while loading sample data. Please try again.",
            status_code=500,
        )

    logger.info(
        "Seed data loaded",
        extra={"purchaseOrdersCreated": po_count, "goodsReceiptsCreated": gr_count},
    )

    return ApiResponse(
        data=SeedDataResponse(
            message="Sample data loaded successfully.",
            purchaseOrdersCreated=po_count,
            goodsReceiptsCreated=gr_count,
        )
    )


# ── GET /admin/settings ───────────────────────────────────────────────────────


@admin_router.get(
    "/settings",
    response_model=ApiResponse[ApprovalSettings],
)
async def get_settings(
    user: Annotated[CurrentUser, Depends(require_role(UserRole.ADMIN))],
):
    """Return the current admin-configurable approval/matching thresholds.

    Admin-only. Falls back to built-in defaults when none have been saved.
    """
    logger.info("Approval settings requested", extra={"userId": user.user_id})

    try:
        values = get_approval_settings()
    except (ClientError, BotoCoreError) as exc:
        logger.error("Failed to read approval settings", extra={"error": str(exc)})
        raise AppError(
            "An error occurred while retrieving settings. Please try again.",
            status_code=500,
        )

    return ApiResponse(data=ApprovalSettings(**values))


# ── PUT /admin/settings ───────────────────────────────────────────────────────


@admin_router.put(
    "/settings",
    response_model=ApiResponse[ApprovalSettings],
)
async def update_settings(
    body: ApprovalSettings,
    user: Annotated[CurrentUser, Depends(require_role(UserRole.ADMIN))],
):
    """Update the admin-configurable approval/matching thresholds (ADMIN only).

    Validated ranges (enforced by the schema):
      - amountThreshold      >= 0
      - confidenceThreshold  0.0-1.0
      - poAmountTolerance    0.0-1.0  (0 = exact match)
      - grQtyTolerance       0.0-1.0  (0 = exact match)
    """
    logger.info(
        "Approval settings update",
        extra={
            "userId": user.user_id,
            "amountThreshold": body.amount_threshold,
            "confidenceThreshold": body.confidence_threshold,
            "poAmountTolerance": body.po_amount_tolerance,
            "grQtyTolerance": body.gr_qty_tolerance,
        },
    )

    try:
        stored = put_approval_settings(
            {
                "amountThreshold":     body.amount_threshold,
                "confidenceThreshold": body.confidence_threshold,
                "poAmountTolerance":   body.po_amount_tolerance,
                "grQtyTolerance":      body.gr_qty_tolerance,
            }
        )
    except (ClientError, BotoCoreError) as exc:
        logger.error("Failed to write approval settings", extra={"error": str(exc)})
        raise AppError(
            "An error occurred while saving settings. Please try again.",
            status_code=500,
        )

    return ApiResponse(data=ApprovalSettings(**stored))


# ── POST /purchase-orders/upload ──────────────────────────────────────────────


@po_router.post(
    "/upload",
    response_model=ApiResponse[PurchaseOrderUploadResponse],
    status_code=201,
)
async def upload_purchase_order(
    body: PurchaseOrderUploadRequest,
    user: Annotated[CurrentUser, Depends(require_role(UserRole.ADMIN))],
):
    """Store a structured Purchase Order for invoice matching (AC-5.1.1, AC-5.1.3).

    Admin-only. The stored record is immediately available to the matcher for
    three-way matching against future invoices.
    """
    created_date = body.created_date or datetime.now(timezone.utc).date().isoformat()

    logger.info(
        "Purchase order upload",
        extra={
            "poNumber": body.po_number,
            "vendorName": body.vendor_name,
            "userId": user.user_id,
        },
    )

    item = {
        "poNumber": body.po_number,
        "vendorName": body.vendor_name,
        "totalAmount": Decimal(str(body.total_amount)),
        "currency": body.currency,
        "createdDate": created_date,
        "status": "OPEN",
    }
    if body.department:
        item["department"] = body.department
    if body.vendor_id:
        item["vendorId"] = body.vendor_id

    try:
        _po_db.put_item(item)
    except (ClientError, BotoCoreError) as exc:
        logger.error("Purchase order write failed", extra={"error": str(exc)})
        raise AppError(
            "An error occurred while storing the purchase order. Please try again.",
            status_code=500,
        )

    return ApiResponse(
        status_code=201,
        data=PurchaseOrderUploadResponse(poNumber=body.po_number),
    )


# ── POST /goods-receipts/upload ───────────────────────────────────────────────


@gr_router.post(
    "/upload",
    response_model=ApiResponse[GoodsReceiptUploadResponse],
    status_code=201,
)
async def upload_goods_receipt(
    body: GoodsReceiptUploadRequest,
    user: Annotated[CurrentUser, Depends(require_role(UserRole.ADMIN))],
):
    """Store a structured Goods Receipt linked to a PO (AC-5.1.2, AC-5.1.3).

    Admin-only. The GR is linked to its PO via ``poNumber`` and becomes
    available for three-way matching.
    """
    received_date = body.received_date or datetime.now(timezone.utc).date().isoformat()

    logger.info(
        "Goods receipt upload",
        extra={
            "grId": body.gr_id,
            "poNumber": body.po_number,
            "userId": user.user_id,
        },
    )

    # AC-5.1.2: a Goods Receipt must be linked to an existing Purchase Order so
    # it is available for three-way matching. Reject orphaned receipts.
    try:
        linked_po = _po_db.get_item({"poNumber": body.po_number})
    except (ClientError, BotoCoreError) as exc:
        logger.error("Goods receipt PO lookup failed", extra={"error": str(exc)})
        raise AppError(
            "An error occurred while storing the goods receipt. Please try again.",
            status_code=500,
        )

    if not linked_po:
        logger.warning(
            "Goods receipt references a non-existent PO",
            extra={"grId": body.gr_id, "poNumber": body.po_number},
        )
        raise AppError(
            f"Purchase order '{body.po_number}' not found. "
            "Upload the purchase order before its goods receipt.",
            status_code=400,
        )

    item = {
        "grId": body.gr_id,
        "poNumber": body.po_number,
        "totalQuantityReceived": Decimal(str(body.total_quantity_received)),
        "receivedDate": received_date,
        "status": body.status,
    }

    try:
        _gr_db.put_item(item)
    except (ClientError, BotoCoreError) as exc:
        logger.error("Goods receipt write failed", extra={"error": str(exc)})
        raise AppError(
            "An error occurred while storing the goods receipt. Please try again.",
            status_code=500,
        )

    return ApiResponse(
        status_code=201,
        data=GoodsReceiptUploadResponse(
            grId=body.gr_id,
            poNumber=body.po_number,
        ),
    )


# ── Helpers ────────────────────────────────────────────────────────────────────


def _write_records(
    db: DynamoClient,
    records: list[dict],
    numeric_fields: tuple[str, ...] = (),
) -> int:
    """Write seed records to a table, converting numeric fields to Decimal.

    Returns the number of records written.
    """
    count = 0
    for record in records:
        item = dict(record)
        for field in numeric_fields:
            if field in item:
                item[field] = Decimal(str(item[field]))
        db.put_item(item)
        count += 1
    return count
