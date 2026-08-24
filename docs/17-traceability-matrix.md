# Requirements → Implementation → Test Traceability Matrix

## IntelliProcess AI Platform

This matrix links every functional requirement (`docs/02-functional-requirements.md`)
to its acceptance criteria (`docs/04-acceptance-criteria.md`), the backend code that
implements it, and the automated tests that verify it.

**Legend — Verification status**

| Symbol | Meaning |
|--------|---------|
| Automated | Covered by an automated unit/integration test that runs in CI |
| Partial | Implemented and partially tested (some ACs verified, others manual) |
| Manual | Implemented but verified manually / via smoke test only (no automated test) |
| Not built | Deferred, stubbed, or not yet implemented in the backend |

All file paths are relative to `backend/`. Test references use
`file :: Class` (pytest classes) or `file :: test_name`.

---

## 1. Coverage Summary

| Module | Requirements | Automated | Partial | Manual | Not built |
|--------|:------------:|:---------:|:-------:|:------:|:---------:|
| SHARED | 6 | 3 | 2 | 1 | 0 |
| AP (Accounts Payable) | 9 | 6 | 1 | 1 | 1 |
| RAG (Records Assistant) | 7 | 1 | 2 | 2 | 2 |
| CROSS-cutting | 3 | 1 | 1 | 1 | 0 |
| **Total** | **25** | **11** | **6** | **5** | **3** |

Notes:
- FR-RAG-007 (Search History) is explicitly deferred (P3) in the requirements.
- The chat integration test file (`tests/integration/test_chat_api.py`) currently
  contains only placeholder comments — chat endpoints are exercised manually.
- `POST /dashboard/stats` and `POST /dashboard/admin/seed-data` are declared in
  `routers/dashboard.py` as comments only; seeding is done via `scripts/seed_data.py`.

---

## 2. Shared Platform Requirements

| Req ID | Requirement | Acceptance Criteria | Implementation | Tests | Status |
|--------|-------------|---------------------|----------------|-------|--------|
| FR-SHARED-001 | User Authentication | AC-1.1.1, AC-1.1.2, AC-1.1.3, AC-1.1.4 | `app/middleware/auth.py` → `get_current_user`, `_parse_cognito_claims`, `_validate_token_with_cognito` | `tests/unit/test_auth.py :: TestCurrentUser` (identity/role resolution); token validation itself verified manually | Partial |
| FR-SHARED-002 | Role-Based Access Control | AC-1.2.1, AC-1.2.2, AC-1.2.3, AC-1.2.4 | `app/middleware/auth.py` → `require_role`, `CurrentUser.has_role`; enforced in every router via `Depends(require_role(...))` | `tests/unit/test_auth.py :: TestCurrentUser`; `tests/integration/test_invoices_api.py` (`test_upload_rejected_for_staff_role`, `test_staff_cannot_list_invoices`, `test_clerk_cannot_approve`); `tests/integration/test_documents_api.py :: test_clerk_cannot_upload_documents` | Automated |
| FR-SHARED-003 | Document Upload | AC-2.1.1–AC-2.1.5, AC-2.2.1, AC-2.2.3, AC-2.4.1 | `app/routers/invoices.py` → `upload_invoice`; `app/routers/documents.py` → `upload_document`; validation in `app/models/schemas.py` (`InvoiceUploadRequest`, `DocumentUploadRequest`) | `tests/unit/test_models.py :: TestInvoiceUploadRequest, TestDocumentUploadRequest`; `tests/integration/test_invoices_api.py :: TestInvoiceUpload`; `tests/integration/test_documents_api.py :: TestDocumentUpload` | Automated |
| FR-SHARED-004 | Document Storage | AC-2.1.1, AC-2.1.4, AC-2.2.1 | `app/services/s3.py` → `S3Client.generate_presigned_post/get`; metadata persisted via `app/services/dynamo.py` → `DynamoClient.put_item` (called from `upload_invoice`/`upload_document`) | Metadata write asserted in `tests/integration/test_invoices_api.py :: test_upload_returns_presigned_url` and `test_documents_api.py :: test_admin_can_upload_document`; S3 encryption/partitioning verified manually | Partial |
| FR-SHARED-005 | Processing Status Tracking | AC-2.3.1, AC-2.3.2, AC-2.3.3, AC-3.1.3 | `app/models/enums.py` → `InvoiceStatus`; transitions in `app/services/processor.py` → `process_invoice`, `_run_pipeline` via `DynamoClient.update_status` (conditional writes) | `tests/unit/test_processor.py :: TestProcessInvoiceHappyPath, TestProcessInvoiceEscalation, TestProcessInvoiceExtractionFailure`; `tests/unit/test_models.py :: TestEnums` | Automated |
| FR-SHARED-006 | Error Handling & User Feedback | AC-2.4.2, AC-2.4.3, AC-2.4.4 | `app/middleware/errors.py` → `AppError`, `register_exception_handlers`; `app/middleware/correlation.py` → `CorrelationIdMiddleware` | `tests/unit/test_middleware.py :: TestErrorHandling, TestCorrelationIdMiddleware` | Automated |

