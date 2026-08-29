"""Data access tools for the RAG Records Assistant.

Each public function is a *tool* callable by the StructuredQueryHandler.
Docstrings are written as LLM tool descriptions — they state what each tool
is for and when to use it.

Design notes
------------
- All functions use the shared ``DynamoClient`` wrapper; no direct boto3 calls.
- ``Decimal`` values returned from DynamoDB are converted to ``int`` or
  ``float`` so results are JSON-serialisable out of the box.
- ``extraction`` is a nested map stored inside each invoice document. Fields
  like ``vendorName`` and ``totalAmount`` live there and are **not** indexed;
  all filtering on those fields is done in-process after fetching candidate
  records.
- Invoices in PROCESSING status have no ``extraction`` key. Every code path
  that reads ``extraction`` guards against its absence.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from botocore.exceptions import ClientError
from strands import tool

from app.config import settings
from app.services.dynamo import DynamoClient

logger = logging.getLogger(__name__)

# ── Module-level DynamoClient singletons (lazy-initialised) ──────────────────

_invoice_client = DynamoClient(settings.INVOICE_TABLE)
_po_client = DynamoClient(settings.PO_TABLE)
_gr_client = DynamoClient(settings.GR_TABLE)


# ── Decimal → Python numeric conversion ──────────────────────────────────────

def _to_number(value: Any) -> int | float | Any:
    """Convert a Decimal to int (if whole) or float; leave other types as-is."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return value


