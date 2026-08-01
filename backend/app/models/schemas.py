"""Pydantic request/response models for all API endpoints."""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, field_validator

from app.models.enums import (
    INVOICE_CONTENT_TYPES,
    RECORDS_CONTENT_TYPES,
    DocumentCategory,
    InvoiceStatus,
)

T = TypeVar("T")


# ─── Generic Response Envelopes ───────────────────────────────────────────────


class ApiResponse(BaseModel, Generic[T]):
    """Standard success response envelope."""

    status_code: int = 200
    data: T


class ErrorResponse(BaseModel):
    """Standard error response envelope."""

    status_code: int
    error: str


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated list response."""

    items: list[T]
    count: int
    next_key: str | None = None


# ─── Presigned URL ────────────────────────────────────────────────────────────


class PresignedPostData(BaseModel):
    """S3 presigned POST URL fields."""

    url: str
    fields: dict[str, str]


# ─── Invoice Schemas ──────────────────────────────────────────────────────────


class InvoiceUploadRequest(BaseModel):
    """Request body for POST /invoices/upload."""

    file_name: str = Field(..., max_length=255, alias="fileName")
    content_type: str = Field(..., alias="contentType")

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        if v not in INVOICE_CONTENT_TYPES:
            raise ValueError(
                f"Unsupported file format. Please upload PDF, PNG, or JPEG. Got: {v}"
            )
        return v

    @field_validator("file_name")
    @classmethod
    def validate_file_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("File name cannot be empty.")
        v = v.strip()
        # Security: prevent path traversal
        if ".." in v or "/" in v or "\\" in v:
            raise ValueError("File name contains invalid characters.")
        allowed_extensions = (".pdf", ".png", ".jpeg", ".jpg")
        if not v.lower().endswith(allowed_extensions):
            raise ValueError(
                "Unsupported file format. Please upload PDF, PNG, or JPEG."
            )
        return v

    model_config = {"populate_by_name": True}


class InvoiceUploadResponse(BaseModel):
    """Response body for POST /invoices/upload."""

    document_id: str = Field(..., alias="documentId")
    upload_url: PresignedPostData = Field(..., alias="uploadUrl")
    expires_in: int = Field(..., alias="expiresIn")

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


class InvoiceListItem(BaseModel):
    """Single invoice in a list response."""

    document_id: str = Field(..., alias="documentId")
    file_name: str = Field(..., alias="fileName")
    status: InvoiceStatus
    uploaded_at: str = Field(..., alias="uploadedAt")
    uploaded_by: str = Field(..., alias="uploadedBy")
    vendor_name: str | None = Field(None, alias="vendorName")
    total_amount: float | None = Field(None, alias="totalAmount")

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


class InvoiceDetailResponse(BaseModel):
    """Full invoice detail response."""

    document_id: str = Field(..., alias="documentId")
    file_name: str = Field(..., alias="fileName")
    status: InvoiceStatus
    uploaded_at: str = Field(..., alias="uploadedAt")
    updated_at: str | None = Field(None, alias="updatedAt")
    uploaded_by: str = Field(..., alias="uploadedBy")
    document_url: str | None = Field(None, alias="documentUrl")
    extraction: dict[str, Any] | None = None
    confidence: dict[str, float] | None = None
    overall_confidence: float | None = Field(None, alias="overallConfidence")
    match_result: dict[str, Any] | None = Field(None, alias="matchResult")
    approval_decision: dict[str, Any] | None = Field(None, alias="approvalDecision")
    error_details: str | None = Field(None, alias="errorDetails")
    processing_duration_ms: int | None = Field(None, alias="processingDurationMs")

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


# ─── Document (Records) Schemas ───────────────────────────────────────────────


class DocumentUploadRequest(BaseModel):
    """Request body for POST /documents/upload."""

    file_name: str = Field(..., max_length=255, alias="fileName")
    content_type: str = Field(..., alias="contentType")
    category: DocumentCategory
    description: str | None = Field(None, max_length=500)

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        if v not in RECORDS_CONTENT_TYPES:
            raise ValueError(
                "Unsupported file format for records. Please upload PDF, DOCX, or TXT."
            )
        return v

    @field_validator("file_name")
    @classmethod
    def validate_file_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("File name cannot be empty.")
        v = v.strip()
        # Security: prevent path traversal
        if ".." in v or "/" in v or "\\" in v:
            raise ValueError("File name contains invalid characters.")
        allowed_extensions = (".pdf", ".docx", ".txt")
        if not v.lower().endswith(allowed_extensions):
            raise ValueError(
                "Unsupported file format for records. Please upload PDF, DOCX, or TXT."
            )
        return v

    model_config = {"populate_by_name": True}


class DocumentUploadResponse(BaseModel):
    """Response body for POST /documents/upload."""

    document_id: str = Field(..., alias="documentId")
    upload_url: PresignedPostData = Field(..., alias="uploadUrl")
    expires_in: int = Field(..., alias="expiresIn")
    note: str = "Document will be available for search after next knowledge base sync."

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


class DocumentListItem(BaseModel):
    """Single document in a list response."""

    document_id: str = Field(..., alias="documentId")
    file_name: str = Field(..., alias="fileName")
    category: DocumentCategory
    uploaded_at: str = Field(..., alias="uploadedAt")
    description: str | None = None
    kb_sync_status: str | None = Field(None, alias="kbSyncStatus")

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


# ─── Manual Approval Schemas ───────────────────────────────────────────────────


class InvoiceApproveRequest(BaseModel):
    """Request body for POST /invoices/{id}/approve.

    Covers AC-3.8.2 (Approve) and AC-3.8.3 (Reject).
    """

    action: str = Field(..., alias="action")
    comment: str = Field(..., min_length=5, max_length=500, alias="comment")

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        allowed = {"APPROVE", "REJECT"}
        if v.upper() not in allowed:
            raise ValueError(f"action must be one of {sorted(allowed)}")
        return v.upper()

    model_config = {"populate_by_name": True}


class InvoiceApproveResponse(BaseModel):
    """Response body for POST /invoices/{id}/approve."""

    document_id: str = Field(..., alias="documentId")
    new_status: str = Field(..., alias="newStatus")
    approver: str
    approved_at: str = Field(..., alias="approvedAt")

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


class ProcessTriggerRequest(BaseModel):
    """Request body for POST /invoices/process (internal demo/testing endpoint)."""

    s3_key: str = Field(..., alias="s3Key", min_length=1)
    bucket: str | None = Field(None)

    @field_validator("s3_key")
    @classmethod
    def validate_s3_key(cls, v: str) -> str:
        if not v.startswith("invoices/"):
            raise ValueError("s3Key must start with 'invoices/'")
        return v

    model_config = {"populate_by_name": True}
