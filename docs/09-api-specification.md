# API Specification

## IntelliProcess AI Platform

---

## 1. API Overview

| Property | Value |
|----------|-------|
| Style | REST |
| Base URL | `https://{api-id}.execute-api.us-east-1.amazonaws.com/prod` |
| Authentication | Bearer token (Cognito JWT) |
| Content Type | application/json |
| CORS | Enabled (frontend origin) |
| Rate Limit | 100 requests/minute per user |
| Version | v1 (implicit in path, no versioning prefix for MVP) |

### Common Headers (All Requests)

```
Authorization: Bearer {id_token}
Content-Type: application/json
X-Correlation-Id: {optional, auto-generated if missing}
```

### Standard Response Envelope

**Success:**
```json
{
  "statusCode": 200,
  "data": { ... }
}
```

**Error:**
```json
{
  "statusCode": 400,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable error description"
  }
}
```

### Error Codes

| HTTP Status | Code | Description |
|-------------|------|-------------|
| 400 | VALIDATION_ERROR | Invalid request parameters |
| 400 | INVALID_FILE_TYPE | Unsupported file format |
| 400 | FILE_TOO_LARGE | File exceeds 10MB limit |
| 401 | UNAUTHORIZED | Missing or invalid token |
| 403 | FORBIDDEN | Insufficient role permissions |
| 404 | NOT_FOUND | Resource does not exist |
| 429 | RATE_LIMIT_EXCEEDED | Too many requests |
| 500 | INTERNAL_ERROR | Unexpected server error |
| 504 | TIMEOUT | AI service timeout |

---

## 2. Authentication Endpoints

Authentication is handled directly by Cognito Hosted UI / Amplify SDK. No custom auth endpoints are needed.

| Flow | Mechanism |
|------|-----------|
| Login | Cognito Hosted UI redirect or Amplify `signIn()` |
| Token Refresh | Amplify auto-refresh via refresh token |
| Logout | Amplify `signOut()` + Cognito token revocation |

---

## 3. Invoice Endpoints

### 3.1 POST /invoices/upload

Request a presigned URL for direct S3 upload.

**Authorization:** AP_CLERK, FINANCE_MANAGER, ADMIN

**Request Body:**
```json
{
  "fileName": "INV-2024-0891.pdf",
  "contentType": "application/pdf"
}
```

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| fileName | string | Yes | Max 255 chars, must end with .pdf/.png/.jpeg |
| contentType | string | Yes | Must be application/pdf, image/png, or image/jpeg |

**Note:** The document type is inferred from the route (`/invoices/upload` → type "invoices"). No explicit `documentType` parameter is needed.

**Response (201 Created):**
```json
{
  "statusCode": 201,
  "data": {
    "documentId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "uploadUrl": {
      "url": "https://intelliprocess-documents-dev.s3.amazonaws.com/",
      "fields": {
        "key": "invoices/f47ac10b-58cc-4372-a567-0e02b2c3d479/INV-2024-0891.pdf",
        "bucket": "intelliprocess-documents-dev",
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Credential": "...",
        "X-Amz-Date": "20260725T103000Z",
        "X-Amz-Security-Token": "...",
        "Policy": "...",
        "X-Amz-Signature": "..."
      }
    },
    "expiresIn": 300
  }
}
```

**Error Responses:**
| Status | Condition |
|--------|-----------|
| 400 | Invalid file type or missing required fields |
| 401 | Not authenticated |
| 403 | User role not permitted to upload invoices |

**Client Upload Flow:**
```
1. POST /invoices/upload → get presigned URL + documentId
2. POST to presigned URL with file as form-data (direct to S3)
3. S3 event triggers processing automatically
4. Client polls GET /invoices/{documentId} for status updates
```

---

### 3.2 GET /invoices

List invoices for the current user (or all invoices for FINANCE_MANAGER/ADMIN).

**Authorization:** AP_CLERK (own only), FINANCE_MANAGER, ADMIN

**Query Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| status | string | No | all | Filter by status |
| limit | integer | No | 20 | Max results (1-100) |
| startKey | string | No | - | Pagination token (base64 encoded) |

**Response (200 OK):**
```json
{
  "statusCode": 200,
  "data": {
    "invoices": [
      {
        "documentId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        "fileName": "INV-2024-0891.pdf",
        "status": "APPROVED",
        "uploadedAt": "2026-07-25T10:30:00Z",
        "uploadedBy": "user-sub-123456",
        "totalAmount": 658.80,
        "vendorName": "Acme Office Supplies Inc.",
        "approver": "SYSTEM"
      }
    ],
    "nextKey": "eyJkb2N1bWVudElkIjoiLi4uIn0=",
    "count": 20
  }
}
```

---

### 3.3 GET /invoices/{documentId}