---

## 3. AP Invoice Agent Requirements

| Req ID | Requirement | Acceptance Criteria | Implementation | Tests | Status |
|--------|-------------|---------------------|----------------|-------|--------|
| FR-AP-001 | Invoice Data Extraction | AC-3.1.1, AC-3.1.3, AC-3.1.5 | `app/services/extraction.py` → `extract_invoice`, `_bda_extract`, `_poll_bda`, `_parse_bda_response`, `_mock_extraction` | Pipeline call verified in `tests/unit/test_processor.py :: TestProcessInvoiceHappyPath` (mocks `extract_invoice`); BDA parsing verified manually via mock path | Partial |
| FR-AP-002 | Extraction Confidence Scoring | AC-3.1.2, AC-3.2.2 | `app/services/extraction.py` → per-field `confidence` + `overallConfidence`; consumed by `rules.py` (RULE-003) | Confidence-threshold behaviour: `tests/unit/test_rules.py :: TestConfidenceThreshold` | Automated |
| FR-AP-003 | Purchase Order Matching | AC-3.3.1, AC-3.3.2, AC-3.3.3, AC-3.3.4 | `app/services/matcher.py` → `match_purchase_order`, `_vendor_names_match`, `_normalise_vendor`, `_closest_amount` | `tests/unit/test_matcher.py :: TestMatchPurchaseOrder, TestVendorNormalisation` | Automated |
| FR-AP-004 | Goods Receipt Matching | AC-3.4.1, AC-3.4.2, AC-3.4.3, AC-3.4.4 | `app/services/matcher.py` → `match_goods_receipt` (2% quantity tolerance, sums split deliveries) | `tests/unit/test_matcher.py :: TestMatchGoodsReceipt` | Automated |
| FR-AP-005 | Three-Way Match Validation | AC-3.5.1, AC-3.5.2, AC-3.5.3 | `app/services/matcher.py` → `three_way_match`; persistence + EXTRACTED→ESCALATED flow in `processor.py` `_run_pipeline` | `tests/unit/test_matcher.py :: TestThreeWayMatch`; persistence in `tests/unit/test_processor.py` | Automated |
| FR-AP-006 | Automatic Approval | AC-3.6.1, AC-3.6.2, AC-3.6.3 | `app/services/rules.py` → `evaluate_approval_rules`, `_evaluate_rules` (RULE-001..004); `processor.py` sets `approver="SYSTEM"` | `tests/unit/test_rules.py :: TestAllRulesPass, TestAmountThreshold, TestConfidenceThreshold, TestApprovedVendor`; `tests/unit/test_processor.py :: TestProcessInvoiceHappyPath` (`test_approved_status_includes_approver_system`) | Automated |
| FR-AP-007 | Exception Escalation | AC-3.7.1, AC-3.7.2, AC-3.7.3, AC-3.7.4 | `app/services/rules.py` → `_escalation_target`; `processor.py` sets ESCALATED + reason + assignee | `tests/unit/test_rules.py` (routing per rule); `tests/unit/test_processor.py :: TestProcessInvoiceEscalation` | Automated |
| FR-AP-008 | Manual Review Interface (P2) | AC-3.8.1, AC-3.8.2, AC-3.8.3 | `app/routers/invoices.py` → `approve_invoice` (API side; ESCALATED→APPROVED/REJECTED, mandatory comment) | `tests/integration/test_invoices_api.py :: TestInvoiceApprove` (approve/reject, RBAC, comment validation, status guard). Side-by-side UI (AC-3.8.1) is frontend/manual | Automated (API) |
| FR-AP-009 | Invoice Processing Summary | AC-3.9.1, AC-3.9.2 | `processor.py` records `processingDurationMs`; dashboard aggregation declared as TODO in `app/routers/dashboard.py` (stub) | `processingDurationMs` recording: `tests/unit/test_processor.py :: test_processing_duration_is_recorded`. Dashboard `/dashboard/stats` endpoint not implemented | Not built (endpoint) |

