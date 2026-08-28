"""Approval rules engine.

Evaluates four ordered business rules and returns an APPROVE or ESCALATE
decision (FR-AP-006, FR-AP-007, AC-3.6.x, AC-3.7.x).

Rule priority order (first failure wins for escalation routing):
  RULE-001  Three-way match must PASS         → ESCALATE to AP_CLERK
  RULE-002  Total amount ≤ $10,000            → ESCALATE to FINANCE_MANAGER
  RULE-003  Overall confidence ≥ 0.85         → ESCALATE to AP_CLERK
  RULE-004  Vendor in approved vendor list    → ESCALATE to AP_CLERK

All four must pass for auto-approval (AC-3.6.1).

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

# Approved vendors list (FR-AP-006 rule 4)
APPROVED_VENDORS: frozenset[str] = frozenset(
    {
        "Acme Office Supplies Inc.",
        "TechParts Global Ltd.",
        "Facilities Maintenance Co.",
        "CloudServ Solutions",
        "PrintWorks Inc.",
    }
)


# ── Public API ────────────────────────────────────────────────────────────────

def evaluate_approval_rules(
    total_amount: float,
    overall_confidence: float,
    vendor_name: str,
    three_way_match_status: str,
    discrepancies: list[str],
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
) -> list[dict[str, Any]]:
    """Build and evaluate all four rules. Returns full results list."""

    rule1_pass = three_way_match_status == "PASS"
    rule2_pass = total_amount <= AMOUNT_THRESHOLD
    rule3_pass = overall_confidence >= CONFIDENCE_THRESHOLD
    rule4_pass = vendor_name in APPROVED_VENDORS

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
                f"{'≤' if rule2_pass else '>'} threshold ${AMOUNT_THRESHOLD:,.2f}"
            ),
        },
        {
            "ruleId": "RULE-003",
            "name":   "Confidence Threshold",
            "passed": rule3_pass,
            "detail": (
                f"Overall confidence {overall_confidence:.2f} "
                f"{'≥' if rule3_pass else '<'} threshold {CONFIDENCE_THRESHOLD:.2f}"
            ),
        },
        {
            "ruleId": "RULE-004",
            "name":   "Approved Vendor",
            "passed": rule4_pass,
            "detail": (
                f"Vendor '{vendor_name}' "
                f"{'is' if rule4_pass else 'is NOT'} in the approved vendor list"
            ),
        },
    ]


def _escalation_target(
    failed_rules: list[dict],
    total_amount: float,
    overall_confidence: float,
    vendor_name: str,
    discrepancies: list[str],
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
            f"threshold of ${AMOUNT_THRESHOLD:,.2f}."
        )
        return "FINANCE_MANAGER", reason

    # RULE-001 failure → AP Clerk with discrepancy details
    if "RULE-001" in failed_ids:
        disc_str = "; ".join(discrepancies) if discrepancies else "match failed"
        reason = f"Three-way match failed: {disc_str}"
        return "AP_CLERK", reason

    # RULE-003 failure
    if "RULE-003" in failed_ids:
        reason = (
            f"Extraction confidence {overall_confidence:.2f} is below the "
            f"required threshold of {CONFIDENCE_THRESHOLD:.2f}. "
            "Manual verification of extracted fields is required."
        )
        return "AP_CLERK", reason

    # RULE-004 failure
    reason = (
        f"Vendor '{vendor_name}' is not in the approved vendor list. "
        "Please verify and add the vendor before approving."
    )
    return "AP_CLERK", reason
