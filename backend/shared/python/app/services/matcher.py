"""Invoice matching service — PO and Goods Receipt matching logic.

Implements:
- match_purchase_order()  — FR-AP-003, AC-3.3.x
- match_goods_receipt()   — FR-AP-004, AC-3.4.x
- three_way_match()       — FR-AP-005, AC-3.5.x

Business rules (from docs/02-functional-requirements.md):
- PO amount tolerance:       5%   (FR-AP-003)  — PO amount   vs Invoice amount
- PO quantity tolerance:     2%   (FR-AP-003)  — PO quantity vs Invoice quantity
- GR quantity tolerance:     2%   (FR-AP-004)  — GR quantity vs Invoice quantity
- GR amount tolerance:       5%   (FR-AP-004)  — GR amount   vs Invoice amount
- Three-way PASS requires PO=MATCHED and GR=CONFIRMED (AC-3.5.1)
- Any failure → THREE_WAY_MATCH_FAIL  (AC-3.5.2)

Four comparisons are performed across the two source documents:
  1. Invoice amount   ↔ Purchase Order amount   (match_purchase_order)
  2. Invoice quantity ↔ Purchase Order quantity (match_purchase_order)
  3. Invoice quantity ↔ Goods Receipt quantity  (match_goods_receipt)
  4. Invoice amount   ↔ Goods Receipt amount     (match_goods_receipt)

All DynamoDB Decimal values are coerced to float before comparison.
"""

import logging
from typing import Any

from app.config import settings
from app.services.dynamo import DynamoClient

logger = logging.getLogger(__name__)

# ── Tolerances ────────────────────────────────────────────────────────────────

_PO_AMOUNT_TOLERANCE = 0.05   # 5 %  — FR-AP-003 (Invoice amount   vs PO amount)
_PO_QTY_TOLERANCE    = 0.02   # 2 %  — FR-AP-003 (Invoice quantity vs PO quantity)
_GR_QTY_TOLERANCE    = 0.02   # 2 %  — FR-AP-004 (Invoice quantity vs GR quantity)
_GR_AMOUNT_TOLERANCE = 0.05   # 5 %  — FR-AP-004 (Invoice amount   vs GR amount)

# Small epsilon so the tolerance boundary is inclusive and immune to floating-
# point rounding (e.g. 658.80 * 1.05 yields a variance of 0.05000000000000004,
# which must still count as "within 5%").
_FLOAT_EPSILON = 1e-9

# ── Service clients (lazy) ────────────────────────────────────────────────────

_po_db = DynamoClient(settings.PO_TABLE)
_gr_db = DynamoClient(settings.GR_TABLE)


# ── Public API ────────────────────────────────────────────────────────────────

