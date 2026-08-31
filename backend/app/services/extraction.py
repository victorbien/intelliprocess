"""Bedrock Data Automation (BDA) extraction service.

Extracts structured invoice fields from a PDF/PNG/JPEG stored in S3.

MVP flow
--------
1.  Call ``InvokeDataAutomationAsync`` with the S3 URI of the invoice.
2.  Poll ``GetDataAutomationStatus`` until the job reaches a terminal state.
3.  Read the JSON result from the BDA output S3 key.
4.  Normalise the BDA response into our internal ``ExtractionResult`` dict.

Retry strategy (from technical-design.md §4.2):
- BDA invocation: 2 retries with exponential backoff (1s, 2s).
- BDA polling: 2s interval, max 60 polls (120s total wait).
- S3 output read: 2 retries with exponential backoff (1s, 2s).

When ``USE_MOCKS=true`` (local dev), the service skips BDA entirely and
returns a deterministic mock result derived from the S3 key so that tests
never require real AWS credentials.

BDA output schema reference
----------------------------
BDA returns a list of ``standardOutputConfiguration.document.blocks``.
Relevant block types:
- ``KEY_VALUE_SET`` — labelled fields (vendor name, invoice number, etc.)
- ``TABLE``         — line-item rows
- ``PAGE``          — page-level metadata

Confidence scores live at ``block.geometry.confidence`` (0.0–1.0).
"""

import json
import logging
import time
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

_BDA_POLL_INTERVAL_S = 2
_BDA_MAX_POLLS = 60          # 60 × 2 s = 120 s max wait
_BDA_OUTPUT_PREFIX = "bda-output/"

# Retry configuration (application-level, per technical-design.md §4.2)
_MAX_RETRIES = 2             # Total attempts = 3 (1 initial + 2 retries)
_RETRY_BASE_DELAY_S = 1.0   # 1s, 2s backoff

# Fields BDA is expected to return — used for normalisation
_FIELD_MAP = {
    "vendor_name":     "vendorName",
    "vendor_address":  "vendorAddress",
    "invoice_number":  "invoiceNumber",
    "invoice_date":    "invoiceDate",
    "due_date":        "dueDate",
    "po_reference":    "poReference",
    "subtotal":        "subtotal",
    "tax_amount":      "taxAmount",
    "total_amount":    "totalAmount",
    "payment_terms":   "paymentTerms",
}

# Error codes that are safe to retry
_RETRYABLE_ERROR_CODES = frozenset([
    "ThrottlingException",
    "TooManyRequestsException",
    "ServiceUnavailableException",
    "InternalServerException",
    "RequestTimeoutException",
])


# ── Public API ────────────────────────────────────────────────────────────────

class ExtractionError(Exception):
    """Raised when invoice extraction fails.

    Attributes
    ----------
    retryable:
        Whether the caller should consider retrying the operation.
    """

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


def extract_invoice(bucket: str, s3_key: str) -> dict[str, Any]:
    """Extract invoice fields from an S3 object using BDA.

    Returns a dict with:
        vendorName, vendorAddress, invoiceNumber, invoiceDate, dueDate,
        poReference, lineItems, subtotal, taxAmount, totalAmount,
        paymentTerms, confidence (per-field), overallConfidence

    All numeric values are returned as ``float`` (Decimal-safe for DynamoDB
    callers who must convert to ``Decimal`` themselves).

    Raises:
        ExtractionError: On BDA failure or unparseable response.
    """
    if settings.USE_MOCKS:
        logger.info(
            "USE_MOCKS=true — returning mock extraction",
            extra={"bucket": bucket, "s3Key": s3_key},
        )
        return _mock_extraction(s3_key)

    return _bda_extract(bucket, s3_key)


# ── BDA implementation ────────────────────────────────────────────────────────