def _convert_decimals(obj: Any) -> Any:
    """Recursively convert all Decimal values in a dict/list structure."""
    if isinstance(obj, dict):
        return {k: _convert_decimals(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_decimals(item) for item in obj]
    return _to_number(obj)


# ── Invoice tools ─────────────────────────────────────────────────────────────

@tool
def query_invoices(
    vendor_name: str | None = None,
    status: str | None = None,
    amount_min: float | None = None,
    amount_max: float | None = None,
    match_status: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Search and filter invoices.

    Use this tool when the user asks about invoices in aggregate or wants a
    list filtered by criteria — for example:
    - "Show me all escalated invoices"
    - "Which invoices are from Acme?"
    - "List invoices over $10,000"
    - "How many invoices failed the three-way match?"

    Parameters
    ----------
    vendor_name:
        Case-insensitive substring to match against ``extraction.vendorName``.
        Pass ``None`` to skip vendor filtering.
    status:
        Exact invoice status to filter by (e.g. ``"ESCALATED"``, ``"APPROVED"``,
        ``"PROCESSING"``). When provided, the GSI-StatusDate index is used for
        efficient retrieval. Pass ``None`` to scan all statuses.
    amount_min:
        Inclusive lower bound on ``extraction.totalAmount``. Pass ``None`` to
        skip.
    amount_max:
        Inclusive upper bound on ``extraction.totalAmount``. Pass ``None`` to
        skip.
    match_status:
        Filter by ``matchResult.threeWayMatch`` value (e.g. ``"PASS"``,
        ``"FAIL"``). Pass ``None`` to skip.
    limit:
        Maximum number of invoices to return after all in-process filters have
        been applied. Defaults to 50.

    Returns
    -------
    dict with keys:
        ``invoices``     — list of matched invoice dicts (Decimals converted),
        ``count``        — number of matched invoices,
        ``total_amount`` — sum of ``extraction.totalAmount`` for matched
                           invoices (0.0 if none have an extraction block).
    """
    candidates: list[dict] = []

    if status:
        # Use GSI-StatusDate for efficient status-keyed retrieval.
        # Paginate until exhausted — we must see every record to produce an
        # accurate count and total_amount, regardless of `limit`.
        last_key = None
        while True:
            batch, last_key = _invoice_client.query_by_index(
                index_name="GSI-StatusDate",
                partition_key="status",
                partition_value=status,
                limit=1000,  # fetch large pages; stop only when DynamoDB says done
                scan_forward=False,  # most-recent first
                exclusive_start_key=last_key,
            )
            candidates.extend(batch)
            if last_key is None:
                break
    else:
        # No status filter — full table scan required (acceptable for MVP scale).
        # Paginate until exhausted for accurate counts and totals.
        try:
            response = _invoice_client.table.scan()
            candidates = response.get("Items", [])
            while "LastEvaluatedKey" in response:
                response = _invoice_client.table.scan(
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                )
                candidates.extend(response.get("Items", []))
        except ClientError:
            logger.exception("tools.query_invoices scan failed")
            raise

    # ── In-process filters ────────────────────────────────────────────────────
    results: list[dict] = []
    total_amount = 0.0

    for inv in candidates:
        extraction: dict = inv.get("extraction") or {}

        # Vendor name: case-insensitive substring match
        if vendor_name:
            stored_vendor: str = extraction.get("vendorName", "")
            if vendor_name.lower() not in stored_vendor.lower():
                continue

        # Amount filters — skip invoices without an extraction block
        inv_amount = extraction.get("totalAmount")
        if amount_min is not None or amount_max is not None:
            if inv_amount is None:
                continue  # no extraction data (e.g. PROCESSING); skip amount filters
            inv_amount_f = float(inv_amount)
            if amount_min is not None and inv_amount_f < amount_min:
                continue
            if amount_max is not None and inv_amount_f > amount_max:
                continue

        # Three-way match status filter
        if match_status:
            three_way = (inv.get("matchResult") or {}).get("threeWayMatch", "")
            if three_way != match_status:
                continue

        results.append(_convert_decimals(inv))
        if inv_amount is not None:
            total_amount += float(inv_amount)

    # `count` and `total_amount` reflect ALL matching records.
    # Only the returned list is truncated to `limit`.
    return {
        "invoices": results[:limit],
        "count": len(results),
        "total_amount": round(total_amount, 2),
    }


@tool
def count_invoices_by_status() -> dict[str, int]:
    """Return a count of invoices grouped by status.

    Use this tool when the user asks for a summary or breakdown of invoice
    statuses — for example:
    - "How many invoices are there in each status?"
    - "How many invoices are pending approval?" (status = ESCALATED)
    - "Give me an overview of the invoice pipeline."

    Returns
    -------
    dict mapping status string to count, e.g.
    ``{"APPROVED": 1, "ESCALATED": 2, "PROCESSING": 1}``.
    """
    return _invoice_client.scan_count_by_status()


@tool
def get_invoice_detail(document_id: str) -> dict[str, Any] | None:
    """Retrieve the full record for a single invoice by its document ID.

    Use this tool when the user asks about a specific invoice by ID or file
    name, or when you need complete extraction and match details to answer a
    question — for example:
    - "What is the status of invoice f47ac10b?"
    - "Show me the line items on INV-2024-0891."
    - "Was invoice a1b2c3d4 approved?"

    Parameters
    ----------
    document_id:
        The UUID primary key of the invoice (``documentId`` attribute).

    Returns
    -------
    Full invoice dict with Decimals converted, or ``None`` if not found.
    """
    item = _invoice_client.get_item({"documentId": document_id})
    if item is None:
        return None
    return _convert_decimals(item)


# ── Purchase Order tools ──────────────────────────────────────────────────────

@tool
def query_purchase_orders(
    po_number: str | None = None,
    vendor_name: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Look up purchase orders by PO number, vendor, or status.

    Use this tool when the user asks about purchase orders — for example:
    - "What is the status of PO-2024-0456?"
    - "Show me all open POs for TechParts."
    - "Which POs are still open?"

    At least one of ``po_number``, ``vendor_name``, or ``status`` should be
    provided. If all are ``None``, a full table scan is performed (acceptable
    for MVP scale).

    Parameters
    ----------
    po_number:
        Exact PO number to look up (primary key lookup). When provided, only
        this PO is returned.
    vendor_name:
        Case-insensitive substring to match against ``vendorName``. Applied
        in-process.
    status:
        Exact PO status string to filter by (e.g. ``"OPEN"``, ``"CLOSED"``).
        Applied in-process.

    Returns
    -------
    dict with keys:
        ``purchase_orders`` — list of matched PO dicts (Decimals converted),
        ``count``           — number of matched POs.
    """
    candidates: list[dict] = []

    if po_number:
        # Direct primary key lookup — most efficient path.
        item = _po_client.get_item({"poNumber": po_number})
        candidates = [item] if item else []
    else:
        # Full table scan — acceptable for MVP with <100 POs.
        try:
            response = _po_client.table.scan()
            candidates = response.get("Items", [])
            while "LastEvaluatedKey" in response:
                response = _po_client.table.scan(
                    ExclusiveStartKey=response["LastEvaluatedKey"]
                )
                candidates.extend(response.get("Items", []))
        except ClientError:
            logger.exception("tools.query_purchase_orders scan failed")
            raise

    # ── In-process filters ────────────────────────────────────────────────────
    results: list[dict] = []
    for po in candidates:
        if vendor_name:
            stored: str = po.get("vendorName", "")
            if vendor_name.lower() not in stored.lower():
                continue
        if status:
            if po.get("status", "") != status:
                continue
        results.append(_convert_decimals(po))

    return {"purchase_orders": results, "count": len(results)}


# ── Goods Receipt tools ───────────────────────────────────────────────────────

@tool
def query_goods_receipts(po_number: str) -> dict[str, Any]:
    """Retrieve all goods receipts linked to a specific purchase order.

    Use this tool when the user asks whether goods have been received for a
    PO, or wants to verify the three-way match evidence — for example:
    - "Have the goods for PO-2024-0456 been received?"
    - "What is the GR status for PO-2024-0457?"
    - "Show me the delivery confirmation for the Acme order."

    Parameters
    ----------
    po_number:
        The PO number to look up goods receipts for (exact match).

    Returns
    -------
    dict with keys:
        ``goods_receipts`` — list of GR dicts (Decimals converted),
        ``count``          — number of GRs found,
        ``all_complete``   — ``True`` if every GR has status ``"COMPLETE"``.
    """
    items, _ = _gr_client.query_by_index(
        index_name="GSI-PONumber",
        partition_key="poNumber",
        partition_value=po_number,
        limit=50,
        scan_forward=True,
    )

    converted = [_convert_decimals(item) for item in items]
    all_complete = bool(converted) and all(
        gr.get("status") == "COMPLETE" for gr in converted
    )

    return {
        "goods_receipts": converted,
        "count": len(converted),
        "all_complete": all_complete,
    }

# ── Supplier analytics tools ──────────────────────────────────────────────────

def _scan_all_invoices() -> list[dict]:
    """Return every invoice item, paginating the table scan to exhaustion.

    Aggregation tools must observe all records to produce accurate totals, so
    this helper walks ``LastEvaluatedKey`` until DynamoDB reports no more pages.
    ``ClientError`` is logged and re-raised, consistent with ``query_invoices``.
    """
    try:
        response = _invoice_client.table.scan()
        items: list[dict] = response.get("Items", [])
        while "LastEvaluatedKey" in response:
            response = _invoice_client.table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))
        return items
    except ClientError:
        logger.exception("tools._scan_all_invoices scan failed")
        raise