def match_purchase_order(
    po_number: str | None,
    vendor_name: str,
    invoice_amount: float,
    invoiced_quantity: float = 0.0,
    amount_tolerance: float = _PO_AMOUNT_TOLERANCE,
    qty_tolerance: float = _PO_QTY_TOLERANCE,
) -> dict[str, Any]:
    """Match an extracted invoice against a Purchase Order.

    Strategy
    --------
    1. If ``po_number`` is present, attempt an *exact* PO number lookup first.
    2. If exact lookup fails (or ``po_number`` is None), fall back to a
       *fuzzy vendor-name* lookup via GSI-VendorDate and pick the PO whose
       amount is closest to the invoice amount.
    3. Compare vendor name (case-insensitive substring check), amount
       (within ``amount_tolerance``) and quantity (Invoice quantity vs PO
       quantity, within ``qty_tolerance``).

    Returns
    -------
    ``{ status, poId, amountVariancePct, quantityVariancePct, poQuantity,
        invoicedQuantity, discrepancies }``

    ``status`` ∈ { "MATCHED", "PARTIAL_MATCH", "NO_MATCH" }
    """
    log_ctx = {
        "poNumber": po_number,
        "vendorName": vendor_name,
        "invoiceAmount": invoice_amount,
        "invoicedQty": invoiced_quantity,
    }

    # ── 1. Exact PO number lookup ──────────────────────────────────────────────
    po = None
    if po_number:
        po = _po_db.get_item({"poNumber": po_number})
        if po:
            logger.debug("Exact PO lookup hit", extra={**log_ctx, "found": True})
        else:
            logger.debug("Exact PO lookup miss", extra={**log_ctx, "found": False})

    # ── 2. Fuzzy fallback: query by vendor name ────────────────────────────────
    if po is None:
        logger.info(
            "Falling back to fuzzy PO search",
            extra={**log_ctx, "reason": "no exact match"},
        )
        pos, _ = _po_db.query_by_index(
            index_name="GSI-VendorDate",
            partition_key="vendorName",
            partition_value=vendor_name,
            limit=10,
            scan_forward=False,
        )
        if not pos:
            # Try case-insensitive by scanning a small set — acceptable for MVP
            pos = _scan_pos_by_vendor(vendor_name)

        if not pos:
            logger.info("PO not found (no match)", extra=log_ctx)
            return {
                "status": "NO_MATCH",
                "poId": None,
                "amountVariancePct": None,
                "poAmount": None,
                "amountInvoiced": invoice_amount,
                "quantityVariancePct": None,
                "poQuantity": None,
                "invoicedQuantity": invoiced_quantity,
                "discrepancies": ["PO not found"],
            }

        po = _closest_amount(pos, invoice_amount)
        logger.debug("Fuzzy PO match candidate", extra={**log_ctx, "candidatePoId": po.get("poNumber")})

    # ── 3. Evaluate discrepancies ──────────────────────────────────────────────
    discrepancies: list[str] = []

    po_amount = _to_float(po.get("totalAmount", 0))
    variance_pct = (
        abs(po_amount - invoice_amount) / po_amount
        if po_amount > 0
        else 1.0
    )

    if variance_pct > amount_tolerance + _FLOAT_EPSILON:
        discrepancies.append(
            f"Amount variance {variance_pct * 100:.1f}%: "
            f"PO ${po_amount:.2f} vs Invoice ${invoice_amount:.2f}"
        )

    po_vendor = po.get("vendorName", "")
    if not _vendor_names_match(po_vendor, vendor_name):
        discrepancies.append(
            f"Vendor mismatch: PO='{po_vendor}', Invoice='{vendor_name}'"
        )

    # ── Quantity check: Invoice quantity vs PO quantity ────────────────────────
    # Only enforced when the PO carries a quantity and the invoice has one, so
    # legacy PO records without ``totalQuantity`` do not fail the match.
    po_quantity = _to_float(po.get("totalQuantity", 0))
    qty_variance_pct: float | None = None
    if po_quantity > 0 and invoiced_quantity > 0:
        qty_variance_pct = abs(po_quantity - invoiced_quantity) / po_quantity
        if qty_variance_pct > qty_tolerance + _FLOAT_EPSILON:
            discrepancies.append(
                f"Quantity variance {qty_variance_pct * 100:.1f}%: "
                f"PO {po_quantity:.0f} vs Invoice {invoiced_quantity:.0f}"
            )

    status = "MATCHED" if not discrepancies else "PARTIAL_MATCH"

    logger.info(
        "PO match result",
        extra={
            **log_ctx,
            "matchedPoId": po["poNumber"],
            "status": status,
            "variancePct": round(variance_pct, 4),
            "qtyVariancePct": round(qty_variance_pct, 4) if qty_variance_pct is not None else None,
            "discrepancies": discrepancies,
        },
    )

    return {
        "status": status,
        "poId": po["poNumber"],
        "amountVariancePct": round(variance_pct, 4),
        "poAmount": po_amount,
        "amountInvoiced": invoice_amount,
        "quantityVariancePct": round(qty_variance_pct, 4) if qty_variance_pct is not None else None,
        "poQuantity": po_quantity if po_quantity > 0 else None,
        "invoicedQuantity": invoiced_quantity,
        "discrepancies": discrepancies,
    }


