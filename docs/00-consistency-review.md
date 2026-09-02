# Consistency Review Report

## IntelliProcess AI Platform

### Cross-Document Analysis & Resolutions

---

## Summary of Findings

After reviewing all 16 specification documents, the following issues were identified and resolved:

| Category | Count | Severity |
|----------|-------|----------|
| Conflicting Requirements | 4 | High |
| Duplicated Functionality | 2 | Medium |
| Missing Acceptance Criteria | 3 | High |
| Missing Implementation Tasks | 2 | Medium |
| Inconsistencies Between Requirements & Design | 5 | High |
| Unrealistic Scope for 3 Weeks | 3 | High |
| Simplification Opportunities | 4 | Medium |

---

## 1. Conflicting Requirements

### C1: AgentCore vs Direct Calls — Contradictory Primary Approach

**Conflict:** 
- Technical Design (Section 3.3) says InvoiceProcessor uses `invoke_ap_agent()` via AgentCore
- AI Agent Design (Section 4) recommends "Start with direct Bedrock KB calls (simpler). Add AgentCore if time permits"
- Implementation Roadmap Day 7 schedules direct `rules.py` function calls (no agent invocation)

**Resolution:** Standardize on **direct function calls** (no AgentCore) as the primary MVP approach. AgentCore is deferred to post-MVP. This removes a significant complexity and risk factor.

**Documents Updated:** Technical Design, AI Agent Design, Implementation Roadmap

---

### C2: Status Transition — EXTRACTED vs MATCHED on Match Failure

**Conflict:**
- Acceptance Criteria AC-3.5.3 says: "status transitions to MATCHED (pass) or remains at EXTRACTED with match failure reason (fail)"
- Component Design status state machine shows: EXTRACTED → ESCALATED (directly, on match failure)
- Functional Requirement FR-SHARED-005 lists MATCHED as a valid status

**Resolution:** Clarify that MATCHED is only set on THREE_WAY_MATCH_PASS. On match failure, the invoice goes directly from EXTRACTED → ESCALATED. The status MATCHED means "ready for rule evaluation" and is a transient state before APPROVED.

**Documents Updated:** Acceptance Criteria (AC-3.5.3), Functional Requirements (FR-SHARED-005 note)

---

### C3: Approval Rule — "Confidence ≥ 0.85" Scope

**Conflict:**
- FR-AP-006 says "All extraction confidence scores ≥ 0.85"
- AI Agent Design rules.py checks `overall_confidence >= 0.85` (average, not all fields)
- Acceptance Criteria AC-3.6.1 says "all confidence scores ≥ 0.85"

**Resolution:** Use **overall confidence ≥ 0.85** (the average). Checking every individual field is overly strict for MVP and would escalate too many valid invoices. Update AC-3.6.1 to match.

**Documents Updated:** Functional Requirements (FR-AP-006), Acceptance Criteria (AC-3.6.1)

---

### C4: Upload API — documentType Parameter Mismatch

**Conflict:**
- Technical Design UploadRequest validator allows: `['invoices', 'purchase-orders', 'goods-receipts', 'records']`
- API Specification POST /invoices/upload does not include `documentType` in request body (only `fileName` and `contentType`)
- The upload handler needs `documentType` to determine S3 prefix

**Resolution:** The `/invoices/upload` endpoint implicitly sets documentType="invoices". The `/documents/upload` endpoint requires an explicit `category` field. No `documentType` field is exposed to the invoice upload API — it's inferred from the route.

**Documents Updated:** Technical Design (UploadRequest model), API Specification (clarification note)

---

## 2. Duplicated Functionality

### D1: DashboardHandler Overloaded

**Observation:** The DashboardHandler Lambda handles 7 different routes (GET /invoices, GET /invoices/{id}, POST /invoices/{id}/approve, GET /documents, POST /documents/sync, GET /dashboard/stats, POST /admin/seed-data). This is a "god function" — too many responsibilities.

