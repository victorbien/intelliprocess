# BDA Invoice Extraction — Integration Handoff

## Summary

The real Bedrock Data Automation (BDA) invoice-extraction path is now wired up
in `backend/app/services/extraction.py`. `extract_invoice(bucket, s3_key)`
returns the same schema the downstream pipeline already consumes
(`processor.py` → `matcher.py` → `rules.py`), so no downstream code changed.

Verified end-to-end against a real invoice PDF in S3
(`invoices/incoming/ForteAU BINV Example.pdf`): BDA extracted the vendor,
invoice number, totals, tax, and line items, and the result matched the schema
returned by the mock path.

## What was NOT required

- **No AWS console configuration.** The extraction uses the AWS-managed public
  invoice blueprint. No custom blueprint or BDA project needs to be created in
  the account.
- **No new S3 bucket.** The existing `intelliprocess-ai-documents` bucket is
  used, with the existing `invoices/` prefix structure.
- BDA and the Records Assistant (Strands + Bedrock Nova) are independent paths;
  they share no runtime dependency.

## Key configuration facts

| Item | Value |
|------|-------|
| Region | `ap-southeast-2` |
| S3 bucket (`DOCUMENT_BUCKET`) | `intelliprocess-ai-documents` |
| Data automation profile | `arn:aws:bedrock:ap-southeast-2:<ACCOUNT_ID>:data-automation-profile/apac.data-automation-v1` |
| Public invoice blueprint | `arn:aws:bedrock:ap-southeast-2:aws:blueprint/bedrock-data-automation-public-invoice` |
| BDA output prefix | `bda-output/` (under the same bucket) |

Notes:
- The account ID in the profile ARN is resolved at runtime via STS
  (`get_caller_identity`), so it is not hardcoded.
- The `apac.` profile prefix is what `ap-southeast-2` resolves to. Other regions
  use different prefixes (`us.`, `eu.`, etc.).

## Dependency change

`boto3`/`botocore` were upgraded from `1.35.0` to `1.43.x`. The older version's
BDA API did not accept `dataAutomationProfileArn` (a required parameter on the
current `InvokeDataAutomationAsync`). After the upgrade, the DynamoDB and
Bedrock (Nova) paths were re-verified and continue to work.

`requirements.txt` should reflect the upgraded pin. Confirm the deployed
Lambda/runtime uses a boto3 that supports the current BDA API.

## The `USE_MOCKS` switch

`extract_invoice()` branches on `settings.USE_MOCKS`:

- `USE_MOCKS=true` → returns a deterministic mock extraction (no AWS calls).
  Use this for local development without credentials.
- `USE_MOCKS=false` → calls real BDA against the S3 object.

The `.env` currently has `USE_MOCKS=false` and `STAGE=dev`, so extraction hits
real BDA. Real AWS credentials are required (e.g. `AWS_PROFILE=team6` with an
active `aws sso login`).

## How the real path works

1. `invoke_data_automation_async` is called with:
   - `inputConfiguration.s3Uri` = the invoice object
   - `outputConfiguration.s3Uri` = `bda-output/<key>`
   - `dataAutomationProfileArn` = the profile ARN above
   - `blueprints` = the public invoice blueprint (stage `LIVE`)
2. The job is polled via `get_data_automation_status` until `Success`
   (statuses: `InProgress` / `Success` / `ServiceError` / `ClientError`).
   Timeout: 40 polls × 3 s = 120 s.
3. The terminal status returns the S3 URI of `job_metadata.json`. That file's
   `output_metadata[].segment_metadata[].custom_output_path` points at the
   inference result JSON, which contains `inference_result` (fields) and
   `explainability_info` (per-field confidence).

## Field mapping (public blueprint → internal schema)

| Blueprint field | Internal field |
|-----------------|----------------|
| `VENDORNAME` | `vendorName` |
| `VENDORADDRESS` | `vendorAddress` |
| `ID` | `invoiceNumber` |
| `DATE` | `invoiceDate` |
| `PO` | `poReference` |
| `SUBTOTAL` | `subtotal` |
| `TOTAL` | `totalAmount` |
| `TAX` (array) | `taxAmount` (summed to a scalar) |
| `SERVICES_TABLE[]` | `lineItems[]` |
| `SERVICES_TABLE[].product description` | `lineItems[].description` |
| `SERVICES_TABLE[].quantity` | `lineItems[].quantity` |
| `SERVICES_TABLE[].unit price` | `lineItems[].unitPrice` |
| `SERVICES_TABLE[].amount` | `lineItems[].amount` |

Per-field confidence comes from `explainability_info`; `overallConfidence` is
the mean of the available field confidences. All numeric values are Python
`float` (the caller converts to `Decimal` for DynamoDB).

## Known gap

The public invoice blueprint does not provide `dueDate` or `paymentTerms`.
`extract_invoice()` returns `None` for these, and the pipeline handles that
safely. If the product requires those fields, create a custom blueprint that
adds them (uses the same JSON schema shape as the public blueprint, with each
field marked `"inferenceType": "explicit"` and a natural-language
`"instruction"`), then point `blueprints` at the custom ARN. This is a product
decision for the invoice module, not a blocker for the current pipeline.

## Result schema (contract with downstream)

```
{
  "vendorName": str | None,
  "vendorAddress": str | None,
  "invoiceNumber": str | None,
  "invoiceDate": str | None,
  "dueDate": str | None,
  "poReference": str | None,
  "subtotal": float | None,
  "taxAmount": float | None,
  "totalAmount": float | None,
  "paymentTerms": str | None,
  "lineItems": [
    {"description": str, "quantity": float, "unitPrice": float, "amount": float}
  ],
  "confidence": {"<fieldName>": float, ...},
  "overallConfidence": float
}
```

## Verification performed

- Real BDA extraction against `ForteAU BINV Example.pdf` returned all required
  keys with correct types (floats, not Decimals).
- `pytest tests/unit/test_processor.py` — 23 passed (downstream pipeline
  unaffected).
- Mock path (`USE_MOCKS=true`) still returns a valid extraction.
- No non-English characters in `extraction.py`.

## Reuse for Purchase Order / Goods Receipt extraction

The same BDA path (public invoice blueprint + `apac.data-automation-v1` profile)
is reused to extract fields from uploaded **Purchase Order** and **Goods
Receipt** documents. `extraction.py` exposes a lower-level, byte-oriented entry
point (`extract_from_bytes(data, timeout_s)`) plus split-phase helpers
(`start_bda_job` / `poll_bda_status` / `finalize_bda_job`) so the
DashboardHandler can run extraction within the API Gateway 29s window and fall
back to an asynchronous, pollable job when a document takes longer:

- The `/purchase-orders/extract` and `/goods-receipts/extract` endpoints attempt
  a synchronous extraction capped at ~18s. If it completes, they return `200`
  with the extracted fields; otherwise they return `202` with
  `{status: "pending", jobId}` (a base64 token wrapping the invocation ARN and
  the document kind).
- The matching `/status` endpoints poll the job and return `200` (done),
  `202` (still running), or `422` (failed).

No custom blueprint is required for POs/GRs — the invoice blueprint's field set
is sufficient for the fields the reference records need (a product decision,
Option A). See `09-api-specification.md` §7A and `07-component-design.md` §4.5b.
