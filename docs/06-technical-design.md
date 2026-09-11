# Technical Design

## IntelliProcess AI Platform

---

## 1. Technology Stack

### 1.1 Frontend

| Layer | Technology | Version | Justification |
|-------|-----------|---------|---------------|
| Framework | React | 18.x | Component-based, team familiarity |
| Build Tool | Vite | 5.x | Fast HMR, simple config |
| Language | TypeScript | 5.x | Type safety, better DX |
| Styling | Tailwind CSS | 3.x | Utility-first, rapid UI development |
| HTTP Client | Axios | 1.x | Interceptors for auth, error handling |
| Auth | AWS Amplify Auth | 6.x | Native Cognito integration |
| State | React Context + useReducer | - | Sufficient for MVP complexity |
| Routing | React Router | 6.x | Standard SPA routing |
| Chat UI | Custom component | - | Lightweight, no extra dependency |

### 1.2 Backend

| Layer | Technology | Version | Justification |
|-------|-----------|---------|---------------|
| Runtime | Python | 3.12 | Best boto3 support, AI/ML ecosystem |
| Framework | None (raw Lambda handlers) | - | Minimal cold start, simple for MVP |
| AWS SDK | boto3 | latest | Native AWS service interaction |
| Validation | Pydantic | 2.x | Request/response validation |
| Utilities | python-dateutil, uuid | stdlib | Date parsing, ID generation |
| Packaging | AWS SAM | latest | Lambda deployment + IaC |

**Implementation note (updated):** The API Lambdas (UploadHandler, ChatHandler,
DashboardHandler) are implemented as a single **FastAPI application served via
Mangum**, packaged in the shared layer; each function's handler entry point is
`lambda_function.lambda_handler` (`from app.main import handler`). API Gateway
still owns routing/CORS/auth at the edge, and each function is wired only to its
designated routes. The InvoiceProcessor Lambda remains a plain S3-event handler.
The original MVP intent (below) was framework-less; the FastAPI+Mangum approach
was adopted for shared middleware, validation, and routing across the app.

**Original decision: No web framework (Flask/FastAPI)**
- Lambda handlers are simple request→response functions
- API Gateway handles routing, CORS, auth
- Adding a framework increases cold start and complexity without benefit for this scale

### 1.3 Infrastructure as Code

| Tool | Purpose | Justification |
|------|---------|---------------|
| AWS SAM (template.yaml) | Lambda + API Gateway + DynamoDB | Simpler than CDK for Lambda-focused apps |
| AWS CLI | Bedrock KB and BDA setup | Some resources require CLI/console setup |

---

## 2. Project Structure

