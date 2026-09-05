"""Unit tests for the invoice processor service (FR-AP-001 through FR-AP-007).

Tests the full pipeline behaviour using mocked service calls so no real
DynamoDB/S3/BDA access is needed.
"""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

from app.models.enums import InvoiceStatus


# ── Fixtures ──────────────────────────────────────────────────────────────────

_GOOD_EXTRACTION = {
    "vendorName":       "Acme Office Supplies Inc.",
    "invoiceNumber":    "INV-TEST-001",
    "invoiceDate":      "2026-07-20",
    "dueDate":          "2026-08-20",
    "poReference":      "PO-2024-0456",
    "totalAmount":      658.80,
    "subtotal":         610.00,
    "taxAmount":        48.80,
    "paymentTerms":     "Net 30",
    "lineItems": [
        {"description": "Paper", "quantity": 10.0, "unitPrice": 45.0, "amount": 450.0},
        {"description": "Ink",   "quantity": 5.0,  "unitPrice": 32.0, "amount": 160.0},
    ],
    "confidence": {
        "vendorName": 0.97, "invoiceNumber": 0.99, "totalAmount": 0.98,
    },
    "overallConfidence": 0.97,
}

_GOOD_PO_RESULT = {
    "status": "MATCHED", "poId": "PO-2024-0456",
    "amountVariancePct": 0.0, "discrepancies": [],
}

_GOOD_GR_RESULT = {
    "status": "CONFIRMED", "grId": "GR-2024-0789",
    "quantityReceived": 15.0, "quantityInvoiced": 15.0, "discrepancies": [],
}

_GOOD_MATCH = {
    "status": "PASS",
    "poMatch": _GOOD_PO_RESULT,
    "grMatch": _GOOD_GR_RESULT,
    "discrepancies": [],
}

_APPROVE_DECISION = {
    "decision": "APPROVE", "reason": "All rules passed.",
    "escalateTo": None,
    "rulesResults": [
        {"ruleId": "RULE-001", "name": "Three-Way Match", "passed": True, "detail": ""},
        {"ruleId": "RULE-002", "name": "Amount Threshold", "passed": True, "detail": ""},
        {"ruleId": "RULE-003", "name": "Confidence Threshold", "passed": True, "detail": ""},
    ],
}

_ESCALATE_DECISION = {
    "decision": "ESCALATE",
    "reason": "Amount $15000.00 exceeds threshold.",
    "escalateTo": "FINANCE_MANAGER",
    "rulesResults": [
        {"ruleId": "RULE-001", "name": "Three-Way Match", "passed": True, "detail": ""},
        {"ruleId": "RULE-002", "name": "Amount Threshold", "passed": False, "detail": ""},
        {"ruleId": "RULE-003", "name": "Confidence Threshold", "passed": True, "detail": ""},
    ],
}

VALID_DOC_ID = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
# Staged incoming key (current upload layout: invoices/incoming/<id>/<file>).
VALID_S3_KEY = f"invoices/incoming/{VALID_DOC_ID}/test.pdf"
PROCESSED_S3_KEY = f"invoices/processed/{VALID_DOC_ID}/test.pdf"
FAILED_S3_KEY = f"invoices/failed/{VALID_DOC_ID}/test.pdf"


def _make_invoice_item(status: str = "UPLOADED") -> dict:
    return {
        "documentId": VALID_DOC_ID,
        "fileName": "test.pdf",
        "status": status,
        "uploadedBy": "user-001",
        "uploadedAt": "2026-07-25T10:00:00Z",
    }


# ── _extract_document_id helper tests ─────────────────────────────────────────