def _bda_extract(bucket: str, s3_key: str) -> dict[str, Any]:
    """Invoke BDA asynchronously and wait for the result.

    Includes application-level retry with exponential backoff for
    transient errors (throttling, service unavailable).
    """
    runtime = boto3.client(
        "bedrock-data-automation-runtime", region_name=settings.AWS_REGION
    )

    s3_input_uri = "s3://invoices/incoming"
    s3_output_uri = "s3://invoices/processed"

    logger.info(
        "Starting BDA extraction",
        extra={"s3Input": s3_input_uri, "bdaProjectArn": settings.BDA_PROJECT_ARN},
    )

    # ── Step 1: Invoke BDA with retry ─────────────────────────────────────────
    invocation_arn = _invoke_bda_with_retry(
        runtime=runtime,
        s3_input_uri=s3_input_uri,
        s3_output_uri=s3_output_uri,
    )

    logger.info("BDA job started", extra={"invocationArn": invocation_arn})

    # ── Step 2: Poll for completion ───────────────────────────────────────────
    _poll_bda(runtime, invocation_arn)

    # ── Step 3: Read output JSON from S3 with retry ───────────────────────────
    raw = _read_bda_output_with_retry(bucket, s3_key)

    # ── Step 4: Validate and parse BDA output ─────────────────────────────────
    _validate_bda_output(raw)
    extraction = _parse_bda_response(raw)

    # ── Step 5: Validate extraction result ────────────────────────────────────
    _validate_extraction_result(extraction)

    logger.info(
        "BDA extraction complete",
        extra={
            "invocationArn": invocation_arn,
            "overallConfidence": extraction.get("overallConfidence"),
            "fieldsExtracted": len([v for v in extraction.get("confidence", {}).values() if v]),
        },
    )
    return extraction


def _invoke_bda_with_retry(
    runtime,
    s3_input_uri: str,
    s3_output_uri: str,
) -> str:
    """Invoke BDA with application-level retry on transient errors.

    Returns the invocation ARN on success.
    """
    last_error: Exception | None = None

    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = runtime.invoke_data_automation_async(
                inputConfiguration={"s3Uri": s3_input_uri},
                dataAutomationConfiguration={
                    "dataAutomationArn": settings.BDA_PROJECT_ARN,
                    "stage": "LIVE",
                },
                outputConfiguration={"s3Uri": s3_output_uri},
            )
            return response["invocationArn"]

        except ClientError as exc:
            error_code = exc.response["Error"]["Code"]
            error_msg = exc.response["Error"]["Message"]
            last_error = exc

            if error_code in _RETRYABLE_ERROR_CODES and attempt < _MAX_RETRIES:
                delay = _RETRY_BASE_DELAY_S * (2 ** attempt)
                logger.warning(
                    "BDA invocation failed (retryable) — retrying",
                    extra={
                        "attempt": attempt + 1,
                        "maxRetries": _MAX_RETRIES,
                        "errorCode": error_code,
                        "delay": delay,
                    },
                )
                time.sleep(delay)
            else:
                logger.error(
                    "BDA invocation failed (non-retryable or retries exhausted)",
                    extra={
                        "attempt": attempt + 1,
                        "errorCode": error_code,
                        "errorMessage": error_msg,
                    },
                )
                raise ExtractionError(
                    f"Failed to start BDA job: {error_msg}",
                    retryable=error_code in _RETRYABLE_ERROR_CODES,
                ) from exc

    # Should not reach here, but guard against it
    raise ExtractionError(
        f"BDA invocation failed after {_MAX_RETRIES + 1} attempts: {last_error}",
        retryable=True,
    )


def _poll_bda(
    runtime,
    invocation_arn: str,
) -> None:
    """Poll BDA status until terminal or timeout.

    Raises ExtractionError on failure or timeout.
    """
    for attempt in range(_BDA_MAX_POLLS):
        time.sleep(_BDA_POLL_INTERVAL_S)
        try:
            status_resp = runtime.get_data_automation_status(
                invocationArn=invocation_arn
            )
        except ClientError as exc:
            error_code = exc.response["Error"]["Code"]
            # For poll, transient errors are tolerable — just log and continue
            if error_code in _RETRYABLE_ERROR_CODES:
                logger.warning(
                    "BDA status poll hit transient error — continuing",
                    extra={
                        "attempt": attempt + 1,
                        "errorCode": error_code,
                        "invocationArn": invocation_arn,
                    },
                )
                continue
            raise ExtractionError(
                f"BDA status poll failed: {exc.response['Error']['Message']}",
                retryable=False,
            ) from exc

        status = status_resp.get("status", "")
        logger.debug(
            "BDA poll",
            extra={"attempt": attempt + 1, "status": status, "invocationArn": invocation_arn},
        )

        if status == "SUCCESS":
            return
        if status in ("FAILED", "SERVICE_ERROR"):
            failure_reason = status_resp.get("failureReason", "Unknown")
            raise ExtractionError(
                f"BDA job failed: {failure_reason}",
                retryable=(status == "SERVICE_ERROR"),
            )

    raise ExtractionError(
        f"BDA job timed out after {_BDA_MAX_POLLS * _BDA_POLL_INTERVAL_S}s",
        retryable=True,
    )


