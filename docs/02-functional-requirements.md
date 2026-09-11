# Functional Requirements

## IntelliProcess AI Platform

---

## 1. Requirements Traceability

All functional requirements are tagged with:
- **Priority**: P1 (MVP-Critical), P2 (MVP-Nice-to-Have), P3 (Deferred)
- **Module**: SHARED, AP (Accounts Payable), RAG (Records Assistant)
- **ID Format**: `FR-{MODULE}-{NUMBER}`

---

## 2. Shared Platform Requirements

### FR-SHARED-001: User Authentication
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Description | The system shall authenticate users before granting access to any functionality |
| Input | Username/email and password (or API key) |
| Output | Authentication token (JWT) or session |
| Business Rule | Invalid credentials shall be rejected with a generic error message |
| Implementation Note | Use Amazon Cognito User Pool with hosted UI for MVP |

### FR-SHARED-002: Role-Based Access Control
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Description | The system shall enforce role-based access control on all API endpoints |
| Roles | AP_CLERK, FINANCE_MANAGER, STAFF, ADMIN |
| Business Rule | Users can only access functions permitted by their assigned role |
| Implementation Note | Cognito groups mapped to IAM policies via API Gateway authorizer |

### FR-SHARED-003: Document Upload
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Description | The system shall accept document uploads via the web interface |
| Supported Formats | PDF, PNG, JPEG (invoices); PDF, DOCX, TXT (records) |
| Max File Size | 10 MB |
| Business Rule | Files exceeding size limit or unsupported format shall be rejected with descriptive error |
| Output | Document stored in S3 with metadata recorded in DynamoDB |

### FR-SHARED-004: Document Storage
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Description | The system shall store all uploaded documents in durable cloud storage |
| Storage | Amazon S3 with server-side encryption (AES-256) |
| Organization | Partitioned by document type: `invoices/`, `purchase-orders/`, `goods-receipts/`, `records/` |
| Metadata | File name, upload timestamp, uploader ID, document type, processing status |

### FR-SHARED-005: Processing Status Tracking
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Description | The system shall track and display the processing status of all documents |
| Statuses | UPLOADED, PROCESSING, EXTRACTED, APPROVED, REJECTED, ESCALATED, ERROR |
| Note | MATCHED was removed as a user-visible status. Matching details are stored as data within the invoice record. The pipeline flows EXTRACTED → APPROVED or EXTRACTED → ESCALATED. |
| Business Rule | Status transitions must be logged with timestamp |
| Output | Real-time status visible on dashboard |

### FR-SHARED-006: Error Handling and User Feedback
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Description | The system shall provide meaningful error messages for all failure scenarios |
| Business Rule | Technical errors shall be logged but not exposed to users; user-friendly messages displayed instead |
| Implementation Note | CloudWatch for logging; generic error codes returned to frontend |

---

## 3. AP Invoice Agent Requirements

### FR-AP-001: Invoice Data Extraction
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Description | The system shall automatically extract structured data from uploaded invoice documents |
| Input | Invoice document (PDF, PNG, JPEG) |
| Extracted Fields | Vendor name, vendor address, invoice number, invoice date, due date, line items (description, quantity, unit price, amount), subtotal, tax, total amount, payment terms, PO reference number |
| Accuracy Target | > 90% field-level accuracy on well-formatted invoices |
| Technology | Bedrock Data Automation (BDA) |
| Output | Structured JSON with extracted fields and confidence scores |
| Implementation Note | MVP uses direct BDA API calls from Lambda (no AgentCore orchestration) |

### FR-AP-002: Extraction Confidence Scoring
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Description | The system shall assign confidence scores to each extracted field |
| Scale | 0.0 to 1.0 |
| Business Rule | Fields with confidence < 0.85 shall be flagged for human review |
| Output | Confidence score per field included in extraction result |

### FR-AP-003: Purchase Order Matching
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Description | The system shall attempt to match extracted invoice data against existing Purchase Orders |
| Matching Criteria | PO number (exact match), vendor name (fuzzy match), total amount (within the PO amount tolerance) |
| Business Rule | If PO reference is present on invoice, system shall first attempt exact PO number match |
| Business Rule | The PO amount tolerance is admin-configurable (default 5%; 0 = exact match) — see FR-CROSS-005 |
| Output | Match result: MATCHED, PARTIAL_MATCH, NO_MATCH |

### FR-AP-004: Goods Receipt Matching
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Description | The system shall verify that goods/services referenced on the invoice have been received |
| Matching Criteria | PO number linkage, quantity received vs. quantity invoiced |
| Business Rule | Invoice quantity must not exceed received quantity by more than the GR quantity tolerance (admin-configurable, default 2%; 0 = exact match) — see FR-CROSS-005 |
| Output | GR match result: CONFIRMED, PARTIAL, NOT_RECEIVED |

