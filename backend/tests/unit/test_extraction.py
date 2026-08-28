"""Unit tests for the BDA extraction service (backend/app/services/extraction.py).

Tests cover:
- Mock mode (USE_MOCKS=true)
- BDA invocation with retry logic
- BDA polling behavior
- BDA output reading with retry
- Response parsing and field normalization
- Validation of BDA output structure
- Validation of extraction results
- Error categorization (retryable vs non-retryable)
"""

import json
import pytest
from unittest.mock import patch, MagicMock, call

from botocore.exceptions import ClientError

from app.services.extraction import (
    ExtractionError,
    extract_invoice,
    _parse_bda_response,
    _parse_table_block,
    _coerce_field,
    _safe_float,
    _validate_bda_output,
    _validate_extraction_result,
    _invoke_bda_with_retry,
    _poll_bda,
    _read_bda_output_with_retry,
)


# ── Fixtures & helpers ────────────────────────────────────────────────────────


def _client_error(code: str, message: str = "Error") -> ClientError:
    """Build a botocore ClientError with the given error code."""
    return ClientError(
        {"Error": {"Code": code, "Message": message}},
        "TestOperation",
    )


def _make_bda_blocks(
    fields: dict[str, str] | None = None,
    table_rows: list[list[str]] | None = None,
    confidence: float = 0.95,
) -> dict:
    """Build a minimal BDA output structure."""
    blocks = []

    if fields:
        for key, value in fields.items():
            blocks.append({
                "blockType": "KEY_VALUE_SET",
                "key": {"text": key},
                "value": {"text": value},
                "geometry": {"confidence": confidence},
            })

    if table_rows:
        rows = []
        # Header row
        rows.append({"cells": [
            {"text": "Description"}, {"text": "Qty"},
            {"text": "Unit Price"}, {"text": "Amount"},
        ]})
        for row in table_rows:
            rows.append({"cells": [{"text": cell} for cell in row]})
        blocks.append({"blockType": "TABLE", "rows": rows})

    return {"blocks": blocks}


# ── Mock mode tests ───────────────────────────────────────────────────────────


class TestMockMode:
    """Tests for USE_MOCKS=true behavior."""

    @patch("app.services.extraction.settings")
    def test_mock_mode_returns_extraction_without_aws(self, mock_settings):
        """When USE_MOCKS=true, extract_invoice returns mock data without calling BDA."""
        mock_settings.USE_MOCKS = True
        result = extract_invoice(
            bucket="test-bucket",
            s3_key="invoices/abc-123/test.pdf",
        )

        assert "vendorName" in result
        assert "invoiceNumber" in result
        assert "totalAmount" in result
        assert "lineItems" in result
        assert "confidence" in result
        assert "overallConfidence" in result
        assert isinstance(result["totalAmount"], float)
        assert result["overallConfidence"] > 0

    @patch("app.services.extraction.settings")
    def test_mock_returns_consistent_structure(self, mock_settings):
        """Mock extraction has the same shape as a real BDA extraction."""
        mock_settings.USE_MOCKS = True
        result = extract_invoice(bucket="b", s3_key="invoices/id/f.pdf")

        # All canonical fields present
        expected_fields = [
            "vendorName", "invoiceNumber", "invoiceDate", "dueDate",
            "totalAmount", "subtotal", "taxAmount", "paymentTerms",
            "poReference", "lineItems", "confidence", "overallConfidence",
        ]
        for field in expected_fields:
            assert field in result, f"Missing field: {field}"

    @patch("app.services.extraction.settings")
    def test_mock_line_items_have_correct_shape(self, mock_settings):
        """Mock line items have description, quantity, unitPrice, amount."""
        mock_settings.USE_MOCKS = True
        result = extract_invoice(bucket="b", s3_key="invoices/id/f.pdf")

        for item in result["lineItems"]:
            assert "description" in item
            assert "quantity" in item
            assert "unitPrice" in item
            assert "amount" in item
            assert isinstance(item["quantity"], float)
            assert isinstance(item["unitPrice"], float)
            assert isinstance(item["amount"], float)


# ── BDA invocation with retry ─────────────────────────────────────────────────