def _read_bda_output_with_retry(bucket: str, s3_key: str) -> dict:
    """Read BDA output JSON from S3 with retry on transient errors."""
    output_key = f"{_BDA_OUTPUT_PREFIX}{s3_key}/output.json"
    s3 = boto3.client("s3", region_name=settings.AWS_REGION)
    last_error: Exception | None = None

    for attempt in range(_MAX_RETRIES + 1):
        try:
            obj = s3.get_object(Bucket=bucket, Key=output_key)
            body = obj["Body"].read()
            return json.loads(body)
        except ClientError as exc:
            error_code = exc.response["Error"]["Code"]
            last_error = exc

            if error_code in _RETRYABLE_ERROR_CODES and attempt < _MAX_RETRIES:
                delay = _RETRY_BASE_DELAY_S * (2 ** attempt)
                logger.warning(
                    "BDA output read failed (retryable) — retrying",
                    extra={
                        "attempt": attempt + 1,
                        "errorCode": error_code,
                        "outputKey": output_key,
                        "delay": delay,
                    },
                )
                time.sleep(delay)
            elif error_code == "NoSuchKey":
                raise ExtractionError(
                    f"BDA output not found at s3://{bucket}/{output_key}. "
                    "The BDA job may have written output to a different location.",
                    retryable=False,
                ) from exc
            else:
                raise ExtractionError(
                    f"Could not read BDA output from s3://{bucket}/{output_key}: "
                    f"{exc.response['Error']['Message']}",
                    retryable=error_code in _RETRYABLE_ERROR_CODES,
                ) from exc
        except json.JSONDecodeError as exc:
            raise ExtractionError(
                f"BDA output is not valid JSON: {exc}",
                retryable=False,
            ) from exc

    raise ExtractionError(
        f"Failed to read BDA output after {_MAX_RETRIES + 1} attempts: {last_error}",
        retryable=True,
    )


# ── Output validation ────────────────────────────────────────────────────────

def _validate_bda_output(raw: dict) -> None:
    """Validate the structure of raw BDA output before parsing.

    Raises ExtractionError if the output is structurally invalid.
    """
    if not isinstance(raw, dict):
        raise ExtractionError(
            f"BDA output is not a JSON object (got {type(raw).__name__})",
            retryable=False,
        )

    blocks = raw.get("blocks")
    if blocks is None:
        # BDA may return results in alternative structures — log a warning
        # but allow parsing to proceed (it will produce an empty extraction)
        logger.warning(
            "BDA output has no 'blocks' field — extraction may be empty",
            extra={"topLevelKeys": list(raw.keys())[:20]},
        )


def _validate_extraction_result(extraction: dict[str, Any]) -> None:
    """Validate the normalized extraction has minimum usable content.

    Logs warnings for missing critical fields but does NOT raise —
    partial extractions are still persisted so humans can review them.
    """
    critical_fields = ["vendorName", "invoiceNumber", "totalAmount"]
    missing = [f for f in critical_fields if not extraction.get(f)]

    if missing:
        logger.warning(
            "Extraction is missing critical fields",
            extra={
                "missingFields": missing,
                "overallConfidence": extraction.get("overallConfidence"),
            },
        )

    overall_conf = extraction.get("overallConfidence", 0.0)
    if overall_conf < 0.5:
        logger.warning(
            "Extraction confidence is very low — document may be unreadable",
            extra={"overallConfidence": overall_conf},
        )


# ── BDA response parsing ─────────────────────────────────────────────────────

def _parse_bda_response(raw: dict) -> dict[str, Any]:
    """Normalise a raw BDA response into our extraction schema.

    BDA returns blocks; we flatten KEY_VALUE_SET blocks into named fields
    and extract TABLE blocks as line items.
    """
    fields: dict[str, Any] = {}
    confidence: dict[str, float] = {}
    line_items: list[dict] = []

    blocks = raw.get("blocks", [])

    for block in blocks:
        block_type = block.get("blockType", "")
        conf = float(block.get("geometry", {}).get("confidence", 0.0))

        if block_type == "KEY_VALUE_SET":
            key = block.get("key", {}).get("text", "").lower().replace(" ", "_")
            value = block.get("value", {}).get("text", "")
            canonical = _FIELD_MAP.get(key)
            if canonical:
                fields[canonical] = _coerce_field(canonical, value)
                confidence[canonical] = conf

        elif block_type == "TABLE":
            line_items = _parse_table_block(block)

    # Compute overall confidence as mean of known fields
    conf_values = list(confidence.values())
    overall = sum(conf_values) / len(conf_values) if conf_values else 0.0

    return {
        **fields,
        "lineItems": line_items,
        "confidence": confidence,
        "overallConfidence": round(overall, 4),
    }