class TestExtractDocumentId:
    def test_extracts_from_staged_key(self):
        """Current layout: invoices/<stage>/<id>/<file> → id is 3rd segment."""
        from app.services.processor import _extract_document_id
        assert _extract_document_id("invoices/incoming/abc-123/file.pdf") == "abc-123"
        assert _extract_document_id("invoices/processed/abc-123/file.pdf") == "abc-123"
        assert _extract_document_id("invoices/failed/abc-123/file.pdf") == "abc-123"

    def test_extracts_from_legacy_key(self):
        """Legacy layout: invoices/<id>/<file> → id is 2nd segment."""
        from app.services.processor import _extract_document_id
        assert _extract_document_id("invoices/abc-123/file.pdf") == "abc-123"

    def test_returns_none_for_short_key(self):
        from app.services.processor import _extract_document_id
        assert _extract_document_id("invoices") is None
        assert _extract_document_id("") is None

    def test_strips_leading_slash(self):
        from app.services.processor import _extract_document_id
        assert _extract_document_id("/invoices/incoming/abc-123/file.pdf") == "abc-123"


# ── _to_dynamo helper tests ────────────────────────────────────────────────────

class TestToDynamo:
    def test_float_becomes_decimal(self):
        from app.services.processor import _to_dynamo
        result = _to_dynamo(658.80)
        assert isinstance(result, Decimal)

    def test_nested_dict_floats_converted(self):
        from app.services.processor import _to_dynamo
        result = _to_dynamo({"amount": 100.5, "qty": 2})
        assert isinstance(result["amount"], Decimal)

    def test_list_floats_converted(self):
        from app.services.processor import _to_dynamo
        result = _to_dynamo([1.5, 2.5])
        assert all(isinstance(v, Decimal) for v in result)

    def test_strings_unchanged(self):
        from app.services.processor import _to_dynamo
        assert _to_dynamo("hello") == "hello"

    def test_none_unchanged(self):
        from app.services.processor import _to_dynamo
        assert _to_dynamo(None) is None

    def test_int_unchanged(self):
        from app.services.processor import _to_dynamo
        # Integers are not floats — should pass through unchanged
        result = _to_dynamo(5)
        assert result == 5
        assert not isinstance(result, Decimal)


# ── process_invoice: skipping logic ───────────────────────────────────────────

class TestProcessInvoiceSkipping:
    """Tests for idempotency and skip conditions."""

    @patch("app.services.processor._invoice_db")
    def test_skips_when_metadata_not_found(self, mock_db):
        """Missing metadata record → skip without error."""
        mock_db.get_item.return_value = None
        from app.services.processor import process_invoice
        # Should not raise
        process_invoice(bucket="test-bucket", s3_key=VALID_S3_KEY)
        # update_status should never be called
        mock_db.update_status.assert_not_called()

    @patch("app.services.processor._invoice_db")
    def test_skips_when_already_processed(self, mock_db):
        """Invoice not in UPLOADED status → skip (idempotency)."""
        mock_db.get_item.return_value = _make_invoice_item(status="APPROVED")
        from app.services.processor import process_invoice
        process_invoice(bucket="test-bucket", s3_key=VALID_S3_KEY)
        mock_db.update_status.assert_not_called()

    @patch("app.services.processor._invoice_db")
    def test_skips_when_invalid_s3_key(self, mock_db):
        """Unparseable S3 key → log and skip without touching DynamoDB."""
        from app.services.processor import process_invoice
        process_invoice(bucket="test-bucket", s3_key="bad-key")
        mock_db.get_item.assert_not_called()


# ── process_invoice: happy path ───────────────────────────────────────────────

