# AWS Service Mapping

## IntelliProcess AI Platform

---

## 1. Service Inventory

### 1.1 Complete AWS Service List

| # | AWS Service | Category | Purpose in Platform | Required |
|---|------------|----------|-------------------|----------|
| 1 | Amazon Bedrock | AI/ML | LLM inference (Claude 3), agent reasoning | Yes |
| 2 | Bedrock Data Automation | AI/ML | Invoice field extraction | Yes |
| 3 | Bedrock Knowledge Bases | AI/ML | Document indexing and RAG retrieval | Yes |
| 4 | Bedrock Guardrails | AI/ML | Content safety, topic control | Yes |
| 5 | Amazon Titan Embeddings v2 | AI/ML | Vector embedding generation | Yes |
| 6 | AWS AgentCore | AI/ML | Agent orchestration (or direct calls) | Optional |
| 7 | AWS Lambda | Compute | Serverless function execution | Yes |
| 8 | Amazon API Gateway | Networking | REST API management, routing, throttling | Yes |
| 9 | Amazon S3 | Storage | Document file storage | Yes |
| 10 | Amazon DynamoDB | Database | Structured metadata storage | Yes |
| 11 | Amazon OpenSearch Serverless | Database | Vector store (managed by Bedrock KB) | Yes |
| 12 | Amazon Cognito | Security | User authentication, pools, groups | Yes |
| 13 | Amazon CloudWatch | Monitoring | Logs, metrics, alarms | Yes |
| 14 | Amazon CloudFront | Networking | Frontend CDN (optional for MVP) | Optional |
| 15 | AWS IAM | Security | Service roles, policies | Yes |
| 16 | AWS SAM / CloudFormation | DevOps | Infrastructure as Code | Yes |

---

## 2. Service-to-Feature Mapping

### 2.1 Feature → Service Matrix

| Feature | Primary Service | Supporting Services |
|---------|----------------|-------------------|
| User login | Cognito | API Gateway (authorizer) |
| Invoice upload | S3, Lambda | API Gateway, DynamoDB |
| Invoice extraction | Bedrock Data Automation | S3, Lambda |
| PO/GR matching | Lambda, DynamoDB | Bedrock (optional reasoning) |
| Auto-approval rules | Lambda | DynamoDB |
| Exception escalation | Lambda, DynamoDB | - |
| Natural language search | Bedrock KB, Bedrock (Claude) | OpenSearch Serverless |
| Source citations | Bedrock KB | S3 (document access) |
| Conversation history | DynamoDB | Lambda |
| Dashboard stats | Lambda, DynamoDB | API Gateway |
| Document ingestion | S3, Bedrock KB | Lambda (trigger) |
| Content guardrails | Bedrock Guardrails | - |

### 2.2 Use Case → Service Mapping

