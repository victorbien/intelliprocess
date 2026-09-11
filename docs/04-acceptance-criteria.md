# Acceptance Criteria

## IntelliProcess AI Platform

---

## Format

Each acceptance criterion follows the **Given-When-Then** (GWT) format:

> **Given** [precondition], **When** [action], **Then** [expected outcome].

Criteria are grouped by user story and each criterion has a unique ID for test traceability.

---

## Epic 1: Platform Access & Authentication

### US-1.1: User Login

| AC ID | Criterion |
|-------|-----------|
| AC-1.1.1 | **Given** a registered user with valid credentials, **When** they submit their username and password on the login page, **Then** they are authenticated and redirected to their role-appropriate dashboard within 3 seconds. |
| AC-1.1.2 | **Given** a user with invalid credentials, **When** they attempt to log in, **Then** the system displays a generic "Invalid credentials" error without revealing which field is incorrect. |
| AC-1.1.3 | **Given** an unauthenticated user, **When** they attempt to access any protected route, **Then** they are redirected to the login page. |
| AC-1.1.4 | **Given** an authenticated session, **When** the session token expires (1 hour), **Then** the user is prompted to re-authenticate. |

### US-1.2: Role-Appropriate Dashboard

| AC ID | Criterion |
|-------|-----------|
| AC-1.2.1 | **Given** a user with role AP_CLERK, **When** they log in, **Then** they see the Invoice Processing dashboard with upload, status list, and escalation queue. |
| AC-1.2.2 | **Given** a user with role FINANCE_MANAGER, **When** they log in, **Then** they see the Invoice Processing dashboard with summary statistics and pending approvals. |
| AC-1.2.3 | **Given** a user with role STAFF, **When** they log in, **Then** they see the Records Assistant chat interface as their primary view. |
| AC-1.2.4 | **Given** a user with role ADMIN, **When** they log in, **Then** they see all platform sections including document management and system configuration. |

---

## Epic 2: Document Management

### US-2.1: Upload Invoice

| AC ID | Criterion |
|-------|-----------|
| AC-2.1.1 | **Given** an AP Clerk on the invoice upload page, **When** they select a valid PDF file (< 10MB) and click upload, **Then** the file is stored in S3 and a confirmation message is displayed with a processing status of "UPLOADED". |
| AC-2.1.2 | **Given** an AP Clerk, **When** they upload a file exceeding 10MB, **Then** the upload is rejected with the message "File size exceeds the 10MB limit." |
| AC-2.1.3 | **Given** an AP Clerk, **When** they upload a file with an unsupported format (e.g., .xlsx), **Then** the upload is rejected with the message "Unsupported file format. Please upload PDF, PNG, or JPEG." |
| AC-2.1.4 | **Given** a successful upload, **When** the file is stored, **Then** metadata is recorded in DynamoDB with: documentId, fileName, uploadTimestamp, uploaderId, documentType="INVOICE", status="UPLOADED". |
| AC-2.1.5 | **Given** an AP Clerk, **When** they drag and drop a valid file onto the upload area, **Then** the same upload flow is triggered as clicking the upload button. |

### US-2.2: Upload Organizational Document

| AC ID | Criterion |
|-------|-----------|
| AC-2.2.1 | **Given** an Administrator on the records management page, **When** they upload a supported document (PDF, DOCX, TXT), **Then** the file is stored in S3 under the `records/` prefix and queued for knowledge base ingestion. |
| AC-2.2.2 | **Given** a successful document upload, **When** the knowledge base sync completes, **Then** the document content is searchable via the Records Assistant within 5 minutes. |
| AC-2.2.3 | **Given** an Administrator, **When** they upload a document, **Then** they can assign a category (Policy, Contract, Finance, Procurement, General). |

### US-2.3: View Document Status

