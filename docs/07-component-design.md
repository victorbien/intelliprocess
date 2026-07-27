# Component Design

## IntelliProcess AI Platform

---

## 1. Component Overview

The system is decomposed into six logical components, each with clear boundaries, responsibilities, and interfaces.

```
┌─────────────────────────────────────────────────────────────────┐
│                    COMPONENT MAP                                  │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐ │
│  │  C1: Auth    │  │  C2: Document│  │  C3: Invoice          │ │
│  │  Component   │  │  Management  │  │  Processing Engine    │ │
│  └──────────────┘  └──────────────┘  └───────────────────────┘ │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐ │
│  │  C4: Records │  │  C5: Dashboard│ │  C6: Shared           │ │
│  │  Assistant   │  │  & Reporting │  │  Infrastructure       │ │
│  └──────────────┘  └──────────────┘  └───────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. C1: Authentication Component

### 2.1 Responsibility
Manages user identity, authentication, session management, and role-based access control.

### 2.2 Sub-Components

```
C1: Authentication
├── C1.1: Cognito User Pool (AWS Managed)
│   ├── User registration and storage
│   ├── Password policies
│   └── Group management (roles)
├── C1.2: API Gateway Authorizer
│   ├── JWT validation
│   ├── Token claims extraction
│   └── Role-based route access
└── C1.3: Frontend Auth Module
    ├── Login/logout UI
    ├── Token management
    ├── Protected route wrapper
    └── Role context provider
```

### 2.3 Interfaces

| Interface | Direction | Protocol | Description |
|-----------|-----------|----------|-------------|
| Login | Frontend → Cognito | HTTPS (Amplify SDK) | Username/password auth |
| Token Validation | API GW → Cognito | Internal | JWT verification per request |
| User Role | Lambda ← API GW | Event context | Claims passed in event.requestContext |

### 2.4 Data Model

```
Cognito User Pool:
├── User Attributes: email, name, custom:department
├── Groups: AP_CLERK, FINANCE_MANAGER, STAFF, ADMIN
└── App Client: intelliprocess-web (no secret, SRP auth)
```

### 2.5 Component Diagram

```
┌─────────────────┐       ┌──────────────────────┐
│   React App     │       │   Amazon Cognito      │
│                 │       │                      │
│  ┌───────────┐  │  1.Auth│  ┌────────────────┐ │
│  │ AuthContext│──┼───────┼─►│  User Pool     │ │
│  │           │◄─┼───────┼──│  (hosted UI)   │ │
│  └───────────┘  │ 2.JWT │  └────────────────┘ │
│       │         │       │         │            │
│       ▼         │       └─────────┼────────────┘
│  ┌───────────┐  │                 │
│  │ Protected │  │                 │ 3.Validate
│  │ Route     │  │                 ▼
│  └───────────┘  │       ┌──────────────────────┐
└─────────────────┘       │  API Gateway         │
                          │  Cognito Authorizer  │
                          └──────────────────────┘
```

---

## 3. C2: Document Management Component

### 3.1 Responsibility
Handles document upload, storage, metadata tracking, and lifecycle management for all document types.

### 3.2 Sub-Components

```
C2: Document Management
├── C2.1: Upload Service
│   ├── Presigned URL generation
│   ├── File validation (type, size)
│   └── Metadata creation
├── C2.2: Storage Layer
│   ├── S3 bucket management
│   ├── Prefix-based organization
│   └── Encryption (SSE-S3)
├── C2.3: Metadata Service
│   ├── Document table CRUD
│   ├── Status transitions
│   └── Query by user/status
└── C2.4: Frontend Upload UI
    ├── Drag-and-drop zone
    ├── Progress indicator
    ├── File validation (client-side)
    └── Status list view