**Resolution:** Accept for MVP (single Lambda with route dispatch is simpler to deploy). Add a routing comment in Technical Design noting this should be split post-MVP. No code change needed — SAM routes all these to one function, and internal routing is handled by a simple path dispatcher.

**Documents Updated:** Technical Design (add note on DashboardHandler routing pattern)

---

### D2: Document Metadata in Two Tables

**Observation:** Invoices have metadata in `IntelliProcess-Invoices` table. Organizational documents have metadata in `IntelliProcess-Documents` table. The upload handler writes to different tables depending on document type. This is correct (different schemas), but the unified pipeline (FR-CROSS-001) means processed invoices should also appear in the Knowledge Base — which reads from S3, not DynamoDB. No actual duplication issue; this is by design.

**Resolution:** No change needed. Clarify in Database Design that the Knowledge Base indexes S3 directly (not DynamoDB), so there's no data duplication concern.

---

## 3. Missing Acceptance Criteria

### M1: No AC for FR-SHARED-006 (Error Handling)

**Gap:** FR-SHARED-006 (Error Handling and User Feedback) has no dedicated acceptance criteria. It's partially covered by AC-2.4.2 (network failure) and AC-3.1.4 (extraction error), but there's no systematic AC for API-level error responses.

**Resolution:** Add AC for error handling: API returns proper error codes, error messages are user-friendly, CloudWatch logs contain correlation IDs.

**Documents Updated:** Acceptance Criteria (new AC-2.4.3, AC-2.4.4)

---

### M2: No AC for FR-CROSS-001 (Unified Pipeline)

**Gap:** The unified pipeline requirement (invoices searchable via Records Assistant) has acceptance criteria only in US-4.6, but no explicit AC for the ingestion mechanism itself — how/when do processed invoices get into the Knowledge Base?

**Resolution:** AC-4.6.2 already states "within 5 minutes" but doesn't specify the mechanism. Add clarification that this depends on a manual KB sync trigger (not automatic for MVP). Downgrade timing expectation.

**Documents Updated:** Acceptance Criteria (AC-4.6.2 updated)

---

### M3: No AC for Admin Seed Data API

**Gap:** The POST /admin/seed-data endpoint exists in the API spec but has no formal acceptance criteria. US-5.1 covers "manage sample data" but the ACs reference document upload, not the seed-data API endpoint.

**Resolution:** Add AC for seed-data endpoint to US-5.1.

**Documents Updated:** Acceptance Criteria (new AC-5.1.4)

---

## 4. Missing Implementation Tasks

### T1: No Task for Bedrock Guardrails Setup

**Gap:** Implementation Roadmap Day 8 mentions "Configure Bedrock Guardrails" as 1 hour for Dev B, but the AWS Service Mapping shows this requires console setup with topic policies and content filters. This is underestimated.

**Resolution:** Keep as 1 hour but note it's console configuration only (not code). Add explicit task description.

**Documents Updated:** Implementation Roadmap (Day 8 task clarified)

---

### T2: No Task for KB Sync After Invoice Processing

**Gap:** FR-CROSS-001 requires processed invoices to be searchable, but no implementation task covers the mechanism. The Roadmap Day 9 says "Connect processed invoices to KB" at 2 hours, but doesn't specify the approach.

**Resolution:** Clarify that this is achieved by the fact that invoices are already stored in S3 under `invoices/` prefix, and the KB data source includes that prefix. A manual KB sync (or the scheduled sync) picks them up. No additional code is needed — just ensure the KB data source config includes `invoices/` prefix. Update Day 9 task description.

**Documents Updated:** Implementation Roadmap (Day 9 task clarified)

---

## 5. Inconsistencies Between Requirements & Design

### I1: SRS Lists "Exception Handling Workflow" as Deferred, But It's Actually P1

**Inconsistency:** SRS Section 2.2 lists "F9: Exception handling workflow" as "Deferred", but FR-AP-007 (Exception Escalation) is P1, and the entire escalation flow is in the MVP.

**Resolution:** The SRS "exception handling workflow" refers to a full multi-step workflow with notifications, reassignment, and SLA tracking — which IS deferred. The basic escalation (status change + reason recording) is MVP. Clarify in SRS.

