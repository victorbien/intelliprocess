# Database Design

## IntelliProcess AI Platform

---

## 1. Database Strategy

### 1.1 Why DynamoDB

| Decision Factor | DynamoDB | Aurora Serverless (Alternative) |
|----------------|----------|-------------------------------|
| Serverless | True serverless, no cold start | v2 has min capacity (cost) |
| Pricing model | Pay-per-request (ideal for low-volume MVP) | Min ~$43/month |
| Schema flexibility | Schema-less (rapid iteration) | Requires migrations |
| Lambda integration | Native, no connection pooling needed | Requires RDS Proxy |
| Access patterns | Key-value + index queries (sufficient) | Full SQL joins |
| Operational overhead | Zero | Backups, patching, monitoring |

**Decision**: DynamoDB on-demand mode. Our access patterns are well-defined key-value lookups and index queries. We don't need relational joins — matching logic is handled in application code.

### 1.2 Data Storage Overview

| Store | Technology | Data Type |
|-------|-----------|-----------|
| Document files | Amazon S3 | Binary (PDF, images, DOCX) |
| Structured metadata | DynamoDB | JSON documents |
| Vector embeddings | OpenSearch Serverless | Vectors (managed by Bedrock KB) |
| User identity | Cognito | User profiles and groups |

---

## 2. DynamoDB Table Design

### 2.1 Table Overview

| Table Name | Purpose | Billing | Encryption |
|-----------|---------|---------|-----------|
| IntelliProcess-Invoices | Invoice metadata, extraction results, status | On-demand | AWS-managed |
| IntelliProcess-PurchaseOrders | PO reference data for matching | On-demand | AWS-managed |
| IntelliProcess-GoodsReceipts | GR reference data for matching | On-demand | AWS-managed |
| IntelliProcess-Conversations | Chat session history | On-demand | AWS-managed |
| IntelliProcess-Documents | General document metadata (records) | On-demand | AWS-managed |

---

## 3. Table Schemas

### 3.1 Invoices Table

**Table Name**: `IntelliProcess-Invoices`

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| documentId | String | PK (Hash) | UUID, unique invoice identifier |
| fileName | String | - | Original uploaded file name |
| s3Key | String | - | Full S3 object key |
| status | String | GSI-1 PK | Current processing status |
| uploadedBy | String | GSI-2 PK | Cognito user sub (uploader) |
| uploadedAt | String | GSI-1 SK, GSI-2 SK | ISO 8601 timestamp |
| updatedAt | String | - | Last status change timestamp |
| documentType | String | - | Always "INVOICE" |
| extraction | Map | - | Extracted field data (see below) |
| confidence | Map | - | Per-field confidence scores |
| overallConfidence | Number | - | Average confidence (0.0-1.0) |
| matchResult | Map | - | Three-way match results |
| approvalDecision | Map | - | Final decision details |
| escalation | Map | - | Escalation details (if applicable) |
| errorDetails | String | - | Error message (if status=ERROR) |
| processingDurationMs | Number | - | Time from upload to decision |

**Global Secondary Indexes:**

| Index Name | Partition Key | Sort Key | Projection | Purpose |
|-----------|--------------|----------|-----------|---------|
| GSI-StatusDate | status | uploadedAt | ALL | List invoices by status |
| GSI-UserDate | uploadedBy | uploadedAt | ALL | List user's invoices |

**Example Item:**

