"""Unit tests for authentication middleware."""

import pytest

from app.middleware.auth import CurrentUser
from app.models.enums import UserRole


class TestCurrentUser:
    """Tests for the CurrentUser dataclass."""

    def test_primary_role_admin_highest(self):
        user = CurrentUser(
            user_id="u1", email="u@test.com", roles=[UserRole.AP_CLERK, UserRole.ADMIN]
        )
        assert user.primary_role == UserRole.ADMIN

    def test_primary_role_finance_manager(self):
        user = CurrentUser(
            user_id="u1", email="u@test.com", roles=[UserRole.FINANCE_MANAGER, UserRole.STAFF]
        )
        assert user.primary_role == UserRole.FINANCE_MANAGER

    def test_primary_role_defaults_to_staff(self):
        user = CurrentUser(user_id="u1", email="u@test.com", roles=[])
        assert user.primary_role == UserRole.STAFF

    def test_has_role_true(self):
        user = CurrentUser(
            user_id="u1", email="u@test.com", roles=[UserRole.AP_CLERK]
        )
        assert user.has_role(UserRole.AP_CLERK) is True
        assert user.has_role(UserRole.AP_CLERK, UserRole.ADMIN) is True

    def test_has_role_false(self):
        user = CurrentUser(
            user_id="u1", email="u@test.com", roles=[UserRole.STAFF]
        )
        assert user.has_role(UserRole.AP_CLERK) is False
        assert user.has_role(UserRole.FINANCE_MANAGER, UserRole.ADMIN) is False

    def test_has_role_multiple_user_roles(self):
        user = CurrentUser(
            user_id="u1",
            email="u@test.com",
            roles=[UserRole.AP_CLERK, UserRole.FINANCE_MANAGER],
        )
        assert user.has_role(UserRole.FINANCE_MANAGER) is True
        assert user.has_role(UserRole.ADMIN) is False