| AC ID | Criterion |
|-------|-----------|
| AC-2.3.1 | **Given** an AP Clerk with uploaded invoices, **When** they view the invoice list, **Then** each invoice shows: file name, upload date, current status, and a status color indicator (green=approved, yellow=processing, red=error, orange=escalated). |
| AC-2.3.2 | **Given** an invoice with status "PROCESSING", **When** the AP Clerk refreshes the page, **Then** the status reflects the latest state (e.g., "EXTRACTED", "MATCHED"). |
| AC-2.3.3 | **Given** multiple invoices, **When** the AP Clerk views the list, **Then** invoices are sorted by upload date (most recent first) by default. |

### US-2.4: Upload Validation Feedback

| AC ID | Criterion |
|-------|-----------|
| AC-2.4.1 | **Given** a user attempting upload, **When** they select no file and click upload, **Then** the system displays "Please select a file to upload." |
| AC-2.4.2 | **Given** a network failure during upload, **When** the upload request fails, **Then** the system displays "Upload failed. Please check your connection and try again." |

### US-2.4 (continued): Error Handling Coverage

| AC ID | Criterion |
|-------|-----------|
| AC-2.4.3 | **Given** any API endpoint, **When** an unexpected server error occurs, **Then** the API returns HTTP 500 with a JSON body `{"error": "An internal error occurred. Please try again."}` and does not expose stack traces or internal details. |
| AC-2.4.4 | **Given** any API error response, **When** the error is logged in CloudWatch, **Then** the log entry includes a correlation ID that matches the `X-Correlation-Id` header returned to the client. |

---

## Epic 3: Automated Invoice Processing

### US-3.1: Automatic Invoice Extraction

| AC ID | Criterion |
|-------|-----------|
| AC-3.1.1 | **Given** an invoice with status "UPLOADED", **When** the extraction process runs, **Then** the system extracts: vendor name, invoice number, invoice date, due date, PO reference, line items, subtotal, tax, and total amount. |
| AC-3.1.2 | **Given** a well-formatted invoice, **When** extraction completes, **Then** at least 90% of extracted fields have confidence scores ≥ 0.85. |
| AC-3.1.3 | **Given** extraction completion, **When** results are stored, **Then** the invoice status transitions from "UPLOADED" to "EXTRACTED" and the extracted JSON is persisted. |
| AC-3.1.4 | **Given** extraction failure (corrupt file, unreadable), **When** BDA returns an error, **Then** the invoice status is set to "ERROR" with an error description logged. |
| AC-3.1.5 | **Given** an invoice is uploaded, **When** the extraction process initiates, **Then** it completes within 30 seconds. |

### US-3.2: View Extracted Data

| AC ID | Criterion |
|-------|-----------|
| AC-3.2.1 | **Given** an invoice with status "EXTRACTED" or later, **When** the AP Clerk clicks on the invoice, **Then** they see all extracted fields in a structured form layout. |
| AC-3.2.2 | **Given** extracted data is displayed, **When** a field has confidence < 0.85, **Then** that field is visually highlighted (amber background) with the confidence percentage shown. |
| AC-3.2.3 | **Given** extracted data is displayed, **When** the AP Clerk views the page, **Then** a thumbnail or preview of the original document is shown alongside the extracted data. |

### US-3.3: Automatic PO Matching

| AC ID | Criterion |
|-------|-----------|
| AC-3.3.1 | **Given** an extracted invoice with a PO reference number, **When** matching runs, **Then** the system finds the PO with that exact number and returns MATCHED if vendor and amount align (within the configured PO amount tolerance, default 5%). |
| AC-3.3.2 | **Given** an extracted invoice without a PO reference, **When** matching runs, **Then** the system attempts fuzzy matching by vendor name + approximate amount and returns PARTIAL_MATCH or NO_MATCH. |
| AC-3.3.3 | **Given** the invoice PO number does not exist in the system, **When** matching runs, **Then** the result is NO_MATCH with reason "PO not found". |
| AC-3.3.4 | **Given** a PO match with amount variance greater than the configured PO amount tolerance (default 5%), **When** matching runs, **Then** the result is PARTIAL_MATCH with the specific discrepancy amount noted. |