def match_goods_receipt(
    po_number: str | None,
    invoiced_quantity: float,
    invoice_amount: float = 0.0,
    qty_tolerance: float = _GR_QTY_TOLERANCE,
    amount_tolerance: float = _GR_AMOUNT_TOLERANCE,
) -> dict[str, Any]:
    """Verify that goods/services for a PO have been received.

    Sums all GR quantities (and amounts) for the given PO (supports partial
    deliveries). Compares:
      - Invoice quantity vs total GR quantity received (within ``qty_tolerance``)
      - Invoice amount   vs total GR amount            (within ``amount_tolerance``)

    Returns
    -------
    ``{ status, grId, quantityReceived, quantityInvoiced, amountReceived,
        amountInvoiced, amountVariancePct, discrepancies }``

    ``status`` ∈ { "CONFIRMED", "PARTIAL", "NOT_RECEIVED" }
    """
    log_ctx = {
        "poNumber": po_number,
        "invoicedQty": invoiced_quantity,
        "invoiceAmount": invoice_amount,
    }

    if not po_number:
        logger.info("GR check skipped — no PO number", extra=log_ctx)
        return {
            "status": "NOT_RECEIVED",
            "grId": None,
            "quantityReceived": 0.0,
            "quantityInvoiced": invoiced_quantity,
            "amountReceived": 0.0,
            "amountInvoiced": invoice_amount,
            "amountVariancePct": None,
            "discrepancies": ["No PO number available for GR lookup"],
        }

    grs, _ = _gr_db.query_by_index(
        index_name="GSI-PONumber",
        partition_key="poNumber",
        partition_value=po_number,
        limit=20,
        scan_forward=False,
    )

    if not grs:
        logger.info("No GRs found for PO", extra=log_ctx)
        return {
            "status": "NOT_RECEIVED",
            "grId": None,
            "quantityReceived": 0.0,
            "quantityInvoiced": invoiced_quantity,
            "amountReceived": 0.0,
            "amountInvoiced": invoice_amount,
            "amountVariancePct": None,
            "discrepancies": [f"No goods receipt found for PO {po_number}"],
        }

    # Sum quantities and amounts across all GRs (handles split deliveries)
    total_received = sum(_to_float(gr.get("totalQuantityReceived", 0)) for gr in grs)
    total_amount_received = sum(_to_float(gr.get("totalAmount", 0)) for gr in grs)
    first_gr_id = grs[0].get("grId")

    # Quantity tolerance (AC-3.4.2): invoiced ≤ received + tolerance %
    tolerance_qty = invoiced_quantity * qty_tolerance
    discrepancies: list[str] = []

    if total_received < invoiced_quantity - tolerance_qty - _FLOAT_EPSILON:
        shortage = invoiced_quantity - total_received
        discrepancies.append(
            f"Quantity shortage: invoiced {invoiced_quantity:.0f}, "
            f"received {total_received:.0f} (short by {shortage:.0f})"
        )
        status = "PARTIAL"
    else:
        status = "CONFIRMED"

    # ── Amount check: Invoice amount vs GR amount ──────────────────────────────
    # Only enforced when the GR carries an amount and the invoice has one, so
    # legacy GR records without ``totalAmount`` do not fail the match.
    amount_variance_pct: float | None = None
    if total_amount_received > 0 and invoice_amount > 0:
        amount_variance_pct = (
            abs(total_amount_received - invoice_amount) / total_amount_received
        )
        if amount_variance_pct > amount_tolerance + _FLOAT_EPSILON:
            discrepancies.append(
                f"GR amount variance {amount_variance_pct * 100:.1f}%: "
                f"GR ${total_amount_received:.2f} vs Invoice ${invoice_amount:.2f}"
            )
            # An amount mismatch downgrades a confirmed receipt to PARTIAL so the
            # three-way match fails and the invoice is escalated.
            if status == "CONFIRMED":
                status = "PARTIAL"

    logger.info(
        "GR match result",
        extra={
            **log_ctx,
            "grId": first_gr_id,
            "totalReceived": total_received,
            "totalAmountReceived": total_amount_received,
            "amountVariancePct": round(amount_variance_pct, 4) if amount_variance_pct is not None else None,
            "status": status,
            "discrepancies": discrepancies,
        },
    )

    return {
        "status": status,
        "grId": first_gr_id,
        "quantityReceived": total_received,
        "quantityInvoiced": invoiced_quantity,
        "amountReceived": total_amount_received if total_amount_received > 0 else None,
        "amountInvoiced": invoice_amount,
        "amountVariancePct": round(amount_variance_pct, 4) if amount_variance_pct is not None else None,
        "discrepancies": discrepancies,
    }


