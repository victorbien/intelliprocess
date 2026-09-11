# User Documentation

## IntelliProcess AI Platform

### Intelligent Accounts Payable & Records Search Assistant

---

## 1. Getting Started

### 1.1 What is IntelliProcess AI?

IntelliProcess AI is an enterprise platform that combines two AI-powered capabilities:

1. **AP Invoice Agent** - Automatically processes vendor invoices by extracting data, matching against Purchase Orders and Goods Receipts, and making approval decisions
2. **Ask-Your-Records Assistant** - A chat interface that lets you search organizational documents using natural language and get answers with source citations

### 1.2 Accessing the System

1. Open the application URL in your web browser (Chrome, Firefox, or Edge recommended)
2. Click "Sign In" to access the login page
3. Enter your email address and password
4. You will be redirected to your role-specific dashboard

### 1.3 User Roles

| Role | Access | Description |
|------|--------|-------------|
| AP Clerk | Invoice upload, status view, Records search | Processes invoices daily |
| Finance Manager | All AP Clerk access + approvals, dashboard | Reviews escalated invoices |
| Staff | Records search only | General document queries |
| Administrator | Full access + document management | System configuration |

### 1.4 First-Time Login

When you receive your initial credentials:
1. Enter the temporary password provided by your administrator
2. You will be prompted to set a new password
3. Password requirements: minimum 8 characters, one uppercase, one lowercase, one number

---

## 2. AP Invoice Processing

### 2.1 Uploading an Invoice

**Who can do this:** AP Clerk, Finance Manager, Administrator

**Steps:**
1. Navigate to **Invoices** in the top navigation
2. Click the **Upload Invoice** button (or drag and drop a file)
3. Select your invoice file (PDF, PNG, or JPEG format, max 10MB)
4. Click **Upload**
5. You will see a confirmation with the document ID and status "Uploaded"

**Supported formats:**
- PDF documents (recommended)
- Scanned images (PNG, JPEG)

**Tips:**
- Ensure the invoice is clear and readable
- For best results, upload the original PDF rather than a scanned copy
- Multi-page PDFs are supported

### 2.2 Understanding Invoice Status

After upload, your invoice progresses through these stages:

| Status | Color | Meaning |
|--------|-------|---------|
| Uploaded | Blue | File received, waiting for processing |
| Processing | Yellow | AI is extracting data from the invoice |
| Extracted | Yellow | Data extracted, matching and rules in progress |
| Approved | Green | Invoice approved for payment |
| Escalated | Orange | Requires manual review |
| Rejected | Red | Invoice rejected by reviewer |
| Error | Red | Processing failed (contact admin) |

### 2.3 Viewing Extracted Data

1. Navigate to **Invoices** to see your invoice list
2. Click on any invoice to see its detail page
3. The detail page shows:
   - **Extracted Fields** - Vendor, invoice number, dates, line items, amounts
   - **Confidence Scores** - How confident the AI is about each field (0-100%)
   - **Match Results** - PO match, Goods Receipt verification, three-way match
   - **Decision** - Approved, escalated, or pending

**Understanding Confidence Scores:**
- Green (85-100%): High confidence, likely correct
- Amber (70-84%): Medium confidence, may need verification
- Red (below 70%): Low confidence, manual review recommended

### 2.4 Automatic Approval

Invoices are automatically approved when ALL of these conditions are met:
- Three-way match passes (Invoice ↔ PO ↔ Goods Receipt align)
- Invoice amount is at or below the amount threshold (default $10,000)
- Overall extraction confidence is at or above the confidence threshold (default 85%)

If any condition fails, the invoice is escalated for manual review.

> The amount and confidence thresholds (and the PO/GR match tolerances) are
> configurable by an administrator on the **Approval Settings** screen — see
> section 5.4. Vendor membership is **not** an auto-approval condition.

### 2.5 Escalation Reasons

| Reason | Escalated To | What To Do |
|--------|-------------|-----------|
| Amount exceeds the amount threshold (default $10,000) | Finance Manager | Manager reviews and approves/rejects |
| Three-way match failed | AP Clerk | Verify PO/GR data, resolve discrepancy |
| Low confidence extraction | AP Clerk | Check extracted data against original |

### 2.6 Manual Approval (Finance Manager)

**Who can do this:** Finance Manager, Administrator

1. Navigate to **Invoices** and filter by status "Escalated"
2. Click on an escalated invoice
3. Review the extracted data alongside the original document
4. Verify the escalation reason shown at the top
5. Click **Approve** or **Reject**
6. Enter a mandatory comment explaining your decision
7. Click **Confirm**

