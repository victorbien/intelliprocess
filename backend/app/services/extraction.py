"""Bedrock Data Automation (BDA) extraction service.

Extracts structured invoice fields from a PDF/PNG/JPEG stored in S3 using the
current BDA API: an async invocation keyed by a data-automation *profile* ARN
plus the AWS-managed public invoice blueprint. BDA returns an
``inference_result`` document which we normalise into our internal schema.

MVP flow
--------
1.  Call ``InvokeDataAutomationAsync`` with the S3 URI of the invoice, the
    data-automation profile ARN, and the public invoice blueprint.
2.  Poll ``GetDataAutomationStatus`` until the job reaches a terminal state.
3.  Follow ``job_metadata.json`` -> ``custom_output_path`` to the inference JSON.
4.  Normalise the blueprint fields into our internal ``ExtractionResult`` dict.

When ``USE_MOCKS=true`` (local dev), the service skips BDA entirely and returns
a deterministic mock result so tests never require real AWS credentials.

Notes
-----
- ap-southeast-2 requires ``dataAutomationProfileArn`` on every invocation; the
  account ID is resolved at runtime via STS.
- The public invoice blueprint ships a trained invoice extractor, so no custom
  blueprint provisioning is needed.
- Confidence per field comes from ``explainability_info`` when present.
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
_BDA_MAX_POLLS = 40          # 40 × 3 s = 120 s max wait (BDA can take ~20-60 s)
_BDA_OUTPUT_PREFIX = "bda-output/"

# Data-automation profile ARN template. BDA requires this on every
# InvokeDataAutomationAsync call. The "apac." profile is what ap-southeast-2
# resolves to. The account ID is resolved at runtime via STS.
_BDA_PROFILE_TEMPLATE = (
    "arn:aws:bedrock:{region}:{account}:data-automation-profile/apac.data-automation-v1"
)

# AWS-managed public Invoice blueprint (no custom provisioning needed).
_BDA_INVOICE_BLUEPRINT_ARN = (
    f"arn:aws:bedrock:{settings.AWS_REGION}:aws"
    f":blueprint/bedrock-data-automation-public-invoice"
)

# Maps the public invoice blueprint's field names -> our internal schema.
# Fields the blueprint does not provide (dueDate, paymentTerms) default to None.
_BP_FIELD_MAP = {
    "VENDORNAME":    "vendorName",
    "VENDORADDRESS": "vendorAddress",
    "ID":            "invoiceNumber",
    "DATE":          "invoiceDate",
    "PO":            "poReference",
    "SUBTOTAL":      "subtotal",
    "TOTAL":         "totalAmount",
}

# Line-item field mapping (blueprint SERVICES_TABLE entry -> our lineItems entry).
_BP_LINE_ITEM_MAP = {
    "product description": "description",
    "quantity":            "quantity",
    "unit price":          "unitPrice",
    "amount":              "amount",
}

# Fields the downstream pipeline expects to always be present in the result.
_EXPECTED_FIELDS = (
    "vendorName", "vendorAddress", "invoiceNumber", "invoiceDate", "dueDate",
    "poReference", "subtotal", "taxAmount", "totalAmount", "paymentTerms",
)


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


class ExtractionTimeout(Exception):
    """Raised when a bounded extraction wait elapses while the BDA job is still
    running. Carries the ``invocation_arn`` so the caller can resume polling
    asynchronously (sync-then-async fallback for the admin upload endpoints)."""

    def __init__(self, invocation_arn: str):
        super().__init__("Extraction still in progress")
        self.invocation_arn = invocation_arn


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
            "USE_MOCKS=true - returning mock extraction",
            extra={"bucket": bucket, "s3Key": s3_key},
        )
        return _mock_extraction(s3_key)

    return _bda_extract(bucket, s3_key)


# Sentinel ARN prefix used when USE_MOCKS is on, so the async poll/finalize
# path can recognise a mock job and return canned data without calling AWS.
_MOCK_ARN_PREFIX = "mock-invocation:"


def start_bda_job(
    file_bytes: bytes,
    filename: str,
    prefix: str,
    content_type: str = "application/pdf",
) -> str:
    """Upload the document and start an async BDA job. Returns the invocation ARN.

    The invocation ARN is the only handle needed to poll and finalise later, so
    it doubles as the async job token for the sync-then-async upload flow.
    """
    import uuid as _uuid

    from app.services.s3 import S3Client

    s3_key = f"{prefix}/{_uuid.uuid4()}/{filename}"

    if settings.USE_MOCKS:
        logger.info("USE_MOCKS=true - mock BDA job started", extra={"s3Key": s3_key})
        return f"{_MOCK_ARN_PREFIX}{s3_key}"

    s3 = S3Client()
    s3.upload_bytes(s3_key, file_bytes, content_type)

    runtime = boto3.client(
        "bedrock-data-automation-runtime", region_name=settings.AWS_REGION
    )
    s3_input_uri = f"s3://{s3.bucket}/{s3_key}"
    s3_output_uri = f"s3://{s3.bucket}/{_BDA_OUTPUT_PREFIX}{s3_key}"

    logger.info(
        "Starting BDA extraction",
        extra={"s3Input": s3_input_uri, "blueprint": _BDA_INVOICE_BLUEPRINT_ARN},
    )
    try:
        response = runtime.invoke_data_automation_async(
            inputConfiguration={"s3Uri": s3_input_uri},
            outputConfiguration={"s3Uri": s3_output_uri},
            dataAutomationProfileArn=_bda_profile_arn(),
            blueprints=[{"blueprintArn": _BDA_INVOICE_BLUEPRINT_ARN, "stage": "LIVE"}],
        )
    except ClientError as exc:
        raise ExtractionError(
            f"Failed to start BDA job: {exc.response['Error']['Message']}"
        ) from exc

    invocation_arn = response["invocationArn"]
    logger.info("BDA job started", extra={"invocationArn": invocation_arn})
    return invocation_arn


def poll_bda_status(invocation_arn: str) -> str:
    """Return a coarse job status: 'InProgress' | 'Success' | 'Failed'.

    Non-blocking (single status call, no sleep). Raises ExtractionError only for
    an unexpected API failure; a failed BDA job is reported as 'Failed'.
    """
    if invocation_arn.startswith(_MOCK_ARN_PREFIX):
        return "Success"

    runtime = boto3.client(
        "bedrock-data-automation-runtime", region_name=settings.AWS_REGION
    )
    try:
        resp = runtime.get_data_automation_status(invocationArn=invocation_arn)
    except ClientError as exc:
        raise ExtractionError(
            f"BDA status poll failed: {exc.response['Error']['Message']}"
        ) from exc

    status = resp.get("status", "")
    if status == "Success":
        return "Success"
    if status in ("ServiceError", "ClientError"):
        return "Failed"
    return "InProgress"


def finalize_bda_job(invocation_arn: str) -> dict[str, Any]:
    """Read + parse the result of a completed BDA job. Assumes status == Success.

    Returns the same normalised extraction dict as ``extract_invoice``.
    """
    if invocation_arn.startswith(_MOCK_ARN_PREFIX):
        s3_key = invocation_arn[len(_MOCK_ARN_PREFIX):]
        return _mock_extraction(s3_key)

    from app.services.s3 import S3Client

    bucket = S3Client().bucket
    runtime = boto3.client(
        "bedrock-data-automation-runtime", region_name=settings.AWS_REGION
    )
    try:
        status_resp = runtime.get_data_automation_status(invocationArn=invocation_arn)
    except ClientError as exc:
        raise ExtractionError(
            f"BDA status read failed: {exc.response['Error']['Message']}"
        ) from exc

    meta_uri = status_resp.get("outputConfiguration", {}).get("s3Uri", "")
    inference = _read_bda_custom_output(bucket, meta_uri)
    extraction = _parse_bda_response(inference)
    _validate_extraction_result(extraction)
    logger.info(
        "BDA extraction complete",
        extra={
            "invocationArn": invocation_arn,
            "overallConfidence": extraction.get("overallConfidence"),
            "vendor": extraction.get("vendorName"),
        },
    )
    return extraction


def extract_from_bytes(
    file_bytes: bytes,
    filename: str,
    prefix: str,
    content_type: str = "application/pdf",
    timeout_s: float | None = None,
) -> dict[str, Any]:
    """Extract invoice-shaped fields from an uploaded document.

    Starts a BDA job and waits for it. If ``timeout_s`` is given and elapses
    while the job is still running, raises ``ExtractionTimeout`` (carrying the
    invocation ARN) so the caller can hand the job off to async polling.

    Reused by the admin PO/GR upload endpoints (Option A: the invoice blueprint
    also captures vendor / id / total, which map onto PO and GR fields).
    """
    # Start the deadline clock BEFORE the upload/invoke so the whole operation
    # (upload + STS + invoke + polling) fits within timeout_s — keeping the HTTP
    # response comfortably under the API Gateway 29s ceiling.
    deadline = None if timeout_s is None else (time.monotonic() + timeout_s)

    invocation_arn = start_bda_job(file_bytes, filename, prefix, content_type)

    for _ in range(_BDA_MAX_POLLS):
        status = poll_bda_status(invocation_arn)
        if status == "Success":
            return finalize_bda_job(invocation_arn)
        if status == "Failed":
            raise ExtractionError("BDA job failed", retryable=True)
        # Bail out to async BEFORE sleeping again if the next poll cycle would
        # risk exceeding the budget (leaves margin for finalize + response).
        if deadline is not None and time.monotonic() + _BDA_POLL_INTERVAL_S >= deadline:
            raise ExtractionTimeout(invocation_arn)
        time.sleep(_BDA_POLL_INTERVAL_S)

    raise ExtractionError(
        f"BDA job timed out after {_BDA_MAX_POLLS * _BDA_POLL_INTERVAL_S}s",
        retryable=True,
    )


# ── BDA implementation ────────────────────────────────────────────────────────

def _bda_profile_arn() -> str:
    """Build the data-automation profile ARN, resolving the account via STS."""
    account = boto3.client(
        "sts", region_name=settings.AWS_REGION
    ).get_caller_identity()["Account"]
    return _BDA_PROFILE_TEMPLATE.format(region=settings.AWS_REGION, account=account)


def _bda_extract(bucket: str, s3_key: str) -> dict[str, Any]:
    """Invoke BDA with the public invoice blueprint and wait for the result."""
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
    _validate_extraction_result(extraction)

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
            raise ExtractionError(
                f"BDA job failed: {reason}",
                retryable=(status == "ServiceError"),
            )

    raise ExtractionError(
        f"BDA job timed out after {_BDA_MAX_POLLS * _BDA_POLL_INTERVAL_S}s",
        retryable=True,
    )


def _read_bda_custom_output(bucket: str, meta_uri: str) -> dict:
    """Follow the BDA job metadata to the custom-output inference result.

    BDA writes a ``job_metadata.json`` whose ``output_metadata`` points at a
    ``custom_output_path`` per segment. That file contains ``inference_result``
    (the extracted fields) and ``explainability_info`` (per-field confidence).
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
        "BDA produced no custom output - the invoice blueprint did not match."
    )