### FR-AP-005: Three-Way Match Validation
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Description | The system shall perform three-way matching (Invoice <-> PO <-> Goods Receipt) |
| Business Rule | Three-way match PASSES only when PO match = MATCHED and GR match = CONFIRMED (each within its admin-configurable tolerance) |
| Output | THREE_WAY_MATCH_PASS or THREE_WAY_MATCH_FAIL with specific discrepancy details |

### FR-AP-006: Automatic Approval
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Description | The system shall automatically approve invoices that pass all validation rules |
| Approval Rules | (RULE-001) Three-way match passes, (RULE-002) Invoice amount ≤ amount threshold (default $10,000), (RULE-003) Overall extraction confidence ≥ confidence threshold (default 0.85) |
| Business Rule | All three conditions must be true for auto-approval. Thresholds are admin-configurable (see FR-CROSS-005). |
| Business Rule | An approved-vendor allow-list check (former RULE-004) has been **removed**; vendor membership no longer gates auto-approval. |
| Output | Invoice status set to APPROVED with approval timestamp and "SYSTEM" approver |

### FR-AP-007: Exception Escalation
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Description | The system shall escalate invoices that fail automatic approval to appropriate personnel |
| Escalation Rules | Amount > $10,000 → Finance Manager; Match failure → AP Clerk; Low confidence → AP Clerk |
| Business Rule | Escalated invoices shall include the specific reason for escalation |
| Output | Invoice status set to ESCALATED with reason and assignee |

### FR-AP-008: Manual Review Interface
| Attribute | Value |
|-----------|-------|
| Priority | P2 |
| Description | The system shall provide a UI for reviewing escalated invoices with extracted data displayed alongside the original document |
| Features | Side-by-side document view, editable extracted fields, approve/reject buttons |
| Business Rule | Manual approval requires a reason/comment |

### FR-AP-009: Invoice Processing Summary
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Description | The system shall display a dashboard summary of invoice processing statistics |
| Metrics | Total processed, auto-approved, escalated, rejected, average processing time |
| Refresh | On page load (not real-time for MVP) |

### FR-AP-010: Reference Data Management (PO / GR)
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Description | Administrators shall be able to create Purchase Order and Goods Receipt reference records used for three-way matching |
| Entry Modes | (1) Manual structured entry; (2) Upload a PO/GR document to auto-extract candidate fields for review |
| Business Rule | A Goods Receipt must reference an existing Purchase Order |
| Business Rule | Extracted fields are pre-filled into an editable form; the admin confirms/corrects before saving (extraction never persists directly) |
| Technology | Amazon Bedrock Data Automation (public invoice blueprint), invoked synchronously with an async fallback |
| Output | PO/GR reference records stored in DynamoDB and available to the matcher |

---

## 4. Ask-Your-Records Assistant Requirements

### FR-RAG-001: Document Ingestion for Knowledge Base
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Description | The system shall ingest organizational documents into a searchable knowledge base |
| Supported Types | Policies, contracts, purchase orders, finance documents, procedures |
| Supported Formats | PDF, DOCX, TXT |
| Processing | Text extraction, chunking, embedding generation, vector storage |
| Technology | Amazon Bedrock Knowledge Bases |
| Implementation Note | MVP uses direct Bedrock KB RetrieveAndGenerate API (no AgentCore). KB data source includes all S3 prefixes (records/, invoices/, purchase-orders/). |

### FR-RAG-002: Natural Language Query Interface
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Description | The system shall provide a chat interface for natural language queries against organizational records |
| Input | Free-text question in English |
| Output | Natural language answer with source citations |
| Business Rule | If no relevant information is found, system shall state it cannot answer rather than hallucinate |

### FR-RAG-003: Source Citation
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Description | Every answer shall include citations referencing the source documents used |
| Citation Format | Document name, page number (if available), relevance score |
| Business Rule | At minimum one citation required for every factual claim in the response |
| Implementation Note | Bedrock Knowledge Bases returns source chunks with metadata |

### FR-RAG-004: Conversation Context
| Attribute | Value |
|-----------|-------|
| Priority | P2 |
| Description | The system shall maintain conversation context within a session for follow-up questions |
| Context Window | Last 5 messages in conversation |
| Business Rule | User can start a new conversation to reset context |
| Implementation Note | Store conversation history in DynamoDB with session TTL |

### FR-RAG-005: Document Scope Filtering
| Attribute | Value |
|-----------|-------|
| Priority | P2 |
| Description | Users shall be able to filter searches by document category |
| Categories | Policies, Contracts, Finance, Procurement, All |
| Business Rule | Default scope is "All" if no filter specified |
| Implementation Note | Use metadata filters in Bedrock Knowledge Base retrieval |