---

## 3. Ask-Your-Records Assistant

### 3.1 Asking a Question

**Who can do this:** All authenticated users

1. Navigate to **Records Assistant** in the top navigation
2. Type your question in the text box at the bottom
3. Press Enter or click the Send button
4. Wait for the AI to generate a response (usually 3-8 seconds)
5. Read the answer and review the source citations below it

**Example questions:**
- "What is the travel reimbursement limit for international trips?"
- "Who approves purchase orders over $5,000?"
- "What are the payment terms for Acme Office Supplies?"
- "Summarize the remote work policy"
- "What invoices did we receive from TechParts last month?"

### 3.2 Understanding Answers

Each response from the assistant includes:
- **Answer** - A natural language response synthesized from your documents
- **Citations** - The source documents used, with document name and page number
- **Relevance Score** - How relevant each source is to your question

**Important:** The assistant only answers based on documents in the system. If it cannot find relevant information, it will tell you rather than guessing.

### 3.3 Using Citations

Citations appear below each answer:
- Click on a citation to view or download the source document
- Each citation shows the document name and page number
- Use citations to verify the information or read the full context

### 3.4 Follow-Up Questions

You can ask follow-up questions that reference previous answers:
- "Tell me more about that"
- "What about international travel?"
- "Who is responsible for approving those?"

The assistant remembers the last 5 messages in your conversation.

To start a fresh conversation (clear context), click the **New Conversation** button.

### 3.5 Filtering by Category

To narrow your search to specific document types:
1. Click the **Category** dropdown above the chat input
2. Select a category: Policies, Contracts, Finance, Procurement, or All
3. Ask your question — results will only come from that category

### 3.6 What the Assistant Cannot Do

The Records Assistant is designed for organizational documents only:
- It will NOT answer general knowledge questions
- It will NOT provide personal opinions or advice
- It will NOT fabricate answers — if it doesn't know, it says so
- It CANNOT access the internet or external systems

If you get a response like "I can only answer questions about organizational records," try rephrasing your question to focus on company documents.

---

## 4. Dashboard (Finance Manager / Admin)

### 4.1 Processing Statistics

The dashboard shows:
- **Total Invoices** - All invoices in the system
- **Auto-Approved** - Invoices approved automatically by the AI
- **Escalated** - Invoices requiring manual review
- **Rejected** - Invoices that were rejected
- **Pending** - Invoices currently being processed
- **Auto-Approval Rate** - Percentage approved without human intervention
- **Avg Processing Time** - Average seconds from upload to decision

### 4.2 Recent Activity

The bottom section shows the most recent actions:
- Which invoices were processed
- Who approved or rejected invoices
- Any errors that occurred

---

## 5. Administration

### 5.1 Uploading Organizational Documents

**Who can do this:** Administrator

1. Navigate to **Admin > Documents**
2. Click **Upload Document**
3. Select the file (PDF, DOCX, or TXT)
4. Choose a category (Policy, Contract, Finance, Procurement, General)
5. Add an optional description
6. Click **Upload**
7. Click **Sync Knowledge Base** to make the document searchable

**Note:** After uploading new documents, it takes up to 5 minutes for them to become searchable in the Records Assistant.

### 5.2 Loading Sample Data

For demo purposes:
1. Navigate to **Admin > Seed Data**
2. Click **Load Default Data**
3. This creates sample Purchase Orders and Goods Receipts for testing

### 5.3 Managing Users

User management is handled through the AWS Cognito console:
- Contact your system administrator to create new users
- Users are assigned to groups: AP_CLERK, FINANCE_MANAGER, STAFF, or ADMIN

### 5.4 Approval Settings

**Who can do this:** Administrator

The auto-approval thresholds and three-way match tolerances used by the AP
Invoice Agent are configurable, so you can tune approval behaviour without a
code change.

1. Navigate to **Admin > Settings**.
2. Adjust any of the following and click **Save**:

| Setting | Meaning | Default |
|---------|---------|---------|
| Amount threshold | Invoices at or below this amount can auto-approve | $10,000 |
| Confidence threshold | Minimum overall extraction confidence to auto-approve | 0.85 (85%) |
| PO amount tolerance | Allowed margin when matching invoice amount to the PO (0 = exact) | 0.05 (5%) |
| GR quantity tolerance | Allowed margin when matching quantities to the Goods Receipt (0 = exact) | 0.02 (2%) |

