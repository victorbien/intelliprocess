"""Integration tests for Module 4 dashboard & admin API endpoints.

Covers:
- GET  /dashboard/stats        (FR-AP-009, AC-3.9.x)
- POST /admin/seed-data        (AC-5.1.4)
- POST /purchase-orders/upload (AC-5.1.1, AC-5.1.3)
- POST /goods-receipts/upload  (AC-5.1.2, AC-5.1.3)
- POST /documents/sync         (FR-CROSS-001)

RBAC enforcement is verified for each endpoint.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.middleware.auth import CurrentUser, get_current_user
from app.models.enums import UserRole


def _admin():
    return CurrentUser(user_id="admin-001", email="admin@test.com", roles=[UserRole.ADMIN])


def _manager():
    return CurrentUser(user_id="mgr-001", email="mgr@test.com", roles=[UserRole.FINANCE_MANAGER])


def _clerk():
    return CurrentUser(user_id="clerk-001", email="clerk@test.com", roles=[UserRole.AP_CLERK])


def _staff():
    return CurrentUser(user_id="staff-001", email="staff@test.com", roles=[UserRole.STAFF])


@pytest.fixture(autouse=True)
def cleanup_overrides():
    yield
    app.dependency_overrides.clear()


async def _post(path, json=None):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(path, json=json or {})


async def _get(path):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


@pytest.mark.asyncio
class TestDashboardStats:
    """GET /dashboard/stats."""

    @patch("app.routers.dashboard._invoice_db")
    async def test_manager_can_view_stats(self, mock_db):
        mock_db.scan_all.return_value = [
            {
                "documentId": "d1", "fileName": "INV-1.pdf", "status": "APPROVED",
                "updatedAt": "2026-07-25T10:05:00Z",
                "approvalDecision": {"approver": "SYSTEM"},
                "processingDurationMs": Decimal("28000"),
            },
            {
                "documentId": "d2", "fileName": "INV-2.pdf", "status": "ESCALATED",
                "updatedAt": "2026-07-25T10:04:00Z",
                "approvalDecision": {"reason": "Amount exceeds threshold"},
                "processingDurationMs": Decimal("32000"),
            },
        ]
        app.dependency_overrides[get_current_user] = lambda: _manager()

        resp = await _get("/dashboard/stats")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["totalInvoices"] == 2
        assert data["statusCounts"]["approved"] == 1
        assert data["statusCounts"]["escalated"] == 1
        assert data["autoApprovalRate"] == 50.0
        assert data["avgProcessingTimeSec"] == 30.0
        assert data["recentActivity"][0]["action"] == "Auto-approved"

    @patch("app.routers.dashboard._invoice_db")
    async def test_admin_can_view_stats(self, mock_db):
        mock_db.scan_all.return_value = []
        app.dependency_overrides[get_current_user] = lambda: _admin()

        resp = await _get("/dashboard/stats")

        assert resp.status_code == 200
        assert resp.json()["data"]["totalInvoices"] == 0

    async def test_clerk_cannot_view_stats(self):
        app.dependency_overrides[get_current_user] = lambda: _clerk()
        resp = await _get("/dashboard/stats")
        assert resp.status_code == 403

    @patch("app.routers.dashboard._invoice_db")
    async def test_scan_failure_returns_500_without_leaking_details(self, mock_db):
        from botocore.exceptions import ClientError

        mock_db.scan_all.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "boom"}}, "Scan"
        )
        app.dependency_overrides[get_current_user] = lambda: _admin()

        resp = await _get("/dashboard/stats")

        assert resp.status_code == 500
        error = resp.json()["error"]
        assert "boom" not in error
        assert "test-invoices" not in error


@pytest.mark.asyncio
class TestSeedData:
    """POST /admin/seed-data."""

    @patch("app.routers.dashboard._gr_db")
    @patch("app.routers.dashboard._po_db")
    async def test_admin_seeds_default_data(self, mock_po, mock_gr):
        mock_po.put_item = MagicMock()
        mock_gr.put_item = MagicMock()
        app.dependency_overrides[get_current_user] = lambda: _admin()

        resp = await _post("/admin/seed-data", {"dataSet": "default"})

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["purchaseOrdersCreated"] == 5
        assert data["goodsReceiptsCreated"] == 5
        assert mock_po.put_item.call_count == 5
        assert mock_gr.put_item.call_count == 5
        # Numeric fields must be Decimal for DynamoDB.
        first_po = mock_po.put_item.call_args_list[0][0][0]
        assert isinstance(first_po["totalAmount"], Decimal)

    @patch("app.routers.dashboard._gr_db")
    @patch("app.routers.dashboard._po_db")
    async def test_defaults_to_default_dataset(self, mock_po, mock_gr):
        mock_po.put_item = MagicMock()
        mock_gr.put_item = MagicMock()
        app.dependency_overrides[get_current_user] = lambda: _admin()

        resp = await _post("/admin/seed-data", {})  # no dataSet

        assert resp.status_code == 200
        assert resp.json()["data"]["purchaseOrdersCreated"] == 5

    async def test_unknown_dataset_returns_400(self):
        app.dependency_overrides[get_current_user] = lambda: _admin()
        resp = await _post("/admin/seed-data", {"dataSet": "bogus"})
        assert resp.status_code == 400

    async def test_non_admin_cannot_seed(self):
        app.dependency_overrides[get_current_user] = lambda: _manager()
        resp = await _post("/admin/seed-data", {"dataSet": "default"})
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestPurchaseOrderUpload:
    """POST /purchase-orders/upload."""

    @patch("app.routers.dashboard._po_db")
    async def test_admin_uploads_po(self, mock_po):
        mock_po.put_item = MagicMock()
        app.dependency_overrides[get_current_user] = lambda: _admin()

        resp = await _post(
            "/purchase-orders/upload",
            {
                "poNumber": "PO-2024-9999",
                "vendorName": "New Vendor Inc.",
                "totalAmount": 1234.56,
                "department": "Ops",
            },
        )

        assert resp.status_code == 201
        assert resp.json()["data"]["poNumber"] == "PO-2024-9999"
        item = mock_po.put_item.call_args[0][0]
        assert item["poNumber"] == "PO-2024-9999"
        assert isinstance(item["totalAmount"], Decimal)
        assert item["totalAmount"] == Decimal("1234.56")
        assert item["createdDate"]  # auto-filled

    async def test_rejects_non_positive_amount(self):
        app.dependency_overrides[get_current_user] = lambda: _admin()
        resp = await _post(
            "/purchase-orders/upload",
            {"poNumber": "PO-1", "vendorName": "V", "totalAmount": 0},
        )
        assert resp.status_code == 400

    async def test_rejects_malformed_po_number(self):
        """Keys with unsafe characters are rejected (security)."""
        app.dependency_overrides[get_current_user] = lambda: _admin()
        resp = await _post(
            "/purchase-orders/upload",
            {"poNumber": "PO 1;DROP", "vendorName": "V", "totalAmount": 10},
        )
        assert resp.status_code == 400

    @patch("app.routers.dashboard._po_db")
    async def test_currency_is_normalised_uppercase(self, mock_po):
        mock_po.put_item = MagicMock()
        app.dependency_overrides[get_current_user] = lambda: _admin()

        resp = await _post(
            "/purchase-orders/upload",
            {"poNumber": "PO-2", "vendorName": "V", "totalAmount": 10, "currency": "usd"},
        )

        assert resp.status_code == 201
        item = mock_po.put_item.call_args[0][0]
        assert item["currency"] == "USD"

    async def test_non_admin_cannot_upload_po(self):
        app.dependency_overrides[get_current_user] = lambda: _clerk()
        resp = await _post(
            "/purchase-orders/upload",
            {"poNumber": "PO-1", "vendorName": "V", "totalAmount": 10},
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestGoodsReceiptUpload:
    """POST /goods-receipts/upload."""

    @patch("app.routers.dashboard._po_db")
    @patch("app.routers.dashboard._gr_db")
    async def test_admin_uploads_gr(self, mock_gr, mock_po):
        mock_gr.put_item = MagicMock()
        mock_po.get_item.return_value = {"poNumber": "PO-2024-9999"}  # PO exists
        app.dependency_overrides[get_current_user] = lambda: _admin()

        resp = await _post(
            "/goods-receipts/upload",
            {"grId": "GR-9999", "poNumber": "PO-2024-9999", "totalQuantityReceived": 40},
        )

        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["grId"] == "GR-9999"
        assert data["poNumber"] == "PO-2024-9999"
        item = mock_gr.put_item.call_args[0][0]
        assert isinstance(item["totalQuantityReceived"], Decimal)

    @patch("app.routers.dashboard._po_db")
    @patch("app.routers.dashboard._gr_db")
    async def test_gr_without_existing_po_rejected(self, mock_gr, mock_po):
        """AC-5.1.2: a GR must be linked to an existing PO."""
        mock_gr.put_item = MagicMock()
        mock_po.get_item.return_value = None  # PO does not exist
        app.dependency_overrides[get_current_user] = lambda: _admin()

        resp = await _post(
            "/goods-receipts/upload",
            {"grId": "GR-9999", "poNumber": "PO-DOES-NOT-EXIST", "totalQuantityReceived": 40},
        )

        assert resp.status_code == 400
        assert "not found" in resp.json()["error"].lower()
        mock_gr.put_item.assert_not_called()

    async def test_non_admin_cannot_upload_gr(self):
        app.dependency_overrides[get_current_user] = lambda: _staff()
        resp = await _post(
            "/goods-receipts/upload",
            {"grId": "GR-1", "poNumber": "PO-1", "totalQuantityReceived": 5},
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestKnowledgeBaseSync:
    """POST /documents/sync."""

    async def test_admin_triggers_sync_dev_fallback(self):
        # STAGE=dev in conftest -> simulated sync, real syncJobId returned.
        app.dependency_overrides[get_current_user] = lambda: _admin()

        resp = await _post("/documents/sync")

        assert resp.status_code == 202
        data = resp.json()["data"]
        assert data["syncJobId"].startswith("local-sync-")
        assert "simulated" in data["message"].lower()

    async def test_non_admin_cannot_sync(self):
        app.dependency_overrides[get_current_user] = lambda: _manager()
        resp = await _post("/documents/sync")
        assert resp.status_code == 403

    @patch("app.routers.documents.start_sync")
    async def test_sync_failure_returns_503(self, mock_sync):
        from app.services.knowledge_base import KnowledgeBaseSyncError

        mock_sync.side_effect = KnowledgeBaseSyncError("Failed to start the knowledge base sync.")
        app.dependency_overrides[get_current_user] = lambda: _admin()

        resp = await _post("/documents/sync")

        assert resp.status_code == 503
