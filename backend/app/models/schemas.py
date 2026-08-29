"""Pydantic request/response models for all API endpoints."""

import re
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


# ─── Chat Schemas ─────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    """Request body for POST /chat."""

    question: str = Field(..., min_length=1, max_length=1000)
    session_id: str | None = Field(None, max_length=64, alias="sessionId")
    category_filter: str | None = Field(None, alias="categoryFilter")

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Question cannot be blank.")
        return v.strip()
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


class ChatCitation(BaseModel):
    """A source reference included in a document-search answer."""

    document_name: str = Field(..., alias="documentName")
    document_id: str = Field(..., alias="documentId")
    page_number: int | None = Field(None, alias="pageNumber")
    relevance_score: float = Field(..., alias="relevanceScore")
    snippet: str
    category: str | None = None
class InvoiceApproveResponse(BaseModel):
    """Response body for POST /invoices/{id}/approve."""

    document_id: str = Field(..., alias="documentId")
    new_status: str = Field(..., alias="newStatus")
    approver: str
    approved_at: str = Field(..., alias="approvedAt")

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


class ChatResponse(BaseModel):
    """Response body for POST /chat."""

    answer: str
    citations: list[ChatCitation] = []
    session_id: str = Field(..., alias="sessionId")
    source_type: str = Field(..., alias="sourceType")
    data_snapshot: dict[str, Any] | None = Field(None, alias="dataSnapshot")
    unavailable: bool | None = None
    response_time_ms: int = Field(..., alias="responseTimeMs")

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


class ChatMessage(BaseModel):
    """A single turn in a conversation history."""

    role: str  # "user" | "assistant"
    content: str
    timestamp: str
    citations: list[ChatCitation] | None = None
    source_type: str | None = Field(None, alias="sourceType")

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


class ChatSessionSummary(BaseModel):
    """Summary of a chat session for the sessions list."""

    session_id: str = Field(..., alias="sessionId")
    first_message: str = Field(..., alias="firstMessage")
    last_activity: str = Field(..., alias="lastActivity")
    message_count: int = Field(..., alias="messageCount")
    summary: str | None = None
    summary_generated_at: str | None = Field(None, alias="summaryGeneratedAt")

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


class ChatSummaryResponse(BaseModel):
    """Response body for POST /chat/sessions/{id}/summary."""

    session_id: str = Field(..., alias="sessionId")
    summary: str
    generated_at: str = Field(..., alias="generatedAt")

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


class ChatSessionDetail(BaseModel):
    """Full conversation history for a session."""

    session_id: str = Field(..., alias="sessionId")
    messages: list[ChatMessage]

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


# ─── Dashboard Schemas (Module 4 — FR-AP-009, AC-3.9.x) ───────────────────────


class RecentActivityItem(BaseModel):
    """A single recent-activity entry on the dashboard."""

    document_id: str = Field(..., alias="documentId")
    file_name: str = Field(..., alias="fileName")
    action: str
    timestamp: str
    actor: str

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


class DashboardStatsResponse(BaseModel):
    """Response body for GET /dashboard/stats.

    Covers AC-3.9.1 (status counts) and AC-3.9.2 (current-state snapshot).
    """

    total_invoices: int = Field(..., alias="totalInvoices")
    status_counts: dict[str, int] = Field(..., alias="statusCounts")
    auto_approval_rate: float = Field(..., alias="autoApprovalRate")
    avg_processing_time_sec: float = Field(..., alias="avgProcessingTimeSec")
    recent_activity: list[RecentActivityItem] = Field(
        default_factory=list, alias="recentActivity"
    )

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


# ─── Admin: Seed Data Schemas (Module 4 — AC-5.1.4) ───────────────────────────


class SeedDataRequest(BaseModel):
    """Request body for POST /admin/seed-data."""

    data_set: str = Field("default", alias="dataSet", max_length=64)

    model_config = {"populate_by_name": True}


class SeedDataResponse(BaseModel):
    """Response body for POST /admin/seed-data."""

    message: str
    purchase_orders_created: int = Field(..., alias="purchaseOrdersCreated")
    goods_receipts_created: int = Field(..., alias="goodsReceiptsCreated")

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


