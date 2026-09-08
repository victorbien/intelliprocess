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
from typing import Any

import pytest
from unittest.mock import patch, MagicMock

from botocore.exceptions import ClientError

from app.services.extraction import (
    ExtractionError,
    extract_invoice,
    _parse_bda_response,
    _coerce_field,
    _safe_float,
    _validate_extraction_result,
    _poll_bda,
)


# ── Fixtures & helpers ────────────────────────────────────────────────────────


def _client_error(code: str, message: str = "Error") -> ClientError:
    """Build a botocore ClientError with the given error code."""
    return ClientError(
        {"Error": {"Code": code, "Message": message}},
        "TestOperation",
    )


def _make_bda_output(
    fields: dict[str, Any] | None = None,
    service_table: list[dict] | None = None,
    confidence: float | None = 0.95,
) -> dict:
    """Build a minimal BDA custom-output document.

    Mirrors the shape ``_parse_bda_response`` consumes: a top-level
    ``inference_result`` dict keyed by blueprint field names (VENDORNAME, ID,
    TOTAL, SERVICES_TABLE, ...) plus an optional ``explainability_info`` list
    carrying per-field ``confidence`` values.
    """
    inference: dict[str, Any] = dict(fields or {})
    if service_table is not None:
        inference["SERVICES_TABLE"] = service_table

    raw: dict[str, Any] = {"inference_result": inference}

    if confidence is not None and fields:
        raw["explainability_info"] = [
            {key: {"confidence": confidence} for key in fields}
        ]
    return raw


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


class TestPollBda:
    """Tests for _poll_bda status polling.

    Current BDA status vocabulary is InProgress / Success / ServiceError /
    ClientError. _poll_bda sleeps at the top of each iteration, returns the full
    status dict on Success, raises on ServiceError (retryable) / ClientError
    (non-retryable), and re-raises any boto3 ClientError from the status call.
    """

    @patch("time.sleep")
    def test_success_on_first_poll(self, mock_sleep):
        """BDA reports Success on first poll → returns the status dict."""
        mock_runtime = MagicMock()
        mock_runtime.get_data_automation_status.return_value = {"status": "Success"}

        result = _poll_bda(mock_runtime, "arn:test")
        assert result == {"status": "Success"}
        assert mock_runtime.get_data_automation_status.call_count == 1

    @patch("time.sleep")
    def test_in_progress_then_success(self, mock_sleep):
        """Multiple InProgress polls followed by Success."""
        mock_runtime = MagicMock()
        mock_runtime.get_data_automation_status.side_effect = [
            {"status": "InProgress"},
            {"status": "InProgress"},
            {"status": "Success"},
        ]

        _poll_bda(mock_runtime, "arn:test")
        assert mock_runtime.get_data_automation_status.call_count == 3

    @patch("time.sleep")
    def test_client_error_status_raises_non_retryable(self, mock_sleep):
        """BDA ClientError status → ExtractionError with retryable=False."""
        mock_runtime = MagicMock()
        mock_runtime.get_data_automation_status.return_value = {
            "status": "ClientError",
            "errorMessage": "Document is corrupted",
        }

        with pytest.raises(ExtractionError) as exc_info:
            _poll_bda(mock_runtime, "arn:test")

        assert "Document is corrupted" in str(exc_info.value)
        assert exc_info.value.retryable is False

    @patch("time.sleep")
    def test_service_error_is_retryable(self, mock_sleep):
        """BDA ServiceError status → ExtractionError with retryable=True."""
        mock_runtime = MagicMock()
        mock_runtime.get_data_automation_status.return_value = {
            "status": "ServiceError",
            "errorMessage": "Internal service issue",
        }

        with pytest.raises(ExtractionError) as exc_info:
            _poll_bda(mock_runtime, "arn:test")

        assert exc_info.value.retryable is True

    @patch("app.services.extraction._BDA_MAX_POLLS", 3)
    @patch("time.sleep")
    def test_timeout_raises_extraction_error(self, mock_sleep):
        """Exceeding max polls → timeout ExtractionError."""
        mock_runtime = MagicMock()
        mock_runtime.get_data_automation_status.return_value = {"status": "InProgress"}

        with pytest.raises(ExtractionError) as exc_info:
            _poll_bda(mock_runtime, "arn:test")

        assert "timed out" in str(exc_info.value)
        assert exc_info.value.retryable is True
        assert mock_runtime.get_data_automation_status.call_count == 3

    @patch("time.sleep")
    def test_client_error_exception_raises(self, mock_sleep):
        """A boto3 ClientError from the status call is wrapped and raised."""
        mock_runtime = MagicMock()
        mock_runtime.get_data_automation_status.side_effect = _client_error(
            "AccessDeniedException", "No permission"
        )

        with pytest.raises(ExtractionError) as exc_info:
            _poll_bda(mock_runtime, "arn:test")

        assert "No permission" in str(exc_info.value)


