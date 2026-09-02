"""Seed sample PO and GR data into DynamoDB for demo/testing.

Loads the default sample Purchase Orders and Goods Receipts (the same set
returned by ``app.services.dashboard.default_seed_data`` / AC-5.1.4) and
writes them to the PurchaseOrders and GoodsReceipts DynamoDB tables.

Numeric fields arrive as ``str`` and are converted to ``Decimal`` before
writing, as DynamoDB rejects native floats.

Table names are resolved from (in priority order):
    1. --po-table / --gr-table CLI arguments
    2. PO_TABLE / GR_TABLE environment variables / .env
    3. The deployed default names (IntelliProcess-{PurchaseOrders,GoodsReceipts}-dev)

Run:
    python -m scripts.seed_data
    python -m scripts.seed_data --stage dev

Requires AWS credentials with DynamoDB write permissions (e.g. the deploy
profile). Set the profile via AWS_PROFILE or standard AWS CLI env vars.
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.config import settings
from app.services.dashboard import default_seed_data

# Numeric fields that must be stored as Decimal in DynamoDB.
_NUMERIC_FIELDS = frozenset(
    {"totalAmount", "totalQuantityReceived"}
)


def _to_dynamo_item(record: dict[str, Any]) -> dict[str, Any]:
    """Convert a seed record's numeric string fields to Decimal."""
    item: dict[str, Any] = {}
    for key, value in record.items():
        if key in _NUMERIC_FIELDS and isinstance(value, str):
            item[key] = Decimal(value)
        else:
            item[key] = value
    return item


def _seed_table(table, records: list[dict[str, Any]], key_field: str, label: str) -> None:
    """Batch-write records into a DynamoDB table."""
    with table.batch_writer() as batch:
        for record in records:
            batch.put_item(Item=_to_dynamo_item(record))
    print(f"  seeded {len(records)} {label}")
    for record in records:
        print(f"    {record[key_field]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed sample PO/GR data into DynamoDB.")
    parser.add_argument("--stage", default=settings.STAGE, help="Deployment stage (for default table names).")
    parser.add_argument(
        "--po-table",
        default=settings.PO_TABLE,
        help="PurchaseOrders table name (defaults to PO_TABLE env, then IntelliProcess-PurchaseOrders-<stage>).",
    )
    parser.add_argument(
        "--gr-table",
        default=settings.GR_TABLE,
        help="GoodsReceipts table name (defaults to GR_TABLE env, then IntelliProcess-GoodsReceipts-<stage>).",
    )
    parser.add_argument(
        "--region",
        default=settings.AWS_REGION,
        help="AWS region (defaults to AWS_REGION from env/.env).",
    )
    args = parser.parse_args()

    po_table_name = args.po_table or f"IntelliProcess-PurchaseOrders-{args.stage}"
    gr_table_name = args.gr_table or f"IntelliProcess-GoodsReceipts-{args.stage}"

    purchase_orders, goods_receipts = default_seed_data()

    dynamodb = boto3.resource("dynamodb", region_name=args.region)
    po_table = dynamodb.Table(po_table_name)
    gr_table = dynamodb.Table(gr_table_name)

    print(f"Seeding data in {args.region}")
    print(f"  PO table: {po_table_name}")
    print(f"  GR table: {gr_table_name}\n")

    try:
        _seed_table(po_table, purchase_orders, "poNumber", "purchase orders")
        _seed_table(gr_table, goods_receipts, "grId", "goods receipts")
    except ClientError as exc:
        print(f"ERROR: {exc.response['Error']['Message']}", file=sys.stderr)
        return 1

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