```
intelliprocess-ai/
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   │   ├── common/
│   │   │   │   ├── Layout.tsx
│   │   │   │   ├── Navbar.tsx
│   │   │   │   ├── ProtectedRoute.tsx
│   │   │   │   └── StatusBadge.tsx
│   │   │   ├── invoice/
│   │   │   │   ├── InvoiceUpload.tsx
│   │   │   │   ├── InvoiceList.tsx
│   │   │   │   ├── InvoiceDetail.tsx
│   │   │   │   ├── ExtractionView.tsx
│   │   │   │   └── MatchingResult.tsx
│   │   │   ├── chat/
│   │   │   │   ├── ChatWindow.tsx
│   │   │   │   ├── MessageBubble.tsx
│   │   │   │   ├── CitationCard.tsx
│   │   │   │   └── CategoryFilter.tsx
│   │   │   └── dashboard/
│   │   │       ├── StatsCards.tsx
│   │   │       └── ProcessingSummary.tsx
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── InvoicesPage.tsx
│   │   │   ├── ChatPage.tsx
│   │   │   └── AdminPage.tsx
│   │   ├── services/
│   │   │   ├── api.ts
│   │   │   ├── auth.ts
│   │   │   └── types.ts
│   │   ├── context/
│   │   │   └── AuthContext.tsx
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── tailwind.config.js
│
├── backend/
│   ├── functions/
│   │   ├── upload_handler/
│   │   │   ├── __init__.py
│   │   │   └── app.py
│   │   ├── invoice_processor/
│   │   │   ├── __init__.py
│   │   │   ├── app.py
│   │   │   ├── extractor.py
│   │   │   ├── matcher.py
│   │   │   └── rules.py
│   │   ├── chat_handler/
│   │   │   ├── __init__.py
│   │   │   └── app.py
│   │   ├── dashboard_handler/
│   │   │   ├── __init__.py
│   │   │   └── app.py
│   │   └── shared/
│   │       ├── __init__.py
│   │       ├── models.py
│   │       ├── dynamo_client.py
│   │       ├── s3_client.py
│   │       └── response.py
│   ├── agents/
│   │   ├── ap_invoice_agent/
│   │   │   ├── agent_config.json
│   │   │   ├── instructions.md
│   │   │   └── tools/
│   │   │       ├── extract_invoice.py
│   │   │       ├── match_po.py
│   │   │       ├── match_gr.py
│   │   │       └── evaluate_rules.py
│   │   └── records_agent/
│   │       ├── agent_config.json
│   │       ├── instructions.md
│   │       └── tools/
│   │           └── search_knowledge_base.py
│   ├── requirements.txt
│   └── template.yaml          # AWS SAM template
│
├── data/
│   ├── sample_invoices/       # 5-10 sample PDF invoices
│   ├── sample_pos/            # Sample PO JSON data
│   ├── sample_grs/            # Sample GR JSON data
│   └── sample_records/        # 20-50 organizational docs
│
├── scripts/
│   ├── seed_data.py           # Load sample PO/GR data to DynamoDB
│   ├── sync_knowledge_base.py # Trigger KB sync
│   └── create_users.py        # Create Cognito test users
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── docs/                      # This documentation
├── .env.example
├── .gitignore
└── README.md
```

---

## 3. Lambda Function Design

### 3.1 Function Specifications

| Function | Trigger | Timeout | Memory | Description |
|----------|---------|---------|--------|-------------|
| UploadHandler | API Gateway POST | 30s | 256MB | Generate presigned URL, create metadata |
| InvoiceProcessor | S3 Event (ObjectCreated) | 300s | 512MB | Orchestrate extraction + matching + rules |
| ChatHandler | API Gateway POST/GET | 60s | 256MB | Handle RAG queries and session history |
| DashboardHandler | API Gateway GET/POST/PUT | 29s | 512MB | Invoice list/detail, approval, stats, admin settings, PO/GR upload + document extraction |

**Note on DashboardHandler:** This function handles multiple routes via the
FastAPI app (see framework note below). It also serves the admin approval
settings (`/admin/settings`) and the PO/GR reference-data endpoints, including
synchronous BDA document extraction (`/purchase-orders/extract`,
`/goods-receipts/extract`) — hence its higher timeout (29s, the API Gateway
integration ceiling) and memory. Post-MVP, split into separate functions for
better isolation and IAM scoping.

### 3.2 Upload Handler Flow

```python
# Pseudocode for upload_handler/app.py
def lambda_handler(event, context):
    """Generate presigned URL for S3 upload and create metadata record."""
    
    # 1. Parse request (file name, content type, document type)
    body = parse_request(event)
    
    # 2. Validate file extension and size
    validate_file(body.file_name, body.content_type)
    
    # 3. Generate unique document ID
    doc_id = str(uuid4())
    
    # 4. Determine S3 key based on document type
    s3_key = f"{body.document_type}/{doc_id}/{body.file_name}"
    
    # 5. Generate presigned POST URL (expires 5 min)
    presigned = s3_client.generate_presigned_post(
        Bucket=BUCKET_NAME,
        Key=s3_key,
        ExpiresIn=300,
        Conditions=[["content-length-range", 1, 10_485_760]]  # 10MB max
    )
    
    # 6. Create DynamoDB metadata record
    dynamo_client.put_item(
        TableName=DOCUMENT_TABLE,
        Item={
            "documentId": doc_id,
            "fileName": body.file_name,
            "s3Key": s3_key,
            "documentType": body.document_type,
            "status": "UPLOADED",
            "uploadedBy": event.requestContext.authorizer.claims.sub,
            "uploadedAt": datetime.utcnow().isoformat(),
        }
    )
    
    # 7. Return presigned URL to client
    return response(201, {"documentId": doc_id, "uploadUrl": presigned})
```