```json
{
  "documentId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "fileName": "INV-2024-0891.pdf",
  "s3Key": "invoices/f47ac10b-58cc-4372-a567-0e02b2c3d479/INV-2024-0891.pdf",
  "status": "APPROVED",
  "uploadedBy": "user-sub-123456",
  "uploadedAt": "2026-07-25T10:30:00Z",
  "updatedAt": "2026-07-25T10:30:28Z",
  "documentType": "INVOICE",
  "extraction": {
    "vendorName": "Acme Office Supplies Inc.",
    "vendorAddress": "123 Business Ave, Suite 400, New York, NY 10001",
    "invoiceNumber": "INV-2024-0891",
    "invoiceDate": "2026-07-20",
    "dueDate": "2026-08-20",
    "poReference": "PO-2024-0456",
    "lineItems": [
      {
        "description": "Premium Copy Paper (10 reams)",
        "quantity": 10,
        "unitPrice": 45.00,
        "amount": 450.00
      },
      {
        "description": "Ink Cartridges - Black",
        "quantity": 5,
        "unitPrice": 32.00,
        "amount": 160.00
      }
    ],
    "subtotal": 610.00,
    "taxAmount": 48.80,
    "totalAmount": 658.80,
    "paymentTerms": "Net 30"
  },
  "confidence": {
    "vendorName": 0.97,
    "invoiceNumber": 0.99,
    "invoiceDate": 0.95,
    "dueDate": 0.93,
    "poReference": 0.98,
    "lineItems": 0.91,
    "subtotal": 0.96,
    "taxAmount": 0.94,
    "totalAmount": 0.98
  },
  "overallConfidence": 0.96,
  "matchResult": {
    "threeWayMatch": "PASS",
    "poMatch": {
      "status": "MATCHED",
      "poId": "PO-2024-0456",
      "amountVariancePct": 0.0,
      "discrepancies": []
    },
    "grMatch": {
      "status": "CONFIRMED",
      "grId": "GR-2024-0789",
      "quantityReceived": 15,
      "quantityInvoiced": 15,
      "discrepancies": []
    }
  },
  "approvalDecision": {
    "decision": "APPROVED",
    "approver": "SYSTEM",
    "approvedAt": "2026-07-25T10:30:28Z",
    "rulesEvaluated": ["RULE-001", "RULE-002", "RULE-003", "RULE-004"],
    "rulesPassed": ["RULE-001", "RULE-002", "RULE-003", "RULE-004"]
  },
  "processingDurationMs": 28000
}
```

---

### 3.2 Purchase Orders Table

**Table Name**: `IntelliProcess-PurchaseOrders`

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| poNumber | String | PK (Hash) | Unique PO identifier (e.g., "PO-2024-0456") |
| vendorName | String | GSI-1 PK | Vendor for fuzzy matching |
| vendorId | String | - | Internal vendor identifier |
| createdDate | String | GSI-1 SK | PO creation date |
| totalAmount | Number | - | Total PO value |
| currency | String | - | Currency code (USD) |
| status | String | - | OPEN, PARTIALLY_RECEIVED, CLOSED |
| lineItems | List | - | PO line items |
| department | String | - | Requesting department |
| approvedBy | String | - | PO approver name |

**Global Secondary Index:**

| Index Name | Partition Key | Sort Key | Purpose |
|-----------|--------------|----------|---------|
| GSI-VendorDate | vendorName | createdDate | Lookup POs by vendor |

**Example Item:**

```json
{
  "poNumber": "PO-2024-0456",
  "vendorName": "Acme Office Supplies Inc.",
  "vendorId": "VENDOR-001",
  "createdDate": "2026-07-01",
  "totalAmount": 658.80,
  "currency": "USD",
  "status": "OPEN",
  "lineItems": [
    {
      "lineNumber": 1,
      "description": "Premium Copy Paper (10 reams)",
      "quantity": 10,
      "unitPrice": 45.00,
      "amount": 450.00
    },
    {
      "lineNumber": 2,
      "description": "Ink Cartridges - Black",
      "quantity": 5,
      "unitPrice": 32.00,
      "amount": 160.00
    }
  ],
  "department": "Administration",
  "approvedBy": "Jane Smith"
}
```

---

### 3.3 Goods Receipts Table

**Table Name**: `IntelliProcess-GoodsReceipts`

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| grId | String | PK (Hash) | Unique GR identifier |
| poNumber | String | GSI-1 PK | Related PO number |
| receivedDate | String | GSI-1 SK | Date goods were received |
| receivedBy | String | - | Person who received goods |
| lineItems | List | - | Items received with quantities |
| totalQuantityReceived | Number | - | Sum of all quantities |
| notes | String | - | Receiving notes |
| status | String | - | COMPLETE, PARTIAL |

**Global Secondary Index:**

| Index Name | Partition Key | Sort Key | Purpose |
|-----------|--------------|----------|---------|
| GSI-PONumber | poNumber | receivedDate | Find GRs for a PO |

**Example Item:**

```json
{
  "grId": "GR-2024-0789",
  "poNumber": "PO-2024-0456",
  "receivedDate": "2026-07-15",
  "receivedBy": "Bob Johnson",
  "lineItems": [
    {
      "lineNumber": 1,
      "description": "Premium Copy Paper (10 reams)",
      "quantityOrdered": 10,
      "quantityReceived": 10,
      "condition": "GOOD"
    },
    {
      "lineNumber": 2,
      "description": "Ink Cartridges - Black",
      "quantityOrdered": 5,
      "quantityReceived": 5,
      "condition": "GOOD"
    }
  ],
  "totalQuantityReceived": 15,
  "notes": "All items received in good condition",
  "status": "COMPLETE"
}
```