class TestInvokeBdaWithRetry:
    """Tests for _invoke_bda_with_retry retry logic."""

    @patch("time.sleep")  # Skip actual delays in tests
    def test_success_on_first_attempt(self, mock_sleep):
        """Successful invocation on first try returns the ARN."""
        mock_runtime = MagicMock()
        mock_runtime.invoke_data_automation_async.return_value = {
            "invocationArn": "arn:aws:bedrock:us-east-1:123:invocation/test-123"
        }

        result = _invoke_bda_with_retry(
            runtime=mock_runtime,
            s3_input_uri="s3://bucket/key",
            s3_output_uri="s3://bucket/output",
        )

        assert result == "arn:aws:bedrock:us-east-1:123:invocation/test-123"
        assert mock_runtime.invoke_data_automation_async.call_count == 1
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    def test_retries_on_throttling_then_succeeds(self, mock_sleep):
        """Throttling on first attempt, success on retry."""
        mock_runtime = MagicMock()
        mock_runtime.invoke_data_automation_async.side_effect = [
            _client_error("ThrottlingException", "Rate exceeded"),
            {"invocationArn": "arn:aws:bedrock:us-east-1:123:invocation/retry-ok"},
        ]

        result = _invoke_bda_with_retry(
            runtime=mock_runtime,
            s3_input_uri="s3://bucket/key",
            s3_output_uri="s3://bucket/output",
        )

        assert result == "arn:aws:bedrock:us-east-1:123:invocation/retry-ok"
        assert mock_runtime.invoke_data_automation_async.call_count == 2
        mock_sleep.assert_called_once_with(1.0)  # First retry delay

    @patch("time.sleep")
    def test_retries_twice_then_succeeds(self, mock_sleep):
        """Two transient failures, then success on third attempt."""
        mock_runtime = MagicMock()
        mock_runtime.invoke_data_automation_async.side_effect = [
            _client_error("ServiceUnavailableException"),
            _client_error("InternalServerException"),
            {"invocationArn": "arn:third-try"},
        ]

        result = _invoke_bda_with_retry(
            runtime=mock_runtime,
            s3_input_uri="s3://b/k",
            s3_output_uri="s3://b/o",
        )

        assert result == "arn:third-try"
        assert mock_runtime.invoke_data_automation_async.call_count == 3
        # Backoff: 1s then 2s
        assert mock_sleep.call_args_list == [call(1.0), call(2.0)]

    @patch("time.sleep")
    def test_exhausts_retries_raises_extraction_error(self, mock_sleep):
        """All retries exhausted → ExtractionError with retryable=True."""
        mock_runtime = MagicMock()
        mock_runtime.invoke_data_automation_async.side_effect = _client_error(
            "ThrottlingException", "Persistent throttle"
        )

        with pytest.raises(ExtractionError) as exc_info:
            _invoke_bda_with_retry(
                runtime=mock_runtime,
                s3_input_uri="s3://b/k",
                s3_output_uri="s3://b/o",
            )

        assert exc_info.value.retryable is True
        assert "Persistent throttle" in str(exc_info.value)
        # 1 initial + 2 retries = 3 total attempts
        assert mock_runtime.invoke_data_automation_async.call_count == 3

    @patch("time.sleep")
    def test_non_retryable_error_fails_immediately(self, mock_sleep):
        """Non-retryable errors (e.g., ValidationException) fail on first attempt."""
        mock_runtime = MagicMock()
        mock_runtime.invoke_data_automation_async.side_effect = _client_error(
            "ValidationException", "Invalid input configuration"
        )

        with pytest.raises(ExtractionError) as exc_info:
            _invoke_bda_with_retry(
                runtime=mock_runtime,
                s3_input_uri="s3://b/k",
                s3_output_uri="s3://b/o",
            )

        assert exc_info.value.retryable is False
        assert mock_runtime.invoke_data_automation_async.call_count == 1
        mock_sleep.assert_not_called()


# ── BDA polling ───────────────────────────────────────────────────────────────


