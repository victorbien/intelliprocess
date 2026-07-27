"""Organizational document management endpoints.

Handles:
- POST /documents/upload — Upload a document for the Knowledge Base
- GET /documents — List documents in the knowledge base
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.config import settings
from app.middleware import CurrentUser, require_role
from app.models.enums import (
    DocumentCategory,
    DocumentType,
    PRESIGNED_URL_EXPIRY_SECONDS,
    UserRole,
)
from app.models.schemas import (
    ApiResponse,
    DocumentListItem,
    DocumentUploadRequest,
    DocumentUploadResponse,
    PaginatedResponse,
    PresignedPostData,
)
from app.services.dynamo import DynamoClient
from app.services.s3 import S3Client

logger = logging.getLogger(__name__)
router = APIRouter()

# Service instances
_documents_db = DynamoClient(settings.DOCUMENT_TABLE)
_s3 = S3Client()


@router.post(
    "/upload",
    response_model=ApiResponse[DocumentUploadResponse],
    status_code=201,
)
async def upload_document(
    body: DocumentUploadRequest,
    user: Annotated[CurrentUser, Depends(require_role(UserRole.ADMIN))],
):
    """Generate a presigned S3 URL for uploading an organizational document.

    Only administrators can upload documents to the Knowledge Base.
    After upload, a KB sync must be triggered for the document to become searchable.
    """
    document_id = str(uuid.uuid4())
    s3_key = f"{DocumentType.RECORD}/{document_id}/{body.file_name}"

    logger.info(
        "Document upload initiated",
        extra={
            "documentId": document_id,
            "fileName": body.file_name,
            "category": body.category,
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
    _documents_db.put_item(
        {
            "documentId": document_id,
            "fileName": body.file_name,
            "s3Key": s3_key,
            "category": body.category.value,
            "uploadedAt": now,
            "uploadedBy": user.user_id,
            "contentType": body.content_type,
            "description": body.description or "",
            "kbSyncStatus": "PENDING",
            "fileSize": 0,  # Updated after actual upload if needed
        }
    )

    logger.info(
        "Document metadata created",
        extra={
            "documentId": document_id,
            "category": body.category,
            "kbSyncStatus": "PENDING",
        },
    )

    return ApiResponse(
        status_code=201,
        data=DocumentUploadResponse(
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
    response_model=ApiResponse[PaginatedResponse[DocumentListItem]],
)
async def list_documents(
    user: Annotated[CurrentUser, Depends(require_role(
        UserRole.AP_CLERK, UserRole.FINANCE_MANAGER, UserRole.STAFF, UserRole.ADMIN
    ))],
    category: DocumentCategory | None = Query(None, description="Filter by category"),
    limit: int = Query(50, ge=1, le=100, description="Max results"),
):
    """List organizational documents in the Knowledge Base.

    All authenticated users can view the document list.
    Optionally filter by category.
    """
    if category:
        # Query by category using GSI-CategoryDate
        items, last_key = _documents_db.query_by_index(
            index_name="GSI-CategoryDate",
            partition_key="category",
            partition_value=category.value,
            limit=limit,
            scan_forward=False,
        )
    else:
        # Return all documents (scan — acceptable for MVP with <100 docs)
        response = _documents_db.table.scan(Limit=limit)
        items = response.get("Items", [])
        items.sort(key=lambda x: x.get("uploadedAt", ""), reverse=True)
        last_key = None  # No pagination for scan in MVP

    document_items = [
        DocumentListItem(
            documentId=item["documentId"],
            fileName=item["fileName"],
            category=item["category"],
            uploadedAt=item["uploadedAt"],
            description=item.get("description") or None,
            kbSyncStatus=item.get("kbSyncStatus"),
        )
        for item in items
    ]

    return ApiResponse(
        data=PaginatedResponse(
            items=document_items,
            count=len(document_items),
            next_key=None,
        )
    )
