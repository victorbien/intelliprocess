# User Stories

## IntelliProcess AI Platform

---

## Story Format

Each user story follows the standard format:

> **As a** [user role], **I want to** [action], **so that** [benefit].

Stories are grouped by epic and tagged with priority and the functional requirement(s) they satisfy.

---

## Epic 1: Platform Access & Authentication

### US-1.1: User Login
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Traces To | FR-SHARED-001, FR-SHARED-002 |

**As a** platform user, **I want to** log in with my credentials, **so that** I can securely access the system features assigned to my role.

### US-1.2: Role-Appropriate Dashboard
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Traces To | FR-SHARED-002 |

**As a** logged-in user, **I want to** see a dashboard tailored to my role, **so that** I can quickly access the functions relevant to my work.

---

## Epic 2: Document Management

### US-2.1: Upload Invoice
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Traces To | FR-SHARED-003, FR-SHARED-004 |

**As an** AP Clerk, **I want to** upload an invoice document (PDF or image), **so that** it can be automatically processed by the system.

### US-2.2: Upload Organizational Document
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Traces To | FR-SHARED-003, FR-RAG-001 |

**As an** Administrator, **I want to** upload organizational records (policies, contracts, procedures), **so that** they become searchable in the Records Assistant.

### US-2.3: View Document Status
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Traces To | FR-SHARED-005 |

**As an** AP Clerk, **I want to** see the current processing status of my uploaded invoices, **so that** I know which ones need attention.

### US-2.4: Upload Validation Feedback
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Traces To | FR-SHARED-003, FR-SHARED-006 |

**As a** user, **I want to** receive clear error messages when my upload fails (wrong format, too large), **so that** I can correct the issue and retry.

---

## Epic 3: Automated Invoice Processing

### US-3.1: Automatic Invoice Extraction
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Traces To | FR-AP-001, FR-AP-002 |

**As an** AP Clerk, **I want** the system to automatically extract key data (vendor, amount, PO number, line items) from my uploaded invoice, **so that** I don't have to manually type this information.

### US-3.2: View Extracted Data
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Traces To | FR-AP-001, FR-AP-002 |

**As an** AP Clerk, **I want to** view the extracted invoice data alongside confidence scores, **so that** I can verify accuracy and identify fields that may need correction.

### US-3.3: Automatic PO Matching
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Traces To | FR-AP-003 |

**As an** AP Clerk, **I want** the system to automatically match my invoice to the corresponding Purchase Order, **so that** I don't have to manually look up and compare PO records.

### US-3.4: Automatic Goods Receipt Verification
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Traces To | FR-AP-004 |

**As an** AP Clerk, **I want** the system to verify that invoiced goods have been received, **so that** we only pay for items we actually received.

### US-3.5: Three-Way Match Result
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Traces To | FR-AP-005 |

**As an** AP Clerk, **I want to** see the result of the three-way match (Invoice <-> PO <-> GR), **so that** I have confidence the invoice is legitimate before it proceeds.

### US-3.6: Automatic Approval of Valid Invoices
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Traces To | FR-AP-006 |

**As a** Finance Manager, **I want** invoices that pass all validation rules to be auto-approved, **so that** low-risk invoices are processed without manual intervention, reducing delays.

### US-3.7: Exception Escalation Notification
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Traces To | FR-AP-007 |

**As an** AP Clerk, **I want to** be notified when an invoice is escalated to me with the specific reason for failure, **so that** I can quickly resolve the issue.

### US-3.8: Manual Invoice Approval
| Attribute | Value |
|-----------|-------|
| Priority | P2 |
| Traces To | FR-AP-008 |

**As a** Finance Manager, **I want to** review escalated invoices with the extracted data displayed alongside the original document, **so that** I can make an informed approve/reject decision.

### US-3.9: Processing Dashboard
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Traces To | FR-AP-009 |

**As a** Finance Manager, **I want to** view summary statistics of invoice processing (approved, escalated, rejected counts), **so that** I can monitor the efficiency of the AP process.

---

## Epic 4: Intelligent Records Search

### US-4.1: Ask a Question
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Traces To | FR-RAG-002 |

**As a** staff member, **I want to** ask a question in natural language about organizational policies or documents, **so that** I get an immediate answer without manually searching through files.

### US-4.2: View Source Citations
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Traces To | FR-RAG-003 |

**As a** staff member, **I want to** see which documents the system used to generate its answer, **so that** I can verify the information and read the original source if needed.