**Documents Updated:** SRS (F9 description clarified)

---

### I2: Technical Design Env Var Name vs SAM Template

**Inconsistency:** 
- Technical Design Section 6.1 uses: `DOCUMENT_BUCKET: intelliprocess-documents-{stage}`
- SAM Template (Deployment Architecture) uses: `intelliprocess-docs-${Stage}-${AWS::AccountId}`

**Resolution (updated post-implementation):** The deployed template uses a
single fixed bucket name **`intelliprocess-ai-documents`** (with
`DeletionPolicy: Retain`), not the earlier stage/account-suffixed names. All
docs (Technical Design §6.1, Deployment Architecture, Database Design, API
Specification, AWS Service Mapping, System Architecture) have been aligned to
`intelliprocess-ai-documents`.

**Documents Updated:** Technical Design (§6.1), Deployment Architecture,
Database Design, API Specification, AWS Service Mapping, System Architecture

---

### I3: Frontend api.ts — approveInvoice Missing `action` Field

**Inconsistency:**
- API Specification requires `{ "action": "APPROVE" or "REJECT", "comment": "..." }` in POST /invoices/{id}/approve
- Technical Design api.ts shows: `api.post(\`/invoices/${id}/approve\`, { comment })` — missing the `action` field

**Resolution:** Update Technical Design api.ts to include action parameter.

**Documents Updated:** Technical Design (Section 4.2)

---

### I4: RAG Document Formats — Requirements vs Upload Validator

**Inconsistency:**
- FR-RAG-001 lists supported formats: "PDF, DOCX, TXT, MD"
- Technical Design UploadRequest validator only allows: `application/pdf, image/png, image/jpeg, image/tiff`
- API Specification /documents/upload allows: `application/pdf, text/plain, application/vnd.openxmlformats-officedocument.wordprocessingml.document`

**Resolution:** The upload validator should have different allowed types for invoices vs. records. Invoices: PDF/PNG/JPEG/TIFF. Records: PDF/DOCX/TXT. The Technical Design validator code is for invoices only. Add a separate records validator or make it route-aware.

**Documents Updated:** Technical Design (add RecordsUploadRequest model)

---

### I5: Conversation Context — P2 in Requirements but Implemented in Week 2

**Inconsistency:**
- FR-RAG-004 (Conversation Context) is marked P2
- Implementation Roadmap Day 9 schedules "Implement conversation history (DynamoDB)" in Week 2
- This contradicts the cut-list which says conversation history is the first thing to cut

**Resolution:** Move conversation history implementation to Day 11 (Week 3). It's P2 and should be done only after all P1 features are solid. Update the cut-list note.

**Documents Updated:** Implementation Roadmap (moved from Day 9 to Day 11)

---

## 6. Unrealistic Scope for 3 Weeks

### S1: Manual Review UI (Side-by-Side) is P2 But Scheduled in Week 2

**Issue:** The side-by-side document review UI (US-3.8, P2) is scheduled for Day 10. Week 2 should focus on P1 features. This 4-hour task could delay P1 completion.

**Resolution:** Move to Week 3 (Day 11). Replace with a simple approve/reject form (no side-by-side view) if implemented at all.

**Documents Updated:** Implementation Roadmap (Day 10 → Day 11)

---

### S2: Dev D Has No Tasks Days 1-4

**Issue:** The Roadmap assigns Dev D only a 1-hour task on Day 5, and a 2-hour task on Day 5. Days 1-4 show no work for Dev D. This is wasted capacity.

**Resolution:** Reassign Dev D to help with sample data preparation (Days 1-3), create test invoice PDFs earlier (Day 3 instead of Day 5), and begin Chat UI wireframes/mockups (Day 4).

**Documents Updated:** Implementation Roadmap (Days 1-4 Dev D tasks added)

---

### S3: "Custom CloudWatch Metrics" is Over-Engineering for MVP