class TestProcessInvoiceHappyPath:
    """Full pipeline for an invoice that should be auto-approved."""

    @patch("app.services.processor.evaluate_approval_rules", return_value=_APPROVE_DECISION)
    @patch("app.services.processor.three_way_match", return_value=_GOOD_MATCH)
    @patch("app.services.processor.match_goods_receipt", return_value=_GOOD_GR_RESULT)
    @patch("app.services.processor.match_purchase_order", return_value=_GOOD_PO_RESULT)
    @patch("app.services.processor.extract_invoice", return_value=_GOOD_EXTRACTION)
    @patch("app.services.processor._invoice_db")
    def test_full_pipeline_auto_approve(
        self, mock_db, mock_extract, mock_po, mock_gr, mock_3way, mock_rules
    ):
        """AC-3.6.1: invoice passes all rules → status becomes APPROVED."""
        mock_db.get_item.return_value = _make_invoice_item("UPLOADED")
        mock_db.update_status = MagicMock()

        from app.services.processor import process_invoice
        process_invoice(bucket="test-bucket", s3_key=VALID_S3_KEY)

        # Verify each pipeline stage was called
        mock_extract.assert_called_once_with(bucket="test-bucket", s3_key=VALID_S3_KEY)
        mock_po.assert_called_once()
        mock_gr.assert_called_once()
        mock_3way.assert_called_once()
        mock_rules.assert_called_once()

        # Verify status transitions: PROCESSING → EXTRACTED → APPROVED
        calls = mock_db.update_status.call_args_list
        statuses = [c.kwargs.get("new_status") or c.args[1] for c in calls]
        assert InvoiceStatus.PROCESSING in statuses
        assert InvoiceStatus.EXTRACTED  in statuses
        assert InvoiceStatus.APPROVED   in statuses

    @patch("app.services.processor.evaluate_approval_rules", return_value=_APPROVE_DECISION)
    @patch("app.services.processor.three_way_match", return_value=_GOOD_MATCH)
    @patch("app.services.processor.match_goods_receipt", return_value=_GOOD_GR_RESULT)
    @patch("app.services.processor.match_purchase_order", return_value=_GOOD_PO_RESULT)
    @patch("app.services.processor.extract_invoice", return_value=_GOOD_EXTRACTION)
    @patch("app.services.processor._invoice_db")
    def test_approved_status_includes_approver_system(
        self, mock_db, mock_extract, mock_po, mock_gr, mock_3way, mock_rules
    ):
        """AC-3.6.1: auto-approved invoices have approver='SYSTEM'."""
        mock_db.get_item.return_value = _make_invoice_item("UPLOADED")
        mock_db.update_status = MagicMock()

        from app.services.processor import process_invoice
        process_invoice(bucket="test-bucket", s3_key=VALID_S3_KEY)

        # Find the APPROVED call and check approvalDecision
        approved_call = next(
            c for c in mock_db.update_status.call_args_list
            if (c.kwargs.get("new_status") or c.args[1]) == InvoiceStatus.APPROVED
        )
        approval = approved_call.kwargs.get("approvalDecision", {})
        assert approval.get("approver") == "SYSTEM"

    @patch("app.services.processor.evaluate_approval_rules", return_value=_APPROVE_DECISION)
    @patch("app.services.processor.three_way_match", return_value=_GOOD_MATCH)
    @patch("app.services.processor.match_goods_receipt", return_value=_GOOD_GR_RESULT)
    @patch("app.services.processor.match_purchase_order", return_value=_GOOD_PO_RESULT)
    @patch("app.services.processor.extract_invoice", return_value=_GOOD_EXTRACTION)
    @patch("app.services.processor._invoice_db")
    def test_processing_duration_is_recorded(
        self, mock_db, mock_extract, mock_po, mock_gr, mock_3way, mock_rules
    ):
        """FR-AP-009: processingDurationMs must be set on completion."""
        mock_db.get_item.return_value = _make_invoice_item("UPLOADED")
        mock_db.update_status = MagicMock()

        from app.services.processor import process_invoice
        process_invoice(bucket="test-bucket", s3_key=VALID_S3_KEY)

        approved_call = next(
            c for c in mock_db.update_status.call_args_list
            if (c.kwargs.get("new_status") or c.args[1]) == InvoiceStatus.APPROVED
        )
        assert "processingDurationMs" in approved_call.kwargs

    @patch("app.services.processor.evaluate_approval_rules", return_value=_APPROVE_DECISION)
    @patch("app.services.processor.three_way_match", return_value=_GOOD_MATCH)
    @patch("app.services.processor.match_goods_receipt", return_value=_GOOD_GR_RESULT)
    @patch("app.services.processor.match_purchase_order", return_value=_GOOD_PO_RESULT)
    @patch("app.services.processor.extract_invoice", return_value=_GOOD_EXTRACTION)
    @patch("app.services.processor._invoice_db")
    def test_gr_lookup_uses_matched_po_id(
        self, mock_db, mock_extract, mock_po, mock_gr, mock_3way, mock_rules
    ):
        """GR lookup should use the matched PO ID, not the extracted po_reference."""
        mock_db.get_item.return_value = _make_invoice_item("UPLOADED")
        from app.services.processor import process_invoice
        process_invoice(bucket="test-bucket", s3_key=VALID_S3_KEY)

        gr_call = mock_gr.call_args
        assert gr_call.kwargs.get("po_number") == "PO-2024-0456"


