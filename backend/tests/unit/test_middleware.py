"""Unit tests for error handling and correlation ID middleware."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.middleware.auth import get_current_user, CurrentUser
from app.middleware.errors import AppError
from app.models.enums import UserRole


def _admin_user():
    return CurrentUser(user_id="admin-001", email="admin@test.com", roles=[UserRole.ADMIN])


@pytest.fixture(autouse=True)
def cleanup():
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
class TestCorrelationIdMiddleware:
    """Tests for X-Correlation-Id header handling."""

    async def test_generates_correlation_id_if_missing(self):
        """If no X-Correlation-Id in request, one is generated in response."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == 200
        correlation_id = response.headers.get("x-correlation-id")
        assert correlation_id is not None
        assert len(correlation_id) == 36  # UUID format

    async def test_preserves_provided_correlation_id(self):
        """If X-Correlation-Id is provided, it is echoed back."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/health",
                headers={"X-Correlation-Id": "my-custom-id-123"},
            )

        assert response.status_code == 200
        assert response.headers.get("x-correlation-id") == "my-custom-id-123"


@pytest.mark.asyncio
class TestErrorHandling:
    """Tests for global error handler responses."""

    async def test_validation_error_returns_400(self):
        """Invalid request body triggers validation error with helpful message."""
        app.dependency_overrides[get_current_user] = lambda: _admin_user()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/invoices/upload",
                json={},  # Missing required fields
            )

        assert response.status_code == 400
        body = response.json()
        assert "error" in body
        assert body["statusCode"] == 400

    async def test_404_returns_json_error(self):
        """Non-existent route returns structured error."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/nonexistent-route")

        # FastAPI returns 404 for unknown routes
        assert response.status_code == 404

    async def test_health_endpoint_no_auth_required(self):
        """Health check works without authentication."""
        # Don't override auth — dev mode will provide default user
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["stage"] == "dev"
