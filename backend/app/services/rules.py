"""Approval rules engine.

Evaluates three ordered business rules and returns an APPROVE or ESCALATE
decision (FR-AP-006, FR-AP-007, AC-3.6.x, AC-3.7.x).

Rule priority order (first failure wins for escalation routing):
  RULE-001  Three-way match must PASS         → ESCALATE to AP_CLERK
  RULE-002  Total amount ≤ threshold          → ESCALATE to FINANCE_MANAGER
  RULE-003  Overall confidence ≥ threshold    → ESCALATE to AP_CLERK

All three must pass for auto-approval (AC-3.6.1).

Note: the approved-vendor list check (formerly RULE-004) has been removed;
vendor membership no longer gates approval.

Note: RULE-002 (amount) is checked *after* RULE-001 (match) in the list but
routes to FINANCE_MANAGER — the escalation target depends on *which* rule
fails, not on rule order.  We collect all failures and pick the highest-
priority routing from the failure set.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

AMOUNT_THRESHOLD: float = 10_000.00
CONFIDENCE_THRESHOLD: float = 0.85


# ── Public API ────────────────────────────────────────────────────────────────

def evaluate_approval_rules(
    total_amount: float,
    overall_confidence: float,
    vendor_name: str,
    three_way_match_status: str,
    discrepancies: list[str],
    amount_threshold: float = AMOUNT_THRESHOLD,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
) -> dict[str, Any]:
    """Evaluate all four approval rules and return the decision.

    Parameters
    ----------
    total_amount:
        Invoice total in USD.
    overall_confidence:
        Average extraction confidence score (0.0–1.0).
    vendor_name:
        Extracted vendor name to check against approved list.
    three_way_match_status:
        "PASS" or "FAIL" from three_way_match().
    discrepancies:
        Combined discrepancy list from PO and GR matching.

    Returns
    -------
    {
        "decision":      "APPROVE" | "ESCALATE",
        "reason":        str,
        "escalateTo":    None | "AP_CLERK" | "FINANCE_MANAGER",
        "rulesResults":  [ { ruleId, name, passed, detail }, ... ],
    }
    """
    rules_results = _evaluate_rules(
        total_amount=total_amount,
        overall_confidence=overall_confidence,
        vendor_name=vendor_name,
        three_way_match_status=three_way_match_status,
        discrepancies=discrepancies,
        amount_threshold=amount_threshold,
        confidence_threshold=confidence_threshold,
    )

    all_passed = all(r["passed"] for r in rules_results)

    if all_passed:
        logger.info(
            "Invoice auto-approved",
            extra={
                "decision": "APPROVE",
                "totalAmount": total_amount,
                "vendor": vendor_name,
            },
        )
        return {
            "decision": "APPROVE",
            "reason": "All approval rules passed.",
            "escalateTo": None,
            "rulesResults": rules_results,
        }

    # Determine escalation target and reason from failed rules
    failed_rules = [r for r in rules_results if not r["passed"]]
    escalate_to, reason = _escalation_target(
        failed_rules=failed_rules,
        total_amount=total_amount,
        overall_confidence=overall_confidence,
        vendor_name=vendor_name,
        discrepancies=discrepancies,
        amount_threshold=amount_threshold,
        confidence_threshold=confidence_threshold,
    )

    logger.info(
        "Invoice escalated",
        extra={
            "decision": "ESCALATE",
            "escalateTo": escalate_to,
            "reason": reason,
            "failedRules": [r["ruleId"] for r in failed_rules],
        },
    )

    return {
        "decision": "ESCALATE",
        "reason": reason,
        "escalateTo": escalate_to,
        "rulesResults": rules_results,
    }


# ── Rule evaluation ────────────────────────────────────────────────────────────

def _evaluate_rules(
    total_amount: float,
    overall_confidence: float,
    vendor_name: str,
    three_way_match_status: str,
    discrepancies: list[str],
    amount_threshold: float = AMOUNT_THRESHOLD,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
) -> list[dict[str, Any]]:
    """Build and evaluate all four rules. Returns full results list."""

    rule1_pass = three_way_match_status == "PASS"
    rule2_pass = total_amount <= amount_threshold
    rule3_pass = overall_confidence >= confidence_threshold

    return [
        {
            "ruleId": "RULE-001",
            "name":   "Three-Way Match",
            "passed": rule1_pass,
            "detail": f"Match status: {three_way_match_status}"
                      + (f" — {', '.join(discrepancies)}" if discrepancies and not rule1_pass else ""),
        },
        {
            "ruleId": "RULE-002",
            "name":   "Amount Threshold",
            "passed": rule2_pass,
            "detail": (
                f"Amount ${total_amount:,.2f} "
                f"{'≤' if rule2_pass else '>'} threshold ${amount_threshold:,.2f}"
            ),
        },
        {
            "ruleId": "RULE-003",
            "name":   "Confidence Threshold",
            "passed": rule3_pass,
            "detail": (
                f"Overall confidence {overall_confidence:.2f} "
                f"{'≥' if rule3_pass else '<'} threshold {confidence_threshold:.2f}"
            ),
        },
    ]


def _escalation_target(
    failed_rules: list[dict],
    total_amount: float,
    overall_confidence: float,
    vendor_name: str,
    discrepancies: list[str],
    amount_threshold: float = AMOUNT_THRESHOLD,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
) -> tuple[str, str]:
    """Return (escalate_to, reason) for the most important failure.

    Priority for FINANCE_MANAGER: amount threshold (RULE-002).
    All other failures route to AP_CLERK.
    """
    failed_ids = {r["ruleId"] for r in failed_rules}

    # RULE-002 failure → Finance Manager regardless of other failures
    if "RULE-002" in failed_ids:
        reason = (
            f"Amount ${total_amount:,.2f} exceeds the auto-approval "
            f"threshold of ${amount_threshold:,.2f}."
        )
        return "FINANCE_MANAGER", reason

    # RULE-001 failure → AP Clerk with discrepancy details
    if "RULE-001" in failed_ids:
        disc_str = "; ".join(discrepancies) if discrepancies else "match failed"
        reason = f"Three-way match failed: {disc_str}"
        return "AP_CLERK", reason

    # RULE-003 failure (the only remaining rule)
    reason = (
        f"Extraction confidence {overall_confidence:.2f} is below the "
        f"required threshold of {confidence_threshold:.2f}. "
        "Manual verification of extracted fields is required."
    )
    return "AP_CLERK", reason