---

### 3.4 Conversations Table

**Table Name**: `IntelliProcess-Conversations`

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| sessionId | String | PK (Hash) | Chat session identifier |
| timestamp | String | SK (Range) | Message timestamp (ISO 8601) |
| userId | String | GSI-1 PK | User who initiated conversation |
| role | String | - | "user" or "assistant" |
| content | String | - | Message text |
| citations | List | - | Citations (assistant messages only) |
| categoryFilter | String | - | Applied filter (if any) |
| ttl | Number | - | TTL epoch (auto-delete after 24h) |

**Global Secondary Index:**

| Index Name | Partition Key | Sort Key | Purpose |
|-----------|--------------|----------|---------|
| GSI-UserSessions | userId | timestamp | List user's recent sessions |

**TTL Configuration**: Items auto-expire after 24 hours to control storage costs.

**Example Items (one conversation turn):**

```json
[
  {
    "sessionId": "sess-abc123",
    "timestamp": "2026-07-25T14:00:00Z",
    "userId": "user-sub-789",
    "role": "user",
    "content": "What is our travel reimbursement policy?",
    "categoryFilter": "policies",
    "ttl": 1753536000
  },
  {
    "sessionId": "sess-abc123",
    "timestamp": "2026-07-25T14:00:08Z",
    "userId": "user-sub-789",
    "role": "assistant",
    "content": "Based on our Travel Policy document, employees can be reimbursed for...",
    "citations": [
      {
        "documentName": "Travel-Policy-2024.pdf",
        "pageNumber": 3,
        "relevanceScore": 0.94,
        "chunkText": "Employees are eligible for reimbursement of travel expenses..."
      }
    ],
    "ttl": 1753536000
  }
]
```

---

### 3.5 Documents Table

**Table Name**: `IntelliProcess-Documents`

| Attribute | Type | Key | Description |
|-----------|------|-----|-------------|
| documentId | String | PK (Hash) | UUID, unique document identifier |
| fileName | String | - | Original file name |
| s3Key | String | - | Full S3 object key |
| category | String | GSI-1 PK | policies, contracts, finance, procurement, general |
| uploadedAt | String | GSI-1 SK | Upload timestamp |
| uploadedBy | String | - | Uploader user ID |
| fileSize | Number | - | File size in bytes |
| contentType | String | - | MIME type |
| kbSyncStatus | String | - | PENDING, SYNCED, FAILED |
| kbSyncedAt | String | - | When KB sync completed |
| description | String | - | Optional document description |

**Global Secondary Index:**

| Index Name | Partition Key | Sort Key | Purpose |
|-----------|--------------|----------|---------|
| GSI-CategoryDate | category | uploadedAt | List documents by category |

---

## 4. S3 Bucket Design

### 4.1 Bucket Structure

**Bucket Name**: `intelliprocess-documents-{stage}-{account-id}`

```
intelliprocess-documents-dev-123456789012/
├── invoices/
│   └── {documentId}/
│       └── {originalFileName}
├── purchase-orders/
│   └── {documentId}/
│       └── {originalFileName}
├── goods-receipts/
│   └── {documentId}/
│       └── {originalFileName}
└── records/
    └── {documentId}/
        └── {originalFileName}
```

### 4.2 Bucket Configuration

```yaml
Properties:
  BucketName: !Sub "intelliprocess-documents-${Stage}-${AWS::AccountId}"
  BucketEncryption:
    ServerSideEncryptionConfiguration:
      - ServerSideEncryptionByDefault:
          SSEAlgorithm: AES256
  PublicAccessBlockConfiguration:
    BlockPublicAcls: true
    BlockPublicPolicy: true
    IgnorePublicAcls: true
    RestrictPublicBuckets: true
  LifecycleConfiguration:
    Rules:
      - Id: CleanupIncompleteUploads
        AbortIncompleteMultipartUpload:
          DaysAfterInitiation: 1
        Status: Enabled
  NotificationConfiguration:
    LambdaConfigurations:
      - Event: "s3:ObjectCreated:*"
        Filter:
          S3Key:
            Rules:
              - Name: prefix
                Value: "invoices/"
        Function: !GetAtt InvoiceProcessorFunction.Arn
```