---

## 4. Ask-Your-Records Assistant Requirements

| Req ID | Requirement | Acceptance Criteria | Implementation | Tests | Status |
|--------|-------------|---------------------|----------------|-------|--------|
| FR-RAG-001 | Document Ingestion for KB | AC-2.2.1, AC-2.2.2, AC-4.6.2 | `app/routers/documents.py` → `upload_document` (S3 + `kbSyncStatus=PENDING`); ingestion via `scripts/sync_knowledge_base.py` (stub) | Upload path: `tests/integration/test_documents_api.py :: TestDocumentUpload`. KB ingestion/sync verified manually | Partial |
| FR-RAG-002 | Natural Language Query Interface | AC-4.1.1, AC-4.1.2, AC-4.1.3, AC-4.1.4 | `app/routers/chat.py` → `post_chat`, `_handle_document`; `app/services/intent.py` → `classify`; `app/services/bedrock.py` → `retrieve_and_generate` | `tests/integration/test_chat_api.py` is a placeholder (empty); verified manually | Manual |
| FR-RAG-003 | Source Citation | AC-4.2.1, AC-4.2.2, AC-4.2.3 | `app/routers/chat.py` (citations in `ChatResponse`); `app/services/bedrock.py` maps KB source chunks to citations | No automated test; verified manually | Manual |
| FR-RAG-004 | Conversation Context (P2) | AC-4.3.1, AC-4.3.2, AC-4.3.3 | `app/routers/chat.py` → `_persist_turn`, `list_sessions`, `get_session` (session-scoped history in `CONVERSATION_TABLE`) | Session persistence exercised via chat endpoints; no automated test | Partial |
| FR-RAG-005 | Document Scope Filtering (P2) | AC-4.4.1, AC-4.4.2 | `app/routers/chat.py` → `category_filter` passed to `_handle_document`; `bedrock.py` applies KB metadata filter | No automated test; verified manually | Manual |
| FR-RAG-006 | Answer Quality Guardrails | AC-4.5.1, AC-4.5.2, AC-4.5.3 | `app/services/intent.py` classification + dev fallback; `_handle_document` unavailable message; Bedrock Guardrails config (infra) | Intent classification logic is unit-testable but currently untested; guardrail behaviour verified manually | Partial |
| FR-RAG-007 | Search History (P3) | — (deferred) | Not implemented (deferred per requirements) | — | Not built (deferred) |

---

## 5. Cross-Cutting Requirements