def _parse_table_block(block: dict) -> list[dict]:
    """Extract line items from a BDA TABLE block."""
    items = []
    rows = block.get("rows", [])
    # Skip header row (index 0)
    for row in rows[1:]:
        cells = row.get("cells", [])
        if len(cells) >= 4:
            try:
                items.append(
                    {
                        "description": cells[0].get("text", ""),
                        "quantity":    _safe_float(cells[1].get("text", "0")),
                        "unitPrice":   _safe_float(cells[2].get("text", "0")),
                        "amount":      _safe_float(cells[3].get("text", "0")),
                    }
                )
            except (IndexError, ValueError):
                pass
    return items


def _coerce_field(field_name: str, raw_value: str) -> Any:
    """Coerce a raw string value to the appropriate Python type."""
    numeric_fields = {"subtotal", "taxAmount", "totalAmount"}
    if field_name in numeric_fields:
        return _safe_float(raw_value)
    return raw_value.strip()


def _safe_float(value: str) -> float:
    """Parse a money/quantity string to float, stripping currency symbols."""
    cleaned = value.replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


# ── Mock implementation ───────────────────────────────────────────────────────

def _mock_extraction(s3_key: str) -> dict[str, Any]:
    """Return a mock extraction based on the document ID embedded in the S3 key.

    The S3 key format is ``invoices/<document_id>/<filename>``.
    We derive a deterministic mock from the filename suffix so different
    test scenarios return different results.
    """
    # Default: well-formed invoice that passes all rules
    result = _build_mock_result(
        vendor_name="Acme Office Supplies Inc.",
        invoice_number="INV-MOCK-0001",
        invoice_date="2026-07-20",
        due_date="2026-08-20",
        po_reference="PO-2024-0456",
        total_amount=658.80,
        subtotal=610.00,
        tax_amount=48.80,
        line_items=[
            {"description": "Premium Copy Paper (10 reams)", "quantity": 10.0,
             "unitPrice": 45.00, "amount": 450.00},
            {"description": "Ink Cartridges - Black", "quantity": 5.0,
             "unitPrice": 32.00, "amount": 160.00},
        ],
        overall_confidence=0.96,
    )
    return result


def _build_mock_result(
    vendor_name: str,
    invoice_number: str,
    invoice_date: str,
    due_date: str,
    po_reference: str | None,
    total_amount: float,
    subtotal: float,
    tax_amount: float,
    line_items: list[dict],
    overall_confidence: float = 0.96,
) -> dict[str, Any]:
    """Construct a complete extraction result dict in the expected schema."""
    per_field_conf = round(overall_confidence, 2)
    confidence = {
        "vendorName":    per_field_conf,
        "invoiceNumber": per_field_conf,
        "invoiceDate":   per_field_conf,
        "dueDate":       per_field_conf,
        "totalAmount":   per_field_conf,
        "subtotal":      per_field_conf,
        "taxAmount":     per_field_conf,
    }
    if po_reference:
        confidence["poReference"] = per_field_conf

    result: dict[str, Any] = {
        "vendorName":    vendor_name,
        "invoiceNumber": invoice_number,
        "invoiceDate":   invoice_date,
        "dueDate":       due_date,
        "totalAmount":   total_amount,
        "subtotal":      subtotal,
        "taxAmount":     tax_amount,
        "paymentTerms":  "Net 30",
        "lineItems":     line_items,
        "confidence":    confidence,
        "overallConfidence": round(overall_confidence, 4),
    }
    if po_reference:
        result["poReference"] = po_reference

    return result