# ── BDA response parsing ──────────────────────────────────────────────────────


class TestParseBdaResponse:
    """Tests for _parse_bda_response normalization (inference_result format)."""

    def test_extracts_key_value_fields(self):
        """Blueprint fields are mapped to canonical field names."""
        raw = _make_bda_output(
            fields={
                "VENDORNAME": "Acme Corp",
                "ID": "INV-001",
                "TOTAL": "$1,234.56",
            }
        )
        result = _parse_bda_response(raw)

        assert result["vendorName"] == "Acme Corp"
        assert result["invoiceNumber"] == "INV-001"
        assert result["totalAmount"] == 1234.56

    def test_extracts_service_table_as_line_items(self):
        """SERVICES_TABLE rows are parsed into the lineItems list."""
        raw = _make_bda_output(
            fields={"VENDORNAME": "Test"},
            service_table=[
                {"product description": "Widget A", "quantity": "10",
                 "unit price": "$5.00", "amount": "$50.00"},
                {"product description": "Widget B", "quantity": "3",
                 "unit price": "$20.00", "amount": "$60.00"},
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
        raw = _make_bda_output(
            fields={"VENDORNAME": "A", "ID": "B"},
            confidence=0.90,
        )
        result = _parse_bda_response(raw)

        assert result["overallConfidence"] == 0.9

    def test_tax_array_is_summed(self):
        """A TAX list is summed into a single taxAmount."""
        raw = _make_bda_output(fields={"VENDORNAME": "A"}, confidence=None)
        raw["inference_result"]["TAX"] = ["10.00", "5.50"]
        result = _parse_bda_response(raw)

        assert result["taxAmount"] == 15.50

    def test_empty_inference_returns_empty_extraction(self):
        """No fields → empty extraction with zero confidence."""
        raw = {"inference_result": {}}
        result = _parse_bda_response(raw)

        assert result["lineItems"] == []
        assert result["confidence"] == {}
        assert result["overallConfidence"] == 0.0

    def test_expected_fields_always_present(self):
        """Downstream-expected fields are always present (None when absent)."""
        result = _parse_bda_response({"inference_result": {"VENDORNAME": "X"}})
        for key in ("vendorName", "invoiceNumber", "invoiceDate", "dueDate",
                    "poReference", "subtotal", "taxAmount", "totalAmount",
                    "paymentTerms"):
            assert key in result
        assert result["vendorName"] == "X"
        assert result["dueDate"] is None

    def test_unknown_fields_are_ignored(self):
        """Blueprint keys not in _BP_FIELD_MAP are silently ignored."""
        raw = _make_bda_output(fields={"UNKNOWNFIELD": "value", "VENDORNAME": "X"})
        result = _parse_bda_response(raw)

        assert "unknownField" not in result
        assert "UNKNOWNFIELD" not in result
        assert result["vendorName"] == "X"

    def test_missing_inference_result_key(self):
        """Raw output is treated as the inference dict when the key is absent."""
        raw = {"VENDORNAME": "Direct"}
        result = _parse_bda_response(raw)

        assert result["vendorName"] == "Direct"
        assert result["lineItems"] == []

    def test_numeric_fields_are_coerced_to_float(self):
        """Fields like totalAmount, subtotal, taxAmount become floats."""
        raw = _make_bda_output(
            fields={"TOTAL": "2,500.99", "SUBTOTAL": "$2,300.00"},
            confidence=None,
        )
        raw["inference_result"]["TAX"] = "200.99"
        result = _parse_bda_response(raw)

        assert result["totalAmount"] == 2500.99
        assert result["subtotal"] == 2300.00
        assert result["taxAmount"] == 200.99

    def test_confidence_per_field(self):
        """Per-field confidence is stored in the confidence dict."""
        raw = _make_bda_output(
            fields={"VENDORNAME": "V", "ID": "I"},
            confidence=0.88,
        )
        result = _parse_bda_response(raw)

        assert result["confidence"]["vendorName"] == 0.88
        assert result["confidence"]["invoiceNumber"] == 0.88


# ── SERVICES_TABLE line-item parsing ──────────────────────────────────────────


class TestParseTableBlock:
    """Tests for SERVICES_TABLE line-item parsing (via _parse_bda_response).

    The old block-of-cells table parser (_parse_table_block) was removed; line
    items now come from the blueprint's ``SERVICES_TABLE`` — a list of dicts
    keyed by blueprint field names — mapped through ``_BP_LINE_ITEM_MAP``.
    """

    def test_parses_service_table_rows(self):
        """Each SERVICES_TABLE row becomes a lineItems entry with mapped keys."""
        raw = {
            "inference_result": {
                "SERVICES_TABLE": [
                    {"product description": "Item", "quantity": "2",
                     "unit price": "10.00", "amount": "20.00"},
                ]
            }
        }
        result = _parse_bda_response(raw)
        assert len(result["lineItems"]) == 1
        item = result["lineItems"][0]
        assert item["description"] == "Item"
        assert item["quantity"] == 2.0
        assert item["unitPrice"] == 10.0
        assert item["amount"] == 20.0

    def test_multiple_rows_all_parsed(self):
        """Multiple rows are all captured in order."""
        raw = {
            "inference_result": {
                "SERVICES_TABLE": [
                    {"product description": "First", "quantity": "1",
                     "unit price": "5", "amount": "5"},
                    {"product description": "Second", "quantity": "3",
                     "unit price": "4", "amount": "12"},
                ]
            }
        }
        result = _parse_bda_response(raw)
        descriptions = [i["description"] for i in result["lineItems"]]
        assert descriptions == ["First", "Second"]

    def test_non_dict_rows_are_skipped(self):
        """Malformed (non-dict) rows are ignored rather than crashing."""
        raw = {
            "inference_result": {
                "SERVICES_TABLE": [
                    "not a dict",
                    {"product description": "Good", "quantity": "1",
                     "unit price": "5", "amount": "5"},
                ]
            }
        }
        result = _parse_bda_response(raw)
        assert len(result["lineItems"]) == 1
        assert result["lineItems"][0]["description"] == "Good"

    def test_missing_service_table_yields_empty_list(self):
        """No SERVICES_TABLE → empty lineItems list (not an error)."""
        raw = {"inference_result": {}}
        result = _parse_bda_response(raw)
        assert result["lineItems"] == []


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

        # STS (for _bda_profile_arn) resolves the account id.
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}

        def client_factory2(service, **kwargs):
            if "bedrock-data-automation-runtime" in service:
                return mock_bda_runtime
            if service == "s3":
                return mock_s3
            if service == "sts":
                return mock_sts
            return MagicMock()

        mock_boto_client.side_effect = client_factory2

        # BDA poll responses: the terminal Success carries the metadata S3 URI.
        meta_uri = "s3://test-bucket/bda-output/invoices/id-1/inv.pdf/job_metadata.json"
        mock_bda_runtime.get_data_automation_status.side_effect = [
            {"status": "InProgress"},
            {"status": "Success", "outputConfiguration": {"s3Uri": meta_uri}},
        ]

        # _read_bda_custom_output follows job_metadata.json → custom_output_path,
        # so S3 is read twice: first the metadata, then the inference result.
        custom_path = "s3://test-bucket/bda-output/invoices/id-1/inv.pdf/0/custom_output.json"
        meta_doc = {
            "output_metadata": [
                {"segment_metadata": [{"custom_output_path": custom_path}]}
            ]
        }
        inference_doc = _make_bda_output(
            fields={
                "VENDORNAME": "Integration Test Vendor",
                "ID": "INT-001",
                "TOTAL": "$500.00",
            },
            service_table=[
                {"product description": "Service A", "quantity": "1",
                 "unit price": "500.00", "amount": "500.00"},
            ],
        )

        def get_object(Bucket, Key, **kwargs):
            body = meta_doc if Key.endswith("job_metadata.json") else inference_doc
            return {"Body": MagicMock(read=lambda: json.dumps(body).encode())}

        mock_s3.get_object.side_effect = get_object

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