```
┌─────────────────────────────────────────────────────────────────────┐
│                    USE CASE 1: AP Invoice Agent                       │
│                                                                      │
│  Upload        Extract         Match          Decide                 │
│  ┌─────┐      ┌─────────┐    ┌──────────┐   ┌──────────┐          │
│  │ S3  │─────►│Bedrock  │───►│ Lambda + │──►│ Lambda   │          │
│  │     │      │  BDA    │    │ DynamoDB │   │ (Rules)  │          │
│  └─────┘      └─────────┘    └──────────┘   └──────────┘          │
│     ▲                                             │                  │
│     │                                             ▼                  │
│  ┌──────────┐                              ┌──────────┐            │
│  │API GW +  │                              │ DynamoDB │            │
│  │ Lambda   │                              │ (Status) │            │
│  └──────────┘                              └──────────┘            │
│     ▲                                                               │
│  ┌──────────┐                                                       │
│  │ Cognito  │                                                       │
│  └──────────┘                                                       │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                 USE CASE 2: Ask-Your-Records                         │
│                                                                      │
│  Ingest          Index           Search         Generate             │
│  ┌─────┐       ┌──────────┐   ┌──────────┐   ┌──────────┐        │
│  │ S3  │──────►│ Bedrock  │──►│ OpenSearch│──►│ Bedrock  │        │
│  │     │       │   KB     │   │Serverless│   │ (Claude) │        │
│  └─────┘       │(chunking │   │(vectors) │   └──────────┘        │
│     ▲          │+embedding)│   └──────────┘        │               │
│     │          └──────────┘                        ▼               │
│  ┌──────────┐                              ┌──────────┐            │
│  │API GW +  │◄─────────────────────────────│ Lambda   │            │
│  │ Lambda   │                              │(ChatHdlr)│            │
│  └──────────┘                              └──────────┘            │
│     ▲                                           │                   │
│  ┌──────────┐                              ┌──────────┐            │
│  │ Cognito  │                              │ DynamoDB │            │
│  └──────────┘                              │(History) │            │
│                                            └──────────┘            │
│  ┌──────────┐                                                       │
│  │Guardrails│ (applied during generation)                           │
│  └──────────┘                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Detailed Service Configuration

### 3.1 Amazon Bedrock

| Configuration | Value |
|--------------|-------|
| Region | us-east-1 |
| Model Access | Claude 3 Sonnet, Claude 3 Haiku, Titan Embeddings v2 |
| Model ID (Primary) | anthropic.claude-3-sonnet-20240229-v1:0 |
| Model ID (Budget) | anthropic.claude-3-haiku-20240307-v1:0 |
| Model ID (Embeddings) | amazon.titan-embed-text-v2:0 |
| Inference Profiles | On-demand (no provisioned throughput) |
| Max tokens per call | 2048 (AP Agent), 1024 (Records Agent) |

**IAM Policy Required:**
```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:InvokeModel",
    "bedrock:InvokeModelWithResponseStream"
  ],
  "Resource": [
    "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet*",
    "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-haiku*",
    "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2*"
  ]
}
```

### 3.2 Bedrock Data Automation (BDA)

| Configuration | Value |
|--------------|-------|
| Blueprint | AWS-managed **public invoice blueprint** (`bedrock-data-automation-public-invoice`) — no custom blueprint/project provisioning required |
| Data automation profile | `apac.data-automation-v1` (profile ARN resolved at runtime via STS) |
| Input Format | PDF, PNG, JPEG |
| Output Format | JSON (`inference_result` + `explainability_info` per-field confidence) |
| Async Processing | Yes (`invoke_data_automation_async` + `get_data_automation_status`) |
| Used by | InvoiceProcessor (invoice extraction) and DashboardHandler (PO/GR document extraction) |

> Implementation note: The current implementation uses the AWS-managed public
> invoice blueprint with a data-automation profile ARN (current BDA API). An
> earlier design assumed a custom project + blueprint (`IntelliProcess-InvoiceExtraction`);
> that is no longer required. See `17-bda-extraction-handoff.md` for the exact
> ARNs and field mapping.

**IAM Policy Required:**
```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:InvokeDataAutomationAsync",
    "bedrock:GetDataAutomationStatus"
  ],
  "Resource": "*"
}
```

> The public-blueprint + profile path uses a wildcard resource (the profile ARN
> is resolved at runtime and is account/region-specific, e.g. `ap-southeast-2`).
> This policy is attached to both the InvoiceProcessor and DashboardHandler roles.

### 3.3 Bedrock Knowledge Bases

| Configuration | Value |
|--------------|-------|
| Knowledge Base Name | IntelliProcess-KB |
| Embedding Model | Amazon Titan Embeddings v2 |
| Vector Store | OpenSearch Serverless (auto-created) |
| Chunking Strategy | Fixed size, 300 tokens, 20% overlap |
| Data Source | S3 bucket (records/, invoices/, purchase-orders/) |
| Sync Schedule | Manual trigger for MVP |
| Retrieval Top-K | 5 |

**IAM Policy Required:**
```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:Retrieve",
    "bedrock:RetrieveAndGenerate",
    "bedrock:StartIngestionJob",
    "bedrock:GetIngestionJob"
  ],
  "Resource": "arn:aws:bedrock:us-east-1:*:knowledge-base/*"
}
```

### 3.4 Bedrock Guardrails

| Configuration | Value |
|--------------|-------|
| Guardrail Name | IntelliProcess-SafetyGuard |
| Content Filters | SEXUAL, VIOLENCE, HATE, INSULTS (all HIGH) |
| Topic Policy | Deny off-topic questions |
| Version | DRAFT (for MVP) |

### 3.5 AWS Lambda

| Function | Runtime | Memory | Timeout | Trigger |
|----------|---------|--------|---------|---------|
| UploadHandler | Python 3.12 | 256 MB | 30s | API Gateway |
| InvoiceProcessor | Python 3.12 | 512 MB | 300s | S3 Event |
| ChatHandler | Python 3.12 | 256 MB | 60s | API Gateway |
| DashboardHandler | Python 3.12 | 128 MB | 10s | API Gateway |

**Shared Lambda Layer:**
- Name: `intelliprocess-shared`
- Contents: shared/ module (dynamo_client, s3_client, response formatter)
- Size: < 5 MB

**IAM Roles (per function):**

| Function | Permissions |
|----------|------------|
| UploadHandler | S3 PutObject, DynamoDB PutItem |
| InvoiceProcessor | S3 GetObject, DynamoDB CRUD, Bedrock InvokeModel, BDA Invoke |
| ChatHandler | DynamoDB CRUD, Bedrock Retrieve/RetrieveAndGenerate, Bedrock InvokeModel |
| DashboardHandler | DynamoDB Query/Scan |

### 3.6 Amazon API Gateway

| Configuration | Value |
|--------------|-------|
| Type | REST API |
| Stage | prod |
| Authorizer | Cognito User Pool |
| Throttle (default) | 100 req/s burst, 50 req/s rate |
| CORS | Enabled for frontend origin |
| Logging | CloudWatch access logs enabled |
| Endpoint Type | Regional |

### 3.7 Amazon S3

| Configuration | Value |
|--------------|-------|
| Bucket Name | intelliprocess-ai-documents (fixed name; `DeletionPolicy: Retain`) |
| Encryption | SSE-S3 (AES-256) |
| Public Access | Blocked (all four settings) |
| Versioning | Disabled (MVP simplicity) |
| Lifecycle | Abort incomplete multipart after 1 day |
| Event Notifications | ObjectCreated:* on invoices/ → Lambda |
| CORS | Configured for frontend presigned uploads |

**S3 CORS Configuration:**
```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["PUT", "POST"],
    "AllowedOrigins": ["http://localhost:5173", "https://*.cloudfront.net"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

### 3.8 Amazon DynamoDB

| Table | Billing | Encryption | TTL |
|-------|---------|-----------|-----|
| IntelliProcess-Invoices | On-demand | AWS-managed | No |
| IntelliProcess-PurchaseOrders | On-demand | AWS-managed | No |
| IntelliProcess-GoodsReceipts | On-demand | AWS-managed | No |
| IntelliProcess-Conversations | On-demand | AWS-managed | Yes (24h) |
| IntelliProcess-Documents | On-demand | AWS-managed | No |
| IntelliProcess-AppConfig | On-demand | AWS-managed | No |

> `IntelliProcess-AppConfig` holds the singleton admin-configurable approval
> settings (amount/confidence thresholds, PO/GR match tolerances). Read by the
> InvoiceProcessor per run; read/written by the DashboardHandler via
> `/admin/settings`. Defined with `DeletionPolicy: Retain`.

### 3.9 Amazon Cognito

| Configuration | Value |
|--------------|-------|
| User Pool Name | IntelliProcess-Users |
| Sign-in | Email + Password |
| Password Policy | 8+ chars, uppercase, lowercase, number |
| MFA | Optional (disabled for MVP) |
| Groups | AP_CLERK, FINANCE_MANAGER, STAFF, ADMIN |
| App Client | intelliprocess-web (no secret, SRP flow) |
| Hosted UI | Enabled (for quick login implementation) |
| Token Expiry | Access: 1h, ID: 1h, Refresh: 30d |

**IAM Policy for API Gateway Authorizer:**
```json
{
  "Effect": "Allow",
  "Action": ["cognito-idp:GetUser"],
  "Resource": "arn:aws:cognito-idp:us-east-1:*:userpool/*"
}
```

### 3.10 Amazon CloudWatch

| Configuration | Value |
|--------------|-------|
| Log Groups | /aws/lambda/{function-name} (auto-created) |
| Log Retention | 30 days |
| Custom Metrics | IntelliProcess namespace |
| Alarms | Lambda errors > 5 in 5 min (optional) |
| Dashboard | IntelliProcess-Operations (optional) |

### 3.11 Amazon OpenSearch Serverless

| Configuration | Value |
|--------------|-------|
| Collection Name | intelliprocess-vectors |
| Type | Vector search |
| Managed By | Bedrock Knowledge Bases (auto-provisioned) |
| Capacity | Auto-scaled |
| Access | Bedrock service role only |

**Note:** This is automatically created and managed when you set up a Bedrock Knowledge Base with OpenSearch as the vector store. No manual configuration needed.

### 3.12 AWS IAM

| Role | Purpose | Trust Policy |
|------|---------|-------------|
| IntelliProcess-LambdaRole-Upload | UploadHandler execution | lambda.amazonaws.com |
| IntelliProcess-LambdaRole-Processor | InvoiceProcessor execution | lambda.amazonaws.com |
| IntelliProcess-LambdaRole-Chat | ChatHandler execution | lambda.amazonaws.com |
| IntelliProcess-LambdaRole-Dashboard | DashboardHandler execution | lambda.amazonaws.com |
| IntelliProcess-BedrockKB-Role | KB access to S3 and OpenSearch | bedrock.amazonaws.com |
| IntelliProcess-BDA-Role | BDA access to S3 | bedrock.amazonaws.com |

---

## 4. Service Dependencies and Setup Order

### 4.1 Provisioning Order (Critical Path)

```
Phase 1: Foundation (must be first)
├── 1. S3 Bucket
├── 2. DynamoDB Tables
├── 3. Cognito User Pool + Groups + App Client
└── 4. IAM Roles

Phase 2: AI Services (depends on Phase 1)
├── 5. Bedrock Model Access (enable in console)
├── 6. Bedrock Knowledge Base + Data Source (S3)
├── 7. BDA Project + Blueprint
└── 8. Bedrock Guardrails

Phase 3: Compute (depends on Phase 1 & 2)
├── 9. Lambda Layer (shared code)
├── 10. Lambda Functions (4)
├── 11. S3 Event Notification → InvoiceProcessor
└── 12. API Gateway + Routes + Authorizer

Phase 4: Frontend & Data
├── 13. Frontend build & deploy (S3 or local)
├── 14. Seed sample data (POs, GRs)
├── 15. Upload sample records → KB sync
└── 16. Create test users in Cognito
```

### 4.2 SAM Template Resource Order

```yaml
# template.yaml resource declaration order
Resources:
  # Phase 1: Foundation
  DocumentsBucket:          # S3
  InvoicesTable:            # DynamoDB
  PurchaseOrdersTable:      # DynamoDB
  GoodsReceiptsTable:       # DynamoDB
  ConversationsTable:       # DynamoDB
  DocumentsTable:           # DynamoDB
  CognitoUserPool:          # Cognito
  CognitoUserPoolClient:    # Cognito
  CognitoAPClerkGroup:      # Cognito Group
  CognitoFinanceGroup:      # Cognito Group
  CognitoStaffGroup:        # Cognito Group
  CognitoAdminGroup:        # Cognito Group
  
  # Phase 3: Compute
  SharedLayer:              # Lambda Layer
  UploadHandlerFunction:    # Lambda
  InvoiceProcessorFunction: # Lambda
  ChatHandlerFunction:      # Lambda
  DashboardHandlerFunction: # Lambda
  ApiGateway:               # API Gateway
  
  # Note: Bedrock KB, BDA, and Guardrails are created via
  # AWS Console or CLI (not fully supported in CloudFormation yet)
```

---

## 5. Service Quotas and Limits

### 5.1 Relevant Service Limits

| Service | Limit | Default | Our Usage | Sufficient? |
|---------|-------|---------|-----------|-------------|
| Lambda concurrent executions | 1000 | 1000 | < 10 | Yes |
| Lambda timeout | 900s max | - | 300s max | Yes |
| API Gateway throttle | 10,000 req/s | 10,000 | < 100 | Yes |
| S3 PUT requests | 3,500/s per prefix | 3,500 | < 10 | Yes |
| DynamoDB on-demand | 40,000 RCU, 40,000 WCU | Auto | < 100 | Yes |
| Bedrock Claude invocations | Varies by model | ~100/min | < 10/min | Yes |
| Bedrock KB retrieval | 100/min | 100 | < 20/min | Yes |
| Cognito User Pool users | 50,000 | 50,000 | < 20 | Yes |
| OpenSearch Serverless OCU | 2 min | 2 | 2 (auto) | Yes |

### 5.2 Cost-Relevant Limits

| Service | Free Tier | Our Expected Usage | Within Free Tier? |
|---------|-----------|-------------------|-------------------|
| Lambda | 1M requests/mo + 400,000 GB-s | ~1,000 requests | Yes |
| API Gateway | 1M REST calls/mo | ~5,000 calls | Yes |
| DynamoDB | 25 RCU + 25 WCU always free | On-demand, low | Mostly |
| S3 | 5 GB standard, 20K GET, 2K PUT | < 1 GB | Yes |
| Cognito | 50,000 MAU | < 20 users | Yes |
| CloudWatch | 5 GB ingestion, 5 GB storage | < 1 GB | Yes |
| Bedrock | No free tier | ~$5-20/mo | Educational credits |
| OpenSearch Serverless | No free tier | ~$5-10/mo | Educational credits |

---

## 6. Region Selection

| Factor | us-east-1 (N. Virginia) | Rationale |
|--------|------------------------|-----------|
| Bedrock Claude 3 | Available | Required |
| Bedrock Data Automation | Available | Required |
| Bedrock Knowledge Bases | Available | Required |
| AgentCore | Available | Required |
| OpenSearch Serverless | Available | Required |
| All other services | Available | Standard |
| Cost | Lowest NA pricing | Budget |
| Latency | Acceptable for demo | Not critical |

**Original decision:** Deploy everything in **us-east-1** for the broadest
Bedrock model selection.

**As deployed (updated):** The current environment is deployed in
**ap-southeast-2**. Bedrock, Bedrock Data Automation (public invoice blueprint
via the `apac.data-automation-v1` profile), DynamoDB, Lambda, S3, API Gateway,
and Cognito are all used in `ap-southeast-2`. Foundation-model/inference-profile
IDs and the BDA profile ARN are region-specific accordingly.

---

## 7. Service Integration Map

```
┌────────────────────────────────────────────────────────────────────────┐
│                        SERVICE INTEGRATION MAP                          │
│                                                                        │
│   ┌─────────┐    auth     ┌────────────┐   routes    ┌──────────┐   │
│   │ Cognito │◄────────────│ API Gateway │────────────►│  Lambda  │   │
│   └─────────┘             └────────────┘             │Functions │   │
│                                                       └────┬─────┘   │
│                                                            │          │
│                        ┌───────────────────────────────────┤          │
│                        │              │            │        │          │
│                        ▼              ▼            ▼        ▼          │
│                 ┌──────────┐  ┌──────────┐ ┌─────────┐ ┌────────┐   │
│                 │    S3    │  │ DynamoDB │ │ Bedrock │ │Bedrock │   │
│                 │          │  │          │ │   KB    │ │  BDA   │   │
│                 └─────┬────┘  └──────────┘ └────┬────┘ └────────┘   │
│                       │                         │                     │
│                       │  S3 event               │  uses               │
│                       ▼                         ▼                     │
│                 ┌──────────┐           ┌──────────────┐              │
│                 │ Lambda   │           │  OpenSearch   │              │
│                 │(Processor)│          │  Serverless   │              │
│                 └──────────┘           │  (Vectors)    │              │
│                                        └──────────────┘              │
│                                                                        │
│   ┌──────────────┐                    ┌──────────────┐               │
│   │  Bedrock     │ (applied to)       │  CloudWatch  │               │
│   │  Guardrails  │────────────────────│  (all logs)  │               │
│   └──────────────┘  KB responses      └──────────────┘               │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Service Setup Checklist

### 8.1 Manual Console/CLI Steps (Not in SAM)

These services require manual setup (CloudFormation support limited):

| # | Service | Action | Time |
|---|---------|--------|------|
| 1 | Bedrock | Enable model access (Claude 3 Sonnet, Haiku, Titan Embed) | 5 min |
| 2 | Bedrock KB | Create Knowledge Base + S3 data source | 15 min |
| 3 | Bedrock KB | Initial sync after uploading sample documents | 5 min |
| 4 | BDA | None required — uses the AWS-managed public invoice blueprint (no custom project/blueprint to create) | 0 min |
| 5 | Guardrails | Create guardrail with topic + content policies | 10 min |
| 6 | Cognito | Create test users and assign to groups | 10 min |

### 8.2 SAM-Managed Resources

Everything else is managed via `sam deploy`:
- S3 Bucket
- DynamoDB Tables (6, incl. AppConfig)
- Lambda Functions (4) + Layer
- API Gateway + Routes + Authorizer
- IAM Roles and Policies
- S3 Event Notifications
- CloudWatch Log Groups

---

## 9. Cost Summary by Service

| Service | Monthly Estimate (MVP Demo) | Notes |
|---------|---------------------------|-------|
| Lambda | $0.00 | Free tier |
| API Gateway | $0.00 | Free tier |
| S3 | $0.05 | < 1 GB |
| DynamoDB | $0.00 | Free tier (on-demand) |
| Cognito | $0.00 | Free tier |
| CloudWatch | $0.00 | Free tier |
| CloudFront | $0.00 | Free tier (if used) |
| Bedrock (Claude) | $5 - $15 | Based on invocations |
| Bedrock (Titan Embed) | $1 - $3 | One-time indexing + queries |
| OpenSearch Serverless | $7 - $15 | Minimum 2 OCU × $0.24/hr |
| BDA | $2 - $5 | Per-page extraction pricing |
| **TOTAL** | **$15 - $40/month** | **Within educational credits** |
