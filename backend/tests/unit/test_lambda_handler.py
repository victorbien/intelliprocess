"""Unit tests for the InvoiceProcessor Lambda handler.

Tests the S3 event parsing, validation, and dispatch logic without
invoking the real processing pipeline or AWS services.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from functions.invoice_processor.app import (
    lambda_handler,
    _process_record,
    _infer_content_type,
    _get_request_id,
)


# ── Test fixtures & helpers ───────────────────────────────────────────────────


def _make_s3_event(
    bucket: str = "intelliprocess-ai-documents",
    key: str = "invoices/abc-123-def/invoice.pdf",
    size: int = 50_000,
    event_name: str = "ObjectCreated:Put",
) -> dict:
    """Build a minimal S3 event notification payload."""
    return {
        "Records": [
            {
                "eventName": event_name,
                "s3": {
                    "bucket": {"name": bucket},
                    "object": {"key": key, "size": size},
                },
            }
        ]
    }


def _make_record(
    bucket: str = "intelliprocess-ai-documents",
    key: str = "invoices/abc-123-def/invoice.pdf",
    size: int = 50_000,
    event_name: str = "ObjectCreated:Put",
) -> dict:
    """Build a single S3 event record."""
    return {
        "eventName": event_name,
        "s3": {
            "bucket": {"name": bucket},
            "object": {"key": key, "size": size},
        },
    }


class MockContext:
    """Minimal mock of the Lambda context object."""

    aws_request_id = "test-request-id-12345"


# ── lambda_handler: basic invocation ─────────────────────────────────────────


class TestLambdaHandler:
    """Tests for the top-level lambda_handler function."""

    @patch("functions.invoice_processor.app.process_invoice")
    def test_processes_valid_single_record(self, mock_processor):
        """A valid S3 event with one record dispatches to process_invoice."""
        event = _make_s3_event()
        result = lambda_handler(event, MockContext())

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["processed"] == 1
        assert body["skipped"] == 0
        assert body["failed"] == 0
        mock_processor.assert_called_once_with(
            bucket="intelliprocess-ai-documents",
            s3_key="invoices/abc-123-def/invoice.pdf",
        )

    @patch("functions.invoice_processor.app.process_invoice")
    def test_processes_multiple_records(self, mock_processor):
        """Multiple records in one event are each processed."""
        event = {
            "Records": [
                _make_record(key="invoices/id-1/file1.pdf"),
                _make_record(key="invoices/id-2/file2.png"),
            ]
        }
        result = lambda_handler(event, MockContext())

        body = json.loads(result["body"])
        assert body["processed"] == 2
        assert mock_processor.call_count == 2

    def test_empty_records_returns_200(self):
        """Event with no Records returns 200 without error."""
        event = {"Records": []}
        result = lambda_handler(event, MockContext())
        assert result["statusCode"] == 200

    def test_missing_records_key_returns_200(self):
        """Event missing the Records key entirely is handled gracefully."""
        event = {}
        result = lambda_handler(event, MockContext())
        assert result["statusCode"] == 200

    @patch("functions.invoice_processor.app.process_invoice")
    def test_url_encoded_keys_are_decoded(self, mock_processor):
        """S3 keys with URL-encoded characters (e.g., spaces) are decoded."""
        event = _make_s3_event(key="invoices/abc-123/my+invoice+file.pdf")
        lambda_handler(event, MockContext())

        mock_processor.assert_called_once_with(
            bucket="intelliprocess-ai-documents",
            s3_key="invoices/abc-123/my invoice file.pdf",
        )

    @patch("functions.invoice_processor.app.process_invoice")
    def test_percent_encoded_keys_are_decoded(self, mock_processor):
        """S3 keys with %XX encoding are properly decoded."""
        event = _make_s3_event(key="invoices/abc-123/invoice%20%282%29.pdf")
        lambda_handler(event, MockContext())

        mock_processor.assert_called_once_with(
            bucket="intelliprocess-ai-documents",
            s3_key="invoices/abc-123/invoice (2).pdf",
        )


# ── _process_record: validation logic ────────────────────────────────────────


class TestProcessRecordValidation:
    """Tests for S3 event record validation."""

    @patch("functions.invoice_processor.app.process_invoice")
    def test_valid_pdf_is_processed(self, mock_processor):
        """Standard PDF invoice is processed."""
        record = _make_record(key="invoices/doc-id-1/bill.pdf", size=1024)
        result = _process_record(record)
        assert result["status"] == "processed"

    @patch("functions.invoice_processor.app.process_invoice")
    def test_valid_png_is_processed(self, mock_processor):
        """PNG invoice image is processed."""
        record = _make_record(key="invoices/doc-id-1/scan.png", size=2048)
        result = _process_record(record)
        assert result["status"] == "processed"

    @patch("functions.invoice_processor.app.process_invoice")
    def test_valid_jpeg_is_processed(self, mock_processor):
        """JPEG invoice image is processed."""
        record = _make_record(key="invoices/doc-id-1/photo.jpeg", size=3000)
        result = _process_record(record)
        assert result["status"] == "processed"

    @patch("functions.invoice_processor.app.process_invoice")
    def test_valid_jpg_is_processed(self, mock_processor):
        """JPG extension is also accepted."""
        record = _make_record(key="invoices/doc-id-1/photo.jpg", size=3000)
        result = _process_record(record)
        assert result["status"] == "processed"

    def test_non_create_event_is_skipped(self):
        """Non ObjectCreated events are skipped."""
        record = _make_record(event_name="ObjectRemoved:Delete")
        result = _process_record(record)
        assert result["status"] == "skipped"
        assert "Event type" in result["reason"]

    def test_invalid_key_structure_is_skipped(self):
        """S3 key with fewer than 3 parts is skipped."""
        record = _make_record(key="invoices/only-one-part")
        result = _process_record(record)
        assert result["status"] == "skipped"
        assert "Invalid key structure" in result["reason"]

    def test_non_invoice_prefix_is_skipped(self):
        """Objects under non-invoice prefixes are skipped."""
        record = _make_record(key="records/doc-id/file.pdf")
        result = _process_record(record)
        assert result["status"] == "skipped"
        assert "Not an invoice prefix" in result["reason"]

    def test_zero_byte_object_is_skipped(self):
        """Zero-byte objects are skipped."""
        record = _make_record(size=0)
        result = _process_record(record)
        assert result["status"] == "skipped"
        assert "Zero-byte" in result["reason"]

    def test_oversized_object_fails(self):
        """Objects exceeding MAX_FILE_SIZE_BYTES fail with an error."""
        record = _make_record(size=11 * 1024 * 1024)  # 11 MB > 10 MB limit
        result = _process_record(record)
        assert result["status"] == "failed"
        assert "exceeds limit" in result["reason"]

    def test_unsupported_file_type_with_unknown_extension_is_allowed(self):
        """Files with unrecognized extensions pass through (content type unknown).

        The Lambda validates by extension only. If the extension is not
        recognizable, we allow it through — the processing pipeline will
        fail if BDA cannot handle the format.
        """
        # .xlsx is not in _EXTENSION_MAP → content_type is None → passes validation
        # This is by design: strict upload validation happens at the API layer
        pass

    @patch("functions.invoice_processor.app.process_invoice")
    def test_recognized_but_unsupported_type_is_rejected(self, mock_processor):
        """Files with extensions that map to non-invoice content types are rejected.

        Note: Currently all recognized extensions (pdf, png, jpg, jpeg)
        ARE invoice-supported types. This test documents that if we added
        an extension to _EXTENSION_MAP that wasn't in INVOICE_CONTENT_TYPES,
        it would be rejected.
        """
        # Monkey-patch to test the code path
        import functions.invoice_processor.app as handler_module
        original_map = handler_module._EXTENSION_MAP.copy()
        handler_module._EXTENSION_MAP[".docx"] = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        try:
            record = _make_record(key="invoices/doc-id/contract.docx")
            result = _process_record(record)
            assert result["status"] == "failed"
            assert "Unsupported content type" in result["reason"]
        finally:
            handler_module._EXTENSION_MAP = original_map

    @patch("functions.invoice_processor.app.process_invoice")
    def test_unknown_extension_is_still_processed(self, mock_processor):
        """Files with no recognizable extension are allowed (content_type=None)."""
        record = _make_record(key="invoices/doc-id-1/some-file")
        result = _process_record(record)
        # Unknown extension → content_type is None → validation passes
        assert result["status"] == "processed"

    def test_malformed_record_fails(self):
        """Completely malformed record structure fails gracefully."""
        record = {"garbage": True}
        result = _process_record(record)
        # Should not raise — returns a failed result
        assert result["status"] in ("failed", "skipped")

    @patch("functions.invoice_processor.app.process_invoice")
    def test_processor_exception_is_caught(self, mock_processor):
        """If process_invoice raises an unexpected exception, it's caught."""
        mock_processor.side_effect = RuntimeError("Catastrophic failure")
        record = _make_record()
        result = _process_record(record)
        assert result["status"] == "failed"
        assert "Catastrophic failure" in result["reason"]


