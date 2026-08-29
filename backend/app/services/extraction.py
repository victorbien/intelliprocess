"""Bedrock Data Automation (BDA) extraction service.

Extracts structured invoice fields from a PDF/PNG/JPEG stored in S3.

MVP flow
--------
1.  Call ``InvokeDataAutomationAsync`` with the S3 URI of the invoice.
2.  Poll ``GetDataAutomationStatus`` until the job reaches a terminal state.
3.  Read the JSON result from the BDA output S3 key.
4.  Normalise the BDA response into our internal ``ExtractionResult`` dict.

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

_BDA_POLL_INTERVAL_S = 3
_BDA_MAX_POLLS = 40   # 40 × 3 s = 120 s max wait (BDA can take ~20-60 s)
_BDA_OUTPUT_PREFIX = "bda-output/"

# Data automation profile ARN prefix for the region. BDA requires this on every
# InvokeDataAutomationAsync call. The "apac." prefix is the profile that
# ap-southeast-2 resolves to. The account ID is resolved at runtime via STS.
_BDA_PROFILE_TEMPLATE = (
    "arn:aws:bedrock:{region}:{account}:data-automation-profile/apac.data-automation-v1"
)

# AWS-managed public Invoice blueprint. Using this avoids provisioning a custom
# blueprint in the account — BDA ships a trained invoice extractor out of the box.
_BDA_INVOICE_BLUEPRINT_ARN = (
    f"arn:aws:bedrock:{settings.AWS_REGION}:aws"
    f":blueprint/bedrock-data-automation-public-invoice"
)

# Maps the public invoice blueprint's field names (left) to our internal
# extraction schema (right). Fields the blueprint does not provide
# (dueDate, paymentTerms) are absent here and default to None downstream.
_BP_FIELD_MAP = {
    "VENDORNAME":     "vendorName",
    "VENDORADDRESS":  "vendorAddress",
    "ID":             "invoiceNumber",
    "DATE":           "invoiceDate",
    "PO":             "poReference",
    "SUBTOTAL":       "subtotal",
    "TOTAL":          "totalAmount",
}

# Line-item field mapping (blueprint SERVICES_TABLE entry -> our lineItems entry).
_BP_LINE_ITEM_MAP = {
    "product description": "description",
    "quantity":            "quantity",
    "unit price":          "unitPrice",
    "amount":              "amount",
}

# Fields our downstream pipeline expects to always be present in the result.
_EXPECTED_FIELDS = (
    "vendorName", "vendorAddress", "invoiceNumber", "invoiceDate", "dueDate",
    "poReference", "subtotal", "taxAmount", "totalAmount", "paymentTerms",
)


# ── Public API ────────────────────────────────────────────────────────────────

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


class ExtractionError(Exception):
    """Raised when invoice extraction fails."""


# ── BDA implementation ────────────────────────────────────────────────────────

def _bda_profile_arn() -> str:
    """Build the data automation profile ARN, resolving the account via STS."""
    account = boto3.client(
        "sts", region_name=settings.AWS_REGION
    ).get_caller_identity()["Account"]
    return _BDA_PROFILE_TEMPLATE.format(region=settings.AWS_REGION, account=account)


def _bda_extract(bucket: str, s3_key: str) -> dict[str, Any]:
    """Invoke BDA with the public invoice blueprint and wait for the result.

    Uses the current BDA API: an async invocation keyed by a data automation
    profile ARN and the AWS-managed public invoice blueprint, followed by
    polling and reading the custom-output JSON from S3.
    """
    runtime = boto3.client(
        "bedrock-data-automation-runtime", region_name=settings.AWS_REGION
    )

    s3_input_uri = f"s3://{bucket}/{s3_key}"
    s3_output_uri = f"s3://{bucket}/{_BDA_OUTPUT_PREFIX}{s3_key}"

    logger.info(
        "Starting BDA extraction",
        extra={"s3Input": s3_input_uri, "blueprint": _BDA_INVOICE_BLUEPRINT_ARN},
    )

    try:
        response = runtime.invoke_data_automation_async(
            inputConfiguration={"s3Uri": s3_input_uri},
            outputConfiguration={"s3Uri": s3_output_uri},
            dataAutomationProfileArn=_bda_profile_arn(),
            blueprints=[
                {"blueprintArn": _BDA_INVOICE_BLUEPRINT_ARN, "stage": "LIVE"}
            ],
        )
    except ClientError as exc:
        raise ExtractionError(
            f"Failed to start BDA job: {exc.response['Error']['Message']}"
        ) from exc

    invocation_arn = response["invocationArn"]
    logger.info("BDA job started", extra={"invocationArn": invocation_arn})

    status_resp = _poll_bda(runtime, invocation_arn)

    # The terminal status carries the S3 URI of the job metadata document.
    meta_uri = status_resp.get("outputConfiguration", {}).get("s3Uri", "")
    inference = _read_bda_custom_output(bucket, meta_uri)

    extraction = _parse_bda_response(inference)
    logger.info(
        "BDA extraction complete",
        extra={
            "invocationArn": invocation_arn,
            "overallConfidence": extraction.get("overallConfidence"),
            "vendor": extraction.get("vendorName"),
        },
    )
    return extraction


def _poll_bda(runtime, invocation_arn: str) -> dict:
    """Poll BDA status until terminal or timeout. Returns final status response."""
    for attempt in range(_BDA_MAX_POLLS):
        time.sleep(_BDA_POLL_INTERVAL_S)
        try:
            status_resp = runtime.get_data_automation_status(
                invocationArn=invocation_arn
            )
        except ClientError as exc:
            raise ExtractionError(
                f"BDA status poll failed: {exc.response['Error']['Message']}"
            ) from exc

        status = status_resp.get("status", "")
        logger.debug(
            "BDA poll",
            extra={"attempt": attempt + 1, "status": status},
        )

        # Current BDA status vocabulary: InProgress / Success / ServiceError / ClientError
        if status == "Success":
            return status_resp
        if status in ("ServiceError", "ClientError"):
            reason = status_resp.get("errorMessage") or status_resp.get(
                "failureReason", "Unknown"
            )
            raise ExtractionError(f"BDA job failed: {reason}")

    raise ExtractionError(
        f"BDA job timed out after {_BDA_MAX_POLLS * _BDA_POLL_INTERVAL_S}s"
    )


def _read_bda_custom_output(bucket: str, meta_uri: str) -> dict:
    """Follow the BDA job metadata to the custom-output inference result.

    BDA writes a ``job_metadata.json`` whose ``output_metadata`` points at a
    ``custom_output_path`` per segment. That file contains ``inference_result``
    (the extracted fields) and ``explainability_info`` (per-field confidence).
    Returns a dict with keys ``inference_result`` and ``explainability_info``.
    """
    if not meta_uri.startswith(f"s3://{bucket}/"):
        raise ExtractionError(f"Unexpected BDA output URI: {meta_uri}")

    s3 = boto3.client("s3", region_name=settings.AWS_REGION)
    meta_key = meta_uri.split(f"{bucket}/", 1)[1]

    try:
        meta = json.loads(s3.get_object(Bucket=bucket, Key=meta_key)["Body"].read())
    except ClientError as exc:
        raise ExtractionError(
            f"Could not read BDA metadata from {meta_uri}: "
            f"{exc.response['Error']['Message']}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"BDA metadata is not valid JSON: {exc}") from exc

    for asset in meta.get("output_metadata", []):
        for seg in asset.get("segment_metadata", []):
            custom_path = seg.get("custom_output_path")
            if custom_path and custom_path.startswith(f"s3://{bucket}/"):
                key = custom_path.split(f"{bucket}/", 1)[1]
                try:
                    return json.loads(
                        s3.get_object(Bucket=bucket, Key=key)["Body"].read()
                    )
                except (ClientError, json.JSONDecodeError) as exc:
                    raise ExtractionError(
                        f"Could not read BDA custom output from {custom_path}: {exc}"
                    ) from exc

    raise ExtractionError(
        "BDA produced no custom output — the invoice blueprint did not match."
    )


def _parse_bda_response(raw: dict) -> dict[str, Any]:
    """Normalise a BDA custom-output document into our extraction schema.

    Maps the public invoice blueprint's field names to our internal names,
    sums the TAX array, flattens SERVICES_TABLE line items, and reads per-field
    confidence from ``explainability_info`` when present.
    """
    inference = raw.get("inference_result", raw) or {}

    fields: dict[str, Any] = {}
    for bp_key, our_key in _BP_FIELD_MAP.items():
        if bp_key in inference and inference[bp_key] not in (None, ""):
            fields[our_key] = _coerce_field(our_key, inference[bp_key])

    # TAX is a list of tax amounts on the public blueprint; sum to a scalar.
    tax_values = inference.get("TAX") or []
    if isinstance(tax_values, list):
        fields["taxAmount"] = round(sum(_safe_float(t) for t in tax_values), 2)
    elif tax_values not in (None, ""):
        fields["taxAmount"] = _safe_float(tax_values)

    # Line items from SERVICES_TABLE.
    line_items: list[dict] = []
    for row in inference.get("SERVICES_TABLE") or []:
        item: dict[str, Any] = {}
        for bp_key, our_key in _BP_LINE_ITEM_MAP.items():
            if bp_key in row:
                if our_key == "description":
                    item[our_key] = str(row[bp_key] or "").strip()
                else:
                    item[our_key] = _safe_float(row[bp_key])
        if item:
            line_items.append(item)

    # Per-field confidence from explainability_info; fall back to a default.
    confidence = _extract_confidence(raw, fields)
    conf_values = [c for c in confidence.values() if c]
    overall = sum(conf_values) / len(conf_values) if conf_values else 0.0

    # Ensure every downstream-expected field is present (None when absent).
    for name in _EXPECTED_FIELDS:
        fields.setdefault(name, None)

    return {
        **fields,
        "lineItems": line_items,
        "confidence": confidence,
        "overallConfidence": round(overall, 4),
    }


def _extract_confidence(raw: dict, fields: dict[str, Any]) -> dict[str, float]:
    """Build a per-field confidence map from BDA explainability info.

    ``explainability_info`` is a list of dicts keyed by the blueprint field
    names, each carrying a ``confidence`` float. Missing entries default to a
    conservative value so the pipeline still has a usable score.
    """
    explain = raw.get("explainability_info") or []
    # explainability_info is typically a list with one dict of field -> {confidence}
    flat: dict[str, Any] = {}
    if isinstance(explain, list):
        for entry in explain:
            if isinstance(entry, dict):
                flat.update(entry)
    elif isinstance(explain, dict):
        flat = explain

    confidence: dict[str, float] = {}
    for bp_key, our_key in _BP_FIELD_MAP.items():
        if our_key not in fields or fields[our_key] is None:
            continue
        info = flat.get(bp_key)
        if isinstance(info, dict) and "confidence" in info:
            confidence[our_key] = round(float(info["confidence"]), 4)
        else:
            # Field was extracted but no explicit score provided.
            confidence[our_key] = 0.9
    return confidence


def _coerce_field(field_name: str, raw_value: str) -> Any:
    """Coerce a raw string value to the appropriate Python type."""
    numeric_fields = {"subtotal", "taxAmount", "totalAmount"}
    if field_name in numeric_fields:
        return _safe_float(raw_value)
    return raw_value.strip()


def _safe_float(value: Any) -> float:
    """Parse a money/quantity value to float.

    Accepts numbers (returned as-is) or strings (currency symbols and thousands
    separators stripped). Anything unparseable becomes 0.0.
    """
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return 0.0
    cleaned = str(value).replace("$", "").replace(",", "").strip()
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
