"""Unit tests for the dashboard statistics and seed-data service.

Covers app/services/dashboard.py:
- compute_stats()      — FR-AP-009, AC-3.9.1, AC-3.9.2
- default_seed_data()  — AC-5.1.4

These are pure-logic tests with no AWS dependency.
"""

from decimal import Decimal

from app.models.enums import InvoiceStatus
from app.services.dashboard import compute_stats, default_seed_data


def _invoice(status, *, approver=None, duration_ms=None, updated="2026-07-25T10:00:00Z", **extra):
    """Build a minimal invoice record for stats tests."""
    item = {
        "documentId": extra.get("documentId", "doc-1"),
        "fileName": extra.get("fileName", "INV.pdf"),
        "status": status,
        "uploadedAt": extra.get("uploadedAt", updated),
        "updatedAt": updated,
    }
    if duration_ms is not None:
        item["processingDurationMs"] = duration_ms
    if approver is not None:
        item["approvalDecision"] = {"approver": approver}
    return item


class TestComputeStatsTotals:
    """Total counts and complete status shape (AC-3.9.1)."""

    def test_empty_returns_zeroed_shape(self):
        stats = compute_stats([])

        assert stats["totalInvoices"] == 0
        assert stats["autoApprovalRate"] == 0.0
        assert stats["avgProcessingTimeSec"] == 0.0
        assert stats["recentActivity"] == []
        # Every known status is present and zeroed.
        for status in InvoiceStatus:
            assert stats["statusCounts"][status.value.lower()] == 0

    def test_counts_group_by_status(self):
        items = [
            _invoice(InvoiceStatus.APPROVED, approver="SYSTEM"),
            _invoice(InvoiceStatus.APPROVED, approver="SYSTEM"),
            _invoice(InvoiceStatus.ESCALATED),
            _invoice(InvoiceStatus.REJECTED),
            _invoice(InvoiceStatus.PROCESSING),
        ]
        stats = compute_stats(items)

        assert stats["totalInvoices"] == 5
        assert stats["statusCounts"]["approved"] == 2
        assert stats["statusCounts"]["escalated"] == 1
        assert stats["statusCounts"]["rejected"] == 1
        assert stats["statusCounts"]["processing"] == 1

    def test_unknown_status_is_recorded_not_dropped(self):
        stats = compute_stats([_invoice("WEIRD_STATUS")])

        assert stats["totalInvoices"] == 1
        assert stats["statusCounts"]["weird_status"] == 1

    def test_missing_status_bucketed_as_unknown(self):
        # Record with no status field at all.
        stats = compute_stats([{"documentId": "d1", "fileName": "x.pdf"}])

        assert stats["totalInvoices"] == 1
        assert stats["statusCounts"]["unknown"] == 1


class TestAutoApprovalRate:
    """Auto-approval rate reflects SYSTEM-approved invoices only."""

    def test_only_system_approvals_count(self):
        items = [
            _invoice(InvoiceStatus.APPROVED, approver="SYSTEM"),
            _invoice(InvoiceStatus.APPROVED, approver="manager@test.com"),  # manual
            _invoice(InvoiceStatus.ESCALATED),
            _invoice(InvoiceStatus.REJECTED),
        ]
        stats = compute_stats(items)

        # 1 of 4 auto-approved -> 25.0%
        assert stats["autoApprovalRate"] == 25.0

    def test_all_auto_approved(self):
        items = [
            _invoice(InvoiceStatus.APPROVED, approver="SYSTEM"),
            _invoice(InvoiceStatus.APPROVED, approver="SYSTEM"),
        ]
        assert compute_stats(items)["autoApprovalRate"] == 100.0

    def test_approval_without_decision_is_not_auto(self):
        # APPROVED but no approvalDecision (e.g. legacy record) -> not auto.
        items = [_invoice(InvoiceStatus.APPROVED)]
        assert compute_stats(items)["autoApprovalRate"] == 0.0


class TestAvgProcessingTime:
    """Average processing time in seconds, ignoring missing/zero durations."""

    def test_average_in_seconds(self):
        items = [
            _invoice(InvoiceStatus.APPROVED, approver="SYSTEM", duration_ms=Decimal("28000")),
            _invoice(InvoiceStatus.ESCALATED, duration_ms=Decimal("32000")),
        ]
        # (28000 + 32000) / 2 / 1000 = 30.0s
        assert compute_stats(items)["avgProcessingTimeSec"] == 30.0

    def test_missing_and_zero_durations_ignored(self):
        items = [
            _invoice(InvoiceStatus.APPROVED, approver="SYSTEM", duration_ms=Decimal("20000")),
            _invoice(InvoiceStatus.PROCESSING),  # no duration
            _invoice(InvoiceStatus.ERROR, duration_ms=Decimal("0")),  # zero ignored
        ]
        # Only the 20000ms record counts -> 20.0s
        assert compute_stats(items)["avgProcessingTimeSec"] == 20.0

    def test_no_durations_returns_zero(self):
        items = [_invoice(InvoiceStatus.PROCESSING)]
        assert compute_stats(items)["avgProcessingTimeSec"] == 0.0


class TestRecentActivity:
    """Recent-activity feed ordering and action labels."""

    def test_sorted_most_recent_first_and_capped(self):
        items = [
            _invoice(InvoiceStatus.APPROVED, approver="SYSTEM", updated=f"2026-07-25T10:{i:02d}:00Z",
                     documentId=f"doc-{i}")
            for i in range(15)
        ]
        activity = compute_stats(items)["recentActivity"]

        assert len(activity) == 10  # capped
        assert activity[0]["timestamp"] == "2026-07-25T10:14:00Z"
        assert activity[-1]["timestamp"] == "2026-07-25T10:05:00Z"

    def test_action_labels(self):
        items = [
            _invoice(InvoiceStatus.APPROVED, approver="SYSTEM", updated="2026-07-25T10:05:00Z"),
            _invoice(InvoiceStatus.APPROVED, approver="mgr@test.com", updated="2026-07-25T10:04:00Z"),
            _invoice(InvoiceStatus.REJECTED, updated="2026-07-25T10:03:00Z"),
        ]
        labels = [a["action"] for a in compute_stats(items)["recentActivity"]]

        assert labels[0] == "Auto-approved"
        assert labels[1] == "Manually approved"
        assert labels[2] == "Rejected"

    def test_escalation_reason_in_label(self):
        item = _invoice(InvoiceStatus.ESCALATED, updated="2026-07-25T10:05:00Z")
        item["approvalDecision"] = {"reason": "Amount exceeds threshold"}

        activity = compute_stats([item])["recentActivity"]
        assert activity[0]["action"] == "Escalated - Amount exceeds threshold"


class TestDefaultSeedData:
    """Default sample data set shape (AC-5.1.4)."""

    def test_returns_five_pos_and_five_grs(self):
        pos, grs = default_seed_data()
        assert len(pos) == 5
        assert len(grs) == 5

    def test_every_gr_links_to_an_existing_po(self):
        pos, grs = default_seed_data()
        po_numbers = {po["poNumber"] for po in pos}
        for gr in grs:
            assert gr["poNumber"] in po_numbers

    def test_po_records_have_required_matching_fields(self):
        pos, _ = default_seed_data()
        for po in pos:
            assert po["poNumber"]
            assert po["vendorName"]
            assert "totalAmount" in po