# ─── Knowledge Base Sync Schemas (Module 4 — FR-CROSS-001) ────────────────────


class KbSyncResponse(BaseModel):
    """Response body for POST /documents/sync."""

    message: str
    sync_job_id: str | None = Field(None, alias="syncJobId")

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


# ─── Admin: Purchase Order Upload Schemas (Module 4 — AC-5.1.1, AC-5.1.3) ──────


# Identifiers used as DynamoDB keys / GSI partition values (PO numbers, GR ids).
# Restricted to a safe, predictable character set to prevent malformed keys.
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


def _validate_identifier(v: str, field: str) -> str:
    """Validate and normalise a key-like identifier (PO number, GR id)."""
    v = v.strip()
    if not v:
        raise ValueError(f"{field} cannot be blank.")
    if not _IDENTIFIER_PATTERN.match(v):
        raise ValueError(
            f"{field} may only contain letters, numbers, and the characters . _ / -"
        )
    return v


class PurchaseOrderUploadRequest(BaseModel):
    """Request body for POST /purchase-orders/upload.

    Admin uploads a structured PO record so the matcher can compare
    future invoices against it (three-way match, FR-AP-003).
    """

    po_number: str = Field(..., alias="poNumber", min_length=1, max_length=64)
    vendor_name: str = Field(..., alias="vendorName", min_length=1, max_length=255)
    total_amount: float = Field(..., alias="totalAmount", gt=0)
    currency: str = Field("USD", min_length=3, max_length=3)
    created_date: str | None = Field(None, alias="createdDate")
    department: str | None = Field(None, max_length=128)
    vendor_id: str | None = Field(None, alias="vendorId", max_length=64)

    @field_validator("po_number")
    @classmethod
    def validate_po_number(cls, v: str) -> str:
        return _validate_identifier(v, "poNumber")

    @field_validator("vendor_name")
    @classmethod
    def vendor_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("vendorName cannot be blank.")
        return v.strip()

    @field_validator("currency")
    @classmethod
    def normalise_currency(cls, v: str) -> str:
        v = v.strip().upper()
        if not v.isalpha():
            raise ValueError("currency must be a 3-letter ISO code (e.g. USD).")
        return v

    model_config = {"populate_by_name": True}


class PurchaseOrderUploadResponse(BaseModel):
    """Response body for POST /purchase-orders/upload."""

    po_number: str = Field(..., alias="poNumber")
    message: str = "Purchase order stored and available for matching."

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


# ─── Admin: Goods Receipt Upload Schemas (Module 4 — AC-5.1.2, AC-5.1.3) ───────


class GoodsReceiptUploadRequest(BaseModel):
    """Request body for POST /goods-receipts/upload.

    Admin uploads a structured GR record linked to a PO so the matcher
    can confirm receipt during three-way match (FR-AP-004).
    """

    gr_id: str = Field(..., alias="grId", min_length=1, max_length=64)
    po_number: str = Field(..., alias="poNumber", min_length=1, max_length=64)
    total_quantity_received: float = Field(
        ..., alias="totalQuantityReceived", gt=0
    )
    received_date: str | None = Field(None, alias="receivedDate")
    status: str = Field("COMPLETE", max_length=32)

    @field_validator("gr_id")
    @classmethod
    def validate_gr_id(cls, v: str) -> str:
        return _validate_identifier(v, "grId")

    @field_validator("po_number")
    @classmethod
    def validate_po_number(cls, v: str) -> str:
        return _validate_identifier(v, "poNumber")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"COMPLETE", "PARTIAL", "PENDING"}
        v = v.strip().upper()
        if v not in allowed:
            raise ValueError(f"status must be one of {sorted(allowed)}")
        return v

    model_config = {"populate_by_name": True}


class GoodsReceiptUploadResponse(BaseModel):
    """Response body for POST /goods-receipts/upload."""

    gr_id: str = Field(..., alias="grId")
    po_number: str = Field(..., alias="poNumber")
    message: str = "Goods receipt stored and linked to the purchase order."

    model_config = {"populate_by_name": True, "serialize_by_alias": True}
