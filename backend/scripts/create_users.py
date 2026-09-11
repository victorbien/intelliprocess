"""Create Cognito test users with assigned roles.

Creates demo users and assigns each to the matching Cognito group:
    clerk@demo.com    -> AP_CLERK
    manager@demo.com  -> FINANCE_MANAGER
    staff@demo.com    -> STAFF
    admin@demo.com    -> ADMIN

The user pool is resolved from (in priority order):
    1. --user-pool-id CLI argument
    2. COGNITO_USER_POOL_ID environment variable / .env
    3. app.config.settings.COGNITO_USER_POOL_ID

Each user is created with a permanent password so they can sign in
immediately (no FORCE_CHANGE_PASSWORD challenge). The script is idempotent:
existing users are updated (group membership + password) rather than
duplicated.

Run:
    python -m scripts.create_users
    python -m scripts.create_users --user-pool-id ap-southeast-2_xxxx --password "Passw0rd!"

Requires AWS credentials with Cognito admin permissions (e.g. the deploy
profile). Set the profile via AWS_PROFILE or the standard AWS CLI env vars.
"""

from __future__ import annotations

import argparse
import sys

import boto3
from botocore.exceptions import ClientError

from app.config import settings

# email -> Cognito group name
_USERS: dict[str, str] = {
    "clerk@demo.com": "AP_CLERK",
    "manager@demo.com": "FINANCE_MANAGER",
    "staff@demo.com": "STAFF",
    "admin@demo.com": "ADMIN",
}

_DEFAULT_PASSWORD = "Passw0rd!"


def _display_name(email: str) -> str:
    """Derive a human-readable name from the local part of the email."""
    local = email.split("@", 1)[0]
    return local.capitalize()


def create_user(
    client,
    user_pool_id: str,
    email: str,
    group: str,
    password: str,
) -> None:
    """Create (or update) a single Cognito user and add it to its group."""
    # 1. Create the user (idempotent: tolerate UsernameExistsException).
    try:
        client.admin_create_user(
            UserPoolId=user_pool_id,
            Username=email,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
                {"Name": "name", "Value": _display_name(email)},
            ],
            MessageAction="SUPPRESS",  # do not send an invitation email
        )
        print(f"  created  {email}")
    except client.exceptions.UsernameExistsException:
        print(f"  exists   {email} (updating password + group)")

    # 2. Set a permanent password so the user can log in directly.
    client.admin_set_user_password(
        UserPoolId=user_pool_id,
        Username=email,
        Password=password,
        Permanent=True,
    )

    # 3. Assign the role group (idempotent — re-adding is a no-op).
    client.admin_add_user_to_group(
        UserPoolId=user_pool_id,
        Username=email,
        GroupName=group,
    )
    print(f"  group    {email} -> {group}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create Cognito demo users.")
    parser.add_argument(
        "--user-pool-id",
        default=settings.COGNITO_USER_POOL_ID,
        help="Cognito User Pool ID (defaults to COGNITO_USER_POOL_ID from env/.env).",
    )
    parser.add_argument(
        "--password",
        default=_DEFAULT_PASSWORD,
        help="Permanent password to set for every demo user.",
    )
    parser.add_argument(
        "--region",
        default=settings.AWS_REGION,
        help="AWS region of the user pool (defaults to AWS_REGION from env/.env).",
    )
    args = parser.parse_args()

    if not args.user_pool_id:
        print(
            "ERROR: No user pool ID. Pass --user-pool-id or set "
            "COGNITO_USER_POOL_ID in your environment / .env.",
            file=sys.stderr,
        )
        return 1

    client = boto3.client("cognito-idp", region_name=args.region)

    print(f"Creating {len(_USERS)} demo users in pool {args.user_pool_id} ({args.region})")
    try:
        for email, group in _USERS.items():
            create_user(client, args.user_pool_id, email, group, args.password)
    except ClientError as exc:
        print(f"ERROR: {exc.response['Error']['Message']}", file=sys.stderr)
        return 1

    print("\nDone. Demo users:")
    for email, group in _USERS.items():
        print(f"  {email:<20} {group}")
    print(f"\nPassword for all users: {args.password}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