class TestPollBda:
    """Tests for _poll_bda status polling."""

    @patch("time.sleep")
    def test_success_on_first_poll(self, mock_sleep):
        """BDA reports SUCCESS on first poll → returns normally."""
        mock_runtime = MagicMock()
        mock_runtime.get_data_automation_status.return_value = {"status": "SUCCESS"}

        # Should not raise
        _poll_bda(mock_runtime, "arn:test")
        assert mock_runtime.get_data_automation_status.call_count == 1

    @patch("time.sleep")
    def test_in_progress_then_success(self, mock_sleep):
        """Multiple IN_PROGRESS polls followed by SUCCESS."""
        mock_runtime = MagicMock()
        mock_runtime.get_data_automation_status.side_effect = [
            {"status": "IN_PROGRESS"},
            {"status": "IN_PROGRESS"},
            {"status": "SUCCESS"},
        ]

        _poll_bda(mock_runtime, "arn:test")
        assert mock_runtime.get_data_automation_status.call_count == 3

    @patch("time.sleep")
    def test_failed_status_raises_extraction_error(self, mock_sleep):
        """BDA FAILED status → ExtractionError with the failure reason."""
        mock_runtime = MagicMock()
        mock_runtime.get_data_automation_status.return_value = {
            "status": "FAILED",
            "failureReason": "Document is corrupted",
        }

        with pytest.raises(ExtractionError) as exc_info:
            _poll_bda(mock_runtime, "arn:test")

        assert "Document is corrupted" in str(exc_info.value)
        assert exc_info.value.retryable is False

    @patch("time.sleep")
    def test_service_error_is_retryable(self, mock_sleep):
        """BDA SERVICE_ERROR status → ExtractionError with retryable=True."""
        mock_runtime = MagicMock()
        mock_runtime.get_data_automation_status.return_value = {
            "status": "SERVICE_ERROR",
            "failureReason": "Internal service issue",
        }

        with pytest.raises(ExtractionError) as exc_info:
            _poll_bda(mock_runtime, "arn:test")

        assert exc_info.value.retryable is True

    @patch("app.services.extraction._BDA_MAX_POLLS", 3)
    @patch("time.sleep")
    def test_timeout_raises_extraction_error(self, mock_sleep):
        """Exceeding max polls → timeout ExtractionError."""
        mock_runtime = MagicMock()
        mock_runtime.get_data_automation_status.return_value = {"status": "IN_PROGRESS"}

        with pytest.raises(ExtractionError) as exc_info:
            _poll_bda(mock_runtime, "arn:test")

        assert "timed out" in str(exc_info.value)
        assert exc_info.value.retryable is True

    @patch("time.sleep")
    def test_transient_poll_error_is_tolerated(self, mock_sleep):
        """Transient ClientError during polling is tolerated, polling continues."""
        mock_runtime = MagicMock()
        mock_runtime.get_data_automation_status.side_effect = [
            _client_error("ThrottlingException"),
            {"status": "SUCCESS"},
        ]

        # Should not raise
        _poll_bda(mock_runtime, "arn:test")
        assert mock_runtime.get_data_automation_status.call_count == 2

    @patch("time.sleep")
    def test_non_transient_poll_error_raises(self, mock_sleep):
        """Non-transient ClientError during polling raises immediately."""
        mock_runtime = MagicMock()
        mock_runtime.get_data_automation_status.side_effect = _client_error(
            "AccessDeniedException", "No permission"
        )

        with pytest.raises(ExtractionError) as exc_info:
            _poll_bda(mock_runtime, "arn:test")

        assert "No permission" in str(exc_info.value)
        assert exc_info.value.retryable is False


# ── BDA output reading with retry ─────────────────────────────────────────────