### US-3.4: Automatic Goods Receipt Verification

| AC ID | Criterion |
|-------|-----------|
| AC-3.4.1 | **Given** a matched PO, **When** GR verification runs, **Then** the system checks if a Goods Receipt exists for that PO number. |
| AC-3.4.2 | **Given** a GR exists, **When** quantity verification runs, **Then** invoiced quantity ≤ received quantity + the configured GR quantity tolerance (default 2%) results in CONFIRMED. |
| AC-3.4.3 | **Given** invoiced quantity exceeds received quantity by more than the configured GR quantity tolerance (default 2%), **When** verification runs, **Then** the result is PARTIAL with the over-invoiced amount noted. |
| AC-3.4.4 | **Given** no GR exists for the matched PO, **When** verification runs, **Then** the result is NOT_RECEIVED. |

### US-3.5: Three-Way Match Result

| AC ID | Criterion |
|-------|-----------|
| AC-3.5.1 | **Given** PO match = MATCHED and GR verification = CONFIRMED, **When** three-way match evaluates, **Then** result is THREE_WAY_MATCH_PASS. |
| AC-3.5.2 | **Given** any match component fails, **When** three-way match evaluates, **Then** result is THREE_WAY_MATCH_FAIL with a list of specific discrepancies. |
| AC-3.5.3 | **Given** three-way match completes, **When** results are stored, **Then** the match details (PO result, GR result, discrepancies) are persisted in the invoice record. If the match passes, processing continues to rule evaluation. If the match fails, the invoice is escalated directly from "EXTRACTED" to "ESCALATED". |

### US-3.6: Automatic Approval of Valid Invoices

| AC ID | Criterion |
|-------|-----------|
| AC-3.6.1 | **Given** an invoice where: three-way match = PASS, amount ≤ the amount threshold (default $10,000), and overall extraction confidence ≥ the confidence threshold (default 0.85), **When** approval rules evaluate, **Then** the invoice is auto-approved with status "APPROVED", approver="SYSTEM", and timestamp recorded. (Vendor membership is no longer evaluated — former RULE-004 removed. Thresholds are admin-configurable.) |
| AC-3.6.2 | **Given** an invoice that meets all criteria except amount > $10,000, **When** approval rules evaluate, **Then** the invoice is NOT auto-approved and is escalated. |
| AC-3.6.3 | **Given** an auto-approved invoice, **When** the AP Clerk views it, **Then** it shows "Auto-Approved" badge with the timestamp. |

### US-3.7: Exception Escalation Notification

| AC ID | Criterion |
|-------|-----------|
| AC-3.7.1 | **Given** an invoice fails auto-approval due to amount > $10,000, **When** escalation runs, **Then** it is assigned to FINANCE_MANAGER role with reason "Amount exceeds auto-approval threshold ($10,000)." |
| AC-3.7.2 | **Given** an invoice fails due to match failure, **When** escalation runs, **Then** it is assigned to AP_CLERK role with specific match discrepancy details. |
| AC-3.7.3 | **Given** an invoice fails due to low confidence score, **When** escalation runs, **Then** it is assigned to AP_CLERK with the specific low-confidence fields listed. |
| AC-3.7.4 | **Given** an escalated invoice, **When** it appears in the assignee's queue, **Then** it displays the escalation reason prominently. |

### US-3.8: Manual Invoice Approval (P2)

| AC ID | Criterion |
|-------|-----------|
| AC-3.8.1 | **Given** a Finance Manager viewing an escalated invoice, **When** they click "Review", **Then** they see the original document and extracted data side by side. |
| AC-3.8.2 | **Given** a Finance Manager on the review screen, **When** they click "Approve" with a mandatory comment, **Then** the invoice status changes to "APPROVED" with their user ID and comment recorded. |
| AC-3.8.3 | **Given** a Finance Manager on the review screen, **When** they click "Reject" with a mandatory reason, **Then** the invoice status changes to "REJECTED" with their user ID and reason recorded. |

### US-3.9: Processing Dashboard

