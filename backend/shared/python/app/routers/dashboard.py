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

import base64
import json

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import JSONResponse

from app.config import settings
from app.middleware import AppError, CurrentUser, require_role
from app.models.enums import (
    DocumentType,
    INVOICE_CONTENT_TYPES,
    MAX_FILE_SIZE_BYTES,
    S3Stage,
    UserRole,
)
from app.models.schemas import (
    ApiResponse,
    ApprovalSettings,
    DashboardStatsResponse,
    ExtractPending,
    GoodsReceiptExtractResponse,
    GoodsReceiptUploadRequest,
    GoodsReceiptUploadResponse,
    PurchaseOrderExtractResponse,
    PurchaseOrderUploadRequest,
    PurchaseOrderUploadResponse,
    SeedDataRequest,
    SeedDataResponse,
)
from app.services.dashboard import compute_stats, default_seed_data
from app.services.dynamo import DynamoClient
from app.services.extraction import (
    ExtractionError,
    ExtractionTimeout,
    extract_from_bytes,
    finalize_bda_job,
    poll_bda_status,
    start_bda_job,
)
from app.services.s3 import S3Client, restage_key
from app.services.settings_store import get_approval_settings, put_approval_settings

# Synchronous wait budget before falling back to async polling. Kept below the
# API Gateway 29s integration ceiling with margin for upload + response.
_SYNC_EXTRACT_TIMEOUT_S = 18.0

logger = logging.getLogger(__name__)

router = APIRouter()
admin_router = APIRouter()
po_router = APIRouter()
gr_router = APIRouter()