### 4.3 S3 Event Notifications

| Prefix | Event | Target | Purpose |
|--------|-------|--------|---------|
| `invoices/` | s3:ObjectCreated:* | InvoiceProcessor Lambda | Trigger extraction |
| `records/` | s3:ObjectCreated:* | (KB sync triggered manually for MVP) | Document indexing |

---

## 5. Access Patterns Summary

### 5.1 Invoices Table Access Patterns

| # | Access Pattern | Key Condition | Index | Frequency |
|---|---------------|---------------|-------|-----------|
| 1 | Get invoice by ID | PK = documentId | Table | High |
| 2 | List invoices by status | PK = status, SK = uploadedAt (desc) | GSI-StatusDate | Medium |
| 3 | List user's invoices | PK = uploadedBy, SK = uploadedAt (desc) | GSI-UserDate | Medium |
| 4 | Update invoice status | PK = documentId | Table | High |
| 5 | Count by status (dashboard) | Scan with filter or count per status | GSI-StatusDate | Low |

### 5.2 Purchase Orders Access Patterns

| # | Access Pattern | Key Condition | Index | Frequency |
|---|---------------|---------------|-------|-----------|
| 1 | Get PO by number | PK = poNumber | Table | High (during matching) |
| 2 | Find POs by vendor | PK = vendorName | GSI-VendorDate | Low (fuzzy match fallback) |

### 5.3 Goods Receipts Access Patterns

| # | Access Pattern | Key Condition | Index | Frequency |
|---|---------------|---------------|-------|-----------|
| 1 | Get GR by ID | PK = grId | Table | Low |
| 2 | Find GRs for a PO | PK = poNumber | GSI-PONumber | High (during matching) |

### 5.4 Conversations Access Patterns

| # | Access Pattern | Key Condition | Index | Frequency |
|---|---------------|---------------|-------|-----------|
| 1 | Get conversation messages | PK = sessionId, SK between timestamps | Table | High |
| 2 | Get last 5 messages | PK = sessionId, SK desc, limit 5 | Table | High |
| 3 | List user sessions | PK = userId | GSI-UserSessions | Low |

---

## 6. Data Consistency and Integrity

### 6.1 Status Transition Enforcement

DynamoDB conditional expressions ensure valid status transitions:

```python
def update_status(doc_id: str, new_status: str, expected_current: str, **attrs):
    """Update status only if current status matches expected."""
    try:
        table.update_item(
            Key={"documentId": doc_id},
            UpdateExpression="SET #status = :new, updatedAt = :now" + 
                           "".join(f", {k} = :{k}" for k in attrs),
            ConditionExpression="#status = :current",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":new": new_status,
                ":current": expected_current,
                ":now": datetime.utcnow().isoformat(),
                **{f":{k}": v for k, v in attrs.items()}
            }
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise AppError(f"Invalid status transition from {expected_current} to {new_status}")
        raise
```

### 6.2 Idempotency

Invoice processing is designed to be idempotent:
- The S3 event may be delivered more than once
- Processing checks current status before proceeding
- If status is already beyond UPLOADED, processing is skipped

```python
def should_process(doc_id: str) -> bool:
    """Only process if status is UPLOADED (idempotency guard)."""
    item = table.get_item(Key={"documentId": doc_id})
    return item.get("Item", {}).get("status") == "UPLOADED"
```

---

## 7. Capacity Planning

### 7.1 MVP Data Volumes

| Table | Expected Items | Avg Item Size | Total Storage |
|-------|---------------|--------------|---------------|
| Invoices | 50 | 3 KB | 150 KB |
| PurchaseOrders | 10 | 1 KB | 10 KB |
| GoodsReceipts | 10 | 0.8 KB | 8 KB |
| Conversations | 500 (with TTL) | 0.5 KB | 250 KB |
| Documents | 50 | 0.5 KB | 25 KB |
| **Total** | **~620** | - | **~443 KB** |

### 7.2 Read/Write Capacity (On-Demand)

On-demand mode means no capacity planning needed. AWS auto-scales to traffic. For the MVP demo:
- Peak writes: ~5 WCU during invoice processing burst
- Peak reads: ~20 RCU during dashboard aggregation
- Well within on-demand free tier (25 RCU + 25 WCU always free)

---