Get full invoice details including extraction results and matching data.

**Authorization:** AP_CLERK (own only), FINANCE_MANAGER, ADMIN

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| documentId | string (UUID) | Invoice identifier |

**Response (200 OK):**
```json
{
  "statusCode": 200,
  "data": {
    "documentId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "fileName": "INV-2024-0891.pdf",
    "status": "APPROVED",
    "uploadedAt": "2026-07-25T10:30:00Z",
    "updatedAt": "2026-07-25T10:30:28Z",
    "uploadedBy": "user-sub-123456",
    "documentUrl": "https://...presigned-get-url...",
    "extraction": {
      "vendorName": {"value": "Acme Office Supplies Inc.", "confidence": 0.97},
      "invoiceNumber": {"value": "INV-2024-0891", "confidence": 0.99},
      "invoiceDate": {"value": "2026-07-20", "confidence": 0.95},
      "dueDate": {"value": "2026-08-20", "confidence": 0.93},
      "poReference": {"value": "PO-2024-0456", "confidence": 0.98},
      "lineItems": {
        "value": [
          {"description": "Premium Copy Paper (10 reams)", "quantity": 10, "unitPrice": 45.00, "amount": 450.00},
          {"description": "Ink Cartridges - Black", "quantity": 5, "unitPrice": 32.00, "amount": 160.00}
        ],
        "confidence": 0.91
      },
      "subtotal": {"value": 610.00, "confidence": 0.96},
      "taxAmount": {"value": 48.80, "confidence": 0.94},
      "totalAmount": {"value": 658.80, "confidence": 0.98},
      "paymentTerms": {"value": "Net 30", "confidence": 0.90}
    },
    "overallConfidence": 0.96,
    "matchResult": {
      "threeWayMatch": "PASS",
      "poMatch": {
        "status": "MATCHED",
        "poNumber": "PO-2024-0456",
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
      "rulesEvaluated": 4,
      "rulesPassed": 4
    },
    "processingDurationMs": 28000
  }
}
```

**Error Responses:**
| Status | Condition |
|--------|-----------|
| 404 | Invoice not found |
| 403 | AP_CLERK trying to view another user's invoice |

---

### 3.4 POST /invoices/{documentId}/approve

Manually approve or reject an escalated invoice.

**Authorization:** FINANCE_MANAGER, ADMIN

**Path Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| documentId | string (UUID) | Invoice identifier |

**Request Body:**
```json
{
  "action": "APPROVE",
  "comment": "Verified with vendor, amount is correct for rush delivery."
}
```

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| action | string | Yes | "APPROVE" or "REJECT" |
| comment | string | Yes | Min 5 chars, max 500 chars |

**Response (200 OK):**
```json
{
  "statusCode": 200,
  "data": {
    "documentId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "newStatus": "APPROVED",
    "approver": "jane.smith@company.com",
    "approvedAt": "2026-07-25T14:22:00Z"
  }
}
```

**Error Responses:**
| Status | Condition |
|--------|-----------|
| 400 | Invoice is not in ESCALATED status |
| 400 | Missing or too-short comment |
| 403 | User is not FINANCE_MANAGER or ADMIN |
| 404 | Invoice not found |

---

## 4. Document Endpoints

### 4.1 POST /documents/upload

Upload an organizational document for the knowledge base.

**Authorization:** ADMIN

**Request Body:**
```json
{
  "fileName": "Travel-Policy-2024.pdf",
  "contentType": "application/pdf",
  "category": "policies",
  "description": "Updated corporate travel and reimbursement policy for FY2024"
}
```

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| fileName | string | Yes | Max 255 chars |
| contentType | string | Yes | application/pdf, text/plain, application/vnd.openxmlformats-officedocument.wordprocessingml.document |
| category | string | Yes | policies, contracts, finance, procurement, general |
| description | string | No | Max 500 chars |

**Response (201 Created):**
```json
{
  "statusCode": 201,
  "data": {
    "documentId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "uploadUrl": {
      "url": "https://intelliprocess-documents-dev.s3.amazonaws.com/",
      "fields": { ... }
    },
    "expiresIn": 300,
    "note": "Document will be available for search after next knowledge base sync."
  }
}
```

---

### 4.2 GET /documents

List organizational documents in the knowledge base.

**Authorization:** All authenticated users

**Query Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| category | string | No | all | Filter by category |
| limit | integer | No | 50 | Max results |
| startKey | string | No | - | Pagination token |

**Response (200 OK):**
```json
{
  "statusCode": 200,
  "data": {
    "documents": [
      {
        "documentId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "fileName": "Travel-Policy-2024.pdf",
        "category": "policies",
        "uploadedAt": "2026-07-20T09:00:00Z",
        "description": "Updated corporate travel and reimbursement policy for FY2024",
        "kbSyncStatus": "SYNCED"
      }
    ],
    "count": 12
  }
}
```

