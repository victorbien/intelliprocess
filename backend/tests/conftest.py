"""Shared test fixtures for backend tests."""

import os
import pytest
from unittest.mock import patch, MagicMock

# Set test environment variables before importing app modules
os.environ.update({
    "AWS_DEFAULT_REGION": "us-east-1",
    "AWS_ACCESS_KEY_ID": "testing",
    "AWS_SECRET_ACCESS_KEY": "testing",
    "AWS_SECURITY_TOKEN": "testing",
    "AWS_SESSION_TOKEN": "testing",
    "STAGE": "dev",
    "DOCUMENT_BUCKET": "test-bucket",
    "INVOICE_TABLE": "test-invoices",
    "PO_TABLE": "test-pos",
    "GR_TABLE": "test-grs",
    "CONVERSATION_TABLE": "test-conversations",
    "DOCUMENT_TABLE": "test-documents",
    "KNOWLEDGE_BASE_ID": "test-kb-id",
    "BDA_PROJECT_ARN": "arn:aws:bedrock:us-east-1:123456789012:data-automation-project/test",
    "GUARDRAIL_ID": "test-guardrail",
    "COGNITO_USER_POOL_ID": "us-east-1_TestPool",
    "COGNITO_APP_CLIENT_ID": "test-client-id",
})


from httpx import ASGITransport, AsyncClient
from app.main import app
from app.middleware.auth import CurrentUser, get_current_user
from app.models.enums import UserRole


@pytest.fixture
def ap_clerk_user():
    """An AP Clerk user for injection into tests."""
    return CurrentUser(
        user_id="clerk-user-001",
        email="clerk@test.com",
        roles=[UserRole.AP_CLERK],
    )


@pytest.fixture
def finance_manager_user():
    """A Finance Manager user for injection into tests."""
    return CurrentUser(
        user_id="manager-user-001",
        email="manager@test.com",
        roles=[UserRole.FINANCE_MANAGER],
    )


@pytest.fixture
def admin_user():
    """An Admin user for injection into tests."""
    return CurrentUser(
        user_id="admin-user-001",
        email="admin@test.com",
        roles=[UserRole.ADMIN],
    )


@pytest.fixture
def staff_user():
    """A Staff user (no invoice access) for injection into tests."""
    return CurrentUser(
        user_id="staff-user-001",
        email="staff@test.com",
        roles=[UserRole.STAFF],
    )


def override_auth(user: CurrentUser):
    """Create an auth override dependency for a given user."""
    async def _override():
        return user
    return _override


@pytest.fixture
def client_as_clerk(ap_clerk_user):
    """Async test client authenticated as AP Clerk."""
    app.dependency_overrides[get_current_user] = override_auth(ap_clerk_user)
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client_as_manager(finance_manager_user):
    """Async test client authenticated as Finance Manager."""
    app.dependency_overrides[get_current_user] = override_auth(finance_manager_user)
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client_as_admin(admin_user):
    """Async test client authenticated as Admin."""
    app.dependency_overrides[get_current_user] = override_auth(admin_user)
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client_as_staff(staff_user):
    """Async test client authenticated as Staff."""
    app.dependency_overrides[get_current_user] = override_auth(staff_user)
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def async_client():
    """Base async client without auth override (uses dev default)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
