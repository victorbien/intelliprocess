"""Integration tests for documents API endpoints."""

import pytest
from unittest.mock import patch, MagicMock
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.middleware.auth import get_current_user, CurrentUser
from app.models.enums import UserRole


def _admin_user():
    return CurrentUser(user_id="admin-001", email="admin@test.com", roles=[UserRole.ADMIN])


def _clerk_user():
    return CurrentUser(user_id="clerk-001", email="clerk@test.com", roles=[UserRole.AP_CLERK])


def _staff_user():
    return CurrentUser(user_id="staff-001", email="staff@test.com", roles=[UserRole.STAFF])


@pytest.fixture(autouse=True)
def cleanup_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
class TestDocumentUpload:
    """Tests for POST /documents/upload."""

    @patch("app.routers.documents._s3")
    @patch("app.routers.documents._documents_db")
    async def test_admin_can_upload_document(self, mock_db, mock_s3):
        """Admin uploads a policy document — returns 201 with presigned URL."""
        mock_s3.generate_presigned_post.return_value = {
            "url": "https://s3.amazonaws.com/test-bucket",
            "fields": {"key": "records/abc/policy.pdf", "Policy": "xxx"},
        }
        mock_db.put_item = MagicMock()

        app.dependency_overrides[get_current_user] = lambda: _admin_user()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/documents/upload",
                json={
                    "fileName": "Travel-Policy.pdf",
                    "contentType": "application/pdf",
                    "category": "policies",
                    "description": "Corporate travel policy 2024",
                },
            )

        assert response.status_code == 201
        data = response.json()["data"]
        assert "documentId" in data
        assert data["uploadUrl"]["url"] == "https://s3.amazonaws.com/test-bucket"
        assert "knowledge base sync" in data["note"].lower()
        mock_db.put_item.assert_called_once()

        # Verify metadata contents
        call_args = mock_db.put_item.call_args[0][0]
        assert call_args["category"] == "policies"
        assert call_args["kbSyncStatus"] == "PENDING"
        assert call_args["description"] == "Corporate travel policy 2024"

    @patch("app.routers.documents._s3")
    @patch("app.routers.documents._documents_db")
    async def test_clerk_cannot_upload_documents(self, mock_db, mock_s3):
        """Non-admin users cannot upload organizational documents."""
        app.dependency_overrides[get_current_user] = lambda: _clerk_user()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/documents/upload",
                json={
                    "fileName": "policy.pdf",
                    "contentType": "application/pdf",
                    "category": "policies",
                },
            )

        assert response.status_code == 403

    @patch("app.routers.documents._s3")
    @patch("app.routers.documents._documents_db")
    async def test_rejects_image_format_for_records(self, mock_db, mock_s3):
        """Image formats are not valid for organizational documents."""
        app.dependency_overrides[get_current_user] = lambda: _admin_user()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/documents/upload",
                json={
                    "fileName": "scan.png",
                    "contentType": "image/png",
                    "category": "policies",
                },
            )

        assert response.status_code == 400
        assert "Unsupported file format for records" in response.json()["error"]


@pytest.mark.asyncio
class TestDocumentList:
    """Tests for GET /documents."""

    @patch("app.routers.documents._documents_db")
    async def test_all_users_can_list_documents(self, mock_db):
        """Any authenticated user can view the document list."""
        mock_db.table.scan.return_value = {
            "Items": [
                {
                    "documentId": "doc-1",
                    "fileName": "Travel-Policy.pdf",
                    "category": "policies",
                    "uploadedAt": "2026-07-20T09:00:00Z",
                    "description": "Travel policy",
                    "kbSyncStatus": "SYNCED",
                }
            ]
        }

        app.dependency_overrides[get_current_user] = lambda: _staff_user()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/documents")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["count"] == 1
        assert data["items"][0]["fileName"] == "Travel-Policy.pdf"
        assert data["items"][0]["category"] == "policies"

    @patch("app.routers.documents._documents_db")
    async def test_filter_by_category(self, mock_db):
        """Category filter queries the GSI-CategoryDate index."""
        mock_db.query_by_index.return_value = (
            [
                {
                    "documentId": "doc-2",
                    "fileName": "Vendor-Contract.pdf",
                    "category": "contracts",
                    "uploadedAt": "2026-07-21T09:00:00Z",
                    "kbSyncStatus": "SYNCED",
                }
            ],
            None,
        )

        app.dependency_overrides[get_current_user] = lambda: _staff_user()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/documents?category=contracts")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["count"] == 1
        mock_db.query_by_index.assert_called_once_with(
            index_name="GSI-CategoryDate",
            partition_key="category",
            partition_value="contracts",
            limit=50,
            scan_forward=False,
        )