| Req ID | Requirement | Acceptance Criteria | Implementation | Tests | Status |
|--------|-------------|---------------------|----------------|-------|--------|
| FR-CROSS-001 | Unified Document Pipeline | AC-4.6.1, AC-4.6.2 | KB data source S3 prefix includes `invoices/`; structured queries via `app/services/tools.py` + `app/routers/chat.py` `_handle_structured` | Structured-query tools not covered by automated tests; end-to-end verified manually | Partial |
| FR-CROSS-002 | Audit Logging (P2) | AC-2.4.4, AC-5.2.2 | Structured logging across services + correlation ID (`app/middleware/correlation.py`); CloudWatch in infra | Correlation ID: `tests/unit/test_middleware.py :: TestCorrelationIdMiddleware`. Log-content assertions are manual | Automated (correlation) |
| FR-CROSS-003 | API Rate Limiting (P2) | — | API Gateway throttling (`backend/template.yaml`) — infrastructure, not app code | Verified manually against deployed stack | Manual |

---

## 6. Administration (User Stories 5.x)

These map to shared/AP requirements above but are called out because they have
their own acceptance criteria.

| User Story | Acceptance Criteria | Implementation | Tests | Status |
|------------|---------------------|----------------|-------|--------|
| US-5.1 Manage Sample Data | AC-5.1.1–AC-5.1.4 | `scripts/seed_data.py` (stub); PO/GR consumed by `matcher.py`. `POST /admin/seed-data` endpoint declared as comment in `routers/dashboard.py` (not implemented) | Matching against seeded data: `tests/unit/test_matcher.py`. Seed endpoint itself untested | Partial |
| US-5.2 Monitor System Health (P2) | AC-5.2.1, AC-5.2.2 | CloudWatch dashboards/logs (infra); correlation IDs in app | `tests/unit/test_middleware.py` (correlation only); health metrics verified manually | Manual |

---

## 7. Test Inventory (reverse index)

| Test file | Requirements covered |
|-----------|----------------------|
| `tests/unit/test_auth.py` | FR-SHARED-001, FR-SHARED-002 |
| `tests/unit/test_matcher.py` | FR-AP-003, FR-AP-004, FR-AP-005 |
| `tests/unit/test_rules.py` | FR-AP-002, FR-AP-006, FR-AP-007 |
| `tests/unit/test_processor.py` | FR-SHARED-005, FR-AP-001, FR-AP-005, FR-AP-006, FR-AP-007, FR-AP-009 |
| `tests/unit/test_models.py` | FR-SHARED-003 (validation) |
| `tests/unit/test_middleware.py` | FR-SHARED-006, FR-CROSS-002 |
| `tests/integration/test_invoices_api.py` | FR-SHARED-002, FR-SHARED-003, FR-AP-008 |
| `tests/integration/test_documents_api.py` | FR-SHARED-002, FR-SHARED-003, FR-RAG-001 |
| `tests/integration/test_chat_api.py` | (placeholder — no active tests) FR-RAG-002 intended |

---

## 8. Gaps & Recommendations

1. **Chat/RAG has no automated coverage.** `test_chat_api.py` is a stub. The
   intent classifier (`app/services/intent.py`) is pure logic and easily
   unit-testable — add tests for `classify()` (structured vs document vs hybrid,
   param extraction, dev fallback) to cover FR-RAG-002/006 without AWS.
2. **Dashboard stats endpoint (FR-AP-009 / AC-3.9.x) is not implemented.**
   `routers/dashboard.py` is a comment-only stub. Either implement
   `GET /dashboard/stats` with an aggregation test, or mark the AC as
   frontend-computed.
3. **Seed-data / KB-sync are script stubs** (`scripts/seed_data.py`,
   `scripts/sync_knowledge_base.py`). US-5.1's `POST /admin/seed-data` endpoint
   (AC-5.1.4) is not built.
4. **Extraction BDA parsing (FR-AP-001)** is only exercised through the mock
   path. Add a unit test for `_parse_bda_response` with a sample BDA block
   payload to cover AC-3.1.1 field mapping.
5. **Citations (FR-RAG-003)** and **scope filtering (FR-RAG-005)** rely on the
   live Bedrock KB and are manual-only. Consider a mocked `BedrockService` test
   asserting citation mapping.
