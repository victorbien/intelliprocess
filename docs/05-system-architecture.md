# System Architecture

## IntelliProcess AI Platform

---

## 1. Architecture Overview

IntelliProcess AI follows a **serverless event-driven architecture** built entirely on AWS managed services. This decision is driven by:

1. **Cost efficiency** - Pay-per-use model ideal for a demo/capstone with sporadic traffic
2. **Reduced operational overhead** - No servers to manage, patch, or scale
3. **Rapid development** - Focus on business logic, not infrastructure plumbing
4. **Built-in scalability** - Handles demo load and could scale to production without re-architecture

### Architecture Style: Serverless Microservices + Event-Driven

The system is decomposed into loosely coupled services that communicate via API Gateway (synchronous) and S3/EventBridge events (asynchronous).

---

## 2. High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT TIER                                          │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                    React SPA (S3 + CloudFront)                            │   │
│  │   ┌─────────────┐  ┌──────────────────┐  ┌────────────────────────┐     │   │
│  │   │  Auth UI    │  │  Invoice Mgmt UI │  │  Records Chat UI       │     │   │
│  │   │  (Cognito)  │  │  (Upload/Status) │  │  (Search/Converse)     │     │   │
│  │   └─────────────┘  └──────────────────┘  └────────────────────────┘     │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ HTTPS
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              API TIER                                             │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                     Amazon API Gateway (REST)                             │   │
│  │          ┌──────────────────────────────────────┐                        │   │
│  │          │   Cognito Authorizer (JWT Validation) │                        │   │
│  │          └──────────────────────────────────────┘                        │   │
│  │   Routes:                                                                 │   │
│  │   POST /invoices/upload          GET /invoices                           │   │
│  │   GET  /invoices/{id}            POST /invoices/{id}/approve             │   │
│  │   POST /documents/upload         POST /chat                              │   │
│  │   GET  /dashboard/stats          GET /documents                          │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ Lambda Proxy Integration
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           APPLICATION TIER                                        │
│                                                                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐ │
│  │  Upload        │  │  Invoice       │  │  Chat          │  │  Dashboard   │ │
│  │  Handler       │  │  Processor     │  │  Handler       │  │  Handler     │ │
│  │  (Lambda)      │  │  (Lambda)      │  │  (Lambda)      │  │  (Lambda)    │ │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘  └──────┬───────┘ │
│          │                    │                    │                   │          │
│          ▼                    ▼                    ▼                   ▼          │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                      AWS AgentCore                                       │    │
│  │   ┌──────────────────────┐    ┌──────────────────────────────┐          │    │
│  │   │  AP Invoice Agent    │    │  Records Search Agent         │          │    │
│  │   │  (Orchestrator)      │    │  (RAG Orchestrator)           │          │    │
│  │   └──────────┬───────────┘    └──────────────┬───────────────┘          │    │
│  │              │                                │                           │    │
│  │              ▼                                ▼                           │    │
│  │   ┌──────────────────┐           ┌──────────────────────────┐           │    │
│  │   │ Tools:           │           │ Tools:                    │           │    │
│  │   │ - Extract        │           │ - RetrieveAndGenerate     │           │    │
│  │   │ - MatchPO        │           │ - FilterByCategory        │           │    │
│  │   │ - MatchGR        │           │ - CitationFormatter       │           │    │
│  │   │ - ApprovalRules  │           └──────────────────────────┘           │    │
│  │   │ - Escalate       │                                                   │    │
│  │   └──────────────────┘                                                   │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                             AI SERVICES TIER                                      │
│                                                                                  │
│  ┌────────────────────┐  ┌────────────────────┐  ┌──────────────────────────┐  │
│  │  Amazon Bedrock    │  │  Bedrock Data      │  │  Bedrock Knowledge       │  │
│  │  (LLM Inference)   │  │  Automation (BDA)  │  │  Bases (RAG)             │  │
│  │                    │  │                    │  │                          │  │
│  │  Claude 3 Sonnet   │  │  Invoice field     │  │  Document chunking       │  │
│  │  Claude 3 Haiku    │  │  extraction        │  │  Embedding generation    │  │
│  │                    │  │  (structured +     │  │  Vector search           │  │
│  │  Agent reasoning   │  │   unstructured)    │  │  Source retrieval        │  │
│  └────────────────────┘  └────────────────────┘  └──────────────────────────┘  │
│                                                                                  │
│  ┌────────────────────┐  ┌────────────────────┐                                │
│  │  Bedrock           │  │  Bedrock           │                                │
│  │  Guardrails        │  │  Embeddings        │                                │
│  │                    │  │  (Titan v2)        │                                │
│  │  Content filtering │  │                    │                                │
│  │  Topic blocking    │  │  Vector generation │                                │
│  └────────────────────┘  └────────────────────┘                                │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                             DATA TIER                                             │
│                                                                                  │
│  ┌────────────────────┐  ┌────────────────────┐  ┌──────────────────────────┐  │
│  │  Amazon S3         │  │  Amazon DynamoDB   │  │  OpenSearch Serverless   │  │
│  │                    │  │                    │  │  (via Knowledge Bases)   │  │
│  │  /invoices/        │  │  InvoiceTable      │  │                          │  │
│  │  /purchase-orders/ │  │  DocumentTable     │  │  Vector embeddings       │  │
│  │  /goods-receipts/  │  │  ConversationTable │  │  (managed by Bedrock KB) │  │
│  │  /records/         │  │  POTable           │  │                          │  │
│  │                    │  │  GRTable           │  │                          │  │
│  └────────────────────┘  └────────────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Architecture Layers

