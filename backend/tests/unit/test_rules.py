"""Unit tests for the approval rules engine (FR-AP-006, FR-AP-007).

Covers every path through evaluate_approval_rules() including:
- All-pass → APPROVE
- Each individual rule failing → correct ESCALATE target and reason
- Multiple rules failing → highest-priority routing wins
"""

import pytest

from app.services.rules import (
    AMOUNT_THRESHOLD,
    CONFIDENCE_THRESHOLD,
    evaluate_approval_rules,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

GOOD_VENDOR = "Any Vendor Pty Ltd."   # vendor no longer gates approval

GOOD_ARGS = dict(
    total_amount        = 500.00,
    overall_confidence  = 0.96,
    vendor_name         = GOOD_VENDOR,
    three_way_match_status = "PASS",
    discrepancies       = [],
)


# ── Happy path ────────────────────────────────────────────────────────────────

class TestAllRulesPass:
    def test_decision_is_approve(self):
        result = evaluate_approval_rules(**GOOD_ARGS)
        assert result["decision"] == "APPROVE"

    def test_escalate_to_is_none(self):
        result = evaluate_approval_rules(**GOOD_ARGS)
        assert result["escalateTo"] is None

    def test_all_rules_evaluated(self):
        result = evaluate_approval_rules(**GOOD_ARGS)
        assert len(result["rulesResults"]) == 3

    def test_all_rules_passed(self):
        result = evaluate_approval_rules(**GOOD_ARGS)
        assert all(r["passed"] for r in result["rulesResults"])

    def test_reason_mentions_passed(self):
        result = evaluate_approval_rules(**GOOD_ARGS)
        assert "passed" in result["reason"].lower()

    def test_amount_exactly_at_threshold(self):
        """Boundary: amount == threshold should still APPROVE (AC-3.6.1: ≤ $10,000)."""
        result = evaluate_approval_rules(**{**GOOD_ARGS, "total_amount": AMOUNT_THRESHOLD})
        assert result["decision"] == "APPROVE"


# ── RULE-002: Amount threshold ─────────────────────────────────────────────────

class TestAmountThreshold:
    def test_amount_over_threshold_escalates(self):
        """AC-3.6.2: amount > $10,000 → ESCALATE."""
        result = evaluate_approval_rules(**{**GOOD_ARGS, "total_amount": 15_000.00})
        assert result["decision"] == "ESCALATE"

    def test_amount_over_threshold_routes_to_finance_manager(self):
        """AC-3.7.1: escalated to FINANCE_MANAGER."""
        result = evaluate_approval_rules(**{**GOOD_ARGS, "total_amount": 15_000.00})
        assert result["escalateTo"] == "FINANCE_MANAGER"

    def test_reason_mentions_threshold(self):
        result = evaluate_approval_rules(**{**GOOD_ARGS, "total_amount": 15_000.00})
        assert "10,000" in result["reason"] or "threshold" in result["reason"].lower()

    def test_amount_just_above_threshold(self):
        result = evaluate_approval_rules(**{**GOOD_ARGS, "total_amount": 10_000.01})
        assert result["decision"] == "ESCALATE"
        assert result["escalateTo"] == "FINANCE_MANAGER"

    def test_rule002_is_marked_failed(self):
        result = evaluate_approval_rules(**{**GOOD_ARGS, "total_amount": 20_000.00})
        rule = next(r for r in result["rulesResults"] if r["ruleId"] == "RULE-002")
        assert not rule["passed"]

    def test_rule002_wins_over_match_failure(self):
        """Amount failure should route to FINANCE_MANAGER even if match also fails."""
        result = evaluate_approval_rules(
            **{
                **GOOD_ARGS,
                "total_amount": 20_000.00,
                "three_way_match_status": "FAIL",
                "discrepancies": ["PO not found"],
            }
        )
        assert result["escalateTo"] == "FINANCE_MANAGER"


# ── RULE-001: Three-way match ──────────────────────────────────────────────────

class TestThreeWayMatch:
    def test_match_fail_escalates(self):
        result = evaluate_approval_rules(
            **{**GOOD_ARGS, "three_way_match_status": "FAIL", "discrepancies": ["Amount mismatch"]}
        )
        assert result["decision"] == "ESCALATE"

    def test_match_fail_routes_to_ap_clerk(self):
        """AC-3.7.2: match failure → AP_CLERK."""
        result = evaluate_approval_rules(
            **{**GOOD_ARGS, "three_way_match_status": "FAIL", "discrepancies": ["PO not found"]}
        )
        assert result["escalateTo"] == "AP_CLERK"

    def test_reason_contains_discrepancy(self):
        result = evaluate_approval_rules(
            **{
                **GOOD_ARGS,
                "three_way_match_status": "FAIL",
                "discrepancies": ["Amount variance 12.5%"],
            }
        )
        assert "Amount variance 12.5%" in result["reason"]

    def test_match_fail_with_empty_discrepancies(self):
        """Should not crash when discrepancies list is empty."""
        result = evaluate_approval_rules(
            **{**GOOD_ARGS, "three_way_match_status": "FAIL", "discrepancies": []}
        )
        assert result["decision"] == "ESCALATE"
        assert result["escalateTo"] == "AP_CLERK"

    def test_rule001_is_marked_failed(self):
        result = evaluate_approval_rules(
            **{**GOOD_ARGS, "three_way_match_status": "FAIL", "discrepancies": []}
        )
        rule = next(r for r in result["rulesResults"] if r["ruleId"] == "RULE-001")
        assert not rule["passed"]


# ── RULE-003: Confidence threshold ────────────────────────────────────────────

class TestConfidenceThreshold:
    def test_low_confidence_escalates(self):
        result = evaluate_approval_rules(**{**GOOD_ARGS, "overall_confidence": 0.72})
        assert result["decision"] == "ESCALATE"

    def test_low_confidence_routes_to_ap_clerk(self):
        """AC-3.7.3: low confidence → AP_CLERK."""
        result = evaluate_approval_rules(**{**GOOD_ARGS, "overall_confidence": 0.72})
        assert result["escalateTo"] == "AP_CLERK"

    def test_reason_mentions_confidence(self):
        result = evaluate_approval_rules(**{**GOOD_ARGS, "overall_confidence": 0.70})
        assert "confidence" in result["reason"].lower() or "0.70" in result["reason"]

    def test_confidence_exactly_at_threshold_approves(self):
        """Boundary: confidence == 0.85 should APPROVE."""
        result = evaluate_approval_rules(**{**GOOD_ARGS, "overall_confidence": CONFIDENCE_THRESHOLD})
        assert result["decision"] == "APPROVE"

    def test_confidence_just_below_threshold(self):
        result = evaluate_approval_rules(**{**GOOD_ARGS, "overall_confidence": 0.8499})
        assert result["decision"] == "ESCALATE"

    def test_rule003_is_marked_failed(self):
        result = evaluate_approval_rules(**{**GOOD_ARGS, "overall_confidence": 0.50})
        rule = next(r for r in result["rulesResults"] if r["ruleId"] == "RULE-003")
        assert not rule["passed"]


# ── Approved vendor rule removed ───────────────────────────────────────────────

class TestVendorNoLongerGates:
    def test_any_vendor_can_approve(self):
        """The approved-vendor list check was removed; vendor never gates approval."""
        result = evaluate_approval_rules(**{**GOOD_ARGS, "vendor_name": "Totally Unknown Supplier Ltd."})
        assert result["decision"] == "APPROVE"

    def test_no_rule004_in_results(self):
        result = evaluate_approval_rules(**GOOD_ARGS)
        ids = {r["ruleId"] for r in result["rulesResults"]}
        assert "RULE-004" not in ids


# ── Rules result structure ─────────────────────────────────────────────────────

class TestRulesResultStructure:
    def test_all_rule_ids_present(self):
        result = evaluate_approval_rules(**GOOD_ARGS)
        ids = {r["ruleId"] for r in result["rulesResults"]}
        assert ids == {"RULE-001", "RULE-002", "RULE-003"}

    def test_each_rule_has_required_keys(self):
        result = evaluate_approval_rules(**GOOD_ARGS)
        for rule in result["rulesResults"]:
            assert "ruleId" in rule
            assert "name"   in rule
            assert "passed" in rule
            assert "detail" in rule

    def test_passed_is_bool(self):
        result = evaluate_approval_rules(**GOOD_ARGS)
        for rule in result["rulesResults"]:
            assert isinstance(rule["passed"], bool)
