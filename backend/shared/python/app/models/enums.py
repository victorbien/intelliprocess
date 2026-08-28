"""Shared enumerations used across the application."""

from enum import StrEnum


class InvoiceStatus(StrEnum):
    """Invoice processing lifecycle statuses."""

    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    EXTRACTED = "EXTRACTED"
    APPROVED = "APPROVED"
    ESCALATED = "ESCALATED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"


class DocumentType(StrEnum):
    """Types of documents stored in the system."""

    INVOICE = "invoices"
    PURCHASE_ORDER = "purchase-orders"
    GOODS_RECEIPT = "goods-receipts"
    RECORD = "records"


class UserRole(StrEnum):
    """Cognito user group roles."""

    AP_CLERK = "AP_CLERK"
    FINANCE_MANAGER = "FINANCE_MANAGER"
    STAFF = "STAFF"
    ADMIN = "ADMIN"


class DocumentCategory(StrEnum):
    """Categories for organizational documents in the Knowledge Base."""

    POLICIES = "policies"
    CONTRACTS = "contracts"
    FINANCE = "finance"
    PROCUREMENT = "procurement"
    GENERAL = "general"


# Valid content types per document type
INVOICE_CONTENT_TYPES = frozenset(
    ["application/pdf", "image/png", "image/jpeg"]
)

RECORDS_CONTENT_TYPES = frozenset(
    [
        "application/pdf",
        "text/plain",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]
)

# Business rule constants
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
PRESIGNED_URL_EXPIRY_SECONDS = 300  # 5 minutes
