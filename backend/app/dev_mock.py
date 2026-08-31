"""Local development mock — activates moto in-process DynamoDB and S3.

Imported automatically when STAGE=dev and AWS credentials are absent.
Creates the DynamoDB tables and S3 bucket defined in settings,
then seeds a handful of sample invoices so the UI has data to display.

This module must be imported BEFORE any boto3 client is created.
"""

import json
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import boto3

from app.config import settings


def _now(offset_minutes: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=offset_minutes)).isoformat()


def start() -> None:
    """Activate moto mocks and provision all local resources."""
    try:
        from moto import mock_aws
    except ImportError:
        return  # moto not installed (production)

    # Activate the single unified mock — persists for the entire process lifetime
    _aws_mock = mock_aws()
    _aws_mock.start()

    _create_tables()
    _create_bucket()
    _seed_invoices()
    _seed_purchase_orders()
    _seed_goods_receipts()
    _seed_documents()
    patch_agent_for_dev()


# ── Table / bucket creation ───────────────────────────────────────────────────

def _dynamo():
    return boto3.client("dynamodb", region_name=settings.AWS_REGION)


def _create_tables() -> None:
    client = _dynamo()

    # Invoices
    client.create_table(
        TableName=settings.INVOICE_TABLE,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "documentId", "AttributeType": "S"},
            {"AttributeName": "status",     "AttributeType": "S"},
            {"AttributeName": "uploadedBy", "AttributeType": "S"},
            {"AttributeName": "uploadedAt", "AttributeType": "S"},
        ],
        KeySchema=[{"AttributeName": "documentId", "KeyType": "HASH"}],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "GSI-StatusDate",
                "KeySchema": [
                    {"AttributeName": "status",     "KeyType": "HASH"},
                    {"AttributeName": "uploadedAt", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "GSI-UserDate",
                "KeySchema": [
                    {"AttributeName": "uploadedBy", "KeyType": "HASH"},
                    {"AttributeName": "uploadedAt", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    )

    # Purchase Orders
    client.create_table(
        TableName=settings.PO_TABLE,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "poNumber",   "AttributeType": "S"},
            {"AttributeName": "vendorName", "AttributeType": "S"},
            {"AttributeName": "createdDate","AttributeType": "S"},
        ],
        KeySchema=[{"AttributeName": "poNumber", "KeyType": "HASH"}],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "GSI-VendorDate",
                "KeySchema": [
                    {"AttributeName": "vendorName",  "KeyType": "HASH"},
                    {"AttributeName": "createdDate", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    )

    # Goods Receipts
    client.create_table(
        TableName=settings.GR_TABLE,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "grId",         "AttributeType": "S"},
            {"AttributeName": "poNumber",     "AttributeType": "S"},
            {"AttributeName": "receivedDate", "AttributeType": "S"},
        ],
        KeySchema=[{"AttributeName": "grId", "KeyType": "HASH"}],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "GSI-PONumber",
                "KeySchema": [
                    {"AttributeName": "poNumber",     "KeyType": "HASH"},
                    {"AttributeName": "receivedDate", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    )

    # Conversations
    client.create_table(
        TableName=settings.CONVERSATION_TABLE,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "sessionId", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "S"},
            {"AttributeName": "userId",    "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "sessionId", "KeyType": "HASH"},
            {"AttributeName": "timestamp", "KeyType": "RANGE"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "GSI-UserSessions",
                "KeySchema": [
                    {"AttributeName": "userId",    "KeyType": "HASH"},
                    {"AttributeName": "timestamp", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "KEYS_ONLY"},
            }
        ],
    )

    # Documents
    client.create_table(
        TableName=settings.DOCUMENT_TABLE,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "documentId", "AttributeType": "S"},
            {"AttributeName": "category",   "AttributeType": "S"},
            {"AttributeName": "uploadedAt", "AttributeType": "S"},
        ],
        KeySchema=[{"AttributeName": "documentId", "KeyType": "HASH"}],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "GSI-CategoryDate",
                "KeySchema": [
                    {"AttributeName": "category",   "KeyType": "HASH"},
                    {"AttributeName": "uploadedAt", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    )


def _create_bucket() -> None:
    s3 = boto3.client("s3", region_name=settings.AWS_REGION)
    # S3 requires an explicit LocationConstraint for every region except
    # us-east-1. Omitting it raises IllegalLocationConstraintException.
    if settings.AWS_REGION == "us-east-1":
        s3.create_bucket(Bucket=settings.DOCUMENT_BUCKET)
    else:
        s3.create_bucket(
            Bucket=settings.DOCUMENT_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": settings.AWS_REGION},
        )


# ── Seed data ─────────────────────────────────────────────────────────────────

def _seed_invoices() -> None:
    table = boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(settings.INVOICE_TABLE)

    def D(v) -> Decimal:
        """Convert float/int to Decimal for DynamoDB."""
        return Decimal(str(v))

    invoices = [
        {
            "documentId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            "fileName": "INV-2024-0891-Acme.pdf",
            "s3Key": "invoices/f47ac10b-58cc-4372-a567-0e02b2c3d479/INV-2024-0891-Acme.pdf",
            "documentType": "invoices",
            "status": "APPROVED",
            "uploadedBy": "dev-user-001",
            "uploadedAt": _now(-120),
            "updatedAt":  _now(-118),
            "contentType": "application/pdf",
            "extraction": {
                "vendorName":     "Acme Office Supplies Inc.",
                "invoiceNumber":  "INV-2024-0891",
                "invoiceDate":    "2026-07-20",
                "dueDate":        "2026-08-20",
                "poReference":    "PO-2024-0456",
                "subtotal":       D(610.00),
                "taxAmount":      D(48.80),
                "totalAmount":    D(658.80),
                "paymentTerms":   "Net 30",
                "lineItems": [
                    {"description": "Premium Copy Paper (10 reams)", "quantity": D(10),
                     "unitPrice": D(45.00), "amount": D(450.00)},
                    {"description": "Ink Cartridges - Black", "quantity": D(5),
                     "unitPrice": D(32.00), "amount": D(160.00)},
                ],
            },
            "confidence": {
                "vendorName": D(0.97), "invoiceNumber": D(0.99), "invoiceDate": D(0.95),
                "poReference": D(0.98), "totalAmount": D(0.98), "subtotal": D(0.96),
            },
            "overallConfidence": D(0.97),
            "matchResult": {
                "threeWayMatch": "PASS",
                "poMatch": {
                    "status": "MATCHED", "poId": "PO-2024-0456",
                    "amountVariancePct": D(0.0), "discrepancies": [],
                },
                "grMatch": {
                    "status": "CONFIRMED", "grId": "GR-2024-0789",
                    "quantityReceived": D(15), "discrepancies": [],
                },
            },
            "approvalDecision": {
                "decision": "APPROVED", "approver": "SYSTEM",
                "approvedAt": _now(-118),
                "rulesEvaluated": ["RULE-001", "RULE-002", "RULE-003", "RULE-004"],
                "rulesPassed":    ["RULE-001", "RULE-002", "RULE-003", "RULE-004"],
            },
            "processingDurationMs": D(28000),
        },
        {
            "documentId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "fileName": "INV-2024-0892-TechParts.pdf",
            "s3Key": "invoices/a1b2c3d4-e5f6-7890-abcd-ef1234567890/INV-2024-0892-TechParts.pdf",
            "documentType": "invoices",
            "status": "ESCALATED",
            "uploadedBy": "dev-user-001",
            "uploadedAt": _now(-60),
            "updatedAt":  _now(-58),
            "contentType": "application/pdf",
            "extraction": {
                "vendorName":   "TechParts Global Ltd.",
                "invoiceNumber": "INV-2024-0892",
                "invoiceDate":  "2026-07-22",
                "totalAmount":  D(15000.00),
                "poReference":  "PO-2024-0457",
                "lineItems": [
                    {"description": "Industrial Servo Motors x10", "quantity": D(10),
                     "unitPrice": D(1500.00), "amount": D(15000.00)},
                ],
            },
            "confidence": {
                "vendorName": D(0.94), "invoiceNumber": D(0.98), "totalAmount": D(0.96),
            },
            "overallConfidence": D(0.96),
            "matchResult": {
                "threeWayMatch": "PASS",
                "poMatch": {
                    "status": "MATCHED", "poId": "PO-2024-0457",
                    "amountVariancePct": D(0.0), "discrepancies": [],
                },
                "grMatch": {
                    "status": "CONFIRMED", "grId": "GR-2024-0790",
                    "quantityReceived": D(10), "discrepancies": [],
                },
            },
            "approvalDecision": {
                "decision":   "ESCALATE",
                "escalateTo": "FINANCE_MANAGER",
                "reason":     "Amount $15000.00 exceeds auto-approval threshold of $10000.00",
            },
            "processingDurationMs": D(31000),
        },
        {
            "documentId": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
            "fileName": "INV-2024-0893-UnknownVendor.pdf",
            "s3Key": "invoices/b2c3d4e5-f6a7-8901-bcde-f12345678901/INV-2024-0893-UnknownVendor.pdf",
            "documentType": "invoices",
            "status": "ESCALATED",
            "uploadedBy": "dev-user-001",
            "uploadedAt": _now(-30),
            "updatedAt":  _now(-28),
            "contentType": "application/pdf",
            "extraction": {
                "vendorName":    "Unknown Supplies Ltd.",
                "invoiceNumber": "INV-2024-0893",
                "invoiceDate":   "2026-07-25",
                "totalAmount":   D(250.00),
                "lineItems": [
                    {"description": "Office Stationery Bundle", "quantity": D(1),
                     "unitPrice": D(250.00), "amount": D(250.00)},
                ],
            },
            "confidence": {
                "vendorName": D(0.91), "invoiceNumber": D(0.97), "totalAmount": D(0.95),
            },
            "overallConfidence": D(0.94),
            "matchResult": {
                "threeWayMatch": "FAIL",
                "poMatch": {"status": "NO_MATCH", "discrepancies": ["PO not found"]},
                "grMatch": {"status": "NOT_RECEIVED", "discrepancies": []},
            },
            "approvalDecision": {
                "decision":   "ESCALATE",
                "escalateTo": "AP_CLERK",
                "reason":     "Three-way match failed: PO not found",
            },
            "processingDurationMs": D(24000),
        },
        {
            "documentId": "c3d4e5f6-a7b8-9012-cdef-123456789012",
            "fileName": "INV-2024-0894-Processing.pdf",
            "s3Key": "invoices/c3d4e5f6-a7b8-9012-cdef-123456789012/INV-2024-0894-Processing.pdf",
            "documentType": "invoices",
            "status": "PROCESSING",
            "uploadedBy": "dev-user-001",
            "uploadedAt": _now(-2),
            "updatedAt":  _now(-2),
            "contentType": "application/pdf",
        },
    ]

    for inv in invoices:
        table.put_item(Item=inv)


def _seed_purchase_orders() -> None:
    table = boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(settings.PO_TABLE)
    pos = [
        {
            "poNumber": "PO-2024-0456",
            "vendorName": "Acme Office Supplies Inc.",
            "vendorId": "VENDOR-001",
            "createdDate": "2026-07-01",
            "totalAmount": Decimal("658.80"),
            "currency": "USD",
            "status": "OPEN",
            "department": "Administration",
        },
        {
            "poNumber": "PO-2024-0457",
            "vendorName": "TechParts Global Ltd.",
            "vendorId": "VENDOR-002",
            "createdDate": "2026-07-05",
            "totalAmount": Decimal("15000.00"),
            "currency": "USD",
            "status": "OPEN",
            "department": "Engineering",
        },
    ]
    for po in pos:
        table.put_item(Item=po)


def _seed_goods_receipts() -> None:
    table = boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(settings.GR_TABLE)
    grs = [
        {
            "grId": "GR-2024-0789",
            "poNumber": "PO-2024-0456",
            "receivedDate": "2026-07-15",
            "totalQuantityReceived": Decimal("15"),
            "status": "COMPLETE",
        },
        {
            "grId": "GR-2024-0790",
            "poNumber": "PO-2024-0457",
            "receivedDate": "2026-07-18",
            "totalQuantityReceived": Decimal("10"),
            "status": "COMPLETE",
        },
    ]
    for gr in grs:
        table.put_item(Item=gr)


def _seed_documents() -> None:
    table = boto3.resource("dynamodb", region_name=settings.AWS_REGION).Table(settings.DOCUMENT_TABLE)
    docs = [
        {
            "documentId": "doc-policy-001",
            "fileName": "Travel-Policy-2024.pdf",
            "s3Key": "records/doc-policy-001/Travel-Policy-2024.pdf",
            "category": "policies",
            "uploadedAt": _now(-2880),
            "uploadedBy": "dev-user-001",
            "description": "Corporate travel and reimbursement policy FY2024",
            "kbSyncStatus": "SYNCED",
            "contentType": "application/pdf",
        },
        {
            "documentId": "doc-contract-001",
            "fileName": "Vendor-Contract-Acme-2024.pdf",
            "s3Key": "records/doc-contract-001/Vendor-Contract-Acme-2024.pdf",
            "category": "contracts",
            "uploadedAt": _now(-1440),
            "uploadedBy": "dev-user-001",
            "description": "Supply agreement with Acme Office Supplies Inc.",
            "kbSyncStatus": "SYNCED",
            "contentType": "application/pdf",
        },
        {
            "documentId": "doc-finance-001",
            "fileName": "Procurement-Guidelines-2024.pdf",
            "s3Key": "records/doc-finance-001/Procurement-Guidelines-2024.pdf",
            "category": "procurement",
            "uploadedAt": _now(-720),
            "uploadedBy": "dev-user-001",
            "description": "Procurement approval thresholds and procedures",
            "kbSyncStatus": "PENDING",
            "contentType": "application/pdf",
        },
    ]
    for doc in docs:
        table.put_item(Item=doc)


def patch_agent_for_dev() -> None:
    """Replace AgentService.stream_answer with a canned response for offline dev.

    Strands Agents calls Amazon Bedrock for inference. When running locally
    without Bedrock credentials, this stub lets the SSE flow work end-to-end
    by yielding a fixed streaming response.
    """
    from app.services import agent as agent_module

    async def _mock_stream_answer(question, session_id, user, category_filter=None):
        canned = (
            "This is a mock response from the local development environment. "
            "Deploy to AWS with Bedrock access to enable the full AI assistant. "
            f"You asked: {question}"
        )
        chunk_size = 24
        for i in range(0, len(canned), chunk_size):
            yield {"type": "token", "content": canned[i:i + chunk_size]}
        yield {
            "type": "done",
            "sessionId": session_id,
            "sourceType": "agent",
            "citations": [],
            "dataSnapshot": None,
        }

    agent_module.AgentService.stream_answer = staticmethod(_mock_stream_answer)

    # Also stub BedrockService.invoke_model so features that call the model
    # directly (e.g. conversation summarization) work offline. moto does not
    # implement the Bedrock runtime invoke_model API.
    from app.services import bedrock as bedrock_module

    def _mock_invoke_model(self, prompt, max_tokens=1024, temperature=0.0):
        return (
            "This is a mock summary generated in the local development "
            "environment. Deploy to AWS with Bedrock access to enable real "
            "summaries."
        )

    bedrock_module.BedrockService.invoke_model = _mock_invoke_model