class TestReadBdaOutputWithRetry:
    """Tests for _read_bda_output_with_retry."""

    @patch("time.sleep")
    @patch("boto3.client")
    def test_success_on_first_read(self, mock_boto_client, mock_sleep):
        """S3 read succeeds on first try."""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps({"blocks": []}).encode())
        }

        result = _read_bda_output_with_retry("test-bucket", "invoices/id/file.pdf")
        assert result == {"blocks": []}
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    @patch("boto3.client")
    def test_retries_on_transient_error(self, mock_boto_client, mock_sleep):
        """Transient S3 error on first read, success on retry."""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.get_object.side_effect = [
            _client_error("ServiceUnavailableException"),
            {"Body": MagicMock(read=lambda: json.dumps({"blocks": []}).encode())},
        ]

        result = _read_bda_output_with_retry("bucket", "invoices/id/f.pdf")
        assert result == {"blocks": []}
        mock_sleep.assert_called_once_with(1.0)

    @patch("time.sleep")
    @patch("boto3.client")
    def test_no_such_key_fails_immediately(self, mock_boto_client, mock_sleep):
        """NoSuchKey error fails immediately without retry."""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.get_object.side_effect = _client_error("NoSuchKey", "Key not found")

        with pytest.raises(ExtractionError) as exc_info:
            _read_bda_output_with_retry("bucket", "invoices/id/f.pdf")

        assert exc_info.value.retryable is False
        assert "not found" in str(exc_info.value)
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    @patch("boto3.client")
    def test_invalid_json_fails_immediately(self, mock_boto_client, mock_sleep):
        """Invalid JSON content fails without retry."""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.get_object.return_value = {
            "Body": MagicMock(read=lambda: b"not valid json {{{")
        }

        with pytest.raises(ExtractionError) as exc_info:
            _read_bda_output_with_retry("bucket", "invoices/id/f.pdf")

        assert "not valid JSON" in str(exc_info.value)
        assert exc_info.value.retryable is False


# ── BDA response parsing ──────────────────────────────────────────────────────


class TestParseBdaResponse:
    """Tests for _parse_bda_response normalization."""

    def test_extracts_key_value_fields(self):
        """KEY_VALUE_SET blocks are mapped to canonical field names."""
        raw = _make_bda_blocks(
            fields={
                "Vendor Name": "Acme Corp",
                "Invoice Number": "INV-001",
                "Total Amount": "$1,234.56",
            }
        )
        result = _parse_bda_response(raw)

        assert result["vendorName"] == "Acme Corp"
        assert result["invoiceNumber"] == "INV-001"
        assert result["totalAmount"] == 1234.56

    def test_extracts_table_as_line_items(self):
        """TABLE blocks are parsed into lineItems list."""
        raw = _make_bda_blocks(
            fields={"Vendor Name": "Test"},
            table_rows=[
                ["Widget A", "10", "$5.00", "$50.00"],
                ["Widget B", "3", "$20.00", "$60.00"],
            ],
        )
        result = _parse_bda_response(raw)

        assert len(result["lineItems"]) == 2
        assert result["lineItems"][0]["description"] == "Widget A"
        assert result["lineItems"][0]["quantity"] == 10.0
        assert result["lineItems"][0]["unitPrice"] == 5.0
        assert result["lineItems"][0]["amount"] == 50.0

    def test_computes_overall_confidence(self):
        """Overall confidence is the mean of all per-field confidences."""
        raw = _make_bda_blocks(
            fields={"Vendor Name": "A", "Invoice Number": "B"},
            confidence=0.90,
        )
        result = _parse_bda_response(raw)

        assert result["overallConfidence"] == 0.9

    def test_empty_blocks_returns_empty_extraction(self):
        """No blocks → empty extraction with zero confidence."""
        raw = {"blocks": []}
        result = _parse_bda_response(raw)

        assert result["lineItems"] == []
        assert result["confidence"] == {}
        assert result["overallConfidence"] == 0.0

    def test_unknown_fields_are_ignored(self):
        """BDA fields not in _FIELD_MAP are silently ignored."""
        raw = _make_bda_blocks(fields={"Unknown Field": "value", "Vendor Name": "X"})
        result = _parse_bda_response(raw)

        assert "unknownField" not in result
        assert result["vendorName"] == "X"

    def test_missing_blocks_key(self):
        """Raw output without 'blocks' key produces empty extraction."""
        raw = {"otherData": "something"}
        result = _parse_bda_response(raw)

        assert result["lineItems"] == []
        assert result["overallConfidence"] == 0.0

    def test_numeric_fields_are_coerced_to_float(self):
        """Fields like totalAmount, subtotal, taxAmount become floats."""
        raw = _make_bda_blocks(
            fields={
                "Total Amount": "2,500.99",
                "Subtotal": "$2,300.00",
                "Tax Amount": "200.99",
            }
        )
        result = _parse_bda_response(raw)

        assert result["totalAmount"] == 2500.99
        assert result["subtotal"] == 2300.00
        assert result["taxAmount"] == 200.99

    def test_confidence_per_field(self):
        """Per-field confidence is stored in the confidence dict."""
        raw = _make_bda_blocks(
            fields={"Vendor Name": "V", "Invoice Number": "I"},
            confidence=0.88,
        )
        result = _parse_bda_response(raw)

        assert result["confidence"]["vendorName"] == 0.88
        assert result["confidence"]["invoiceNumber"] == 0.88