| AC ID | Criterion |
|-------|-----------|
| AC-3.9.1 | **Given** a Finance Manager on the dashboard, **When** the page loads, **Then** they see: total invoices processed, count auto-approved, count escalated, count rejected, and count pending. |
| AC-3.9.2 | **Given** the dashboard, **When** data is displayed, **Then** counts reflect the current state of all invoices in the system (not real-time, refreshed on page load). |

---

## Epic 4: Intelligent Records Search

### US-4.1: Ask a Question

| AC ID | Criterion |
|-------|-----------|
| AC-4.1.1 | **Given** a staff member in the chat interface, **When** they type a question (e.g., "What is the travel reimbursement policy?") and press send, **Then** they receive a natural language answer within 10 seconds. |
| AC-4.1.2 | **Given** a question is submitted, **When** relevant documents exist in the knowledge base, **Then** the answer is synthesized from those documents (not fabricated). |
| AC-4.1.3 | **Given** a question is submitted, **When** the response is generated, **Then** it is displayed in a readable chat bubble format with markdown rendering. |
| AC-4.1.4 | **Given** an empty question, **When** the user clicks send, **Then** the system displays "Please enter a question." and does not make an API call. |

### US-4.2: View Source Citations

| AC ID | Criterion |
|-------|-----------|
| AC-4.2.1 | **Given** an answer is displayed, **When** the user views it, **Then** citations are shown below the answer with: document name, page number (if available), and a relevance indicator. |
| AC-4.2.2 | **Given** citations are displayed, **When** the user clicks on a citation, **Then** they can view or download the source document. |
| AC-4.2.3 | **Given** an answer, **When** citations are present, **Then** at least one citation is provided for every factual claim. |

### US-4.3: Follow-Up Questions (P2)

| AC ID | Criterion |
|-------|-----------|
| AC-4.3.1 | **Given** a previous question and answer in the session, **When** the user asks a follow-up (e.g., "What about international travel?"), **Then** the system uses the previous context to provide a relevant answer. |
| AC-4.3.2 | **Given** a conversation with 5+ messages, **When** the user asks another question, **Then** the system uses the last 5 messages as context (older messages are dropped). |
| AC-4.3.3 | **Given** an active conversation, **When** the user clicks "New Conversation", **Then** the context is cleared and subsequent questions are treated independently. |

### US-4.4: Filter by Document Category (P2)

| AC ID | Criterion |
|-------|-----------|
| AC-4.4.1 | **Given** the chat interface, **When** the user selects "Policies" from the category dropdown before asking, **Then** the search only retrieves from documents categorized as policies. |
| AC-4.4.2 | **Given** no category filter selected, **When** the user asks a question, **Then** all document categories are searched (default behavior). |

### US-4.5: Honest Uncertainty

| AC ID | Criterion |
|-------|-----------|
| AC-4.5.1 | **Given** a question with no relevant documents in the knowledge base, **When** the system responds, **Then** it states "I don't have enough information in the available records to answer this question" rather than generating a speculative answer. |
| AC-4.5.2 | **Given** a question outside the organizational scope (e.g., "What's the weather?"), **When** the system responds, **Then** it politely declines with "I can only answer questions about organizational records and documents." |
| AC-4.5.3 | **Given** a question with low-confidence retrieval results, **When** the system responds, **Then** it qualifies its answer with appropriate hedging (e.g., "Based on limited information I found..."). |

### US-4.6: Search Invoices and POs

| AC ID | Criterion |
|-------|-----------|
| AC-4.6.1 | **Given** processed invoices exist in the knowledge base, **When** an AP Clerk asks "What invoices did we receive from Acme Corp?", **Then** the system returns relevant invoice information with citations to the source documents. |
| AC-4.6.2 | **Given** the unified pipeline is active, **When** a new invoice is processed and a KB sync is triggered (manually or scheduled), **Then** the invoice's extracted data becomes searchable via the Records Assistant. Sync is manual for MVP; not automatic on each upload. |

---