```

### 3.3 Interfaces

| Interface | Direction | Protocol | Description |
|-----------|-----------|----------|-------------|
| RequestUploadURL | Frontend → Lambda | REST POST | Get presigned URL |
| UploadFile | Frontend → S3 | HTTPS POST | Direct upload to S3 |
| S3Notification | S3 → Lambda | Event | Trigger on ObjectCreated |
| GetDocuments | Frontend → Lambda | REST GET | List user's documents |
| UpdateStatus | Internal Lambda | DynamoDB Put | Status state machine |

### 3.4 Status State Machine

```
                    ┌──────────┐
                    │ UPLOADED  │
                    └─────┬────┘
                          │ (S3 event triggers processor)
                          ▼
                    ┌──────────┐
                    │PROCESSING│
                    └─────┬────┘
                          │
                 ┌────────┼────────┐
                 │                 │
                 ▼                 ▼
          ┌──────────┐      ┌───────┐
          │EXTRACTED │      │ ERROR │
          └─────┬────┘      └───────┘
                │
                │ (matching + rules evaluated)
                │
       ┌────────┼────────┐
       │                 │
       ▼                 ▼
┌──────────┐      ┌──────────┐
│ APPROVED │      │ESCALATED │
│ (auto)   │      └─────┬────┘
└──────────┘             │
                ┌────────┼────────┐
                │                 │
                ▼                 ▼
         ┌──────────┐      ┌──────────┐
         │ APPROVED │      │ REJECTED │
         │ (manual) │      │          │
         └──────────┘      └──────────┘
```

**Note:** The MATCHED status was removed in the consistency review. Match results are stored as data within the invoice record, but do not appear as a separate user-visible status. The pipeline goes directly from EXTRACTED → APPROVED or EXTRACTED → ESCALATED.

### 3.5 Valid Status Transitions

| From | To | Trigger |
|------|----|---------|
| UPLOADED | PROCESSING | S3 event received |
| PROCESSING | EXTRACTED | BDA extraction complete |
| PROCESSING | ERROR | BDA failure |
| EXTRACTED | APPROVED | Three-way match pass + all rules pass |
| EXTRACTED | ESCALATED | Match failure, rule failure, or low confidence |
| ESCALATED | APPROVED | Manual approval |
| ESCALATED | REJECTED | Manual rejection |

---

## 4. C3: Invoice Processing Engine

### 4.1 Responsibility
Orchestrates the end-to-end automated invoice processing pipeline: extraction, matching, rule evaluation, and disposition.

### 4.2 Sub-Components

```
C3: Invoice Processing Engine
├── C3.1: Extraction Module
│   ├── BDA invocation
│   ├── Response parsing
│   ├── Confidence scoring
│   └── Field normalization
├── C3.2: Matching Module
│   ├── PO lookup and comparison
│   ├── GR lookup and verification
│   ├── Three-way match orchestration
│   └── Tolerance calculations
├── C3.3: Rules Engine
│   ├── Approval threshold rules
│   ├── Confidence threshold rules
│   ├── Vendor whitelist check
│   └── Escalation routing logic
└── C3.4: AgentCore AP Agent
    ├── Agent instructions
    ├── Tool definitions
    └── Orchestration logic
```

### 4.3 Extraction Module Detail

```python
# C3.1 Interface Contract
class ExtractionResult:
    vendor_name: str          # confidence: float
    vendor_address: str       # confidence: float
    invoice_number: str       # confidence: float
    invoice_date: date        # confidence: float
    due_date: date            # confidence: float
    po_reference: str | None  # confidence: float
    line_items: list[LineItem] # confidence: float (per item)
    subtotal: Decimal         # confidence: float
    tax_amount: Decimal       # confidence: float
    total_amount: Decimal     # confidence: float
    payment_terms: str | None # confidence: float
    raw_response: dict        # Full BDA response for debugging
    overall_confidence: float # Average of all field confidences
```

### 4.4 Matching Module Detail

```python
# C3.2 Interface Contract
class MatchRequest:
    extraction: ExtractionResult
    document_id: str

class POMatchResult:
    status: Literal["MATCHED", "PARTIAL_MATCH", "NO_MATCH"]
    po_id: str | None
    po_data: dict | None
    discrepancies: list[str]    # e.g., ["Amount differs by $45.00"]
    amount_variance_pct: float  # e.g., 0.03 = 3%

class GRMatchResult:
    status: Literal["CONFIRMED", "PARTIAL", "NOT_RECEIVED"]
    gr_id: str | None
    quantity_received: int | None
    quantity_invoiced: int | None
    discrepancies: list[str]

class ThreeWayMatchResult:
    status: Literal["PASS", "FAIL"]
    po_result: POMatchResult
    gr_result: GRMatchResult
    all_discrepancies: list[str]
