"""Authentication middleware — Cognito JWT validation and role-based access control.

This module provides FastAPI dependencies for:
1. Extracting and validating the JWT from the Authorization header.
2. Resolving the current user identity and role from token claims.
3. Enforcing role-based access on specific routes.

In Lambda behind API Gateway with a Cognito Authorizer, the token is already validated
by the time it reaches the handler. The claims are passed in the request context.
For local development (uvicorn), we decode the JWT using Cognito JWKS.
"""

import logging
from dataclasses import dataclass
from typing import Annotated

import boto3
from fastapi import Depends, Request
from botocore.exceptions import ClientError

from app.config import settings
from app.middleware.errors import AppError
from app.models.enums import UserRole

logger = logging.getLogger(__name__)


@dataclass
class CurrentUser:
    """Resolved user identity from JWT claims."""

    user_id: str  # Cognito 'sub'
    email: str
    roles: list[UserRole]

    @property
    def primary_role(self) -> UserRole:
        """Return the highest-privilege role assigned to the user."""
        role_priority = [UserRole.ADMIN, UserRole.FINANCE_MANAGER, UserRole.AP_CLERK, UserRole.STAFF]
        for role in role_priority:
            if role in self.roles:
                return role
        return UserRole.STAFF

    def has_role(self, *roles: UserRole) -> bool:
        """Check if user has any of the specified roles."""
        return any(r in self.roles for r in roles)


async def get_current_user(request: Request) -> CurrentUser:
    """FastAPI dependency — extract authenticated user from request.

    When running behind API Gateway + Cognito Authorizer:
      Claims are in event["requestContext"]["authorizer"]["claims"]
      Mangum passes these through the ASGI scope.

    For local development:
      Reads Authorization header and decodes JWT claims.
      Falls back to a dev user if STAGE=dev and no token provided.

    Raises:
        AppError(401): If authentication fails.
    """
    # Check for Lambda/API Gateway authorizer claims (via Mangum)
    scope = request.scope
    aws_event = scope.get("aws.event", {})
    authorizer_claims = (
        aws_event.get("requestContext", {})
        .get("authorizer", {})
        .get("claims", {})
    )

    if authorizer_claims:
        return _parse_cognito_claims(authorizer_claims)

    # Local development fallback — extract from Authorization header
    auth_header = request.headers.get("Authorization", "")

    if not auth_header:
        if settings.STAGE == "dev":
            # Dev convenience: return a default dev user
            logger.debug("No auth header in dev mode — using default dev user")
            return CurrentUser(
                user_id="dev-user-001",
                email="dev@localhost",
                roles=[UserRole.ADMIN],
            )
        raise AppError("Authentication required. Please log in.", status_code=401)

    if not auth_header.startswith("Bearer "):
        raise AppError("Invalid authorization header format.", status_code=401)

    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        raise AppError("Authentication token is empty.", status_code=401)

    # In production local testing, validate against Cognito
    return await _validate_token_with_cognito(token)


def _parse_cognito_claims(claims: dict) -> CurrentUser:
    """Parse Cognito authorizer claims into a CurrentUser."""
    user_id = claims.get("sub", "")
    email = claims.get("email", claims.get("cognito:username", ""))

    # Cognito groups come as a space-separated string or list
    groups_raw = claims.get("cognito:groups", "")
    if isinstance(groups_raw, str):
        groups = [g.strip() for g in groups_raw.split(",") if g.strip()]
    elif isinstance(groups_raw, list):
        groups = groups_raw
    else:
        groups = []

    roles = []
    for g in groups:
        try:
            roles.append(UserRole(g))
        except ValueError:
            logger.warning("Unknown role in claims: %s", g)

    if not roles:
        roles = [UserRole.STAFF]

    return CurrentUser(user_id=user_id, email=email, roles=roles)


async def _validate_token_with_cognito(token: str) -> CurrentUser:
    """Validate JWT by calling Cognito GetUser with the access token.

    This is a simplified validation approach suitable for MVP.
    Production systems should verify JWT signature using JWKS.
    """
    try:
        client = boto3.client("cognito-idp", region_name=settings.AWS_REGION)
        response = client.get_user(AccessToken=token)

        user_id = response.get("Username", "")
        attributes = {
            attr["Name"]: attr["Value"] for attr in response.get("UserAttributes", [])
        }
        email = attributes.get("email", user_id)

        # Fetch user groups
        groups_response = client.admin_list_groups_for_user(
            Username=user_id,
            UserPoolId=settings.COGNITO_USER_POOL_ID,
        )
        groups = [g["GroupName"] for g in groups_response.get("Groups", [])]

        roles = []
        for g in groups:
            try:
                roles.append(UserRole(g))
            except ValueError:
                pass

        if not roles:
            roles = [UserRole.STAFF]

        return CurrentUser(user_id=user_id, email=email, roles=roles)

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code in ("NotAuthorizedException", "UserNotFoundException"):
            raise AppError("Invalid or expired authentication token.", status_code=401)
        logger.error("Cognito validation failed: %s", str(e))
        raise AppError("Authentication service error.", status_code=500)
    except Exception as e:
        logger.error("Unexpected auth error: %s", str(e), exc_info=True)
        raise AppError("Authentication failed.", status_code=401)


# ─── Role-Based Access Dependencies ──────────────────────────────────────────


def require_role(*allowed_roles: UserRole):
    """Create a FastAPI dependency that enforces role-based access.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_role(UserRole.ADMIN))])
        def admin_endpoint(): ...

        # Or inject user:
        @router.get("/invoices")
        def list_invoices(user: CurrentUser = Depends(require_role(UserRole.AP_CLERK, UserRole.ADMIN))):
            ...
    """

    async def _check_role(
        user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if not user.has_role(*allowed_roles):
            logger.warning(
                "Access denied — user %s with roles %s attempted to access route requiring %s",
                user.user_id,
                user.roles,
                allowed_roles,
            )
            raise AppError("Insufficient permissions for this action.", status_code=403)
        return user

    return _check_role