### US-4.3: Follow-Up Questions
| Attribute | Value |
|-----------|-------|
| Priority | P2 |
| Traces To | FR-RAG-004 |

**As a** staff member, **I want to** ask follow-up questions that reference my previous question, **so that** I can drill deeper into a topic without repeating context.

### US-4.4: Filter by Document Category
| Attribute | Value |
|-----------|-------|
| Priority | P2 |
| Traces To | FR-RAG-005 |

**As a** staff member, **I want to** filter my search to a specific document category (e.g., only Policies, only Contracts), **so that** I get more relevant and focused answers.

### US-4.5: Honest Uncertainty
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Traces To | FR-RAG-006 |

**As a** staff member, **I want** the system to clearly tell me when it doesn't have enough information to answer my question, **so that** I am not misled by fabricated answers.

### US-4.6: Search Invoices and POs
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Traces To | FR-CROSS-001 |

**As an** AP Clerk, **I want to** ask the Records Assistant questions about previously processed invoices and purchase orders (e.g., "What was the total from Vendor X last month?"), **so that** I can quickly find financial information without digging through files.

---

## Epic 5: System Administration

### US-5.1: Manage Sample Data
| Attribute | Value |
|-----------|-------|
| Priority | P1 |
| Traces To | FR-SHARED-004 |

**As an** Administrator, **I want to** upload sample Purchase Orders and Goods Receipts into the system, **so that** the three-way matching has reference data to work with.

### US-5.2: Monitor System Health
| Attribute | Value |
|-----------|-------|
| Priority | P2 |
| Traces To | FR-CROSS-002 |

**As an** Administrator, **I want to** view system logs and error counts, **so that** I can identify and troubleshoot issues.

---

## User Story Map (Sprint Allocation)

```
Week 1 (Foundation)          Week 2 (Core AI)              Week 3 (Integration & Polish)
─────────────────────        ────────────────────          ─────────────────────────────
US-1.1 User Login            US-3.3 PO Matching            US-3.8 Manual Review UI
US-1.2 Role Dashboard        US-3.4 GR Verification        US-3.9 Processing Dashboard
US-2.1 Upload Invoice        US-3.5 Three-Way Match        US-4.3 Follow-Up Questions
US-2.2 Upload Records        US-3.6 Auto Approval          US-4.4 Category Filtering
US-2.3 View Status           US-3.7 Escalation             US-5.2 Monitor Health
US-2.4 Upload Validation     US-4.1 Ask Question           End-to-end testing
US-3.1 Auto Extraction       US-4.2 Source Citations        Demo preparation
US-3.2 View Extracted        US-4.5 Honest Uncertainty
US-5.1 Manage Sample Data    US-4.6 Search Invoices/POs
```

---

## Story Point Estimates (Fibonacci)

| Story | Estimate | Rationale |
|-------|----------|-----------|
| US-1.1 | 3 | Cognito setup with hosted UI |
| US-1.2 | 2 | Conditional rendering based on role |
| US-2.1 | 3 | S3 presigned URL upload flow |
| US-2.2 | 3 | Same as invoice upload but different S3 prefix + KB sync |
| US-2.3 | 2 | DynamoDB query + status display |
| US-2.4 | 1 | Frontend validation logic |
| US-3.1 | 8 | BDA integration, Lambda orchestration |
| US-3.2 | 3 | Frontend display with confidence indicators |
| US-3.3 | 5 | Matching logic with fuzzy comparison |
| US-3.4 | 5 | GR lookup and quantity comparison |
| US-3.5 | 3 | Combines US-3.3 and US-3.4 results |
| US-3.6 | 3 | Rule engine evaluation |
| US-3.7 | 3 | Status update + reason recording |
| US-3.8 | 5 | Side-by-side UI with edit capability |
| US-3.9 | 3 | Aggregation query + chart display |
| US-4.1 | 5 | Bedrock KB RetrieveAndGenerate integration |
| US-4.2 | 3 | Parse and display citation metadata |
| US-4.3 | 3 | Session history management |
| US-4.4 | 2 | Metadata filter on retrieval call |
| US-4.5 | 2 | Prompt engineering + guardrails config |
| US-4.6 | 2 | Depends on FR-CROSS-001 pipeline |
| US-5.1 | 2 | Bulk upload script/UI for PO/GR data |
| US-5.2 | 2 | CloudWatch dashboard or simple log viewer |
| **Total** | **72** | ~24 pts/week across team |