```

### 4.5 Rules Engine Detail

```python
# C3.3 Approval Rules (evaluated in order)
APPROVAL_RULES = [
    {
        "id": "RULE-001",
        "name": "Three-Way Match Required",
        "condition": "three_way_match.status == 'PASS'",
        "on_fail": {"action": "ESCALATE", "to": "AP_CLERK",
                    "reason": "Three-way match failed: {discrepancies}"}
    },
    {
        "id": "RULE-002",
        "name": "Amount Threshold",
        "condition": "extraction.total_amount <= 10000",
        "on_fail": {"action": "ESCALATE", "to": "FINANCE_MANAGER",
                    "reason": "Amount ${amount} exceeds auto-approval threshold"}
    },
    {
        "id": "RULE-003",
        "name": "Confidence Threshold",
        "condition": "extraction.overall_confidence >= 0.85",
        "on_fail": {"action": "ESCALATE", "to": "AP_CLERK",
                    "reason": "Low confidence fields: {low_fields}"}
    },
    {
        "id": "RULE-004",
        "name": "Approved Vendor",
        "condition": "extraction.vendor_name in APPROVED_VENDORS",
        "on_fail": {"action": "ESCALATE", "to": "AP_CLERK",
                    "reason": "Vendor '{vendor}' not in approved vendor list"}
    }
]
# If ALL rules pass → AUTO APPROVE
# First rule that fails → ESCALATE with that rule's routing
```

### 4.6 Component Interaction Sequence

```
┌──────────┐   ┌───────────┐   ┌──────────┐   ┌──────────┐   ┌─────────┐
│S3 Event  │   │Invoice    │   │Extraction│   │Matching  │   │Rules    │
│          │   │Processor  │   │Module    │   │Module    │   │Engine   │
└────┬─────┘   └─────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬────┘
     │               │              │              │              │
     │ 1.ObjectCreated              │              │              │
     │──────────────►│              │              │              │
     │               │ 2.extract()  │              │              │
     │               │─────────────►│              │              │
     │               │              │──►BDA API    │              │
     │               │              │◄──response   │              │
     │               │ 3.result     │              │              │
     │               │◄─────────────│              │              │
     │               │              │              │              │
     │               │ 4.match(extraction)         │              │
     │               │────────────────────────────►│              │
     │               │              │              │──►DynamoDB   │
     │               │              │              │   (PO/GR)    │
     │               │ 5.match_result              │              │
     │               │◄────────────────────────────│              │
     │               │              │              │              │
     │               │ 6.evaluate(extraction, match_result)       │
     │               │───────────────────────────────────────────►│
     │               │ 7.decision (APPROVE/ESCALATE)              │
     │               │◄───────────────────────────────────────────│
     │               │              │              │              │
     │               │ 8.update DynamoDB           │              │
     │               │              │              │              │
```

---

## 5. C4: Records Assistant Component

### 5.1 Responsibility
Provides natural language search across organizational documents using Retrieval Augmented Generation (RAG).

### 5.2 Sub-Components

```
C4: Records Assistant
├── C4.1: Chat Interface (Frontend)
│   ├── Message input and display
│   ├── Citation rendering
│   ├── Category filter selector
│   ├── Conversation session management
│   └── Loading/typing indicators
├── C4.2: Chat Handler (Lambda)
│   ├── Request validation
│   ├── Conversation history retrieval
│   ├── Agent invocation
│   └── Response formatting
├── C4.3: AgentCore Records Agent
│   ├── RAG orchestration
│   ├── Query reformulation
│   ├── Guardrails enforcement
│   └── Citation assembly
├── C4.4: Knowledge Base
│   ├── Document ingestion
│   ├── Chunking and embedding
│   ├── Semantic retrieval
│   └── Metadata filtering
└── C4.5: Conversation Store
    ├── Session management
    ├── History retrieval (last 5)
    └── TTL-based cleanup