@tool
def top_suppliers(limit: int = 10) -> dict[str, Any]:
    """Rank suppliers by total invoice spend.

    Use this tool when the user asks which vendors account for the most
    spend or business — for example:
    - "Who are our top suppliers?"
    - "Which vendors do we spend the most with?"
    - "Show me the top 5 suppliers by total invoiced amount."

    Parameters
    ----------
    limit:
        Maximum number of suppliers to return (capped at 10). Defaults to 10.

    Returns
    -------
    dict with keys:
        ``suppliers`` — list of {vendorName, totalAmount, invoiceCount},
                        sorted by totalAmount descending, length <= 10,
        ``count``     — number of suppliers in the ranked list.
    """
    totals: dict[str, float] = {}
    counts: dict[str, int] = {}

    for inv in _scan_all_invoices():
        extraction = inv.get("extraction")
        if not extraction:
            # Skip invoices without an extraction block (e.g. PROCESSING).
            continue
        vendor = extraction.get("vendorName")
        if vendor is None:
            continue
        amount = extraction.get("totalAmount")
        totals[vendor] = totals.get(vendor, 0.0) + (
            float(amount) if amount is not None else 0.0
        )
        counts[vendor] = counts.get(vendor, 0) + 1

    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    cap = min(limit, 10)
    suppliers = [
        {
            "vendorName": vendor,
            "totalAmount": total,
            "invoiceCount": counts[vendor],
        }
        for vendor, total in ranked[:cap]
    ]

    return _convert_decimals({"suppliers": suppliers, "count": len(suppliers)})