### 3.3 Invoice Processor Flow

```python
# Pseudocode for invoice_processor/app.py
def lambda_handler(event, context):
    """Triggered by S3 upload event. Orchestrates full invoice processing."""
    
    # 1. Parse S3 event to get bucket/key
    s3_key = event["Records"][0]["s3"]["object"]["key"]
    doc_id = extract_doc_id(s3_key)
    
    # 2. Update status to PROCESSING
    update_status(doc_id, "PROCESSING")
    
    try:
        # 3. Call BDA for extraction
        extraction_result = extractor.extract_invoice(BUCKET_NAME, s3_key)
        
        # 4. Store extraction results, update status
        store_extraction(doc_id, extraction_result)
        update_status(doc_id, "EXTRACTED")
        
        # 5. Run PO and GR matching (direct function calls — no AgentCore)
        po_result = matcher.match_purchase_order(
            po_number=extraction_result.get("poReference"),
            vendor_name=extraction_result["vendorName"],
            invoice_amount=extraction_result["totalAmount"]
        )
        gr_result = matcher.match_goods_receipt(
            po_number=po_result.get("poId", extraction_result.get("poReference")),
            invoiced_quantity=sum(item["quantity"] for item in extraction_result["lineItems"])
        )
        
        # 6. Evaluate three-way match
        three_way = "PASS" if (po_result["status"] == "MATCHED" and
                               gr_result["status"] == "CONFIRMED") else "FAIL"
        all_discrepancies = po_result["discrepancies"] + gr_result["discrepancies"]
        
        # 6b. Load admin-configurable thresholds/tolerances (AppConfig; defaults if unset)
        settings = settings_store.get_approval_settings()
        # (poAmountTolerance/grQtyTolerance are passed into the matcher calls above;
        #  amountThreshold/confidenceThreshold are passed into rules below)

        # 7. Apply approval rules (RULE-001 match, RULE-002 amount, RULE-003 confidence)
        decision = rules.evaluate(
            total_amount=extraction_result["totalAmount"],
            overall_confidence=extraction_result["overallConfidence"],
            vendor_name=extraction_result["vendorName"],  # for logging only; not a rule
            three_way_match_status=three_way,
            discrepancies=all_discrepancies
        )
        
        # 8. Store match results and update final status
        store_match_results(doc_id, po_result, gr_result, three_way)
        if decision["decision"] == "APPROVE":
            update_status(doc_id, "APPROVED", approver="SYSTEM")
        else:
            update_status(doc_id, "ESCALATED", reason=decision["reason"],
                         assignee=decision["escalateTo"])
    
    except Exception as e:
        update_status(doc_id, "ERROR", error=str(e))
        logger.error(f"Processing failed for {doc_id}: {e}")
```

### 3.4 Chat Handler Flow

```python
# Pseudocode for chat_handler/app.py
def lambda_handler(event, context):
    """Handle natural language queries via RAG."""
    
    # 1. Parse request
    body = parse_request(event)
    user_id = get_user_id(event)
    
    # 2. Get conversation history (last 5 messages)
    history = get_conversation_history(user_id, body.session_id)
    
    # 3. Invoke Bedrock KB RetrieveAndGenerate (direct call — no AgentCore)
    response = bedrock_client.retrieve_and_generate(
        input={"text": body.question},
        retrieveAndGenerateConfiguration={
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": KNOWLEDGE_BASE_ID,
                "modelArn": MODEL_ARN,
            }
        },
        sessionId=body.session_id
    )
    
    # 4. Format citations
    citations = format_citations(response.source_documents)
    
    # 5. Store conversation turn
    store_conversation(user_id, body.session_id, body.question, response.answer)
    
    # 6. Return response
    return response(200, {
        "answer": response.answer,
        "citations": citations,
        "sessionId": body.session_id
    })
```