---

### 4.3 POST /documents/sync

Trigger knowledge base synchronization (ingests new documents).

**Authorization:** ADMIN

**Request Body:** None (empty body)

**Response (202 Accepted):**
```json
{
  "statusCode": 202,
  "data": {
    "message": "Knowledge base sync initiated. New documents will be searchable within 5 minutes.",
    "syncJobId": "sync-job-12345"
  }
}
```

---

## 5. Chat Endpoints

### 5.1 POST /chat

Submit a natural language question to the Records Assistant.

**Authorization:** All authenticated users

**Request Body:**
```json
{
  "question": "What is the maximum travel reimbursement for international trips?",
  "sessionId": "sess-abc123",
  "categoryFilter": "policies"
}
```

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| question | string | Yes | 1-1000 chars |
| sessionId | string | No | If omitted, new session created. Max 64 chars. |
| categoryFilter | string | No | policies, contracts, finance, procurement, all (default: all) |

**Response (200 OK):**
```json
{
  "statusCode": 200,
  "data": {
    "answer": "According to the Travel Policy (2024), the maximum reimbursement for international business travel is $5,000 per trip. This includes airfare, accommodation (up to $250/night), meals (up to $75/day per diem), and ground transportation. Pre-approval is required for any trip exceeding $3,000 in estimated costs.",
    "citations": [
      {
        "documentName": "Travel-Policy-2024.pdf",
        "documentId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "pageNumber": 7,
        "relevanceScore": 0.94,
        "snippet": "International travel reimbursement shall not exceed $5,000 per trip inclusive of all expenses...",
        "category": "policies"
      },
      {
        "documentName": "Travel-Policy-2024.pdf",
        "documentId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "pageNumber": 8,
        "relevanceScore": 0.87,
        "snippet": "Pre-approval by department head is mandatory for estimated trip costs exceeding $3,000...",
        "category": "policies"
      }
    ],
    "sessionId": "sess-abc123",
    "responseTimeMs": 4200
  }
}
```

**Error Responses:**
| Status | Condition |
|--------|-----------|
| 400 | Empty question or exceeds 1000 chars |
| 400 | Invalid category filter value |
| 504 | Bedrock timeout (> 60s) |

**Special Response (No Information Found):**
```json
{
  "statusCode": 200,
  "data": {
    "answer": "I don't have enough information in the available records to answer this question. You may want to check with the relevant department directly.",
    "citations": [],
    "sessionId": "sess-abc123",
    "responseTimeMs": 2100
  }
}
```

---

### 5.2 GET /chat/sessions

List the current user's recent chat sessions.

**Authorization:** All authenticated users

**Query Parameters:**
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| limit | integer | No | 10 | Max sessions to return |

**Response (200 OK):**
```json
{
  "statusCode": 200,
  "data": {
    "sessions": [
      {
        "sessionId": "sess-abc123",
        "firstMessage": "What is the maximum travel reimbursement...",
        "lastActivity": "2026-07-25T14:00:08Z",
        "messageCount": 4
      }
    ]
  }
}
```

---

### 5.3 GET /chat/sessions/{sessionId}

Retrieve conversation history for a specific session.

**Authorization:** Owner of the session only

**Response (200 OK):**
```json
{
  "statusCode": 200,
  "data": {
    "sessionId": "sess-abc123",
    "messages": [
      {
        "role": "user",
        "content": "What is the maximum travel reimbursement for international trips?",
        "timestamp": "2026-07-25T14:00:00Z"
      },
      {
        "role": "assistant",
        "content": "According to the Travel Policy (2024)...",
        "citations": [...],
        "timestamp": "2026-07-25T14:00:08Z"
      }
    ]
  }
}
```

---

## 6. Dashboard Endpoints

### 6.1 GET /dashboard/stats

Get invoice processing summary statistics.

**Authorization:** FINANCE_MANAGER, ADMIN

**Response (200 OK):**
```json
{
  "statusCode": 200,
  "data": {
    "totalInvoices": 47,
    "statusCounts": {
      "uploaded": 2,
      "processing": 1,
      "extracted": 0,
      "matched": 0,
      "approved": 35,
      "escalated": 5,
      "rejected": 2,
      "error": 2
    },
    "autoApprovalRate": 74.5,
    "avgProcessingTimeSec": 26,
    "recentActivity": [
      {
        "documentId": "f47ac10b...",
        "fileName": "INV-2024-0891.pdf",
        "action": "Auto-approved",
        "timestamp": "2026-07-25T10:30:28Z",
        "actor": "SYSTEM"
      },
      {
        "documentId": "b23de45f...",
        "fileName": "INV-2024-0892.pdf",
        "action": "Escalated - Amount exceeds threshold",
        "timestamp": "2026-07-25T10:28:15Z",
        "actor": "SYSTEM"
      }
    ]
  }
}
```

