"""Re-run matching + approval rules for an already-processed invoice.

Why this exists
---------------
Invoices processed before the PO-matching fix (a referenced-but-missing PO
number used to fuzzy-match an unrelated PO and produce a false three-way PASS)
have a stale ``matchResult`` / ``approvalDecision`` persisted in DynamoDB. The
matcher fix only changes behaviour for *future* processing; it does not rewrite
records that were already approved/escalated.

This script re-runs ONLY the matching + approval-rules stage against the
extraction data already stored on the invoice record (no BDA re-call, no S3
dependency), then writes back the corrected ``matchResult``,
``approvalDecision`` and status. Extraction results are left untouched.

Usage
-----
    # Preview the corrected verdict without writing (recommended first):
    python -m scripts.reprocess_invoice <documentId> --dry-run

    # Apply the correction:
    python -m scripts.reprocess_invoice <documentId>

    # Reprocess every APPROVED invoice (e.g. to sweep pre-fix false matches):
    python -m scripts.reprocess_invoice --all-approved --dry-run
    python -m scripts.reprocess_invoice --all-approved

Requires AWS credentials with DynamoDB read/write on the invoices table.
Only invoices in a terminal state (APPROVED, ESCALATED, ERROR) are eligible;
in-flight records (UPLOADED/PROCESSING/EXTRACTED) are skipped so a live
pipeline run is never clobbered.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.config import settings
from app.models.enums import InvoiceStatus
from app.services.dynamo import DynamoClient
from app.services.processor import run_matching_and_decision, _to_dynamo

# Statuses we are willing to overwrite. In-flight records are left alone.
_ELIGIBLE_STATUSES = frozenset(
    {InvoiceStatus.APPROVED, InvoiceStatus.ESCALATED, InvoiceStatus.ERROR}
)


def _deep_floatify(obj: Any) -> Any:
    """Recursively convert DynamoDB Decimals to float/int for the matcher.

    The matcher and rules coerce with ``float(...)`` but nested Decimals inside
    the stored ``extraction`` (e.g. line-item quantities) are easier to reason
    about as native numbers first.
    """
    if isinstance(obj, Decimal):
        # Preserve integers as int so quantities like 171 stay clean.
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    if isinstance(obj, dict):
        return {k: _deep_floatify(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_floatify(v) for v in obj]
    return obj


def _summarise(match_result: dict, decision: dict) -> str:
    po = match_result.get("poMatch", {})
    gr = match_result.get("grMatch", {})
    return (
        f"three-way={match_result.get('status')} "
        f"PO={po.get('status')}(poId={po.get('poId')}) "
        f"GR={gr.get('status')} "
        f"decision={decision.get('decision')} "
        f"reason={decision.get('reason')!r}"
    )


def reprocess_one(
    invoice_db: DynamoClient,
    document_id: str,
    *,
    dry_run: bool,
) -> bool:
    """Reprocess a single invoice. Returns True if a change was (or would be) made."""
    item = invoice_db.get_item({"documentId": document_id})
    if not item:
        print(f"  SKIP  {document_id}: not found")
        return False

    status = item.get("status", "")
    if status not in _ELIGIBLE_STATUSES:
        print(f"  SKIP  {document_id}: status {status!r} is not eligible")
        return False

    extraction = item.get("extraction")
    if not extraction:
        print(f"  SKIP  {document_id}: no stored extraction to re-match")
        return False

    # Rebuild the extraction dict the matcher expects. overallConfidence is
    # stored as a top-level attribute, not inside `extraction`.
    extraction = _deep_floatify(dict(extraction))
    extraction.setdefault(
        "overallConfidence", _deep_floatify(item.get("overallConfidence", 0))
    )

    old_match = item.get("matchResult", {}) or {}
    old_decision = item.get("approvalDecision", {}) or {}

    match_result, decision = run_matching_and_decision(
        extraction, log_ctx={"documentId": document_id, "reprocess": True}
    )

    old_status = InvoiceStatus(status) if status in InvoiceStatus.__members__ else status
    new_status = (
        InvoiceStatus.APPROVED
        if decision["decision"] == "APPROVE"
        else InvoiceStatus.ESCALATED
    )

    print(f"  {document_id}")
    print(f"    poReference : {extraction.get('poReference')!r}")
    print(f"    BEFORE      : status={old_status} "
          f"three-way={ (old_match.get('threeWayMatch') or old_match.get('status')) } "
          f"decision={old_decision.get('decision')}")
    print(f"    AFTER       : status={new_status} {_summarise(match_result, decision)}")

    if dry_run:
        print("    (dry-run — no write)")
        return old_status != new_status or old_decision.get("decision") != decision["decision"]

    now = datetime.now(timezone.utc).isoformat()
    approval_record: dict[str, Any] = {
        "decision":     decision["decision"],
        "reason":       decision["reason"],
        "escalateTo":   decision.get("escalateTo"),
        "rulesResults": decision["rulesResults"],
    }
    if decision["decision"] == "APPROVE":
        approval_record["approver"]   = "SYSTEM"
        approval_record["approvedAt"] = now
        approval_record["reprocessedAt"] = now
    else:
        approval_record["reprocessedAt"] = now

    invoice_db.update_status(
        document_id=document_id,
        new_status=new_status,
        matchResult=_to_dynamo(match_result),
        approvalDecision=_to_dynamo(approval_record),
    )
    print("    WROTE corrected matchResult + approvalDecision")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Re-run matching + approval rules for processed invoice(s)."
    )
    parser.add_argument("document_id", nargs="?", help="Invoice documentId to reprocess.")
    parser.add_argument(
        "--all-approved",
        action="store_true",
        help="Reprocess every invoice currently in APPROVED status.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the corrected verdict without writing to DynamoDB.",
    )
    args = parser.parse_args()

    if not args.document_id and not args.all_approved:
        parser.error("provide a documentId or --all-approved")

    invoice_db = DynamoClient(settings.INVOICE_TABLE)
    print(f"Invoice table: {settings.INVOICE_TABLE}")
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'APPLY'}\n")

    changed = 0
    if args.all_approved:
        items = invoice_db.scan_all()
        targets = [
            i["documentId"]
            for i in items
            if i.get("status") == InvoiceStatus.APPROVED and i.get("documentId")
        ]
        print(f"Found {len(targets)} APPROVED invoice(s) to reprocess\n")
        for doc_id in targets:
            if reprocess_one(invoice_db, doc_id, dry_run=args.dry_run):
                changed += 1
    else:
        if reprocess_one(invoice_db, args.document_id, dry_run=args.dry_run):
            changed += 1

    verb = "would change" if args.dry_run else "changed"
    print(f"\nDone. {changed} invoice(s) {verb}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