---

## 4. Frontend Technical Design

### 4.1 Authentication Flow

```typescript
// services/auth.ts
import { signIn, signOut, getCurrentUser, fetchAuthSession } from 'aws-amplify/auth';

export const login = async (username: string, password: string) => {
  const result = await signIn({ username, password });
  return result;
};

export const getToken = async (): Promise<string> => {
  const session = await fetchAuthSession();
  return session.tokens?.idToken?.toString() ?? '';
};

export const getUserRole = async (): Promise<string> => {
  const session = await fetchAuthSession();
  const groups = session.tokens?.idToken?.payload['cognito:groups'] as string[];
  return groups?.[0] ?? 'STAFF';
};
```

### 4.2 API Service Layer

```typescript
// services/api.ts
import axios from 'axios';
import { getToken } from './auth';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
});

// Attach JWT to every request
api.interceptors.request.use(async (config) => {
  const token = await getToken();
  config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// API methods
export const uploadInvoice = async (file: File) => {
  // 1. Get presigned URL
  const { data } = await api.post('/invoices/upload', {
    fileName: file.name,
    contentType: file.type,
    documentType: 'invoices',
  });
  
  // 2. Upload directly to S3
  await axios.post(data.uploadUrl.url, createFormData(data.uploadUrl.fields, file));
  
  return data.documentId;
};

export const getInvoices = () => api.get('/invoices');
export const getInvoiceDetail = (id: string) => api.get(`/invoices/${id}`);
export const askQuestion = (question: string, sessionId?: string, category?: string) =>
  api.post('/chat', { question, sessionId, categoryFilter: category });
export const getDashboardStats = () => api.get('/dashboard/stats');
export const approveInvoice = (id: string, action: 'APPROVE' | 'REJECT', comment: string) =>
  api.post(`/invoices/${id}/approve`, { action, comment });
```

### 4.3 Key Component Design

```typescript
// components/chat/ChatWindow.tsx - Core pattern
interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  timestamp: string;
}

const ChatWindow: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string>(generateSessionId());
  const [category, setCategory] = useState<string>('all');

  const handleSend = async () => {
    if (!input.trim()) return;
    
    // Add user message
    const userMsg: Message = { id: uuid(), role: 'user', content: input, timestamp: now() };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);
    
    try {
      const { data } = await askQuestion(input, sessionId, category);
      const assistantMsg: Message = {
        id: uuid(),
        role: 'assistant',
        content: data.answer,
        citations: data.citations,
        timestamp: now(),
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (err) {
      // Show error message in chat
    } finally {
      setLoading(false);
    }
  };

  return (/* JSX with message list, input area, category filter */);
};
```

---

## 5. Error Handling Strategy

### 5.1 Backend Error Handling

```python
# shared/response.py
import json
import logging
from functools import wraps

logger = logging.getLogger()

class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code

def api_handler(func):
    """Decorator for Lambda handlers with standard error handling."""
    @wraps(func)
    def wrapper(event, context):
        try:
            return func(event, context)
        except AppError as e:
            logger.warning(f"Application error: {e.message}")
            return {
                "statusCode": e.status_code,
                "headers": cors_headers(),
                "body": json.dumps({"error": e.message})
            }
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "headers": cors_headers(),
                "body": json.dumps({"error": "An internal error occurred. Please try again."})
            }
    return wrapper
```

### 5.2 Error Categories

| Category | HTTP Code | User Message | Logging |
|----------|-----------|-------------|---------|
| Validation error | 400 | Specific field error | WARN |
| Authentication | 401 | "Please log in" | INFO |
| Authorization | 403 | "Insufficient permissions" | WARN |
| Not found | 404 | "Resource not found" | INFO |
| BDA failure | 500 | "Document processing failed" | ERROR |
| Bedrock timeout | 504 | "Request timed out, please retry" | ERROR |
| Unexpected | 500 | "Internal error occurred" | ERROR |