# ── Table block parsing ───────────────────────────────────────────────────────


class TestParseTableBlock:
    """Tests for _parse_table_block."""

    def test_skips_header_row(self):
        """First row is treated as header and skipped."""
        block = {
            "rows": [
                {"cells": [{"text": "H1"}, {"text": "H2"}, {"text": "H3"}, {"text": "H4"}]},
                {"cells": [{"text": "Item"}, {"text": "2"}, {"text": "10.00"}, {"text": "20.00"}]},
            ]
        }
        items = _parse_table_block(block)
        assert len(items) == 1
        assert items[0]["description"] == "Item"

    def test_skips_rows_with_fewer_than_4_cells(self):
        """Rows with <4 cells are skipped."""
        block = {
            "rows": [
                {"cells": [{"text": "H1"}, {"text": "H2"}, {"text": "H3"}, {"text": "H4"}]},
                {"cells": [{"text": "Only two"}, {"text": "cells"}]},
                {"cells": [{"text": "Good"}, {"text": "1"}, {"text": "5"}, {"text": "5"}]},
            ]
        }
        items = _parse_table_block(block)
        assert len(items) == 1
        assert items[0]["description"] == "Good"

    def test_empty_rows_list(self):
        """No rows → empty list."""
        block = {"rows": []}
        assert _parse_table_block(block) == []

    def test_only_header_row(self):
        """Only header row → empty list."""
        block = {
            "rows": [
                {"cells": [{"text": "A"}, {"text": "B"}, {"text": "C"}, {"text": "D"}]}
            ]
        }
        assert _parse_table_block(block) == []


# ── Field coercion ────────────────────────────────────────────────────────────


class TestCoerceField:
    """Tests for _coerce_field."""

    def test_numeric_field_coerced_to_float(self):
        assert _coerce_field("totalAmount", "$1,500.75") == 1500.75

    def test_string_field_stripped(self):
        assert _coerce_field("vendorName", "  Acme Corp  ") == "Acme Corp"

    def test_empty_numeric_returns_zero(self):
        assert _coerce_field("subtotal", "") == 0.0


class TestSafeFloat:
    """Tests for _safe_float."""

    def test_plain_number(self):
        assert _safe_float("123.45") == 123.45

    def test_with_dollar_sign(self):
        assert _safe_float("$1,234.56") == 1234.56

    def test_with_commas(self):
        assert _safe_float("1,000,000.00") == 1000000.0

    def test_empty_string_returns_zero(self):
        assert _safe_float("") == 0.0

    def test_non_numeric_returns_zero(self):
        assert _safe_float("not a number") == 0.0

    def test_whitespace_only_returns_zero(self):
        assert _safe_float("   ") == 0.0


# ── Validation ────────────────────────────────────────────────────────────────


class TestValidateBdaOutput:
    """Tests for _validate_bda_output."""

    def test_valid_output_passes(self):
        """Well-formed BDA output does not raise."""
        _validate_bda_output({"blocks": []})

    def test_missing_blocks_logs_warning_but_does_not_raise(self):
        """Missing 'blocks' key logs a warning but does not raise."""
        # Should not raise
        _validate_bda_output({"otherKey": "data"})

    def test_non_dict_raises(self):
        """Non-dict BDA output raises ExtractionError."""
        with pytest.raises(ExtractionError) as exc_info:
            _validate_bda_output([1, 2, 3])  # type: ignore

        assert "not a JSON object" in str(exc_info.value)
        assert exc_info.value.retryable is False


