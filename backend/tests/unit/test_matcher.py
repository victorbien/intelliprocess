"""Unit tests for PO matching, GR matching, and three-way match (FR-AP-003 to FR-AP-005).

Uses moto mock_aws to avoid real DynamoDB calls.
All DynamoDB numeric values stored as Decimal (required by boto3 resource API).
"""

import os
import pytest
from decimal import Decimal
from unittest.mock import patch

# ── moto setup (must happen before any boto3 import) ─────────────────────────

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID",  "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")

from moto import mock_aws   # noqa: E402  — import after env vars set


# ── Helpers ────────────────────────────────────────────────────────────────────

def _create_po_table(dynamodb, table_name: str):
    """Create a minimal PO table with GSI-VendorDate."""
    return dynamodb.create_table(
        TableName=table_name,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "poNumber",   "AttributeType": "S"},
            {"AttributeName": "vendorName", "AttributeType": "S"},
            {"AttributeName": "createdDate","AttributeType": "S"},
        ],
        KeySchema=[{"AttributeName": "poNumber", "KeyType": "HASH"}],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "GSI-VendorDate",
                "KeySchema": [
                    {"AttributeName": "vendorName",  "KeyType": "HASH"},
                    {"AttributeName": "createdDate", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    )


def _create_gr_table(dynamodb, table_name: str):
    """Create a minimal GR table with GSI-PONumber."""
    return dynamodb.create_table(
        TableName=table_name,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "grId",         "AttributeType": "S"},
            {"AttributeName": "poNumber",     "AttributeType": "S"},
            {"AttributeName": "receivedDate", "AttributeType": "S"},
        ],
        KeySchema=[{"AttributeName": "grId", "KeyType": "HASH"}],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "GSI-PONumber",
                "KeySchema": [
                    {"AttributeName": "poNumber",     "KeyType": "HASH"},
                    {"AttributeName": "receivedDate", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    )


@pytest.fixture()
def tables():
    """Spin up moto DynamoDB with PO and GR tables for each test."""
    with mock_aws():
        import boto3
        from app.config import settings

        ddb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_po_table(ddb, settings.PO_TABLE)
        _create_gr_table(ddb, settings.GR_TABLE)

        po_table = ddb.Table(settings.PO_TABLE)
        gr_table = ddb.Table(settings.GR_TABLE)

        # Seed a known PO
        po_table.put_item(Item={
            "poNumber":   "PO-2024-0456",
            "vendorName": "Acme Office Supplies Inc.",
            "createdDate": "2026-07-01",
            "totalAmount": Decimal("658.80"),
            "status":      "OPEN",
        })

        # Seed a second PO for fuzzy / multiple-candidate tests
        po_table.put_item(Item={
            "poNumber":   "PO-2024-0457",
            "vendorName": "TechParts Global Ltd.",
            "createdDate": "2026-07-05",
            "totalAmount": Decimal("15000.00"),
            "status":      "OPEN",
        })

        # Seed a GR for PO-2024-0456
        gr_table.put_item(Item={
            "grId":     "GR-2024-0789",
            "poNumber": "PO-2024-0456",
            "receivedDate": "2026-07-15",
            "totalQuantityReceived": Decimal("15"),
            "status": "COMPLETE",
        })

        # Reinitialise module-level DynamoClient singletons to use the mocked resource
        from app.services import matcher as _matcher_mod
        from app.services.dynamo import DynamoClient

        _matcher_mod._po_db = DynamoClient(settings.PO_TABLE)
        _matcher_mod._gr_db = DynamoClient(settings.GR_TABLE)

        yield {"po": po_table, "gr": gr_table}


# ══════════════════════════════════════════════════════════════════════════════
# PO Matching tests
# ══════════════════════════════════════════════════════════════════════════════

class TestMatchPurchaseOrder:

    def test_exact_match_within_tolerance(self, tables):
        """AC-3.3.1: exact PO number, vendor aligned, amount within 5%."""
        from app.services.matcher import match_purchase_order
        result = match_purchase_order(
            po_number="PO-2024-0456",
            vendor_name="Acme Office Supplies Inc.",
            invoice_amount=658.80,
        )
        assert result["status"] == "MATCHED"
        assert result["poId"] == "PO-2024-0456"
        assert result["discrepancies"] == []

    def test_exact_match_amount_at_5pct_boundary(self, tables):
        """Boundary: exactly 5 % variance → still MATCHED (not partial)."""
        from app.services.matcher import match_purchase_order
        over_5pct = 658.80 * 1.05
        result = match_purchase_order(
            po_number="PO-2024-0456",
            vendor_name="Acme Office Supplies Inc.",
            invoice_amount=over_5pct,
        )
        # 5 % exactly is at the boundary — rule is > 5 % triggers discrepancy
        assert result["status"] == "MATCHED"
        assert result["discrepancies"] == []

    def test_amount_over_tolerance_partial_match(self, tables):
        """AC-3.3.4: amount variance > 5% → PARTIAL_MATCH."""
        from app.services.matcher import match_purchase_order
        result = match_purchase_order(
            po_number="PO-2024-0456",
            vendor_name="Acme Office Supplies Inc.",
            invoice_amount=800.00,  # ~21 % over
        )
        assert result["status"] == "PARTIAL_MATCH"
        assert any("variance" in d.lower() for d in result["discrepancies"])

    def test_po_not_found_returns_no_match(self, tables):
        """AC-3.3.3: unknown PO number → NO_MATCH."""
        from app.services.matcher import match_purchase_order
        result = match_purchase_order(
            po_number="PO-NONEXISTENT",
            vendor_name="Some Vendor",
            invoice_amount=100.00,
        )
        assert result["status"] == "NO_MATCH"
        assert result["poId"] is None
        assert result["discrepancies"] != []

    def test_fuzzy_match_no_po_number(self, tables):
        """AC-3.3.2: no PO reference → fall back to vendor fuzzy match."""
        from app.services.matcher import match_purchase_order
        result = match_purchase_order(
            po_number=None,
            vendor_name="Acme Office Supplies Inc.",
            invoice_amount=658.80,
        )
        # May be MATCHED or PARTIAL_MATCH depending on vendor normalisation
        assert result["status"] in ("MATCHED", "PARTIAL_MATCH")
        assert result["poId"] == "PO-2024-0456"

    def test_vendor_mismatch_causes_partial(self, tables):
        """Vendor name completely different → adds discrepancy → PARTIAL_MATCH."""
        from app.services.matcher import match_purchase_order
        result = match_purchase_order(
            po_number="PO-2024-0456",
            vendor_name="Totally Different Company",
            invoice_amount=658.80,
        )
        assert result["status"] == "PARTIAL_MATCH"
        assert any("vendor" in d.lower() for d in result["discrepancies"])

    def test_result_contains_amount_variance_pct(self, tables):
        from app.services.matcher import match_purchase_order
        result = match_purchase_order(
            po_number="PO-2024-0456",
            vendor_name="Acme Office Supplies Inc.",
            invoice_amount=658.80,
        )
        assert "amountVariancePct" in result
        assert result["amountVariancePct"] == pytest.approx(0.0, abs=1e-4)


# ══════════════════════════════════════════════════════════════════════════════
# GR Matching tests
# ══════════════════════════════════════════════════════════════════════════════

class TestMatchGoodsReceipt:

    def test_confirmed_when_qty_matches(self, tables):
        """AC-3.4.2: invoiced qty ≤ received + 2% → CONFIRMED."""
        from app.services.matcher import match_goods_receipt
        result = match_goods_receipt(po_number="PO-2024-0456", invoiced_quantity=15)
        assert result["status"] == "CONFIRMED"
        assert result["grId"] == "GR-2024-0789"
        assert result["discrepancies"] == []

    def test_confirmed_within_tolerance(self, tables):
        """Invoiced qty slightly above received but within 2% tolerance."""
        from app.services.matcher import match_goods_receipt
        # 15 received, 15.2 invoiced — 0.2/15 ≈ 1.3 % < 2 %
        result = match_goods_receipt(po_number="PO-2024-0456", invoiced_quantity=15.2)
        assert result["status"] == "CONFIRMED"

    def test_partial_when_over_tolerance(self, tables):
        """AC-3.4.3: invoiced > received beyond 2% → PARTIAL."""
        from app.services.matcher import match_goods_receipt
        # 15 received, 20 invoiced → 33 % shortage
        result = match_goods_receipt(po_number="PO-2024-0456", invoiced_quantity=20)
        assert result["status"] == "PARTIAL"
        assert any("shortage" in d.lower() for d in result["discrepancies"])

    def test_not_received_when_no_gr(self, tables):
        """AC-3.4.4: no GR for PO → NOT_RECEIVED."""
        from app.services.matcher import match_goods_receipt
        result = match_goods_receipt(po_number="PO-NO-GR", invoiced_quantity=5)
        assert result["status"] == "NOT_RECEIVED"
        assert result["grId"] is None

    def test_not_received_when_no_po_number(self, tables):
        """GR check with None po_number → NOT_RECEIVED."""
        from app.services.matcher import match_goods_receipt
        result = match_goods_receipt(po_number=None, invoiced_quantity=10)
        assert result["status"] == "NOT_RECEIVED"

    def test_result_contains_quantity_fields(self, tables):
        from app.services.matcher import match_goods_receipt
        result = match_goods_receipt(po_number="PO-2024-0456", invoiced_quantity=15)
        assert "quantityReceived" in result
        assert "quantityInvoiced" in result
        assert result["quantityInvoiced"] == 15


# ══════════════════════════════════════════════════════════════════════════════
# Three-way match tests
# ══════════════════════════════════════════════════════════════════════════════

class TestThreeWayMatch:

    def _po_match(self, status="MATCHED", discrepancies=None):
        return {"status": status, "poId": "PO-001", "amountVariancePct": 0.0,
                "discrepancies": discrepancies or []}

    def _gr_match(self, status="CONFIRMED", discrepancies=None):
        return {"status": status, "grId": "GR-001", "quantityReceived": 10.0,
                "quantityInvoiced": 10.0, "discrepancies": discrepancies or []}

    def test_pass_when_both_matched_and_confirmed(self):
        """AC-3.5.1: MATCHED + CONFIRMED → THREE_WAY_MATCH_PASS."""
        from app.services.matcher import three_way_match
        result = three_way_match(self._po_match("MATCHED"), self._gr_match("CONFIRMED"))
        assert result["status"] == "PASS"
        assert result["discrepancies"] == []

    def test_fail_when_po_partial(self):
        """AC-3.5.2: PARTIAL_MATCH → FAIL."""
        from app.services.matcher import three_way_match
        result = three_way_match(
            self._po_match("PARTIAL_MATCH", ["Amount variance 10%"]),
            self._gr_match("CONFIRMED"),
        )
        assert result["status"] == "FAIL"
        assert "Amount variance 10%" in result["discrepancies"]

    def test_fail_when_po_no_match(self):
        from app.services.matcher import three_way_match
        result = three_way_match(
            self._po_match("NO_MATCH", ["PO not found"]),
            self._gr_match("CONFIRMED"),
        )
        assert result["status"] == "FAIL"

    def test_fail_when_gr_partial(self):
        """AC-3.5.2: GR PARTIAL → FAIL."""
        from app.services.matcher import three_way_match
        result = three_way_match(
            self._po_match("MATCHED"),
            self._gr_match("PARTIAL", ["Quantity shortage"]),
        )
        assert result["status"] == "FAIL"
        assert "Quantity shortage" in result["discrepancies"]

    def test_fail_when_gr_not_received(self):
        from app.services.matcher import three_way_match
        result = three_way_match(
            self._po_match("MATCHED"),
            self._gr_match("NOT_RECEIVED", ["No goods receipt found"]),
        )
        assert result["status"] == "FAIL"

    def test_discrepancies_accumulate_from_both(self):
        """Both PO and GR discrepancies appear in combined list."""
        from app.services.matcher import three_way_match
        result = three_way_match(
            self._po_match("PARTIAL_MATCH", ["PO amount variance"]),
            self._gr_match("PARTIAL",       ["Quantity shortage"]),
        )
        assert "PO amount variance" in result["discrepancies"]
        assert "Quantity shortage"  in result["discrepancies"]

    def test_result_contains_po_and_gr_sub_results(self):
        from app.services.matcher import three_way_match
        result = three_way_match(self._po_match(), self._gr_match())
        assert "poMatch" in result
        assert "grMatch" in result


# ══════════════════════════════════════════════════════════════════════════════
# Vendor name normalisation tests
# ══════════════════════════════════════════════════════════════════════════════

class TestVendorNormalisation:
    """Tests for the _vendor_names_match helper (indirectly via match_purchase_order)."""

    def test_case_insensitive(self):
        from app.services.matcher import _vendor_names_match
        assert _vendor_names_match("Acme Inc.", "acme inc.")

    def test_strips_legal_suffixes(self):
        from app.services.matcher import _vendor_names_match
        assert _vendor_names_match("Acme Office Supplies Inc.", "Acme Office Supplies")

    def test_completely_different_names_no_match(self):
        from app.services.matcher import _vendor_names_match
        assert not _vendor_names_match("Alpha Corp", "Beta LLC")
