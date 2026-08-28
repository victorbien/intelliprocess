"""Invoice processing endpoints.

Handles:
- POST /invoices/upload            — Generate presigned URL for invoice upload
- GET  /invoices                   — List invoices (filtered by user role)
- GET  /invoices/{document_id}     — Get full invoice detail
- POST /invoices/{document_id}/approve  — Manually approve or reject a escalated invoice
- POST /invoices/process           — S3-event processing trigger (internal)
"""

import base64
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from app.config import settings
from app.middleware import AppError, CurrentUser, get_current_user, require_role
from app.models.enums import (
    DocumentType,
    InvoiceStatus,
    PRESIGNED_URL_EXPIRY_SECONDS,
    UserRole,
)
from app.models.schemas import (
    ApiResponse,
    InvoiceApproveRequest,
    InvoiceApproveResponse,
    InvoiceDetailResponse,
    InvoiceListItem,
    InvoiceUploadRequest,
    InvoiceUploadResponse,
    PaginatedResponse,
    PresignedPostData,
    ProcessTriggerRequest,
)
from app.services.dynamo import DynamoClient
from app.services.processor import process_invoice
from app.services.s3 import S3Client

logger = logging.getLogger(__name__)
router = APIRouter()

# Service instances (initialized once, reused across requests)
_invoice_db = DynamoClient(settings.INVOICE_TABLE)
_s3 = S3Client()


@router.post(
    "/upload",
    response_model=ApiResponse[InvoiceUploadResponse],
    status_code=201,
)
async def upload_invoice(
    body: InvoiceUploadRequest,
    user: Annotated[
        CurrentUser,
        Depends(require_role(UserRole.AP_CLERK, UserRole.FINANCE_MANAGER, UserRole.ADMIN)),
    ],
):
    """Generate a presigned S3 URL for direct invoice upload.

    The client uses the returned URL and fields to POST the file directly to S3.
    Upon successful S3 upload, an S3 event triggers the InvoiceProcessor Lambda.
    """
    document_id = str(uuid.uuid4())
    s3_key = f"{DocumentType.INVOICE}/incoming/{body.file_name}"

    logger.info(
        "Invoice upload initiated",
        extra={
            "documentId": document_id,
            "fileName": body.file_name,
            "userId": user.user_id,
        },
    )

    # Generate presigned POST URL
    presigned = _s3.generate_presigned_post(
        key=s3_key,
        content_type=body.content_type,
    )

    # Create metadata record in DynamoDB
    now = datetime.now(timezone.utc).isoformat()
    _invoice_db.put_item(
        {
            "documentId": document_id,
            "fileName": body.file_name,
            "s3Key": s3_key,
            "documentType": DocumentType.INVOICE,
            "status": InvoiceStatus.UPLOADED,
            "uploadedBy": user.user_id,
            "uploadedAt": now,
            "updatedAt": now,
            "contentType": body.content_type,
        }
    )

    logger.info(
        "Invoice metadata created",
        extra={"documentId": document_id, "status": InvoiceStatus.UPLOADED},
    )

    return ApiResponse(
        status_code=201,
        data=InvoiceUploadResponse(
            documentId=document_id,
            uploadUrl=PresignedPostData(
                url=presigned["url"],
                fields=presigned["fields"],
            ),
            expiresIn=PRESIGNED_URL_EXPIRY_SECONDS,
        ),
    )