### 5.3 Retry Strategy

| Service | Retry Behavior |
|---------|---------------|
| Bedrock API calls | 3 retries with exponential backoff (1s, 2s, 4s) |
| DynamoDB writes | boto3 default retry (5 retries) |
| S3 operations | boto3 default retry |
| BDA extraction | 2 retries (extraction is idempotent) |

---

## 6. Configuration Management

### 6.1 Environment Variables

```yaml
# Shared environment variables (set in SAM template Globals)
STAGE: {stage}
DOCUMENT_BUCKET: intelliprocess-ai-documents
INVOICE_TABLE: IntelliProcess-Invoices-{stage}
DOCUMENT_TABLE: IntelliProcess-Documents-{stage}
PO_TABLE: IntelliProcess-PurchaseOrders-{stage}
GR_TABLE: IntelliProcess-GoodsReceipts-{stage}
CONVERSATION_TABLE: IntelliProcess-Conversations-{stage}
CONFIG_TABLE: IntelliProcess-AppConfig-{stage}   # admin approval settings
KNOWLEDGE_BASE_ID: <set after KB creation>
BDA_PROJECT_ARN: <optional; not required for the public-blueprint path>
BEDROCK_MODEL_ID: anthropic.claude-3-sonnet-20240229-v1:0
USE_MOCKS: "false"    # "true" for local dev (skips real AWS/BDA calls)
LOG_LEVEL: INFO
```

> Note: `USE_MOCKS` controls whether extraction (and other AWS integrations)
> call real services or return deterministic mocks. It is `"false"` in the
> deployed stack (real BDA) and can be `"true"` for local development. The
> deployed value comes from the SAM template, not from `.env`.

### 6.2 Frontend Configuration

```typescript
// .env.local (not committed)
VITE_API_URL=https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/prod
VITE_USER_POOL_ID=us-east-1_XXXXXXXXX
VITE_USER_POOL_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxx
VITE_AWS_REGION=us-east-1
```

---

## 7. Logging and Observability

### 7.1 Structured Logging

```python
# All Lambda functions use structured JSON logging
import json
import logging

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

def log_event(event_type: str, doc_id: str, **kwargs):
    logger.info(json.dumps({
        "event": event_type,
        "documentId": doc_id,
        "timestamp": datetime.utcnow().isoformat(),
        **kwargs
    }))

# Usage:
log_event("extraction_complete", doc_id, confidence=0.92, fields_extracted=12)
log_event("match_result", doc_id, po_match="MATCHED", gr_match="CONFIRMED")
log_event("approval_decision", doc_id, decision="APPROVED", approver="SYSTEM")
```

### 7.2 CloudWatch Metrics (Post-MVP)

Custom metrics are deferred to post-MVP. For the MVP, use standard Lambda metrics (Duration, Errors, Invocations) and CloudWatch Logs Insights for ad-hoc queries.

| Metric | Namespace | Dimensions | Status |
|--------|-----------|-----------|--------|
| InvoicesProcessed | IntelliProcess | Status (APPROVED/ESCALATED/ERROR) | Post-MVP |
| ExtractionDuration | IntelliProcess | - | Post-MVP |
| ChatResponseTime | IntelliProcess | - | Post-MVP |
| MatchResult | IntelliProcess | Result (PASS/FAIL) | Post-MVP |

### 7.3 Correlation IDs

Every request receives a correlation ID that flows through all service calls:

```python
correlation_id = event.get("headers", {}).get("x-correlation-id", str(uuid4()))
# Passed to all downstream calls and logged with every log entry
```

---

## 8. Security Implementation Details

### 8.1 Input Validation (Pydantic Models)