# =============================================================================
# ALTERNATIVE IMPLEMENTATION - New-API BDA path (Danae)
# =============================================================================
# The active implementation above uses the older BDA API
# (dataAutomationConfiguration + dataAutomationArn) and parses a blocks
# response. That path is not reachable against the current BDA service in
# ap-southeast-2, which now requires dataAutomationProfileArn plus a project or
# inline blueprints, and returns inference_result (not blocks).
#
# The block below is a working alternative verified end-to-end against a real
# invoice PDF. It uses the current BDA API with the AWS-managed public invoice
# blueprint, resolves the data automation profile ARN at runtime via STS, and
# maps the blueprint fields to the same extraction schema the pipeline expects
# (vendorName, invoiceNumber, totalAmount, lineItems, confidence,
# overallConfidence).
#
# HOW TO USE (local testing of real BDA):
#   1. Comment out or rename the active _bda_extract / _parse_bda_response above.
#   2. Uncomment the block below (remove the leading #
#
# """Bedrock Data Automation (BDA) extraction service.
#
# Extracts structured invoice fields from a PDF/PNG/JPEG stored in S3.
#
# MVP flow
# --------
# 1.  Call ``InvokeDataAutomationAsync`` with the S3 URI of the invoice.
# 2.  Poll ``GetDataAutomationStatus`` until the job reaches a terminal state.
# 3.  Read the JSON result from the BDA output S3 key.
# 4.  Normalise the BDA response into our internal ``ExtractionResult`` dict.
#
# When ``USE_MOCKS=true`` (local dev), the service skips BDA entirely and
# returns a deterministic mock result derived from the S3 key so that tests
# never require real AWS credentials.
#
# BDA output schema reference
# ----------------------------
# BDA returns a list of ``standardOutputConfiguration.document.blocks``.
# Relevant block types:
# - ``KEY_VALUE_SET`` — labelled fields (vendor name, invoice number, etc.)
# - ``TABLE``         — line-item rows
# - ``PAGE``          — page-level metadata
#
# Confidence scores live at ``block.geometry.confidence`` (0.0–1.0).
# """
#
# import json
# import logging
# import time
# from typing import Any
#
# import boto3
# from botocore.exceptions import ClientError
#
# from app.config import settings
#
# logger = logging.getLogger(__name__)
#
# # ── Constants ────────────────────────────────────────────────────────────────
#
# _BDA_POLL_INTERVAL_S = 3
# _BDA_MAX_POLLS = 40   # 40 × 3 s = 120 s max wait (BDA can take ~20-60 s)
# _BDA_OUTPUT_PREFIX = "bda-output/"
#
# # Data automation profile ARN prefix for the region. BDA requires this on every
# # InvokeDataAutomationAsync call. The "apac." prefix is the profile that
# # ap-southeast-2 resolves to. The account ID is resolved at runtime via STS.
# _BDA_PROFILE_TEMPLATE = (
#     "arn:aws:bedrock:{region}:{account}:data-automation-profile/apac.data-automation-v1"
# )
#
# # AWS-managed public Invoice blueprint. Using this avoids provisioning a custom
# # blueprint in the account — BDA ships a trained invoice extractor out of the box.
# _BDA_INVOICE_BLUEPRINT_ARN = (
#     f"arn:aws:bedrock:{settings.AWS_REGION}:aws"
#     f":blueprint/bedrock-data-automation-public-invoice"
# )
#
# # Maps the public invoice blueprint's field names (left) to our internal
# # extraction schema (right). Fields the blueprint does not provide
# # (dueDate, paymentTerms) are absent here and default to None downstream.
# _BP_FIELD_MAP = {
#     "VENDORNAME":     "vendorName",
#     "VENDORADDRESS":  "vendorAddress",
#     "ID":             "invoiceNumber",
#     "DATE":           "invoiceDate",
#     "PO":             "poReference",
#     "SUBTOTAL":       "subtotal",
#     "TOTAL":          "totalAmount",
# }
#
# # Line-item field mapping (blueprint SERVICES_TABLE entry -> our lineItems entry).
# _BP_LINE_ITEM_MAP = {
#     "product description": "description",
#     "quantity":            "quantity",
#     "unit price":          "unitPrice",
#     "amount":              "amount",
# }
#
# # Fields our downstream pipeline expects to always be present in the result.
# _EXPECTED_FIELDS = (
#     "vendorName", "vendorAddress", "invoiceNumber", "invoiceDate", "dueDate",
#     "poReference", "subtotal", "taxAmount", "totalAmount", "paymentTerms",
# )
#
#
# # ── Public API ────────────────────────────────────────────────────────────────
#
# def extract_invoice(bucket: str, s3_key: str) -> dict[str, Any]:
#     """Extract invoice fields from an S3 object using BDA.
#
#     Returns a dict with:
#         vendorName, vendorAddress, invoiceNumber, invoiceDate, dueDate,
#         poReference, lineItems, subtotal, taxAmount, totalAmount,
#         paymentTerms, confidence (per-field), overallConfidence
#
#     All numeric values are returned as ``float`` (Decimal-safe for DynamoDB
#     callers who must convert to ``Decimal`` themselves).
#
#     Raises:
#         ExtractionError: On BDA failure or unparseable response.
#     """
#     if settings.USE_MOCKS:
#         logger.info(
#             "USE_MOCKS=true — returning mock extraction",
#             extra={"bucket": bucket, "s3Key": s3_key},
#         )
#         return _mock_extraction(s3_key)
#
#     return _bda_extract(bucket, s3_key)
#
#
# class ExtractionError(Exception):
#     """Raised when invoice extraction fails."""
#
#
# # ── BDA implementation ────────────────────────────────────────────────────────
#
# def _bda_profile_arn() -> str:
#     """Build the data automation profile ARN, resolving the account via STS."""
#     account = boto3.client(
#         "sts", region_name=settings.AWS_REGION
#     ).get_caller_identity()["Account"]
#     return _BDA_PROFILE_TEMPLATE.format(region=settings.AWS_REGION, account=account)
#
#
# def _bda_extract(bucket: str, s3_key: str) -> dict[str, Any]:
#     """Invoke BDA with the public invoice blueprint and wait for the result.
#
#     Uses the current BDA API: an async invocation keyed by a data automation
#     profile ARN and the AWS-managed public invoice blueprint, followed by
#     polling and reading the custom-output JSON from S3.
#     """
#     runtime = boto3.client(
#         "bedrock-data-automation-runtime", region_name=settings.AWS_REGION
#     )
#
#     s3_input_uri = f"s3://{bucket}/{s3_key}"
#     s3_output_uri = f"s3://{bucket}/{_BDA_OUTPUT_PREFIX}{s3_key}"
#
#     logger.info(
#         "Starting BDA extraction",
#         extra={"s3Input": s3_input_uri, "blueprint": _BDA_INVOICE_BLUEPRINT_ARN},
#     )
#
#     try:
#         response = runtime.invoke_data_automation_async(
#             inputConfiguration={"s3Uri": s3_input_uri},
#             outputConfiguration={"s3Uri": s3_output_uri},
#             dataAutomationProfileArn=_bda_profile_arn(),
#             blueprints=[
#                 {"blueprintArn": _BDA_INVOICE_BLUEPRINT_ARN, "stage": "LIVE"}
#             ],
#         )
#     except ClientError as exc:
#         raise ExtractionError(
#             f"Failed to start BDA job: {exc.response['Error']['Message']}"
#         ) from exc
#
#     invocation_arn = response["invocationArn"]
#     logger.info("BDA job started", extra={"invocationArn": invocation_arn})
#
#     status_resp = _poll_bda(runtime, invocation_arn)
#
#     # The terminal status carries the S3 URI of the job metadata document.
#     meta_uri = status_resp.get("outputConfiguration", {}).get("s3Uri", "")
#     inference = _read_bda_custom_output(bucket, meta_uri)
#
#     extraction = _parse_bda_response(inference)
#     logger.info(
#         "BDA extraction complete",
#         extra={
#             "invocationArn": invocation_arn,
#             "overallConfidence": extraction.get("overallConfidence"),
#             "vendor": extraction.get("vendorName"),
#         },
#     )
#     return extraction
#
#
# def _poll_bda(runtime, invocation_arn: str) -> dict:
#     """Poll BDA status until terminal or timeout. Returns final status response."""
#     for attempt in range(_BDA_MAX_POLLS):
#         time.sleep(_BDA_POLL_INTERVAL_S)
#         try:
#             status_resp = runtime.get_data_automation_status(
#                 invocationArn=invocation_arn
#             )
#         except ClientError as exc:
#             raise ExtractionError(
#                 f"BDA status poll failed: {exc.response['Error']['Message']}"
#             ) from exc
#
#         status = status_resp.get("status", "")
#         logger.debug(
#             "BDA poll",
#             extra={"attempt": attempt + 1, "status": status},
#         )
#
#         # Current BDA status vocabulary: InProgress / Success / ServiceError / ClientError
#         if status == "Success":
#             return status_resp
#         if status in ("ServiceError", "ClientError"):
#             reason = status_resp.get("errorMessage") or status_resp.get(
#                 "failureReason", "Unknown"
#             )
#             raise ExtractionError(f"BDA job failed: {reason}")
#
#     raise ExtractionError(
#         f"BDA job timed out after {_BDA_MAX_POLLS * _BDA_POLL_INTERVAL_S}s"
#     )
#
#
# def _read_bda_custom_output(bucket: str, meta_uri: str) -> dict:
#     """Follow the BDA job metadata to the custom-output inference result.
#
#     BDA writes a ``job_metadata.json`` whose ``output_metadata`` points at a
#     ``custom_output_path`` per segment. That file contains ``inference_result``
#     (the extracted fields) and ``explainability_info`` (per-field confidence).
#     Returns a dict with keys ``inference_result`` and ``explainability_info``.
#     """
#     if not meta_uri.startswith(f"s3://{bucket}/"):
#         raise ExtractionError(f"Unexpected BDA output URI: {meta_uri}")
#
#     s3 = boto3.client("s3", region_name=settings.AWS_REGION)
#     meta_key = meta_uri.split(f"{bucket}/", 1)[1]
#
#     try:
#         meta = json.loads(s3.get_object(Bucket=bucket, Key=meta_key)["Body"].read())
#     except ClientError as exc:
#         raise ExtractionError(
#             f"Could not read BDA metadata from {meta_uri}: "
#             f"{exc.response['Error']['Message']}"
#         ) from exc
#     except json.JSONDecodeError as exc:
#         raise ExtractionError(f"BDA metadata is not valid JSON: {exc}") from exc
#
#     for asset in meta.get("output_metadata", []):
#         for seg in asset.get("segment_metadata", []):
#             custom_path = seg.get("custom_output_path")
#             if custom_path and custom_path.startswith(f"s3://{bucket}/"):
#                 key = custom_path.split(f"{bucket}/", 1)[1]
#                 try:
#                     return json.loads(
#                         s3.get_object(Bucket=bucket, Key=key)["Body"].read()
#                     )
#                 except (ClientError, json.JSONDecodeError) as exc:
#                     raise ExtractionError(
#                         f"Could not read BDA custom output from {custom_path}: {exc}"
#                     ) from exc
#
#     raise ExtractionError(
#         "BDA produced no custom output — the invoice blueprint did not match."
#     )
#
#
# def _parse_bda_response(raw: dict) -> dict[str, Any]:
#     """Normalise a BDA custom-output document into our extraction schema.
#
#     Maps the public invoice blueprint's field names to our internal names,
#     sums the TAX array, flattens SERVICES_TABLE line items, and reads per-field
#     confidence from ``explainability_info`` when present.
#     """
#     inference = raw.get("inference_result", raw) or {}
#
#     fields: dict[str, Any] = {}
#     for bp_key, our_key in _BP_FIELD_MAP.items():
#         if bp_key in inference and inference[bp_key] not in (None, ""):
#             fields[our_key] = _coerce_field(our_key, inference[bp_key])
#
#     # TAX is a list of tax amounts on the public blueprint; sum to a scalar.
#     tax_values = inference.get("TAX") or []
#     if isinstance(tax_values, list):
#         fields["taxAmount"] = round(sum(_safe_float(t) for t in tax_values), 2)
#     elif tax_values not in (None, ""):
#         fields["taxAmount"] = _safe_float(tax_values)
#
#     # Line items from SERVICES_TABLE.
#     line_items: list[dict] = []
#     for row in inference.get("SERVICES_TABLE") or []:
#         item: dict[str, Any] = {}
#         for bp_key, our_key in _BP_LINE_ITEM_MAP.items():
#             if bp_key in row:
#                 if our_key == "description":
#                     item[our_key] = str(row[bp_key] or "").strip()
#                 else:
#                     item[our_key] = _safe_float(row[bp_key])
#         if item:
#             line_items.append(item)
#
#     # Per-field confidence from explainability_info; fall back to a default.
#     confidence = _extract_confidence(raw, fields)
#     conf_values = [c for c in confidence.values() if c]
#     overall = sum(conf_values) / len(conf_values) if conf_values else 0.0
#
#     # Ensure every downstream-expected field is present (None when absent).
#     for name in _EXPECTED_FIELDS:
#         fields.setdefault(name, None)
#
#     return {
#         **fields,
#         "lineItems": line_items,
#         "confidence": confidence,
#         "overallConfidence": round(overall, 4),
#     }
#
#
# def _extract_confidence(raw: dict, fields: dict[str, Any]) -> dict[str, float]:
#     """Build a per-field confidence map from BDA explainability info.
#
#     ``explainability_info`` is a list of dicts keyed by the blueprint field
#     names, each carrying a ``confidence`` float. Missing entries default to a
#     conservative value so the pipeline still has a usable score.
#     """
#     explain = raw.get("explainability_info") or []
#     # explainability_info is typically a list with one dict of field -> {confidence}
#     flat: dict[str, Any] = {}
#     if isinstance(explain, list):
#         for entry in explain:
#             if isinstance(entry, dict):
#                 flat.update(entry)
#     elif isinstance(explain, dict):
#         flat = explain
#
#     confidence: dict[str, float] = {}
#     for bp_key, our_key in _BP_FIELD_MAP.items():
#         if our_key not in fields or fields[our_key] is None:
#             continue
#         info = flat.get(bp_key)
#         if isinstance(info, dict) and "confidence" in info:
#             confidence[our_key] = round(float(info["confidence"]), 4)
#         else:
#             # Field was extracted but no explicit score provided.
#             confidence[our_key] = 0.9
#     return confidence
#
#
# def _coerce_field(field_name: str, raw_value: str) -> Any:
#     """Coerce a raw string value to the appropriate Python type."""
#     numeric_fields = {"subtotal", "taxAmount", "totalAmount"}
#     if field_name in numeric_fields:
#         return _safe_float(raw_value)
#     return raw_value.strip()
#
#
# def _safe_float(value: Any) -> float:
#     """Parse a money/quantity value to float.
#
#     Accepts numbers (returned as-is) or strings (currency symbols and thousands
#     separators stripped). Anything unparseable becomes 0.0.
#     """
#     if isinstance(value, bool):
#         return 0.0
#     if isinstance(value, (int, float)):
#         return float(value)
#     if value is None:
#         return 0.0
#     cleaned = str(value).replace("$", "").replace(",", "").strip()
#     try:
#         return float(cleaned)
#     except (ValueError, TypeError):
#         return 0.0
#
#
# # ── Mock implementation ───────────────────────────────────────────────────────
#
# def _mock_extraction(s3_key: str) -> dict[str, Any]:
#     """Return a mock extraction based on the document ID embedded in the S3 key.
#
#     The S3 key format is ``invoices/<document_id>/<filename>``.
#     We derive a deterministic mock from the filename suffix so different
#     test scenarios return different results.
#     """
#     # Default: well-formed invoice that passes all rules
#     result = _build_mock_result(
#         vendor_name="Acme Office Supplies Inc.",
#         invoice_number="INV-MOCK-0001",
#         invoice_date="2026-07-20",
#         due_date="2026-08-20",
#         po_reference="PO-2024-0456",
#         total_amount=658.80,
#         subtotal=610.00,
#         tax_amount=48.80,
#         line_items=[
#             {"description": "Premium Copy Paper (10 reams)", "quantity": 10.0,
#              "unitPrice": 45.00, "amount": 450.00},
#             {"description": "Ink Cartridges - Black", "quantity": 5.0,
#              "unitPrice": 32.00, "amount": 160.00},
#         ],
#         overall_confidence=0.96,
#     )
#     return result
#
#
# def _build_mock_result(
#     vendor_name: str,
#     invoice_number: str,
#     invoice_date: str,
#     due_date: str,
#     po_reference: str | None,
#     total_amount: float,
#     subtotal: float,
#     tax_amount: float,
#     line_items: list[dict],
#     overall_confidence: float = 0.96,
# ) -> dict[str, Any]:
#     """Construct a complete extraction result dict in the expected schema."""
#     per_field_conf = round(overall_confidence, 2)
#     confidence = {
#         "vendorName":    per_field_conf,
#         "invoiceNumber": per_field_conf,
#         "invoiceDate":   per_field_conf,
#         "dueDate":       per_field_conf,
#         "totalAmount":   per_field_conf,
#         "subtotal":      per_field_conf,
#         "taxAmount":     per_field_conf,
#     }
#     if po_reference:
#         confidence["poReference"] = per_field_conf
#
#     result: dict[str, Any] = {
#         "vendorName":    vendor_name,
#         "invoiceNumber": invoice_number,
#         "invoiceDate":   invoice_date,
#         "dueDate":       due_date,
#         "totalAmount":   total_amount,
#         "subtotal":      subtotal,
#         "taxAmount":     tax_amount,
#         "paymentTerms":  "Net 30",
#         "lineItems":     line_items,
#         "confidence":    confidence,
#         "overallConfidence": round(overall_confidence, 4),
#     }
#     if po_reference:
#         result["poReference"] = po_reference
#
#     return result
