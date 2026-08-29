"""DynamoDB service — metadata CRUD operations with structured logging."""

import logging
from datetime import datetime, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)


class DynamoClient:
    """Wrapper around DynamoDB table operations with error handling.

    The underlying boto3 resource and Table object are created lazily on first use
    so that importing this module does not require a configured AWS environment.
    """

    def __init__(self, table_name: str):
        self._table_name = table_name
        self._resource = None  # Initialized lazily
        self._table_obj = None  # Initialized lazily

    def _get_table(self):
        """Return the boto3 Table object, initializing it on first call."""
        if not self._table_name:
            raise RuntimeError(
                "DynamoDB table name is not configured. "
                "Check INVOICE_TABLE / DOCUMENT_TABLE environment variables."
            )
        if self._table_obj is None:
            self._resource = boto3.resource("dynamodb", region_name=settings.AWS_REGION)
            self._table_obj = self._resource.Table(self._table_name)
        return self._table_obj

    @property
    def table(self):
        return self._get_table()

    def put_item(self, item: dict[str, Any]) -> None:
        """Create or overwrite an item."""
        try:
            self._get_table().put_item(Item=item)
            logger.info(
                "DynamoDB put_item success",
                extra={"table": self._table_name, "key": _extract_key(item)},
            )
        except ClientError as e:
            logger.error(
                "DynamoDB put_item failed",
                extra={"table": self._table_name, "error": str(e)},
            )
            raise

    def get_item(self, key: dict[str, str]) -> dict[str, Any] | None:
        """Get a single item by primary key. Returns None if not found."""
        try:
            response = self._get_table().get_item(Key=key)
            item = response.get("Item")
            if item is None:
                logger.debug(
                    "DynamoDB get_item not found",
                    extra={"table": self._table_name, "key": key},
                )
            return item
        except ClientError as e:
            logger.error(
                "DynamoDB get_item failed",
                extra={"table": self._table_name, "key": key, "error": str(e)},
            )
            raise

    def update_status(
        self,
        document_id: str,
        new_status: str,
        expected_current: str | None = None,
        **extra_attrs: Any,
    ) -> None:
        """Update document status with optional conditional check and extra attributes.

        Args:
            document_id: The document primary key.
            new_status: Target status value.
            expected_current: If provided, update only succeeds if current status matches.
            **extra_attrs: Additional attributes to set (e.g., reason, assignee).

        Raises:
            ClientError: If conditional check fails or DynamoDB errors.
        """
        now = datetime.now(timezone.utc).isoformat()

        update_expr_parts = ["#status = :new_status", "updatedAt = :now"]
        attr_names: dict[str, str] = {"#status": "status"}
        attr_values: dict[str, Any] = {":new_status": new_status, ":now": now}

        for attr_key, attr_val in extra_attrs.items():
            update_expr_parts.append(f"{attr_key} = :{attr_key}")
            attr_values[f":{attr_key}"] = attr_val

        update_expression = "SET " + ", ".join(update_expr_parts)

        kwargs: dict[str, Any] = {
            "Key": {"documentId": document_id},
            "UpdateExpression": update_expression,
            "ExpressionAttributeNames": attr_names,
            "ExpressionAttributeValues": attr_values,
        }

        if expected_current is not None:
            kwargs["ConditionExpression"] = "#status = :expected"
            kwargs["ExpressionAttributeValues"][":expected"] = expected_current

        try:
            self._get_table().update_item(**kwargs)
            logger.info(
                "DynamoDB status updated",
                extra={
                    "table": self._table_name,
                    "documentId": document_id,
                    "newStatus": new_status,
                },
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning(
                    "DynamoDB conditional update failed — status mismatch",
                    extra={
                        "table": self._table_name,
                        "documentId": document_id,
                        "expectedStatus": expected_current,
                        "targetStatus": new_status,
                    },
                )
            else:
                logger.error(
                    "DynamoDB update_item failed",
                    extra={"table": self._table_name, "error": str(e)},
                )
            raise

    def query_by_index(
        self,
        index_name: str,
        partition_key: str,
        partition_value: str,
        limit: int = 20,
        scan_forward: bool = False,
        exclusive_start_key: dict | None = None,
    ) -> tuple[list[dict[str, Any]], dict | None]:
        """Query a GSI and return (items, last_evaluated_key).

        Args:
            index_name: GSI name.
            partition_key: Partition key attribute name.
            partition_value: Value to match.
            limit: Max items to return.
            scan_forward: True for ascending sort, False for descending.
            exclusive_start_key: Pagination cursor.

        Returns:
            Tuple of (items list, last_evaluated_key or None).
        """
        kwargs: dict[str, Any] = {
            "IndexName": index_name,
            "KeyConditionExpression": Key(partition_key).eq(partition_value),
            "Limit": limit,
            "ScanIndexForward": scan_forward,
        }
        if exclusive_start_key:
            kwargs["ExclusiveStartKey"] = exclusive_start_key

        try:
            response = self._get_table().query(**kwargs)
            items = response.get("Items", [])
            last_key = response.get("LastEvaluatedKey")
            return items, last_key
        except ClientError as e:
            logger.error(
                "DynamoDB query failed",
                extra={
                    "table": self._table_name,
                    "index": index_name,
                    "error": str(e),
                },
            )
            raise

    def scan_count_by_status(self) -> dict[str, int]:
        """Scan table and count items grouped by status. Used for dashboard stats.

        Note: Scan is acceptable here because invoice volume is low in MVP (<100 items).
        For production, use a separate counter table or CloudWatch metrics.
        """
        counts: dict[str, int] = {}
        try:
            response = self._get_table().scan(
                ProjectionExpression="#s",
                ExpressionAttributeNames={"#s": "status"},
            )
            for item in response.get("Items", []):
                status = item.get("status", "UNKNOWN")
                counts[status] = counts.get(status, 0) + 1

            # Handle pagination for larger datasets
            while "LastEvaluatedKey" in response:
                response = self._get_table().scan(
                    ProjectionExpression="#s",
                    ExpressionAttributeNames={"#s": "status"},
                    ExclusiveStartKey=response["LastEvaluatedKey"],
                )
                for item in response.get("Items", []):
                    status = item.get("status", "UNKNOWN")
                    counts[status] = counts.get(status, 0) + 1

            return counts
        except ClientError as e:
            logger.error(
                "DynamoDB scan failed",
                extra={"table": self._table_name, "error": str(e)},
            )
            raise


def _extract_key(item: dict) -> str:
    """Extract a readable key from an item for logging."""
    for key_name in ("documentId", "poNumber", "grId", "sessionId"):
        if key_name in item:
            return f"{key_name}={item[key_name]}"
    return "unknown"
