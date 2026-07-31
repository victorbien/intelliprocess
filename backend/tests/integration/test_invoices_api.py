"""Integration tests for invoice API endpoints."""

import pytest
from unittest.mock import patch, MagicMock
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.middleware.auth import get_current_user, CurrentUser
from app.models.enums import UserRole, InvoiceStatus


def _clerk_user():
    return CurrentUser(user_id="clerk-001", email="clerk@test.com", roles=[UserRole.AP_CLERK])


def _manager_user():
    return CurrentUser(user_id="mgr-001", email="mgr@test.com", roles=[UserRole.FINANCE_MANAGER])


def _staff_user():
    return CurrentUser(user_id="staff-001", email="staff@test.com", roles=[UserRole.STAFF])


@pytest.fixture(autouse=True)
def cleanup_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
class TestInvoiceUpload:
    """Tests for POST /invoices/upload."""

    @patch("app.routers.invoices._s3")
    @patch("app.routers.invoices._invoice_db")
    async def test_upload_returns_presigned_url(self, mock_db, mock_s3):
        """Valid upload request returns 201 with presigned URL and documentId."""
        mock_s3.generate_presigned_post.return_value = {
            "url": "https://s3.amazonaws.com/test-bucket",
            "fields": {"key": "invoices/abc/test.pdf", "Policy": "xxx"},
        }
        mock_db.put_item = MagicMock()

        app.dependency_overrides[get_current_user] = lambda: _clerk_user()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/invoices/upload",
                json={"fileName": "invoice.pdf", "contentType": "application/pdf"},
            )

        assert response.status_code == 201
        data = response.json()["data"]
        assert "documentId" in data
        assert data["uploadUrl"]["url"] == "https://s3.amazonaws.com/test-bucket"
        assert data["expiresIn"] == 300
        mock_db.put_item.assert_called_once()

    @patch("app.routers.invoices._s3")
    @patch("app.routers.invoices._invoice_db")
    async def test_upload_rejects_unsupported_format(self, mock_db, mock_s3):
        """Unsupported content type returns 400 with descriptive error."""
        app.dependency_overrides[get_current_user] = lambda: _clerk_user()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/invoices/upload",
                json={"fileName": "data.xlsx", "contentType": "application/vnd.ms-excel"},
            )

        assert response.status_code == 400
        assert "Unsupported file format" in response.json()["error"]
        mock_db.put_item.assert_not_called()

    @patch("app.routers.invoices._s3")
    @patch("app.routers.invoices._invoice_db")
    async def test_upload_rejected_for_staff_role(self, mock_db, mock_s3):
        """Staff users cannot upload invoices — returns 403."""
        app.dependency_overrides[get_current_user] = lambda: _staff_user()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/invoices/upload",
                json={"fileName": "invoice.pdf", "contentType": "application/pdf"},
            )

        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["error"]


@pytest.mark.asyncio
class TestInvoiceList:
    """Tests for GET /invoices."""

    @patch("app.routers.invoices._invoice_db")
    async def test_clerk_sees_own_invoices(self, mock_db):
        """AP Clerk queries GSI-UserDate with their own user_id."""
        mock_db.query_by_index.return_value = (
            [
                {
                    "documentId": "doc-1",
                    "fileName": "inv1.pdf",
                    "status": "UPLOADED",
                    "uploadedAt": "2026-07-25T10:00:00Z",
                    "uploadedBy": "clerk-001",
                }
            ],
            None,
        )

        app.dependency_overrides[get_current_user] = lambda: _clerk_user()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/invoices")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["count"] == 1
        assert data["items"][0]["documentId"] == "doc-1"
        mock_db.query_by_index.assert_called_once_with(
            index_name="GSI-UserDate",
            partition_key="uploadedBy",
            partition_value="clerk-001",
            limit=20,
            scan_forward=False,
            exclusive_start_key=None,
        )

    @patch("app.routers.invoices._invoice_db")
    async def test_manager_sees_all_invoices(self, mock_db):
        """Finance Manager gets all invoices via scan."""
        mock_db.table.scan.return_value = {
            "Items": [
                {
                    "documentId": "doc-1",
                    "fileName": "inv1.pdf",
                    "status": "APPROVED",
                    "uploadedAt": "2026-07-25T10:00:00Z",
                    "uploadedBy": "clerk-001",
                },
                {
                    "documentId": "doc-2",
                    "fileName": "inv2.pdf",
                    "status": "ESCALATED",
                    "uploadedAt": "2026-07-25T11:00:00Z",
                    "uploadedBy": "clerk-002",
                },
            ]
        }

        app.dependency_overrides[get_current_user] = lambda: _manager_user()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/invoices")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["count"] == 2

    @patch("app.routers.invoices._invoice_db")
    async def test_staff_cannot_list_invoices(self, mock_db):
        """Staff users cannot access invoice list — returns 403."""
        app.dependency_overrides[get_current_user] = lambda: _staff_user()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/invoices")

        assert response.status_code == 403


@pytest.mark.asyncio
class TestInvoiceDetail:
    """Tests for GET /invoices/{document_id}."""

    @patch("app.routers.invoices._s3")
    @patch("app.routers.invoices._invoice_db")
    async def test_get_detail_success(self, mock_db, mock_s3):
        """Valid document ID returns full invoice detail."""
        mock_db.get_item.return_value = {
            "documentId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            "fileName": "test.pdf",
            "status": "EXTRACTED",
            "uploadedAt": "2026-07-25T10:00:00Z",
            "updatedAt": "2026-07-25T10:00:30Z",
            "uploadedBy": "clerk-001",
            "s3Key": "invoices/f47ac10b-58cc-4372-a567-0e02b2c3d479/test.pdf",
        }
        mock_s3.generate_presigned_get.return_value = "https://s3.presigned/url"

        app.dependency_overrides[get_current_user] = lambda: _clerk_user()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/invoices/f47ac10b-58cc-4372-a567-0e02b2c3d479")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["documentId"] == "f47ac10b-58cc-4372-a567-0e02b2c3d479"
        assert data["status"] == "EXTRACTED"
        assert data["documentUrl"] == "https://s3.presigned/url"

    @patch("app.routers.invoices._s3")
    @patch("app.routers.invoices._invoice_db")
    async def test_get_detail_not_found(self, mock_db, mock_s3):
        """Non-existent document ID returns 404."""
        mock_db.get_item.return_value = None

        app.dependency_overrides[get_current_user] = lambda: _clerk_user()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/invoices/f47ac10b-58cc-4372-a567-0e02b2c3d479")

        assert response.status_code == 404
        assert "not found" in response.json()["error"].lower()

    @patch("app.routers.invoices._s3")
    @patch("app.routers.invoices._invoice_db")
    async def test_clerk_cannot_view_other_users_invoice(self, mock_db, mock_s3):
        """AP Clerk cannot view an invoice uploaded by another user."""
        mock_db.get_item.return_value = {
            "documentId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "fileName": "other.pdf",
            "status": "UPLOADED",
            "uploadedAt": "2026-07-25T10:00:00Z",
            "uploadedBy": "different-user",
            "s3Key": "invoices/doc-other/other.pdf",
        }

        app.dependency_overrides[get_current_user] = lambda: _clerk_user()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/invoices/a1b2c3d4-e5f6-7890-abcd-ef1234567890")

        assert response.status_code == 403

    async def test_invalid_uuid_returns_400(self):
        """Non-UUID document_id in path returns 400 (our handler normalises all validation errors)."""
        app.dependency_overrides[get_current_user] = lambda: _clerk_user()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/invoices/not-a-valid-uuid")

        assert response.status_code == 400