## Epic 5: System Administration

### US-5.1: Manage Sample Data

| AC ID | Criterion |
|-------|-----------|
| AC-5.1.1 | **Given** an Administrator, **When** they submit structured PO data via POST /purchase-orders/upload, **Then** it is stored in DynamoDB and available for invoice matching. |
| AC-5.1.2 | **Given** an Administrator, **When** they submit a Goods Receipt via POST /goods-receipts/upload, **Then** it is linked to an existing PO (rejected with 400 if the PO does not exist) and available for three-way matching. |
| AC-5.1.5 | **Given** an Administrator, **When** they upload a PO/GR document via POST /purchase-orders/extract or /goods-receipts/extract, **Then** candidate fields are extracted (via BDA), returned without being persisted, and pre-filled into an editable form for the admin to confirm and save. |
| AC-5.1.6 | **Given** an extraction that does not complete within the synchronous window (~18s), **When** the extract endpoint responds, **Then** it returns 202 with a jobId, and the client polls the corresponding /extract/status endpoint until it returns the fields (200) or an error (422). |
| AC-5.1.7 | **Given** a PO/GR document upload or extraction is in progress, **When** the admin views the form, **Then** the form fields and Save button are disabled and no additional file can be uploaded until it completes. |
| AC-5.1.3 | **Given** sample data is uploaded, **When** a new invoice references that PO, **Then** the matching logic can find and compare against it. |
| AC-5.1.4 | **Given** an Administrator, **When** they call POST /admin/seed-data, **Then** sample Purchase Orders and Goods Receipts are loaded into DynamoDB and a success message is returned with the counts created. |

### US-5.2: Monitor System Health (P2)

| AC ID | Criterion |
|-------|-----------|
| AC-5.2.1 | **Given** an Administrator, **When** they navigate to the system health page, **Then** they see: recent error count, API call volume, and average response times. |
| AC-5.2.2 | **Given** a Lambda function error occurs, **When** the Administrator checks logs, **Then** the error details are available in CloudWatch with correlation IDs. |

### US-5.3: Configure Approval Settings

| AC ID | Criterion |
|-------|-----------|
| AC-5.3.1 | **Given** an Administrator, **When** they call GET /admin/settings, **Then** the current approval thresholds are returned (amountThreshold, confidenceThreshold, poAmountTolerance, grQtyTolerance), falling back to built-in defaults if none saved. |
| AC-5.3.2 | **Given** an Administrator, **When** they submit valid values via PUT /admin/settings, **Then** the settings are persisted to the AppConfig table and echoed back. |
| AC-5.3.3 | **Given** a value outside its allowed range (confidence/tolerances 0–1, amount ≥ 0), **When** PUT /admin/settings is called, **Then** the request is rejected with 400. |
| AC-5.3.4 | **Given** updated settings, **When** the next invoice is processed, **Then** the pipeline applies the new thresholds/tolerances to matching and approval. |
| AC-5.3.5 | **Given** a non-ADMIN user, **When** they call /admin/settings, **Then** the request is rejected with 403. |

---

## Acceptance Criteria Summary

| Epic | Stories | Total AC | P1 AC | P2 AC |
|------|---------|----------|-------|-------|
| 1. Platform Access | 2 | 8 | 8 | 0 |
| 2. Document Management | 4 | 14 | 12 | 2 |
| 3. Invoice Processing | 7 | 26 | 20 | 6 |
| 4. Records Search | 6 | 16 | 10 | 6 |
| 5. Administration | 3 | 14 | 12 | 2 |
| **Total** | **22** | **78** | **62** | **16** |

---

## Definition of Done (Global)

An individual user story is considered **Done** when:

1. All P1 acceptance criteria pass
2. Code is committed to the main branch
3. No critical or high-severity bugs remain
4. API endpoint (if applicable) returns correct responses for happy path and primary error cases
5. CloudWatch logging is in place for the feature
6. Basic input validation is implemented
7. Feature is demonstrable in the web UI (if user-facing)