**Issue:** Technical Design Section 7.2 specifies custom CloudWatch metrics (InvoicesProcessed, ExtractionDuration, ChatResponseTime, MatchResult). This requires additional code in every Lambda for `put_metric_data` calls.

**Resolution:** Downgrade to P2. Standard Lambda metrics (Duration, Errors, Invocations) plus structured log queries are sufficient for MVP. Remove custom metrics from MVP scope; rely on CloudWatch Logs Insights for ad-hoc analysis.

**Documents Updated:** Technical Design (Section 7.2 marked as post-MVP)

---

## 7. Simplification Opportunities

### O1: Remove AgentCore Dependency Entirely from MVP

**Opportunity:** AgentCore adds complexity (agent configuration, tool definitions, response parsing) without meaningful benefit for the MVP. The AP processing is a fixed sequential pipeline, and the Records search is a single `retrieve_and_generate` call.

**Simplification:** Use direct function calls for AP matching/rules, and direct Bedrock KB API for RAG. This saves ~8 hours of agent setup/debugging time.

**Impact:** AI Agent Design document retains both approaches but clearly marks direct calls as the MVP path.

---

### O2: Simplify Status State Machine

**Opportunity:** The status MATCHED is only held for milliseconds between matching and rule evaluation (they happen in the same Lambda invocation). It adds no user-facing value.

**Simplification:** Remove MATCHED as an externally visible status. The pipeline goes: UPLOADED → PROCESSING → EXTRACTED → APPROVED/ESCALATED/ERROR. Matching details are stored as data within the invoice record, not as a separate status.

**Impact:** Reduces status complexity from 8 states to 6. Simplifies frontend StatusBadge logic.

---

### O3: Merge UploadHandler Routes Into DashboardHandler

**Opportunity:** Having a separate UploadHandler Lambda means two Lambda packages to maintain. The upload logic is small (validate + presigned URL + DynamoDB write).

**Decision:** Keep separate for now. The UploadHandler needs S3 write permissions while DashboardHandler only needs read. Merging would over-privilege the combined function. Separation is correct.

---

### O4: Drop TIFF Support

**Opportunity:** TIFF files are rarely used for invoices in modern workflows. Supporting TIFF adds a format that's hard to test and unlikely to be encountered in a demo.

**Simplification:** Support PDF, PNG, JPEG only. Saves edge-case testing time.

**Impact:** Minor — update upload validators and documentation.

---

## 8. Resolution Summary

| # | Finding | Action Taken |
|---|---------|-------------|
| C1 | AgentCore vs Direct Calls | Standardized on direct calls for MVP |
| C2 | Status on match failure | EXTRACTED → ESCALATED (skip MATCHED on failure) |
| C3 | Confidence threshold | Changed to overall confidence (average) |
| C4 | documentType in upload API | Inferred from route, not explicit param |
| D1 | DashboardHandler overloaded | Accepted for MVP, noted for future split |
| D2 | Two metadata tables | By design, no change needed |
| M1 | No AC for error handling | Added AC-2.4.3 and AC-2.4.4 |
| M2 | No AC for unified pipeline mechanism | Updated AC-4.6.2 with sync clarification |
| M3 | No AC for seed-data API | Added AC-5.1.4 |
| T1 | Guardrails task underspecified | Clarified as console configuration |
| T2 | KB sync for invoices | Clarified as S3 prefix inclusion |
| I1 | SRS F9 vs FR-AP-007 | Clarified scope difference |
| I2 | Bucket name mismatch | Standardized on SAM template naming |
| I3 | approveInvoice missing action | Added action param to api.ts |
| I4 | RAG format validator mismatch | Added RecordsUploadRequest |
| I5 | P2 feature in Week 2 schedule | Moved conversation history to Week 3 |
| S1 | P2 review UI in Week 2 | Moved to Week 3 |
| S2 | Dev D idle Days 1-4 | Redistributed tasks |
| S3 | Custom CloudWatch metrics | Downgraded to post-MVP |
| O1 | Remove AgentCore from MVP | Confirmed direct calls as primary |
| O2 | Simplify status machine | Removed MATCHED as visible status |
| O3 | Merge upload handler | Kept separate (correct for security) |
| O4 | Drop TIFF support | Removed TIFF from supported formats |