```python
from pydantic import BaseModel, Field, validator
from typing import Optional

class UploadRequest(BaseModel):
    fileName: str = Field(..., max_length=255)
    contentType: str = Field(...)
    documentType: str = Field(...)
    
    @validator('contentType')
    def validate_content_type(cls, v):
        allowed = ['application/pdf', 'image/png', 'image/jpeg']
        if v not in allowed:
            raise ValueError(f'Unsupported content type: {v}')
        return v
    
    @validator('documentType')
    def validate_doc_type(cls, v):
        allowed = ['invoices', 'purchase-orders', 'goods-receipts', 'records']
        if v not in allowed:
            raise ValueError(f'Invalid document type: {v}')
        return v

class RecordsUploadRequest(BaseModel):
    fileName: str = Field(..., max_length=255)
    contentType: str = Field(...)
    category: str = Field(...)
    description: Optional[str] = Field(None, max_length=500)
    
    @validator('contentType')
    def validate_content_type(cls, v):
        allowed = ['application/pdf', 'text/plain',
                   'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
        if v not in allowed:
            raise ValueError(f'Unsupported content type for records: {v}')
        return v
    
    @validator('category')
    def validate_category(cls, v):
        allowed = ['policies', 'contracts', 'finance', 'procurement', 'general']
        if v not in allowed:
            raise ValueError(f'Invalid category: {v}')
        return v

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    sessionId: Optional[str] = Field(None, max_length=64)
    categoryFilter: Optional[str] = Field(None)
    
    @validator('categoryFilter')
    def validate_category(cls, v):
        if v and v not in ['policies', 'contracts', 'finance', 'procurement', 'all']:
            raise ValueError(f'Invalid category: {v}')
        return v
```

### 8.2 S3 Presigned URL Security

```python
# Presigned URLs are scoped and time-limited
presigned_url = s3_client.generate_presigned_post(
    Bucket=BUCKET_NAME,
    Key=s3_key,
    Fields={"Content-Type": content_type},
    Conditions=[
        {"Content-Type": content_type},
        ["content-length-range", 1, 10_485_760],  # 1 byte to 10MB
    ],
    ExpiresIn=300  # 5 minutes
)
```

---

## 9. Performance Optimization

### 9.1 Lambda Cold Start Mitigation

| Strategy | Implementation |
|----------|---------------|
| Minimal dependencies | Only import what's needed per function |
| Layer for boto3 | Shared Lambda layer for AWS SDK |
| Global connections | Initialize clients outside handler |
| Small package size | Exclude dev dependencies |

```python
# Initialize clients outside handler (reused across warm invocations)
import boto3

dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')
bedrock_client = boto3.client('bedrock-runtime')

table = dynamodb.Table(os.environ['INVOICE_TABLE'])

def lambda_handler(event, context):
    # Handler uses pre-initialized clients
    ...
```

### 9.2 DynamoDB Access Patterns

| Access Pattern | Key Design | Index |
|----------------|-----------|-------|
| Get invoice by ID | PK=documentId | Table (hash key) |
| List invoices by user | PK=uploadedBy, SK=uploadedAt | GSI-1 |
| List invoices by status | PK=status, SK=uploadedAt | GSI-2 |
| Get PO by number | PK=poNumber | Table (hash key) |
| Get GR by PO number | PK=poNumber | Table (hash key) |
| Get conversation | PK=sessionId, SK=timestamp | Table (composite) |

---

## 10. Development Workflow

### 10.1 Local Development

```bash
# Frontend
cd frontend && npm run dev     # Vite dev server on localhost:5173

# Backend (local invoke)
cd backend && sam local invoke UploadHandler -e events/upload.json

# Backend (local API)
cd backend && sam local start-api --port 3001
```

### 10.2 Deployment Pipeline

```bash
# Build and deploy backend
cd backend
sam build
sam deploy --guided  # First time (creates samconfig.toml)
sam deploy           # Subsequent deploys

# Deploy frontend
cd frontend
npm run build
aws s3 sync dist/ s3://intelliprocess-frontend-{stage}/ --delete
```

### 10.3 Git Branching

```
main (protected)
├── develop (integration)
│   ├── feature/auth-setup
│   ├── feature/invoice-extraction
│   ├── feature/po-matching
│   ├── feature/chat-rag
│   └── feature/dashboard
```

Short-lived feature branches merged to `develop` via PR. `develop` merged to `main` for deployment milestones.
