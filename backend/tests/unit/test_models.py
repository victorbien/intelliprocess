"""Unit tests for Pydantic models and validation logic."""

import pytest
from pydantic import ValidationError

from app.models.enums import DocumentCategory, InvoiceStatus, UserRole
from app.models.schemas import (
    DocumentUploadRequest,
    InvoiceUploadRequest,
)


class TestInvoiceUploadRequest:
    """Tests for invoice upload request validation."""

    def test_valid_pdf_upload(self):
        req = InvoiceUploadRequest(fileName="invoice.pdf", contentType="application/pdf")
        assert req.file_name == "invoice.pdf"
        assert req.content_type == "application/pdf"

    def test_valid_png_upload(self):
        req = InvoiceUploadRequest(fileName="scan.png", contentType="image/png")
        assert req.file_name == "scan.png"

    def test_valid_jpeg_upload(self):
        req = InvoiceUploadRequest(fileName="photo.jpeg", contentType="image/jpeg")
        assert req.file_name == "photo.jpeg"

    def test_valid_jpg_extension(self):
        req = InvoiceUploadRequest(fileName="photo.jpg", contentType="image/jpeg")
        assert req.file_name == "photo.jpg"

    def test_rejects_unsupported_content_type(self):
        with pytest.raises(ValidationError) as exc_info:
            InvoiceUploadRequest(fileName="data.xlsx", contentType="application/vnd.ms-excel")
        errors = exc_info.value.errors()
        assert any("Unsupported file format" in str(e["msg"]) for e in errors)

    def test_rejects_tiff_content_type(self):
        with pytest.raises(ValidationError):
            InvoiceUploadRequest(fileName="scan.tiff", contentType="image/tiff")

    def test_rejects_unsupported_extension(self):
        with pytest.raises(ValidationError) as exc_info:
            InvoiceUploadRequest(fileName="data.xlsx", contentType="application/pdf")
        errors = exc_info.value.errors()
        assert any("Unsupported file format" in str(e["msg"]) for e in errors)

    def test_rejects_empty_filename(self):
        with pytest.raises(ValidationError) as exc_info:
            InvoiceUploadRequest(fileName="   ", contentType="application/pdf")
        errors = exc_info.value.errors()
        assert any("empty" in str(e["msg"]).lower() for e in errors)

    def test_rejects_filename_too_long(self):
        long_name = "a" * 252 + ".pdf"  # 256 chars total
        with pytest.raises(ValidationError):
            InvoiceUploadRequest(fileName=long_name, contentType="application/pdf")

    def test_strips_whitespace_from_filename(self):
        req = InvoiceUploadRequest(fileName="  invoice.pdf  ", contentType="application/pdf")
        assert req.file_name == "invoice.pdf"

    def test_rejects_path_traversal(self):
        with pytest.raises(ValidationError) as exc_info:
            InvoiceUploadRequest(fileName="../../../etc/passwd.pdf", contentType="application/pdf")
        errors = exc_info.value.errors()
        assert any("invalid characters" in str(e["msg"]).lower() for e in errors)

    def test_rejects_slashes_in_filename(self):
        with pytest.raises(ValidationError):
            InvoiceUploadRequest(fileName="path/to/invoice.pdf", contentType="application/pdf")

    def test_rejects_backslashes_in_filename(self):
        with pytest.raises(ValidationError):
            InvoiceUploadRequest(fileName="path\\to\\invoice.pdf", contentType="application/pdf")


class TestDocumentUploadRequest:
    """Tests for organizational document upload request validation."""

    def test_valid_pdf_document(self):
        req = DocumentUploadRequest(
            fileName="policy.pdf",
            contentType="application/pdf",
            category="policies",
            description="Travel policy 2024",
        )
        assert req.file_name == "policy.pdf"
        assert req.category == DocumentCategory.POLICIES

    def test_valid_docx_document(self):
        req = DocumentUploadRequest(
            fileName="contract.docx",
            contentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            category="contracts",
        )
        assert req.category == DocumentCategory.CONTRACTS

    def test_valid_txt_document(self):
        req = DocumentUploadRequest(
            fileName="notes.txt",
            contentType="text/plain",
            category="general",
        )
        assert req.category == DocumentCategory.GENERAL

    def test_rejects_image_for_records(self):
        with pytest.raises(ValidationError) as exc_info:
            DocumentUploadRequest(
                fileName="scan.png",
                contentType="image/png",
                category="policies",
            )
        errors = exc_info.value.errors()
        assert any("Unsupported file format for records" in str(e["msg"]) for e in errors)

    def test_rejects_invalid_category(self):
        with pytest.raises(ValidationError):
            DocumentUploadRequest(
                fileName="doc.pdf",
                contentType="application/pdf",
                category="invalid_category",
            )

    def test_description_optional(self):
        req = DocumentUploadRequest(
            fileName="doc.pdf",
            contentType="application/pdf",
            category="finance",
        )
        assert req.description is None

    def test_description_max_length(self):
        with pytest.raises(ValidationError):
            DocumentUploadRequest(
                fileName="doc.pdf",
                contentType="application/pdf",
                category="finance",
                description="x" * 501,
            )

    def test_rejects_path_traversal_in_document_name(self):
        with pytest.raises(ValidationError):
            DocumentUploadRequest(
                fileName="../../secret.pdf",
                contentType="application/pdf",
                category="policies",
            )


class TestEnums:
    """Tests for enum values and membership."""

    def test_invoice_status_values(self):
        assert InvoiceStatus.UPLOADED == "UPLOADED"
        assert InvoiceStatus.APPROVED == "APPROVED"
        assert InvoiceStatus.ESCALATED == "ESCALATED"
        assert InvoiceStatus.ERROR == "ERROR"

    def test_user_role_values(self):
        assert UserRole.AP_CLERK == "AP_CLERK"
        assert UserRole.FINANCE_MANAGER == "FINANCE_MANAGER"
        assert UserRole.ADMIN == "ADMIN"
        assert UserRole.STAFF == "STAFF"

    def test_document_category_values(self):
        assert DocumentCategory.POLICIES == "policies"
        assert DocumentCategory.CONTRACTS == "contracts"