---

## 7. Admin Endpoints

### 7.1 POST /admin/seed-data

Load sample PO and GR data for demonstration (dev/demo only).

**Authorization:** ADMIN

**Request Body:**
```json
{
  "dataSet": "default"
}
```

**Response (200 OK):**
```json
{
  "statusCode": 200,
  "data": {
    "message": "Sample data loaded successfully",
    "purchaseOrdersCreated": 5,
    "goodsReceiptsCreated": 5
  }
}
```

---

## 8. API Gateway Configuration (SAM)

```yaml
# API Gateway resource in template.yaml
ApiGateway:
  Type: AWS::Serverless::Api
  Properties:
    Name: !Sub "IntelliProcess-API-${Stage}"
    StageName: !Ref Stage
    Auth:
      DefaultAuthorizer: CognitoAuthorizer
      Authorizers:
        CognitoAuthorizer:
          UserPoolArn: !GetAtt CognitoUserPool.Arn
    Cors:
      AllowMethods: "'GET,POST,PUT,DELETE,OPTIONS'"
      AllowHeaders: "'Content-Type,Authorization,X-Correlation-Id'"
      AllowOrigin: "'*'"  # Restrict to frontend domain in production
    ThrottleConfig:
      BurstLimit: 50
      RateLimit: 100

# Example function with API event
UploadHandlerFunction:
  Type: AWS::Serverless::Function
  Properties:
    Handler: app.lambda_handler
    CodeUri: functions/upload_handler/
    Runtime: python3.12
    Timeout: 30
    MemorySize: 256
    Layers:
      - !Ref SharedLayer
    Environment:
      Variables:
        DOCUMENT_BUCKET: !Ref DocumentsBucket
        INVOICE_TABLE: !Ref InvoicesTable
    Policies:
      - S3CrudPolicy:
          BucketName: !Ref DocumentsBucket
      - DynamoDBCrudPolicy:
          TableName: !Ref InvoicesTable
    Events:
      UploadInvoice:
        Type: Api
        Properties:
          RestApiId: !Ref ApiGateway
          Path: /invoices/upload
          Method: POST
      UploadDocument:
        Type: Api
        Properties:
          RestApiId: !Ref ApiGateway
          Path: /documents/upload
          Method: POST
```

---

## 9. API Endpoint Summary

| Method | Path | Handler | Auth Roles | Purpose |
|--------|------|---------|-----------|---------|
| POST | /invoices/upload | UploadHandler | AP_CLERK, FINANCE_MANAGER, ADMIN | Get presigned upload URL |
| GET | /invoices | DashboardHandler | AP_CLERK*, FINANCE_MANAGER, ADMIN | List invoices |
| GET | /invoices/{id} | DashboardHandler | AP_CLERK*, FINANCE_MANAGER, ADMIN | Get invoice detail |
| POST | /invoices/{id}/approve | DashboardHandler | FINANCE_MANAGER, ADMIN | Manual approve/reject |
| POST | /documents/upload | UploadHandler | ADMIN | Upload KB document |
| GET | /documents | DashboardHandler | All authenticated | List KB documents |
| POST | /documents/sync | DashboardHandler | ADMIN | Trigger KB sync |
| POST | /chat | ChatHandler | All authenticated | Ask RAG question |
| GET | /chat/sessions | ChatHandler | All authenticated | List chat sessions |
| GET | /chat/sessions/{id} | ChatHandler | Owner only | Get session history |
| GET | /dashboard/stats | DashboardHandler | FINANCE_MANAGER, ADMIN | Processing stats |
| POST | /admin/seed-data | DashboardHandler | ADMIN | Load sample data |

*AP_CLERK can only see their own invoices.

---

## 10. Pagination Pattern

All list endpoints use cursor-based pagination with DynamoDB's `LastEvaluatedKey`:

```
Request:  GET /invoices?limit=20&startKey=eyJkb2N1bWVudElkIjoiYWJjIn0=
Response: { "data": { "invoices": [...], "nextKey": "eyJ..." | null, "count": 20 } }
```

- `startKey`: Base64-encoded JSON of DynamoDB's LastEvaluatedKey
- `nextKey`: Provided in response if more results exist; `null` if last page
- Client passes `nextKey` as `startKey` in next request

---

## 11. CORS Configuration

```
Access-Control-Allow-Origin: * (dev) | https://intelliprocess.example.com (prod)
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization, X-Correlation-Id
Access-Control-Max-Age: 86400
```

All Lambda responses include CORS headers via the shared response formatter.