def three_way_match(
    po_result: dict[str, Any],
    gr_result: dict[str, Any],
) -> dict[str, Any]:
    """Combine PO and GR results into the three-way match verdict.

    PASS iff: po_result["status"] == "MATCHED" AND gr_result["status"] == "CONFIRMED"
    Anything else → FAIL with accumulated discrepancies (AC-3.5.1, AC-3.5.2).
    """
    po_pass = po_result["status"] == "MATCHED"
    gr_pass = gr_result["status"] == "CONFIRMED"

    all_discrepancies: list[str] = (
        po_result.get("discrepancies", []) + gr_result.get("discrepancies", [])
    )

    if po_pass and gr_pass:
        status = "PASS"
    else:
        status = "FAIL"

    logger.info(
        "Three-way match result",
        extra={
            "status": status,
            "poStatus": po_result["status"],
            "grStatus": gr_result["status"],
            "discrepancies": all_discrepancies,
        },
    )

    return {
        "status": status,
        "poMatch": po_result,
        "grMatch": gr_result,
        "discrepancies": all_discrepancies,
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _to_float(value: Any) -> float:
    """Coerce a DynamoDB Decimal or str/int/float to float."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _vendor_names_match(name_a: str, name_b: str) -> bool:
    """Case-insensitive substring check between two vendor names.

    Uses a relaxed match suitable for MVP: returns True if either name
    contains the other (after normalisation).
    """
    a = _normalise_vendor(name_a)
    b = _normalise_vendor(name_b)
    return a in b or b in a


def _normalise_vendor(name: str) -> str:
    """Lower-case, strip common legal suffixes and punctuation."""
    stop_words = {"inc", "ltd", "llc", "co", "corp", "limited", "incorporated"}
    tokens = [
        t for t in name.lower().replace(",", " ").replace(".", " ").split()
        if t not in stop_words
    ]
    return " ".join(tokens)


def _closest_amount(pos: list[dict], target: float) -> dict:
    """Return the PO whose totalAmount is closest to target."""
    return min(
        pos,
        key=lambda p: abs(_to_float(p.get("totalAmount", 0)) - target),
    )


def _scan_pos_by_vendor(vendor_name: str) -> list[dict]:
    """Fallback scan for vendor name (case-insensitive, MVP only).

    Scans the full PO table and filters client-side.  Acceptable because
    the PO table has very few items (<20) in the demo environment.
    """
    try:
        response = _po_db.table.scan()
        items = response.get("Items", [])
        norm_target = _normalise_vendor(vendor_name)
        return [
            item for item in items
            if norm_target in _normalise_vendor(item.get("vendorName", ""))
            or _normalise_vendor(item.get("vendorName", "")) in norm_target
        ]
    except Exception as exc:
        logger.warning("PO scan fallback failed: %s", exc)
        return []