# ── process_invoice: escalation path ─────────────────────────────────────────

class TestProcessInvoiceEscalation:

    @patch("app.services.processor.evaluate_approval_rules", return_value=_ESCALATE_DECISION)
    @patch("app.services.processor.three_way_match", return_value=_GOOD_MATCH)
    @patch("app.services.processor.match_goods_receipt", return_value=_GOOD_GR_RESULT)
    @patch("app.services.processor.match_purchase_order", return_value=_GOOD_PO_RESULT)
    @patch("app.services.processor.extract_invoice", return_value=_GOOD_EXTRACTION)
    @patch("app.services.processor._invoice_db")
    def test_escalated_when_rules_fail(
        self, mock_db, mock_extract, mock_po, mock_gr, mock_3way, mock_rules
    ):
        """AC-3.7.x: when rules fail, status becomes ESCALATED."""
        mock_db.get_item.return_value = _make_invoice_item("UPLOADED")
        mock_db.update_status = MagicMock()

        from app.services.processor import process_invoice
        process_invoice(bucket="test-bucket", s3_key=VALID_S3_KEY)

        calls = mock_db.update_status.call_args_list
        statuses = [c.kwargs.get("new_status") or c.args[1] for c in calls]
        assert InvoiceStatus.ESCALATED in statuses
        assert InvoiceStatus.APPROVED  not in statuses

    @patch("app.services.processor.evaluate_approval_rules", return_value=_ESCALATE_DECISION)
    @patch("app.services.processor.three_way_match", return_value=_GOOD_MATCH)
    @patch("app.services.processor.match_goods_receipt", return_value=_GOOD_GR_RESULT)
    @patch("app.services.processor.match_purchase_order", return_value=_GOOD_PO_RESULT)
    @patch("app.services.processor.extract_invoice", return_value=_GOOD_EXTRACTION)
    @patch("app.services.processor._invoice_db")
    def test_escalate_includes_reason_and_target(
        self, mock_db, mock_extract, mock_po, mock_gr, mock_3way, mock_rules
    ):
        """Escalated records must include reason and escalateTo (AC-3.7.1 - AC-3.7.3)."""
        mock_db.get_item.return_value = _make_invoice_item("UPLOADED")
        mock_db.update_status = MagicMock()

        from app.services.processor import process_invoice
        process_invoice(bucket="test-bucket", s3_key=VALID_S3_KEY)

        escalated_call = next(
            c for c in mock_db.update_status.call_args_list
            if (c.kwargs.get("new_status") or c.args[1]) == InvoiceStatus.ESCALATED
        )
        approval = escalated_call.kwargs.get("approvalDecision", {})
        assert approval.get("escalateTo") == "FINANCE_MANAGER"
        assert approval.get("reason") != ""


# ── process_invoice: extraction failure ───────────────────────────────────────