@tool
def supplier_order_accuracy(limit: int = 10) -> dict[str, Any]:
    """Rank suppliers by order accuracy (three-way match rate).

    Use this tool when the user asks which vendors are most reliable against
    purchase orders and goods receipts — for example:
    - "Which suppliers have the best order accuracy?"
    - "Rank vendors by match rate."
    - "Who are our most reliable suppliers?"

    Parameters
    ----------
    limit:
        Maximum number of suppliers to return (capped at 10). Defaults to 10.

    Returns
    -------
    dict with keys:
        ``suppliers`` — list of {vendorName, matchRate, invoicesEvaluated},
                        sorted by matchRate descending, length <= 10,
        ``count``     — number of suppliers in the ranked list.
    """
    evaluated: dict[str, int] = {}
    matched: dict[str, int] = {}

    for inv in _scan_all_invoices():
        extraction = inv.get("extraction") or {}
        vendor = extraction.get("vendorName")
        if vendor is None:
            continue
        match_result = inv.get("matchResult")
        if not match_result:
            # Only invoices carrying a matchResult block are evaluated.
            continue
        evaluated[vendor] = evaluated.get(vendor, 0) + 1
        # The authoritative accuracy verdict is the overall three-way match
        # result. poMatch/grMatch carry their own vocabularies
        # ("MATCHED"/"CONFIRMED"), while threeWayMatch is "PASS" only when both
        # the purchase order and goods receipt reconcile.
        if match_result.get("threeWayMatch") == "PASS":
            matched[vendor] = matched.get(vendor, 0) + 1

    suppliers_all = []
    for vendor, evaluated_count in evaluated.items():
        if evaluated_count == 0:
            # Guard against zero denominator; exclude from ranking.
            continue
        match_rate = matched.get(vendor, 0) / evaluated_count
        suppliers_all.append(
            {
                "vendorName": vendor,
                "matchRate": match_rate,
                "invoicesEvaluated": evaluated_count,
            }
        )

    suppliers_all.sort(key=lambda s: s["matchRate"], reverse=True)
    cap = min(limit, 10)
    suppliers = suppliers_all[:cap]

    return _convert_decimals({"suppliers": suppliers, "count": len(suppliers)})


@tool
def supplier_lowest_prices() -> dict[str, Any]:
    """Compare suppliers by average pricing.

    Use this tool when the user asks which vendors are cheapest or wants a
    price comparison — for example:
    - "Which suppliers have the lowest prices?"
    - "Compare vendors by average invoice amount."
    - "What's the average line-item price per supplier?"

    Returns
    -------
    dict with keys:
        ``suppliers`` — list of {vendorName, avgInvoiceAmount, avgUnitPrice},
                        where avgUnitPrice is null for suppliers with no line
                        items,
        ``count``     — number of suppliers reported.
    """
    invoice_amounts: dict[str, list[float]] = {}
    unit_prices: dict[str, list[float]] = {}

    for inv in _scan_all_invoices():
        extraction = inv.get("extraction")
        if not extraction:
            # Skip invoices without an extraction block.
            continue
        vendor = extraction.get("vendorName")
        if vendor is None:
            continue

        invoice_amounts.setdefault(vendor, [])
        unit_prices.setdefault(vendor, [])

        amount = extraction.get("totalAmount")
        if amount is not None:
            invoice_amounts[vendor].append(float(amount))

        for item in extraction.get("lineItems") or []:
            unit_price = (item or {}).get("unitPrice")
            if unit_price is not None:
                unit_prices[vendor].append(float(unit_price))

    suppliers = []
    for vendor in invoice_amounts:
        amounts = invoice_amounts[vendor]
        prices = unit_prices.get(vendor, [])
        avg_invoice_amount = sum(amounts) / len(amounts) if amounts else 0.0
        avg_unit_price = sum(prices) / len(prices) if prices else None
        suppliers.append(
            {
                "vendorName": vendor,
                "avgInvoiceAmount": avg_invoice_amount,
                "avgUnitPrice": avg_unit_price,
            }
        )

    return _convert_decimals({"suppliers": suppliers, "count": len(suppliers)})