# ── Output validation ────────────────────────────────────────────────────────

def _validate_extraction_result(extraction: dict[str, Any]) -> None:
    """Validate the normalized extraction has minimum usable content.

    Logs warnings for missing critical fields but does NOT raise - partial
    extractions are still persisted so humans can review them.
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
            "Extraction confidence is very low - document may be unreadable",
            extra={"overallConfidence": overall_conf},
        )


# ── BDA response parsing ─────────────────────────────────────────────────────

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

    # TAX may be a list of tax amounts (public blueprint) or a scalar.
    tax_values = inference.get("TAX")
    if isinstance(tax_values, list):
        fields["taxAmount"] = round(sum(_safe_float(t) for t in tax_values), 2)
    elif tax_values not in (None, ""):
        fields["taxAmount"] = _safe_float(tax_values)

    # Line items from SERVICES_TABLE.
    line_items: list[dict] = []
    for row in inference.get("SERVICES_TABLE") or []:
        if not isinstance(row, dict):
            continue
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


def _coerce_field(field_name: str, raw_value: Any) -> Any:
    """Coerce a raw value to the appropriate Python type."""
    numeric_fields = {"subtotal", "taxAmount", "totalAmount"}
    if field_name in numeric_fields:
        return _safe_float(raw_value)
    return str(raw_value).strip()


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
    """Return a mock extraction that passes all rules (matches seeded PO/GR)."""
    return _build_mock_result(
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