---

## Documentation Synchronization (post-implementation)

This section records a documentation-only synchronization pass that aligned the
specification set with the implemented system after a round of implementation
changes. No source code was changed as part of this pass.

### Changes reflected

| # | Implementation change | Docs updated |
|---|-----------------------|--------------|
| 1 | Real BDA extraction via the **current API** (`InvokeDataAutomationAsync` + `dataAutomationProfileArn`, `get_data_automation_status` polling) using the **AWS-managed public invoice blueprint** (`bedrock-data-automation-public-invoice`, profile `apac.data-automation-v1`) — no custom blueprint/project | 06, 07, 11, 12, 15, 17-handoff |
| 2 | **Admin-configurable approval settings** stored in a new **`IntelliProcess-AppConfig`** DynamoDB table (singleton `APPROVAL_SETTINGS`; amount/confidence thresholds, PO amount tolerance, GR quantity tolerance); `GET`/`PUT /admin/settings` | 02, 04, 05, 06, 07, 08, 09, 12, 15, 16 |
| 3 | **Approved-vendor rule (RULE-004) removed** — approval now uses RULE-001 (three-way), RULE-002 (amount ≤ threshold), RULE-003 (confidence ≥ threshold); approver `SYSTEM` | 02, 04, 07, 08, 10, 14, 16 |
| 4 | **PO/GR upload-and-extract** endpoints, sync-then-async (`200` fields or `202` + `jobId`; `/status` `200/202/422`) reusing the BDA path | 02, 04, 05, 07, 09, 16, 17-handoff |
| 5 | **CORS preflight fix** — `AddDefaultAuthorizerToCorsPreflight: false` on a REGIONAL API with `BinaryMediaTypes: [multipart/form-data]` | 09, 15 |
| 6 | **API handler/layer packaging** — handler entry `lambda_function.lambda_handler` (FastAPI + Mangum), shared layer `BuildMethod: makefile` | 06, 09, 15 |
| 7 | **S3 key format** and **fixed bucket name** `intelliprocess-ai-documents` (`DeletionPolicy: Retain`); prefixes `invoices/`, `po-uploads/`, `gr-uploads/`, `bda-output/` | 05, 06, 08, 09, 10, 12, 15 |
| 8 | **`USE_MOCKS`** switch in the template (`"false"` for deployed stages) | 06, 07, 15, 17-handoff |
| 9 | **IAM** — InvoiceProcessor `GetItem` on AppConfig + `Scan` on PurchaseOrders; DashboardHandler BDA `Invoke`/`GetStatus`, `s3:PutObject`, AppConfig read/write; DashboardHandler raised to 512 MB / 29 s | 12, 15 |

### Approach and preserved-history notes

- Where the implementation diverged from an earlier design decision, the
  original text was preserved and annotated (marked "original"/"historical" or
  "superseded") rather than deleted — e.g. the **region** (design assumed
  `us-east-1`; **as deployed: `ap-southeast-2`**) in AWS Service Mapping, the
  framework note in Technical Design, and the custom-blueprint BDA prompt in
  Prompt Design (§4).
- The illustrative SAM template excerpt in Deployment Architecture (§2.1) is
  supplemented by a new **§2.2 "Recent Implementation Changes"** that lists the
  exact deltas from the deployed `backend/template.yaml`.

### Remaining known divergences (documentation-level, not introduced here)

- **AgentCore** references (e.g. ADR-005 in System Architecture, "AP Agent"
  wording in Component Design) predate this pass and were **not** rewritten;
  the current agent path is direct Bedrock/Strands as already noted in AI Agent
  Design. These are pre-existing design/implementation divergences, not caused
  by this session's changes.
- The Prompt Design custom-blueprint field list (§4.1) is retained as a
  reference for consumed invoice fields; the public blueprint does not return
  `dueDate`/`paymentTerms` (handled as `None`).