New settings apply to invoices processed after they are saved. Existing
decisions are not re-evaluated.

### 5.5 Adding Purchase Orders and Goods Receipts

**Who can do this:** Administrator

Purchase Orders and Goods Receipts are the reference records the AP Invoice
Agent matches invoices against. Besides loading sample data (section 5.2), you
can add them from documents:

1. Navigate to **Admin > Purchase Orders** (or **Goods Receipts**).
2. Upload a PO or GR document (PDF, PNG, or JPEG).
3. The system extracts the fields for you to review. Extraction usually
   completes within a few seconds; for larger documents it continues in the
   background and the screen updates when it is ready.
4. While an upload and extraction is in progress, the upload controls are
   disabled so a second file cannot be submitted until the current one
   finishes.
5. Review the extracted fields, correct anything if needed, and save the
   record.

---

## 6. Troubleshooting

### 6.1 Common Issues

| Problem | Solution |
|---------|----------|
| Cannot log in | Check email/password. Use "Forgot Password" if needed. |
| Upload fails | Check file format (PDF/PNG/JPEG) and size (< 10MB) |
| Invoice stuck on "Processing" | Wait up to 30 seconds. If still stuck after 2 minutes, contact admin. |
| Chat returns no answer | Rephrase your question. The information may not be in the system. |
| "Session expired" message | Log in again — sessions expire after 1 hour |
| Slow responses | AI queries take 3-10 seconds. This is normal. |
| Extraction looks wrong | Low confidence fields are highlighted — report to admin |

### 6.2 Error Messages

| Error | Meaning | Action |
|-------|---------|--------|
| "File size exceeds limit" | File > 10MB | Compress or split the file |
| "Unsupported format" | Wrong file type | Use PDF, PNG, or JPEG |
| "Insufficient permissions" | Wrong role | Contact admin for role change |
| "Service temporarily unavailable" | AWS service issue | Wait a few minutes and retry |
| "Request timed out" | AI took too long | Retry the operation |

### 6.3 Getting Help

For technical issues:
- Check this documentation first
- Contact your system administrator
- Provide the document ID or error message when reporting issues

---

## 7. FAQ

**Q: How accurate is the AI extraction?**
A: For well-formatted PDF invoices, accuracy is typically above 90%. Scanned or handwritten documents may have lower accuracy, which is reflected in the confidence scores.

**Q: Can I edit extracted data?**
A: In the current version, extracted data is read-only. If data is incorrect, escalate the invoice for manual review.

**Q: How long does invoice processing take?**
A: Typical processing time is 20-30 seconds from upload to decision.

**Q: What documents can the Records Assistant search?**
A: All documents uploaded to the system — policies, contracts, invoices, purchase orders, and other organizational records.

**Q: Is my data secure?**
A: Yes. All data is encrypted at rest and in transit. Access is controlled by your user role. Documents are stored in secure AWS infrastructure.

**Q: Can I delete an uploaded invoice?**
A: In the current version, deletion is not available through the UI. Contact your administrator.

**Q: How many invoices can I upload at once?**
A: Currently, invoices are uploaded one at a time. Batch upload is planned for a future release.

**Q: Can the Records Assistant see emails or Teams messages?**
A: No. It only searches documents explicitly uploaded to the system.

---

## 8. Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Enter | Send chat message |
| Shift + Enter | New line in chat input |
| Ctrl + K | Focus search/chat input |
| Escape | Close modal/detail view |

---

## 9. Browser Support

| Browser | Supported | Notes |
|---------|-----------|-------|
| Chrome 90+ | Yes | Recommended |
| Firefox 90+ | Yes | Full support |
| Edge 90+ | Yes | Full support |
| Safari 15+ | Yes | Minor styling differences |
| Internet Explorer | No | Not supported |

---

## 10. Glossary

| Term | Definition |
|------|-----------|
| AP | Accounts Payable — the department that processes vendor invoices |
| PO | Purchase Order — an official document requesting goods/services |
| GR | Goods Receipt — confirmation that ordered items were received |
| Three-Way Match | Verification that Invoice, PO, and GR all agree |
| RAG | Retrieval Augmented Generation — AI technique for answering questions from documents |
| BDA | Bedrock Data Automation — AWS service for extracting data from documents |
| Escalation | Routing an invoice to a human reviewer when auto-approval rules fail |
| Knowledge Base | The indexed collection of documents searchable by the assistant |
| Citation | A reference to the source document used to generate an answer |
| Confidence Score | How certain the AI is about an extracted field (0-100%) |