### 3.1 Client Tier

| Component | Technology | Responsibility |
|-----------|-----------|----------------|
| Web Application | React 18 + Vite | Single-page application |
| UI Framework | Tailwind CSS or AWS Amplify UI | Consistent styling |
| Auth Library | AWS Amplify Auth | Cognito integration |
| HTTP Client | Axios or fetch | API communication |
| Hosting | S3 + CloudFront (or local dev) | Static file serving |

**Architecture Decision**: React SPA over server-side rendering because:
- Simpler deployment (static files to S3)
- Team familiarity with React
- No need for SEO (internal enterprise app)
- Reduces backend complexity

### 3.2 API Tier

| Component | Technology | Responsibility |
|-----------|-----------|----------------|
| API Gateway | Amazon API Gateway (REST) | Request routing, throttling, CORS |
| Authorization | Cognito User Pool Authorizer | JWT token validation |
| Rate Limiting | API Gateway throttling | 100 req/min per user |

**Architecture Decision**: REST API over WebSocket because:
- Simpler implementation for MVP
- All operations are request-response (no real-time streaming needed)
- Invoice processing is asynchronous (poll for status)
- Chat responses are short enough for synchronous response

### 3.3 Application Tier

| Component | Technology | Responsibility |
|-----------|-----------|----------------|
| Lambda Functions | Python 3.12 | Business logic execution |
| Agent Orchestration | AWS AgentCore | AI agent reasoning and tool use |
| Event Processing | S3 Event Notifications | Trigger processing on upload |

**Architecture Decision**: Python over Node.js because:
- Better AWS SDK (boto3) ergonomics for AI/ML services
- Native support in Bedrock SDK examples
- Simpler data manipulation for matching logic
- Team familiarity

### 3.4 AI Services Tier

| Component | Technology | Responsibility |
|-----------|-----------|----------------|
| LLM Inference | Amazon Bedrock (Claude 3) | Agent reasoning, text generation |
| Document Extraction | Bedrock Data Automation | Structured field extraction from invoices |
| Knowledge Base | Bedrock Knowledge Bases | Document indexing, retrieval, RAG |
| Embeddings | Amazon Titan Embeddings v2 | Vector generation for semantic search |
| Safety | Bedrock Guardrails | Content filtering, topic control |

**Architecture Decision**: Bedrock over self-hosted models because:
- No infrastructure management
- Pay-per-token pricing suitable for demo
- Integrated with other AWS services
- AgentCore native integration

### 3.5 Data Tier

| Component | Technology | Responsibility |
|-----------|-----------|----------------|
| Object Storage | Amazon S3 | Document files (invoices, records) |
| Metadata Store | Amazon DynamoDB | Invoice status, PO/GR data, conversations |
| Vector Store | OpenSearch Serverless | Semantic search (managed by Bedrock KB) |

**Architecture Decision**: DynamoDB over RDS because:
- Serverless (no instance management)
- Pay-per-request pricing for low-volume MVP
- Schema flexibility during rapid development
- Sub-millisecond reads for status lookups
- Simpler than managing PostgreSQL connections in Lambda