class TestProcessInvoiceExtractionFailure:

    @patch("app.services.processor.extract_invoice")
    @patch("app.services.processor._invoice_db")
    def test_extraction_failure_sets_error_status(self, mock_db, mock_extract):
        """AC-3.1.4: BDA failure → status = ERROR."""
        from app.services.extraction import ExtractionError
        mock_db.get_item.return_value = _make_invoice_item("UPLOADED")
        mock_db.update_status = MagicMock()
        mock_extract.side_effect = ExtractionError("BDA timed out")

        from app.services.processor import process_invoice
        process_invoice(bucket="test-bucket", s3_key=VALID_S3_KEY)

        calls = mock_db.update_status.call_args_list
        statuses = [c.kwargs.get("new_status") or c.args[1] for c in calls]
        assert InvoiceStatus.ERROR in statuses
        assert InvoiceStatus.APPROVED   not in statuses
        assert InvoiceStatus.ESCALATED  not in statuses

    @patch("app.services.processor.extract_invoice")
    @patch("app.services.processor._invoice_db")
    def test_error_detail_stored_on_failure(self, mock_db, mock_extract):
        """Error message is stored in errorDetails (AC-3.1.4)."""
        from app.services.extraction import ExtractionError
        mock_db.get_item.return_value = _make_invoice_item("UPLOADED")
        mock_db.update_status = MagicMock()
        mock_extract.side_effect = ExtractionError("Corrupt file")

        from app.services.processor import process_invoice
        process_invoice(bucket="test-bucket", s3_key=VALID_S3_KEY)

        error_call = next(
            c for c in mock_db.update_status.call_args_list
            if (c.kwargs.get("new_status") or c.args[1]) == InvoiceStatus.ERROR
        )
        assert "Corrupt file" in (error_call.kwargs.get("errorDetails") or "")

    @patch("app.services.processor.extract_invoice")
    @patch("app.services.processor._invoice_db")
    def test_unexpected_exception_sets_error_status(self, mock_db, mock_extract):
        """Any unhandled exception in the pipeline → ERROR, not a crash."""
        mock_db.get_item.return_value = _make_invoice_item("UPLOADED")
        mock_db.update_status = MagicMock()
        mock_extract.side_effect = RuntimeError("Unexpected crash")

        from app.services.processor import process_invoice
        # Should not raise — the pipeline catches all exceptions
        process_invoice(bucket="test-bucket", s3_key=VALID_S3_KEY)

        calls = mock_db.update_status.call_args_list
        statuses = [c.kwargs.get("new_status") or c.args[1] for c in calls]
        assert InvoiceStatus.ERROR in statuses

    @patch("app.services.processor.extract_invoice")
    @patch("app.services.processor._invoice_db")
    def test_error_detail_is_truncated_at_1000_chars(self, mock_db, mock_extract):
        """Very long error messages are truncated (guard against oversized items)."""
        from app.services.extraction import ExtractionError
        mock_db.get_item.return_value = _make_invoice_item("UPLOADED")
        mock_db.update_status = MagicMock()
        mock_extract.side_effect = ExtractionError("x" * 2000)

        from app.services.processor import process_invoice
        process_invoice(bucket="test-bucket", s3_key=VALID_S3_KEY)

        error_call = next(
            c for c in mock_db.update_status.call_args_list
            if (c.kwargs.get("new_status") or c.args[1]) == InvoiceStatus.ERROR
        )
        error_detail = error_call.kwargs.get("errorDetails", "")
        assert len(error_detail) <= 1000


# ── process_invoice: concurrency guard ───────────────────────────────────────

class TestProcessInvoiceConcurrency:

    @patch("app.services.processor._invoice_db")
    def test_concurrent_invocation_skips_gracefully(self, mock_db):
        """If PROCESSING transition fails (ConditionalCheckFailed), second invocation skips."""
        from botocore.exceptions import ClientError
        mock_db.get_item.return_value = _make_invoice_item("UPLOADED")

        # Simulate DynamoDB conditional check failure (another Lambda got there first)
        error_response = {
            "Error": {"Code": "ConditionalCheckFailedException", "Message": "failed"}
        }
        mock_db.update_status.side_effect = ClientError(error_response, "UpdateItem")

        from app.services.processor import process_invoice
        # Should not raise
        process_invoice(bucket="test-bucket", s3_key=VALID_S3_KEY)