```

### 5.3 RAG Pipeline Detail

```
┌───────────┐     ┌──────────────┐     ┌──────────────────┐
│ User      │     │ Chat Handler │     │ AgentCore        │
│ Question  │────►│ (Lambda)     │────►│ Records Agent    │
└───────────┘     └──────────────┘     └────────┬─────────┘
                                                 │
                                    ┌────────────┼────────────┐
                                    │            │            │
                                    ▼            │            ▼
                         ┌──────────────┐       │   ┌──────────────┐
                         │ Retrieve     │       │   │ Guardrails   │
                         │ (KB Search)  │       │   │ (Topic/      │
                         │              │       │   │  Content)    │
                         │ 1.Embed query│       │   └──────────────┘
                         │ 2.Vector     │       │
                         │   search     │       │
                         │ 3.Return top │       │
                         │   k chunks   │       │
                         └──────┬───────┘       │
                                │               │
                                ▼               │
                         ┌──────────────┐       │
                         │ Generate     │       │
                         │ (LLM Call)   │◄──────┘
                         │              │
                         │ Context:     │
                         │ - Retrieved  │
                         │   chunks     │
                         │ - History    │
                         │ - System     │
                         │   prompt     │
                         └──────┬───────┘
                                │
                                ▼
                         ┌──────────────┐
                         │ Response +   │
                         │ Citations    │
                         └──────────────┘
```

### 5.4 Citation Data Structure

```typescript
interface Citation {
  documentName: string;      // "Travel-Policy-2024.pdf"
  documentId: string;        // UUID reference
  pageNumber?: number;       // Page if available from PDF
  chunkText: string;         // The relevant text snippet (truncated)
  relevanceScore: number;    // 0.0 - 1.0
  category: string;          // "policies" | "contracts" | etc.
  s3Uri?: string;            // For download link generation
}

interface ChatResponse {
  answer: string;            // Markdown-formatted answer
  citations: Citation[];     // 1-5 citations
  sessionId: string;         // For follow-up context
  responseTime: number;      // milliseconds
}
```

---

## 6. C5: Dashboard & Reporting Component

### 6.1 Responsibility
Aggregates and displays processing statistics, provides at-a-glance system status.

### 6.2 Sub-Components

```
C5: Dashboard & Reporting
├── C5.1: Stats Aggregator (Lambda)
│   ├── DynamoDB scan/query for counts
│   ├── Status group-by aggregation
│   └── Average processing time calculation
├── C5.2: Dashboard UI (Frontend)
│   ├── Summary stat cards
│   ├── Status distribution (pie/bar chart)
│   └── Recent activity list
└── C5.3: Admin View (Frontend)
    ├── System health indicators
    └── Error count display
```

### 6.3 Dashboard Data Model

```typescript
interface DashboardStats {
  totalInvoices: number;
  statusCounts: {
    uploaded: number;
    processing: number;
    extracted: number;
    matched: number;
    approved: number;
    escalated: number;
    rejected: number;
    error: number;
  };
  autoApprovalRate: number;     // percentage
  avgProcessingTimeSec: number; // seconds from upload to decision
  recentActivity: ActivityItem[];  // last 10 status changes
}

interface ActivityItem {
  documentId: string;
  fileName: string;
  action: string;        // "Auto-approved" | "Escalated" | "Uploaded"
  timestamp: string;
  actor: string;         // "SYSTEM" | user name
}
```

---

## 7. C6: Shared Infrastructure Component

### 7.1 Responsibility
Provides cross-cutting concerns used by all other components.

### 7.2 Sub-Components

```
C6: Shared Infrastructure
├── C6.1: S3 Client Wrapper
│   ├── Presigned URL generation
│   ├── Object get/put operations
│   └── Prefix listing
├── C6.2: DynamoDB Client Wrapper
│   ├── CRUD operations
│   ├── Query by GSI
│   ├── Batch operations
│   └── Conditional updates (status transitions)
├── C6.3: Response Formatter
│   ├── Standard API response structure
│   ├── CORS headers
│   └── Error response formatting
├── C6.4: Logger
│   ├── Structured JSON logging
│   ├── Correlation ID propagation
│   └── Log level configuration
├── C6.5: Validation
│   ├── Pydantic model definitions
│   ├── Common validators
│   └── Sanitization utilities
└── C6.6: Configuration
    ├── Environment variable access
    ├── Feature flags (simple)
    └── Constants (thresholds, limits)
```

### 7.3 Shared Module Interface

```python
# backend/functions/shared/dynamo_client.py
class DynamoClient:
    def __init__(self, table_name: str):
        self.table = boto3.resource('dynamodb').Table(table_name)
    
    def get_item(self, key: dict) -> dict | None: ...
    def put_item(self, item: dict) -> None: ...
    def update_status(self, doc_id: str, new_status: str, **attrs) -> None: ...
    def query_by_index(self, index: str, key_condition: dict) -> list[dict]: ...
    def scan_with_filter(self, filter_expr: dict) -> list[dict]: ...