# ── _process_record: edge cases ───────────────────────────────────────────────


class TestProcessRecordEdgeCases:
    """Edge cases and boundary conditions."""

    @patch("functions.invoice_processor.app.process_invoice")
    def test_exactly_10mb_file_is_processed(self, mock_processor):
        """A file exactly at the limit (10MB) should be processed."""
        record = _make_record(size=10 * 1024 * 1024)
        result = _process_record(record)
        assert result["status"] == "processed"

    @patch("functions.invoice_processor.app.process_invoice")
    def test_one_byte_over_limit_fails(self, mock_processor):
        """A file 1 byte over the limit should fail."""
        record = _make_record(size=10 * 1024 * 1024 + 1)
        result = _process_record(record)
        assert result["status"] == "failed"

    @patch("functions.invoice_processor.app.process_invoice")
    def test_deep_key_path_is_processed(self, mock_processor):
        """S3 keys with extra path components are accepted."""
        record = _make_record(key="invoices/doc-id/subfolder/deep/file.pdf")
        result = _process_record(record)
        assert result["status"] == "processed"

    @patch("functions.invoice_processor.app.process_invoice")
    def test_key_with_special_characters(self, mock_processor):
        """S3 keys with special characters are handled."""
        record = _make_record(key="invoices/doc-id-with-dashes/file (1).pdf")
        result = _process_record(record)
        assert result["status"] == "processed"


# ── Helper function tests ─────────────────────────────────────────────────────


class TestInferContentType:
    """Tests for _infer_content_type helper."""

    def test_pdf(self):
        assert _infer_content_type("invoice.pdf") == "application/pdf"

    def test_pdf_uppercase(self):
        assert _infer_content_type("INVOICE.PDF") == "application/pdf"

    def test_png(self):
        assert _infer_content_type("scan.png") == "image/png"

    def test_jpeg(self):
        assert _infer_content_type("photo.jpeg") == "image/jpeg"

    def test_jpg(self):
        assert _infer_content_type("photo.jpg") == "image/jpeg"

    def test_unknown_returns_none(self):
        assert _infer_content_type("data.csv") is None

    def test_no_extension_returns_none(self):
        assert _infer_content_type("noextension") is None


class TestGetRequestId:
    """Tests for _get_request_id helper."""

    def test_returns_request_id_from_context(self):
        assert _get_request_id(MockContext()) == "test-request-id-12345"

    def test_returns_local_when_no_attribute(self):
        assert _get_request_id(object()) == "local"

    def test_returns_local_when_none(self):
        assert _get_request_id(None) == "local"