# ── process_invoice: S3 stage-folder moves (incoming → processed | failed) ────

class TestProcessInvoiceStaging:
    """The source object is moved between incoming/processed/failed folders."""

    @patch("app.services.processor.evaluate_approval_rules", return_value=_APPROVE_DECISION)
    @patch("app.services.processor.three_way_match", return_value=_GOOD_MATCH)
    @patch("app.services.processor.match_goods_receipt", return_value=_GOOD_GR_RESULT)
    @patch("app.services.processor.match_purchase_order", return_value=_GOOD_PO_RESULT)
    @patch("app.services.processor.extract_invoice", return_value=_GOOD_EXTRACTION)
    @patch("app.services.processor._s3")
    @patch("app.services.processor._invoice_db")
    def test_success_moves_incoming_to_processed(
        self, mock_db, mock_s3, mock_extract, mock_po, mock_gr, mock_3way, mock_rules
    ):
        """A fully-processed invoice is moved incoming/ → processed/."""
        mock_db.get_item.return_value = _make_invoice_item("UPLOADED")
        mock_db.update_status = MagicMock()

        from app.services.processor import process_invoice
        process_invoice(bucket="test-bucket", s3_key=VALID_S3_KEY)

        mock_s3.move_object.assert_called_once_with(VALID_S3_KEY, PROCESSED_S3_KEY)

        # The new (processed) key is persisted on the final status update.
        final_call = next(
            c for c in mock_db.update_status.call_args_list
            if (c.kwargs.get("new_status") or c.args[1]) == InvoiceStatus.APPROVED
        )
        assert final_call.kwargs.get("s3Key") == PROCESSED_S3_KEY

    @patch("app.services.processor.extract_invoice")
    @patch("app.services.processor._s3")
    @patch("app.services.processor._invoice_db")
    def test_failure_moves_incoming_to_failed(self, mock_db, mock_s3, mock_extract):
        """An extraction failure moves incoming/ → failed/ and records the key."""
        from app.services.extraction import ExtractionError
        mock_db.get_item.return_value = _make_invoice_item("UPLOADED")
        mock_db.update_status = MagicMock()
        mock_extract.side_effect = ExtractionError("Corrupt file")

        from app.services.processor import process_invoice
        process_invoice(bucket="test-bucket", s3_key=VALID_S3_KEY)

        mock_s3.move_object.assert_called_once_with(VALID_S3_KEY, FAILED_S3_KEY)

        error_call = next(
            c for c in mock_db.update_status.call_args_list
            if (c.kwargs.get("new_status") or c.args[1]) == InvoiceStatus.ERROR
        )
        assert error_call.kwargs.get("s3Key") == FAILED_S3_KEY

    @patch("app.services.processor.evaluate_approval_rules", return_value=_APPROVE_DECISION)
    @patch("app.services.processor.three_way_match", return_value=_GOOD_MATCH)
    @patch("app.services.processor.match_goods_receipt", return_value=_GOOD_GR_RESULT)
    @patch("app.services.processor.match_purchase_order", return_value=_GOOD_PO_RESULT)
    @patch("app.services.processor.extract_invoice", return_value=_GOOD_EXTRACTION)
    @patch("app.services.processor._s3")
    @patch("app.services.processor._invoice_db")
    def test_legacy_key_is_not_moved(
        self, mock_db, mock_s3, mock_extract, mock_po, mock_gr, mock_3way, mock_rules
    ):
        """A legacy (unstaged) key is left untouched — no move attempted."""
        mock_db.get_item.return_value = _make_invoice_item("UPLOADED")
        mock_db.update_status = MagicMock()

        legacy_key = f"invoices/{VALID_DOC_ID}/test.pdf"
        from app.services.processor import process_invoice
        process_invoice(bucket="test-bucket", s3_key=legacy_key)

        mock_s3.move_object.assert_not_called()