# backend/functions/shared/s3_client.py
class S3Client:
    def __init__(self, bucket: str):
        self.bucket = bucket
        self.client = boto3.client('s3')
    
    def generate_presigned_post(self, key: str, content_type: str, max_size: int) -> dict: ...
    def generate_presigned_get(self, key: str, expires: int = 3600) -> str: ...
    def get_object(self, key: str) -> bytes: ...

# backend/functions/shared/response.py
def success(body: dict, status_code: int = 200) -> dict: ...
def error(message: str, status_code: int = 400) -> dict: ...
def cors_headers() -> dict: ...
```

---

## 8. Component Dependencies

```
┌──────────────────────────────────────────────────────┐
│                  DEPENDENCY GRAPH                      │
│                                                      │
│   C1 (Auth) ◄─────── All components depend on C1    │
│       │                                              │
│       ▼                                              │
│   C6 (Shared) ◄────── All components depend on C6   │
│       │                                              │
│       ├──────────────────────┐                       │
│       │                      │                       │
│       ▼                      ▼                       │
│   C2 (Document Mgmt)    C5 (Dashboard)              │
│       │                      ▲                       │
│       │                      │                       │
│       ├──────────────────────┤                       │
│       │                      │                       │
│       ▼                      │                       │
│   C3 (Invoice Engine) ───────┘                       │
│       │                                              │
│       │ (processed docs feed into)                   │
│       ▼                                              │
│   C4 (Records Assistant)                             │
│       │                                              │
│       └─── Uses C2's stored documents via KB         │
└──────────────────────────────────────────────────────┘
```

### Dependency Table

| Component | Depends On | Depended By |
|-----------|-----------|-------------|
| C1: Auth | Cognito (external) | C2, C3, C4, C5 |
| C2: Document Mgmt | C1, C6 | C3, C4, C5 |
| C3: Invoice Engine | C1, C2, C6 | C4 (via KB), C5 |
| C4: Records Assistant | C1, C6, Bedrock KB | C5 (indirectly) |
| C5: Dashboard | C1, C6 | None |
| C6: Shared | None (standalone) | C1, C2, C3, C4, C5 |

---

## 9. Component Communication Patterns

| From | To | Pattern | Mechanism |
|------|----|---------|-----------|
| Frontend → Backend | Synchronous | REST API (API Gateway) |
| S3 → InvoiceProcessor | Asynchronous | S3 Event Notification |
| InvoiceProcessor → BDA | Synchronous | AWS SDK (boto3) |
| InvoiceProcessor → AgentCore | Synchronous | AWS SDK |
| ChatHandler → AgentCore | Synchronous | AWS SDK |
| AgentCore → Bedrock KB | Synchronous | Internal AWS |
| AgentCore → Bedrock LLM | Synchronous | Internal AWS |
| Lambda → DynamoDB | Synchronous | AWS SDK |
| Frontend → S3 | Synchronous | Presigned URL (direct) |

---

## 10. Deployment Units

Each component maps to one or more deployment artifacts:

| Component | Deployment Unit | Artifact |
|-----------|----------------|----------|
| C1 | Cognito User Pool | SAM/CloudFormation resource |
| C2 | UploadHandler Lambda + S3 Bucket | SAM package |
| C3 | InvoiceProcessor Lambda | SAM package |
| C4 | ChatHandler Lambda + Bedrock KB | SAM package + manual KB setup |
| C5 | DashboardHandler Lambda | SAM package |
| C6 | Lambda Layer | Shared code layer |
| Frontend | S3 Static Website | npm build → S3 sync |

### Lambda Layer for Shared Code

```yaml
# In SAM template.yaml
SharedLayer:
  Type: AWS::Serverless::LayerVersion
  Properties:
    LayerName: intelliprocess-shared
    ContentUri: functions/shared/
    CompatibleRuntimes:
      - python3.12
    Description: Shared utilities (DynamoDB client, S3 client, response formatter)
```

All Lambda functions reference this layer, avoiding code duplication while keeping individual function packages small.