---

## 4. Key Data Flows

### 4.1 Invoice Processing Flow (Asynchronous)

```
User uploads     S3 Event        Lambda              BDA              Lambda
invoice    ──►  Notification  ──►  triggers    ──►  extracts   ──►  matching
(PDF/IMG)       (s3:ObjectCreated)  processing      fields           + approval
                                                                         │
                                                                         ▼
                                                                   DynamoDB
                                                                   (status update)
```

**Detailed Steps:**
1. User uploads invoice via presigned S3 URL
2. S3 event notification triggers `InvoiceProcessor` Lambda
3. Lambda calls Bedrock Data Automation for field extraction
4. Extracted data stored in DynamoDB (status → EXTRACTED)
5. Lambda invokes AgentCore AP Agent for matching logic
6. Agent uses tools to query PO/GR tables and evaluate rules
7. Agent returns decision: APPROVED or ESCALATED with reasons
8. DynamoDB updated with final status

### 4.2 Records Search Flow (Synchronous)

```
User asks       API Gateway      Lambda         AgentCore        Bedrock KB
question  ──►  /chat       ──►  handler   ──►  RAG Agent  ──►  Retrieve &
                                                    │            Generate
                                                    ▼                │
                                              LLM synthesizes       │
                                              answer with      ◄────┘
                                              citations
                                                    │
                                                    ▼
                                              Response to user
```

**Detailed Steps:**
1. User submits question via chat interface
2. API Gateway routes to `ChatHandler` Lambda
3. Lambda invokes AgentCore Records Agent
4. Agent calls Bedrock Knowledge Base RetrieveAndGenerate
5. KB performs semantic search, retrieves relevant chunks
6. LLM synthesizes answer with source citations
7. Response returned synchronously to user (< 10s)

### 4.3 Document Ingestion Flow (Asynchronous)

```
Admin uploads       S3 stores         Bedrock KB          OpenSearch
document      ──►  in /records/  ──►  sync job      ──►  Serverless
                    prefix            (scheduled or       (vectors stored)
                                       on-demand)
```

**Detailed Steps:**
1. Admin uploads document to S3 `/records/` prefix
2. Bedrock Knowledge Base data source points to this S3 prefix
3. KB sync job (manual trigger or scheduled) processes new documents
4. Documents are chunked, embedded (Titan v2), and indexed
5. Content becomes searchable via RAG queries

---

## 5. Integration Architecture

### 5.1 Cross-Use-Case Integration

The two use cases share infrastructure and data through:

```
                    ┌─────────────────────────────┐
                    │       Shared S3 Bucket       │
                    │                             │
                    │  /invoices/    /records/    │
                    │  /purchase-orders/          │
                    │  /goods-receipts/           │
                    └──────────┬──────────────────┘
                               │
                 ┌─────────────┼─────────────────┐
                 │             │                  │
                 ▼             ▼                  ▼
          ┌──────────┐  ┌──────────┐  ┌────────────────┐
          │ AP Agent │  │ Bedrock  │  │ Records Agent  │
          │ (BDA +   │  │   KB     │  │ (RAG Search)   │
          │ Matching) │  │ (indexes │  │                │
          └──────────┘  │  all S3  │  └────────────────┘
                        │ prefixes)│
                        └──────────┘
```

**Key Integration Point**: The Bedrock Knowledge Base indexes ALL S3 prefixes, meaning:
- Processed invoices are searchable via the Records Assistant
- POs and GRs are queryable through natural language
- Organizational documents (policies, contracts) are all in the same search index

This creates the unified experience where an AP Clerk can ask "Show me all invoices from Vendor X" through the chat interface.

### 5.2 Authentication Flow

```
┌────────┐     ┌──────────┐     ┌─────────────┐     ┌───────────┐
│ React  │────►│ Cognito  │────►│ API Gateway │────►│  Lambda   │
│  App   │◄────│ Hosted UI│     │ Authorizer  │     │ Functions │
└────────┘     └──────────┘     └─────────────┘     └───────────┘
    │               │                   │
    │  1. Login     │  2. JWT Token     │  3. Validate Token
    │  redirect     │  returned         │  on each request
    │               │                   │
    └───────────────┴───────────────────┘
```

---