# Service instances (initialized once, reused across requests).
_invoice_db = DynamoClient(settings.INVOICE_TABLE)
_po_db = DynamoClient(settings.PO_TABLE)
_gr_db = DynamoClient(settings.GR_TABLE)
_s3 = S3Client()

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
        po_count = _write_records(
            _po_db, purchase_orders, numeric_fields=("totalAmount", "totalQuantity")
        )
        gr_count = _write_records(
            _gr_db,
            goods_receipts,
            numeric_fields=("totalQuantityReceived", "totalAmount"),
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
        "totalQuantity": Decimal(str(body.total_quantity)),
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


# ── Upload-and-extract helpers ────────────────────────────────────────────────


def _encode_job(invocation_arn: str, kind: str, s3_key: str | None = None) -> str:
    """Encode an async extract job into an opaque stateless token.

    Carries the incoming ``s3_key`` so the status endpoint can move the object
    to processed/failed once the async job resolves.
    """
    raw = json.dumps({"arn": invocation_arn, "kind": kind, "s3Key": s3_key}).encode()
    return base64.urlsafe_b64encode(raw).decode()


def _decode_job(token: str, expected_kind: str) -> tuple[str, str | None]:
    """Decode a job token → (invocation_arn, s3_key). Raises AppError if bad."""
    try:
        data = json.loads(base64.urlsafe_b64decode(token.encode()))
        if data.get("kind") != expected_kind or not data.get("arn"):
            raise ValueError("token mismatch")
        return str(data["arn"]), data.get("s3Key")
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise AppError("Invalid or expired job id.", status_code=400) from exc


def _restage_upload(s3_key: str | None, stage: str) -> None:
    """Best-effort move of an uploaded PO/GR object to processed/failed.

    Never raises: a storage-housekeeping failure must not turn a successful
    extraction into an error response for the admin.
    """
    if not s3_key:
        return
    dest = restage_key(s3_key, stage)
    if dest == s3_key:
        return
    try:
        _s3.move_object(s3_key, dest)
    except Exception as exc:  # noqa: BLE001 — best-effort housekeeping
        logger.error(
            "Failed to restage uploaded document",
            extra={"from": s3_key, "toStage": stage, "error": str(exc)},
        )


def _sum_line_item_quantities(extraction: dict) -> float:
    """Sum the quantity across all extracted line items (0.0 if none)."""
    line_items = extraction.get("lineItems") or []
    return sum(
        float(li.get("quantity", 0))
        for li in line_items
        if isinstance(li, dict) and isinstance(li.get("quantity"), (int, float))
    )


def _map_po(extraction: dict) -> PurchaseOrderExtractResponse:
    total = extraction.get("totalAmount")
    total_qty = _sum_line_item_quantities(extraction)
    return PurchaseOrderExtractResponse(
        poNumber=_clean_str(extraction.get("invoiceNumber")),
        vendorName=_clean_str(extraction.get("vendorName")),
        totalAmount=float(total) if isinstance(total, (int, float)) and total else None,
        totalQuantity=total_qty if total_qty > 0 else None,
        overallConfidence=extraction.get("overallConfidence"),
    )


def _map_gr(extraction: dict) -> GoodsReceiptExtractResponse:
    total = extraction.get("totalAmount")
    total_qty = _sum_line_item_quantities(extraction)
    return GoodsReceiptExtractResponse(
        grId=_clean_str(extraction.get("invoiceNumber")),
        poNumber=_clean_str(extraction.get("poReference")),
        totalQuantityReceived=total_qty if total_qty > 0 else None,
        totalAmount=float(total) if isinstance(total, (int, float)) and total else None,
        overallConfidence=extraction.get("overallConfidence"),
    )


async def _read_upload(file: UploadFile) -> tuple[bytes, str, str]:
    """Read + validate an uploaded document. Returns (bytes, filename, content_type).

    Raises AppError (400) on an unsupported type or oversized/empty file.
    """
    content_type = file.content_type or "application/octet-stream"
    if content_type not in INVOICE_CONTENT_TYPES:
        raise AppError(
            f"Unsupported file type '{content_type}'. Upload a PDF, PNG, or JPEG.",
            status_code=400,
        )

    data = await file.read()
    if not data:
        raise AppError("The uploaded file is empty.", status_code=400)
    if len(data) > MAX_FILE_SIZE_BYTES:
        raise AppError(
            f"File exceeds the maximum size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB.",
            status_code=400,
        )

    return data, (file.filename or "upload.pdf"), content_type


# ── POST /purchase-orders/extract ─────────────────────────────────────────────


@po_router.post("/extract")
async def extract_purchase_order(
    user: Annotated[CurrentUser, Depends(require_role(UserRole.ADMIN))],
    file: Annotated[UploadFile, File(...)],
):
    """Start PO extraction from an uploaded document (ADMIN, no persistence).

    Sync-then-async: waits up to ~20s for BDA. If it finishes, returns 200 with
    the mapped PO fields; if still running, returns 202 with a jobId the client
    polls via GET /purchase-orders/extract/status. The frontend pre-fills the PO
    form so the admin can confirm/correct before saving.
    """
    data, filename, content_type = await _read_upload(file)
    logger.info("PO extract requested", extra={"userId": user.user_id, "fileName": filename})

    try:
        extraction, s3_key = extract_from_bytes(
            file_bytes=data,
            filename=filename,
            prefix=DocumentType.PURCHASE_ORDER,
            content_type=content_type,
            timeout_s=_SYNC_EXTRACT_TIMEOUT_S,
        )
    except ExtractionTimeout as pending:
        # Still running: hand off to async polling; the status endpoint moves
        # the object once the job resolves.
        token = _encode_job(pending.invocation_arn, "po", pending.s3_key)
        return JSONResponse(
            status_code=202,
            content=ApiResponse(status_code=202, data=ExtractPending(jobId=token)).model_dump(by_alias=True),
        )
    except ExtractionError as exc:
        logger.error("PO extraction failed", extra={"reason": str(exc)})
        _restage_upload(getattr(exc, "s3_key", None), S3Stage.FAILED)
        raise AppError(
            "Could not extract details from the document. Enter the fields manually.",
            status_code=422,
        )

    _restage_upload(s3_key, S3Stage.PROCESSED)
    return ApiResponse(data=_map_po(extraction))


@po_router.get("/extract/status")
async def po_extract_status(
    user: Annotated[CurrentUser, Depends(require_role(UserRole.ADMIN))],
    job_id: Annotated[str, Query(alias="jobId")],
):
    """Poll a pending PO extraction job. Returns 200 (fields), 202 (pending), or 422."""
    invocation_arn, s3_key = _decode_job(job_id, "po")
    try:
        status = poll_bda_status(invocation_arn)
    except ExtractionError as exc:
        logger.error("PO extract status failed", extra={"reason": str(exc)})
        raise AppError("Could not check extraction status. Try again.", status_code=422)

    if status == "InProgress":
        return JSONResponse(
            status_code=202,
            content=ApiResponse(status_code=202, data=ExtractPending(jobId=job_id)).model_dump(by_alias=True),
        )
    if status == "Failed":
        _restage_upload(s3_key, S3Stage.FAILED)
        raise AppError(
            "Could not extract details from the document. Enter the fields manually.",
            status_code=422,
        )

    extraction = finalize_bda_job(invocation_arn)
    _restage_upload(s3_key, S3Stage.PROCESSED)
    return ApiResponse(data=_map_po(extraction))


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
        "totalAmount": Decimal(str(body.total_amount)),
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


# ── POST /goods-receipts/extract ──────────────────────────────────────────────


@gr_router.post("/extract")
async def extract_goods_receipt(
    user: Annotated[CurrentUser, Depends(require_role(UserRole.ADMIN))],
    file: Annotated[UploadFile, File(...)],
):
    """Start GR extraction from an uploaded document (ADMIN, no persistence).

    Sync-then-async: waits up to ~20s for BDA. If it finishes, returns 200 with
    the mapped GR fields (document id -> grId, PO reference -> poNumber, summed
    line-item quantities -> totalQuantityReceived); if still running, returns 202
    with a jobId the client polls via GET /goods-receipts/extract/status.
    """
    data, filename, content_type = await _read_upload(file)
    logger.info("GR extract requested", extra={"userId": user.user_id, "fileName": filename})

    try:
        extraction, s3_key = extract_from_bytes(
            file_bytes=data,
            filename=filename,
            prefix=DocumentType.GOODS_RECEIPT,
            content_type=content_type,
            timeout_s=_SYNC_EXTRACT_TIMEOUT_S,
        )
    except ExtractionTimeout as pending:
        token = _encode_job(pending.invocation_arn, "gr", pending.s3_key)
        return JSONResponse(
            status_code=202,
            content=ApiResponse(status_code=202, data=ExtractPending(jobId=token)).model_dump(by_alias=True),
        )
    except ExtractionError as exc:
        logger.error("GR extraction failed", extra={"reason": str(exc)})
        _restage_upload(getattr(exc, "s3_key", None), S3Stage.FAILED)
        raise AppError(
            "Could not extract details from the document. Enter the fields manually.",
            status_code=422,
        )

    _restage_upload(s3_key, S3Stage.PROCESSED)
    return ApiResponse(data=_map_gr(extraction))


@gr_router.get("/extract/status")
async def gr_extract_status(
    user: Annotated[CurrentUser, Depends(require_role(UserRole.ADMIN))],
    job_id: Annotated[str, Query(alias="jobId")],
):
    """Poll a pending GR extraction job. Returns 200 (fields), 202 (pending), or 422."""
    invocation_arn, s3_key = _decode_job(job_id, "gr")
    try:
        status = poll_bda_status(invocation_arn)
    except ExtractionError as exc:
        logger.error("GR extract status failed", extra={"reason": str(exc)})
        raise AppError("Could not check extraction status. Try again.", status_code=422)

    if status == "InProgress":
        return JSONResponse(
            status_code=202,
            content=ApiResponse(status_code=202, data=ExtractPending(jobId=job_id)).model_dump(by_alias=True),
        )
    if status == "Failed":
        _restage_upload(s3_key, S3Stage.FAILED)
        raise AppError(
            "Could not extract details from the document. Enter the fields manually.",
            status_code=422,
        )

    extraction = finalize_bda_job(invocation_arn)
    _restage_upload(s3_key, S3Stage.PROCESSED)
    return ApiResponse(data=_map_gr(extraction))


# ── Helpers ────────────────────────────────────────────────────────────────────


def _clean_str(value: object) -> str | None:
    """Return a trimmed non-empty string, or None."""
    if isinstance(value, str):
        s = value.strip()
        return s or None
    return None


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