class TestValidateExtractionResult:
    """Tests for _validate_extraction_result (logs warnings, no exceptions)."""

    def test_complete_extraction_passes_silently(self):
        """Full extraction with all critical fields does not raise."""
        extraction = {
            "vendorName": "Test",
            "invoiceNumber": "INV-1",
            "totalAmount": 100.0,
            "overallConfidence": 0.95,
        }
        # Should not raise
        _validate_extraction_result(extraction)

    def test_missing_critical_fields_does_not_raise(self):
        """Missing fields log a warning but do not raise."""
        extraction = {
            "overallConfidence": 0.90,
            "lineItems": [],
            "confidence": {},
        }
        # Should not raise — only logs
        _validate_extraction_result(extraction)

    def test_low_confidence_does_not_raise(self):
        """Low confidence logs a warning but does not raise."""
        extraction = {
            "vendorName": "X",
            "invoiceNumber": "Y",
            "totalAmount": 10.0,
            "overallConfidence": 0.3,
        }
        # Should not raise — only logs
        _validate_extraction_result(extraction)


# ── ExtractionError ───────────────────────────────────────────────────────────


class TestExtractionError:
    """Tests for ExtractionError exception class."""

    def test_default_not_retryable(self):
        err = ExtractionError("something broke")
        assert err.retryable is False
        assert "something broke" in str(err)

    def test_retryable_flag(self):
        err = ExtractionError("throttled", retryable=True)
        assert err.retryable is True

    def test_can_be_raised_and_caught(self):
        with pytest.raises(ExtractionError):
            raise ExtractionError("test")


# ── Integration: extract_invoice with BDA (mocked AWS) ───────────────────────


class TestExtractInvoiceFullFlow:
    """End-to-end test of extract_invoice with mocked AWS clients."""

    @patch("app.services.extraction.settings")
    @patch("time.sleep")
    @patch("boto3.client")
    def test_full_bda_flow_success(self, mock_boto_client, mock_sleep, mock_settings):
        """Full BDA flow: invoke → poll → read → parse → return extraction."""
        mock_settings.USE_MOCKS = False
        mock_settings.AWS_REGION = "us-east-1"
        mock_settings.BDA_PROJECT_ARN = "arn:aws:bedrock:us-east-1:123:data-automation-project/test"

        # Set up mock clients
        mock_bda_runtime = MagicMock()
        mock_s3 = MagicMock()

        def client_factory(service, **kwargs):
            if "bedrock-data-automation-runtime" in service:
                return mock_bda_runtime
            if service == "s3":
                return mock_s3
            return MagicMock()

        mock_boto_client.side_effect = client_factory

        # BDA invoke response
        mock_bda_runtime.invoke_data_automation_async.return_value = {
            "invocationArn": "arn:invocation/test"
        }

        # BDA poll responses
        mock_bda_runtime.get_data_automation_status.side_effect = [
            {"status": "IN_PROGRESS"},
            {"status": "SUCCESS"},
        ]

        # S3 output read
        bda_output = _make_bda_blocks(
            fields={
                "Vendor Name": "Integration Test Vendor",
                "Invoice Number": "INT-001",
                "Total Amount": "$500.00",
            },
            table_rows=[["Service A", "1", "500.00", "500.00"]],
        )
        mock_s3.get_object.return_value = {
            "Body": MagicMock(read=lambda: json.dumps(bda_output).encode())
        }

        result = extract_invoice(bucket="test-bucket", s3_key="invoices/id-1/inv.pdf")

        assert result["vendorName"] == "Integration Test Vendor"
        assert result["invoiceNumber"] == "INT-001"
        assert result["totalAmount"] == 500.0
        assert len(result["lineItems"]) == 1
        assert result["overallConfidence"] > 0

    @patch("app.services.extraction.settings")
    @patch("time.sleep")
    @patch("boto3.client")
    def test_full_bda_flow_invocation_failure(self, mock_boto_client, mock_sleep, mock_settings):
        """BDA invocation failure raises ExtractionError."""
        mock_settings.USE_MOCKS = False
        mock_settings.AWS_REGION = "us-east-1"
        mock_settings.BDA_PROJECT_ARN = "arn:test"

        mock_bda_runtime = MagicMock()
        mock_boto_client.return_value = mock_bda_runtime

        mock_bda_runtime.invoke_data_automation_async.side_effect = _client_error(
            "ValidationException", "Invalid project ARN"
        )

        with pytest.raises(ExtractionError) as exc_info:
            extract_invoice(bucket="b", s3_key="invoices/id/f.pdf")

        assert "Invalid project ARN" in str(exc_info.value)