## 8. SAM Template (Database Resources)

```yaml
# DynamoDB Tables in template.yaml
Resources:
  InvoicesTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub "IntelliProcess-Invoices-${Stage}"
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: documentId
          AttributeType: S
        - AttributeName: status
          AttributeType: S
        - AttributeName: uploadedBy
          AttributeType: S
        - AttributeName: uploadedAt
          AttributeType: S
      KeySchema:
        - AttributeName: documentId
          KeyType: HASH
      GlobalSecondaryIndexes:
        - IndexName: GSI-StatusDate
          KeySchema:
            - AttributeName: status
              KeyType: HASH
            - AttributeName: uploadedAt
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
        - IndexName: GSI-UserDate
          KeySchema:
            - AttributeName: uploadedBy
              KeyType: HASH
            - AttributeName: uploadedAt
              KeyType: RANGE
          Projection:
            ProjectionType: ALL

  PurchaseOrdersTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub "IntelliProcess-PurchaseOrders-${Stage}"
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: poNumber
          AttributeType: S
        - AttributeName: vendorName
          AttributeType: S
        - AttributeName: createdDate
          AttributeType: S
      KeySchema:
        - AttributeName: poNumber
          KeyType: HASH
      GlobalSecondaryIndexes:
        - IndexName: GSI-VendorDate
          KeySchema:
            - AttributeName: vendorName
              KeyType: HASH
            - AttributeName: createdDate
              KeyType: RANGE
          Projection:
            ProjectionType: ALL

  GoodsReceiptsTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub "IntelliProcess-GoodsReceipts-${Stage}"
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: grId
          AttributeType: S
        - AttributeName: poNumber
          AttributeType: S
        - AttributeName: receivedDate
          AttributeType: S
      KeySchema:
        - AttributeName: grId
          KeyType: HASH
      GlobalSecondaryIndexes:
        - IndexName: GSI-PONumber
          KeySchema:
            - AttributeName: poNumber
              KeyType: HASH
            - AttributeName: receivedDate
              KeyType: RANGE
          Projection:
            ProjectionType: ALL

  ConversationsTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub "IntelliProcess-Conversations-${Stage}"
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: sessionId
          AttributeType: S
        - AttributeName: timestamp
          AttributeType: S
        - AttributeName: userId
          AttributeType: S
      KeySchema:
        - AttributeName: sessionId
          KeyType: HASH
        - AttributeName: timestamp
          KeyType: RANGE
      GlobalSecondaryIndexes:
        - IndexName: GSI-UserSessions
          KeySchema:
            - AttributeName: userId
              KeyType: HASH
            - AttributeName: timestamp
              KeyType: RANGE
          Projection:
            ProjectionType: KEYS_ONLY
      TimeToLiveSpecification:
        AttributeName: ttl
        Enabled: true

  DocumentsTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub "IntelliProcess-Documents-${Stage}"
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: documentId
          AttributeType: S
        - AttributeName: category
          AttributeType: S
        - AttributeName: uploadedAt
          AttributeType: S
      KeySchema:
        - AttributeName: documentId
          KeyType: HASH
      GlobalSecondaryIndexes:
        - IndexName: GSI-CategoryDate
          KeySchema:
            - AttributeName: category
              KeyType: HASH
            - AttributeName: uploadedAt
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
```

---

## 9. Data Seeding Strategy

For the MVP demo, sample data is loaded via a seed script:

```python
# scripts/seed_data.py (simplified)
SAMPLE_POS = [
    {"poNumber": "PO-2024-0456", "vendorName": "Acme Office Supplies Inc.", ...},
    {"poNumber": "PO-2024-0457", "vendorName": "TechParts Global Ltd.", ...},
    {"poNumber": "PO-2024-0458", "vendorName": "Facilities Maintenance Co.", ...},
    # ... 5-10 total POs
]

SAMPLE_GRS = [
    {"grId": "GR-2024-0789", "poNumber": "PO-2024-0456", ...},
    {"grId": "GR-2024-0790", "poNumber": "PO-2024-0457", ...},
    # ... matching GRs for POs
]

APPROVED_VENDORS = [
    "Acme Office Supplies Inc.",
    "TechParts Global Ltd.",
    "Facilities Maintenance Co.",
    "CloudServ Solutions",
    "PrintWorks Inc."
]
```

This seed data ensures the demo can show successful matches, partial matches, and no-match scenarios.