@router.get(
    "",
    response_model=ApiResponse[PaginatedResponse[InvoiceListItem]],
)
async def list_invoices(
    user: Annotated[
        CurrentUser,
        Depends(require_role(UserRole.AP_CLERK, UserRole.FINANCE_MANAGER, UserRole.ADMIN)),
    ],
    status: InvoiceStatus | None = Query(None, description="Filter by status"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    start_key: str | None = Query(None, alias="startKey", description="Pagination token"),
):
    """List invoices. AP_CLERK sees only their own; FINANCE_MANAGER/ADMIN see all."""
    exclusive_start_key = None
    if start_key:
        try:
            exclusive_start_key = json.loads(base64.b64decode(start_key))
        except Exception:
            raise AppError("Invalid pagination token.", status_code=400)

    # Determine query strategy based on role and filters
    if status:
        # Query by status (GSI-StatusDate)
        items, last_key = _invoice_db.query_by_index(
            index_name="GSI-StatusDate",
            partition_key="status",
            partition_value=status.value,
            limit=limit,
            scan_forward=False,
            exclusive_start_key=exclusive_start_key,
        )
    elif user.has_role(UserRole.FINANCE_MANAGER, UserRole.ADMIN):
        # Managers/admins see all — query by a broad status or scan
        # For MVP, use a scan with limit (acceptable for <100 invoices)
        items, last_key = _query_all_invoices(limit, exclusive_start_key)
    else:
        # AP_CLERK sees only their own invoices (GSI-UserDate)
        items, last_key = _invoice_db.query_by_index(
            index_name="GSI-UserDate",
            partition_key="uploadedBy",
            partition_value=user.user_id,
            limit=limit,
            scan_forward=False,
            exclusive_start_key=exclusive_start_key,
        )

    # Filter by user for AP_CLERK when querying by status
    if status and not user.has_role(UserRole.FINANCE_MANAGER, UserRole.ADMIN):
        items = [i for i in items if i.get("uploadedBy") == user.user_id]

    # Map to response models
    invoice_items = [
        InvoiceListItem(
            documentId=item["documentId"],
            fileName=item["fileName"],
            status=item["status"],
            uploadedAt=item["uploadedAt"],
            uploadedBy=item["uploadedBy"],
            vendorName=item.get("extraction", {}).get("vendorName") if item.get("extraction") else None,
            totalAmount=item.get("extraction", {}).get("totalAmount") if item.get("extraction") else None,
        )
        for item in items
    ]

    # Encode next key for pagination
    next_key = None
    if last_key:
        next_key = base64.b64encode(json.dumps(last_key).encode()).decode()

    return ApiResponse(
        data=PaginatedResponse(
            items=invoice_items,
            count=len(invoice_items),
            next_key=next_key,
        )
    )


@router.get(
    "/{document_id}",
    response_model=ApiResponse[InvoiceDetailResponse],
)
async def get_invoice_detail(
    document_id: Annotated[str, Path(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")],
    user: Annotated[
        CurrentUser,
        Depends(require_role(UserRole.AP_CLERK, UserRole.FINANCE_MANAGER, UserRole.ADMIN)),
    ],
):
    """Get full invoice detail including extraction results and match data."""
    item = _invoice_db.get_item({"documentId": document_id})

    if not item:
        raise AppError("Invoice not found.", status_code=404)

    # AP_CLERK can only view their own invoices
    if not user.has_role(UserRole.FINANCE_MANAGER, UserRole.ADMIN):
        if item.get("uploadedBy") != user.user_id:
            raise AppError("Insufficient permissions for this action.", status_code=403)

    # Generate presigned GET URL for document viewing
    document_url = None
    if item.get("s3Key"):
        try:
            document_url = _s3.generate_presigned_get(item["s3Key"])
        except Exception:
            logger.warning(
                "Failed to generate document URL for %s", document_id
            )

    return ApiResponse(
        data=InvoiceDetailResponse(
            documentId=item["documentId"],
            fileName=item["fileName"],
            status=item["status"],
            uploadedAt=item["uploadedAt"],
            updatedAt=item.get("updatedAt"),
            uploadedBy=item["uploadedBy"],
            documentUrl=document_url,
            extraction=item.get("extraction"),
            confidence=item.get("confidence"),
            overallConfidence=_to_float(item.get("overallConfidence")),
            matchResult=item.get("matchResult"),
            approvalDecision=item.get("approvalDecision"),
            errorDetails=item.get("errorDetails"),
            processingDurationMs=_to_int(item.get("processingDurationMs")),
        )
    )


@router.post(
    "/{document_id}/approve",
    response_model=ApiResponse[InvoiceApproveResponse],
)
async def approve_invoice(
    document_id: Annotated[
        str,
        Path(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"),
    ],
    body: InvoiceApproveRequest,
    user: Annotated[
        CurrentUser,
        Depends(require_role(UserRole.FINANCE_MANAGER, UserRole.ADMIN)),
    ],
):
    """Manually approve or reject an escalated invoice.

    Only FINANCE_MANAGER and ADMIN roles can call this endpoint (AC-3.8.2, AC-3.8.3).
    The invoice must be in ESCALATED status.
    A mandatory comment (≥5 chars) is required for audit purposes.
    """
    item = _invoice_db.get_item({"documentId": document_id})
    if not item:
        raise AppError("Invoice not found.", status_code=404)

    if item.get("status") != InvoiceStatus.ESCALATED:
        raise AppError(
            f"Invoice cannot be reviewed — current status is '{item.get('status')}'. "
            "Only ESCALATED invoices can be manually approved or rejected.",
            status_code=400,
        )

    is_approve = body.action == "APPROVE"
    new_status = InvoiceStatus.APPROVED if is_approve else InvoiceStatus.REJECTED
    now = datetime.now(timezone.utc).isoformat()

    approval_record = {
        "decision":   body.action,
        "approver":   user.email if user.email else user.user_id,
        "approvedAt": now,
        "comment":    body.comment,
    }

    logger.info(
        "Manual invoice review",
        extra={
            "documentId": document_id,
            "action": body.action,
            "reviewer": user.user_id,
            "newStatus": new_status,
        },
    )

    _invoice_db.update_status(
        document_id=document_id,
        new_status=new_status,
        expected_current=InvoiceStatus.ESCALATED,
        approvalDecision=approval_record,
    )

    return ApiResponse(
        data=InvoiceApproveResponse(
            documentId=document_id,
            newStatus=new_status,
            approver=user.email if user.email else user.user_id,
            approvedAt=now,
        )
    )


@router.post(
    "/process",
    status_code=202,
    include_in_schema=False,   # Internal endpoint — not in public API docs
)
async def trigger_processing(
    payload: ProcessTriggerRequest,
    user: Annotated[
        CurrentUser,
        Depends(require_role(UserRole.ADMIN)),
    ],
):
    """Manually trigger invoice processing for a specific document.

    In production this is invoked by the S3 event on the InvoiceProcessor Lambda.
    This endpoint allows demo/testing of the processing pipeline via HTTP.

    Request body: { "s3Key": "invoices/<id>/<filename>", "bucket": "..." (optional) }
    """
    bucket = payload.bucket or settings.DOCUMENT_BUCKET
    s3_key = payload.s3_key

    logger.info(
        "Manual pipeline trigger",
        extra={"bucket": bucket, "s3Key": s3_key, "userId": user.user_id},
    )

    process_invoice(bucket=bucket, s3_key=s3_key)

    return {"message": "Processing pipeline triggered.", "s3Key": s3_key}


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _query_all_invoices(
    limit: int, exclusive_start_key: dict | None
) -> tuple[list[dict], dict | None]:
    """Scan all invoices (for admin/manager views). MVP only — low volume.

    Note: Application-level sort after scan. Pagination with scan does not
    guarantee global order, but acceptable for MVP with <100 items.
    """
    kwargs: dict = {
        "Limit": limit,
        "ProjectionExpression": "documentId, fileName, #s, uploadedAt, uploadedBy, extraction",
        "ExpressionAttributeNames": {"#s": "status"},
    }
    if exclusive_start_key:
        kwargs["ExclusiveStartKey"] = exclusive_start_key

    try:
        response = _invoice_db.table.scan(**kwargs)
        items = response.get("Items", [])
        last_key = response.get("LastEvaluatedKey")

        # Sort by uploadedAt descending (scan doesn't guarantee order)
        items.sort(key=lambda x: x.get("uploadedAt", ""), reverse=True)
        return items, last_key
    except Exception as e:
        logger.error("Failed to scan invoices: %s", str(e))
        raise AppError("Failed to retrieve invoices.", status_code=500)


def _to_float(value) -> float | None:
    """Safely convert DynamoDB Decimal to float."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value) -> int | None:
    """Safely convert DynamoDB Decimal to int."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