## 6. Security Architecture

### 6.1 Network Security

| Layer | Control |
|-------|---------|
| Client → API | HTTPS/TLS 1.2+ (enforced by API Gateway) |
| API → Lambda | AWS internal (VPC not required for managed services) |
| Lambda → AWS Services | IAM role-based access (least privilege) |
| S3 | Block public access, bucket policy restricts to application |

### 6.2 Identity & Access

| Component | Mechanism |
|-----------|-----------|
| User Authentication | Cognito User Pool (username/password) |
| API Authorization | Cognito JWT Authorizer on API Gateway |
| Service Authorization | IAM roles per Lambda function |
| S3 Access | Presigned URLs (time-limited, scoped) |

### 6.3 Data Protection

| Data State | Protection |
|-----------|-----------|
| At Rest (S3) | SSE-S3 (AES-256) |
| At Rest (DynamoDB) | AWS-managed encryption |
| In Transit | TLS 1.2+ everywhere |
| Secrets | No hardcoded secrets; IAM roles for service access |

---

## 7. Architectural Decisions Record (ADR)

### ADR-001: Serverless over Container-Based
- **Decision**: Use Lambda + API Gateway over ECS/EKS
- **Rationale**: Zero infrastructure management, pay-per-use, faster development
- **Trade-off**: 15s cold start possible (mitigated by provisioned concurrency if needed)

### ADR-002: Single S3 Bucket with Prefixes over Multiple Buckets
- **Decision**: One bucket with path-based organization
- **Rationale**: Simpler IAM policies, single Bedrock KB data source, easier management
- **Trade-off**: Less isolation between document types (acceptable for single-tenant MVP)

### ADR-003: DynamoDB over Aurora Serverless
- **Decision**: Use DynamoDB for all structured data
- **Rationale**: True serverless (no cold start issues), simpler for key-value/document patterns, pay-per-request
- **Trade-off**: No relational joins (handled in application logic for matching)

### ADR-004: Synchronous Chat over Streaming
- **Decision**: Return complete chat responses (no token streaming)
- **Rationale**: Simpler API (no WebSocket), adequate for MVP demo, reduces frontend complexity
- **Trade-off**: User waits 5-10s for full response (acceptable with loading indicator)

### ADR-005: AgentCore over Custom Agent Loop
- **Decision**: Use AWS AgentCore for agent orchestration
- **Rationale**: Managed service handles tool orchestration, retry logic, memory; reduces custom code
- **Trade-off**: Less control over agent behavior (acceptable for standard use cases)

### ADR-006: Bedrock KB Managed Vector Store over Self-Managed
- **Decision**: Let Bedrock Knowledge Bases manage the OpenSearch Serverless collection
- **Rationale**: Automatic chunking, embedding, indexing; no vector DB expertise needed
- **Trade-off**: Less control over chunking strategy (default 300-token chunks are sufficient for MVP)

---

## 8. Scalability Considerations (Post-MVP)

While not required for the capstone demo, the architecture supports future scaling:

| Concern | Current (MVP) | Future Scale |
|---------|---------------|-------------|
| Concurrent users | 10 | 1000+ (Lambda auto-scales) |
| Invoice volume | ~50/demo | 15,000/month (async queue) |
| Document corpus | 50 docs | 10,000+ (KB handles) |
| Multi-tenancy | Single tenant | Add tenant partition key |
| Availability | Single region | Multi-region with Route53 |

---

## 9. Cost Estimation (Monthly - Demo Usage)

| Service | Estimated Cost | Notes |
|---------|---------------|-------|
| Lambda | $0 - $1 | Free tier covers demo usage |
| API Gateway | $0 - $1 | Free tier: 1M calls/month |
| S3 | $0.05 | < 1GB storage |
| DynamoDB | $0 - $1 | On-demand, minimal reads/writes |
| Cognito | $0 | Free tier: 50,000 MAU |
| Bedrock (Claude) | $5 - $20 | ~1000 invocations at demo scale |
| Bedrock (Titan Embed) | $1 - $5 | Embedding 50 documents |
| Bedrock KB | $5 - $10 | OpenSearch Serverless minimum |
| BDA | $2 - $10 | ~50 invoice extractions |
| CloudFront | $0 | Free tier covers demo |
| **Total Estimate** | **$15 - $50/month** | Within educational credits |