### FR-RAG-006: Answer Quality Guardrails
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Description | The system shall implement guardrails to prevent inappropriate or off-topic responses |
| Rules | (1) Only answer questions related to organizational records, (2) Do not generate content unrelated to the document corpus, (3) Clearly state uncertainty when confidence is low |
| Technology | Bedrock Guardrails |

### FR-RAG-007: Search History
| Attribute | Value |
|-----------|-------|
| Priority | P3 (Deferred) |
| Description | The system shall maintain a searchable history of past queries and answers |
| Reason Deferred | Not critical for MVP demonstration |

---

## 5. Cross-Cutting Requirements

### FR-CROSS-001: Unified Document Pipeline
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Description | Documents uploaded for AP processing shall also be indexed in the knowledge base for RAG search |
| Business Rule | Invoices, POs, and GRs are searchable via the Records Assistant after KB sync |
| Benefit | Demonstrates integration between the two use cases |
| Implementation Note | The KB data source S3 prefix includes invoices/ — no extra pipeline needed. A manual KB sync (or scheduled sync) indexes newly processed invoices. |

### FR-CROSS-002: Audit Logging
| Attribute | Value |
|-----------|-------|
| Priority | P2 |
| Description | The system shall log all significant actions (uploads, approvals, searches) |
| Storage | CloudWatch Logs |
| Retention | 30 days for MVP |

### FR-CROSS-003: API Rate Limiting
| Attribute | Value |
|-----------|-------|
| Priority | P2 |
| Description | The system shall enforce rate limits on API endpoints to prevent abuse |
| Limits | 100 requests/minute per user |
| Implementation Note | API Gateway throttling configuration |

### FR-CROSS-005: Admin-Configurable Approval Settings
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Description | Administrators shall be able to view and adjust the thresholds that drive auto-approval and three-way matching |
| Settings | amountThreshold (USD, default 10000), confidenceThreshold (0–1, default 0.85), poAmountTolerance (0–1, default 0.05), grQtyTolerance (0–1, default 0.02) |
| Business Rule | Settings are persisted (AppConfig table) and applied to subsequent invoice processing; when unset, built-in defaults apply |
| Business Rule | A tolerance of 0 means an exact match is required |
| Access | ADMIN role only (`GET`/`PUT /admin/settings`) |
| Output | Persisted approval settings applied by the matcher and rules engine |

---

## 6. Requirements Summary Matrix

| ID | Requirement | Priority | Module | Sprint |
|----|-------------|----------|--------|--------|
| FR-SHARED-001 | User Authentication | P1 | SHARED | Week 1 |
| FR-SHARED-002 | Role-Based Access Control | P1 | SHARED | Week 1 |
| FR-SHARED-003 | Document Upload | P1 | SHARED | Week 1 |
| FR-SHARED-004 | Document Storage | P1 | SHARED | Week 1 |
| FR-SHARED-005 | Processing Status Tracking | P1 | SHARED | Week 1 |
| FR-SHARED-006 | Error Handling | P1 | SHARED | Week 1 |
| FR-AP-001 | Invoice Data Extraction | P1 | AP | Week 1 |
| FR-AP-002 | Confidence Scoring | P1 | AP | Week 1 |
| FR-AP-003 | PO Matching | P1 | AP | Week 2 |
| FR-AP-004 | GR Matching | P1 | AP | Week 2 |
| FR-AP-005 | Three-Way Match | P1 | AP | Week 2 |
| FR-AP-006 | Automatic Approval | P1 | AP | Week 2 |
| FR-AP-007 | Exception Escalation | P1 | AP | Week 2 |
| FR-AP-008 | Manual Review UI | P2 | AP | Week 3 |
| FR-AP-009 | Processing Summary | P1 | AP | Week 3 |
| FR-AP-010 | Reference Data Management (PO/GR) | P1 | AP | Week 2 |
| FR-RAG-001 | Document Ingestion | P1 | RAG | Week 1 |
| FR-RAG-002 | NL Query Interface | P1 | RAG | Week 2 |
| FR-RAG-003 | Source Citation | P1 | RAG | Week 2 |
| FR-RAG-004 | Conversation Context | P2 | RAG | Week 3 |
| FR-RAG-005 | Document Scope Filtering | P2 | RAG | Week 3 |
| FR-RAG-006 | Answer Guardrails | P1 | RAG | Week 2 |
| FR-CROSS-001 | Unified Document Pipeline | P1 | CROSS | Week 2 |
| FR-CROSS-002 | Audit Logging | P2 | CROSS | Week 3 |
| FR-CROSS-003 | API Rate Limiting | P2 | CROSS | Week 3 |
| FR-CROSS-005 | Admin-Configurable Approval Settings | P1 | CROSS | Week 3 |
