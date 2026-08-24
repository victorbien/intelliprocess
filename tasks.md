# Implementation Tasks

## IntelliProcess AI Platform

---

## Module 1: SHARED — Foundation & Infrastructure (Week 1)

Requirements: FR-SHARED-001 through FR-SHARED-006
Acceptance Criteria: AC-1.1.x, AC-1.2.x, AC-2.1.x, AC-2.2.x, AC-2.3.x, AC-2.4.x

| # | Task | Status |
|---|------|--------|
| 1.1 | Shared models — Pydantic schemas, enums, response envelope | [x] |
| 1.2 | Shared services — DynamoDB client wrapper, S3 client wrapper | [x] |
| 1.3 | Error handling — AppError, correlation ID middleware, response helpers | [x] |
| 1.4 | Auth middleware — Cognito JWT validation, role-based dependency | [x] |
| 1.5 | Invoices router — POST /upload, GET /list, GET /{id} | [x] |
| 1.6 | Documents router — POST /upload, GET /list | [x] |
| 1.7 | Unit tests — models, services, auth, upload validation | [x] |

---

## Module 2: AP — Invoice Processing Engine (Week 1-2)

Requirements: FR-AP-001 through FR-AP-009
Acceptance Criteria: AC-3.1.x through AC-3.9.x

| # | Task | Status |
|---|------|--------|
| 2.1 | BDA extraction service — invoke BDA, parse response | [x] |
| 2.2 | PO matching service — exact + fuzzy match logic | [x] |
| 2.3 | GR matching service — quantity verification with tolerance | [x] |
| 2.4 | Three-way match orchestration | [x] |
| 2.5 | Approval rules engine — evaluate 4 rules, route escalations | [x] |
| 2.6 | Invoice processor — full pipeline orchestration (S3 trigger) | [x] |
| 2.7 | Manual approval endpoint — POST /invoices/{id}/approve | [x] |
| 2.8 | Unit tests — matcher, rules, processor | [x] |

---

## Module 3: RAG — Records Search Assistant (Week 2)

Requirements: FR-RAG-001 through FR-RAG-006
Acceptance Criteria: AC-4.1.x through AC-4.6.x

| # | Task | Status |
|---|------|--------|
| 3.1 | Bedrock KB service — RetrieveAndGenerate wrapper | [ ] |
| 3.2 | Citation extraction and formatting | [ ] |
| 3.3 | Chat router — POST /chat endpoint | [ ] |
| 3.4 | Conversation history — DynamoDB store/retrieve (P2) | [ ] |
| 3.5 | Category filter support (P2) | [ ] |
| 3.6 | Guardrails integration | [ ] |
| 3.7 | Unit tests — chat handler, citations | [ ] |

---

## Module 4: DASHBOARD — Stats & Admin (Week 3)

Requirements: FR-AP-009, FR-CROSS-001
Acceptance Criteria: AC-3.9.x, AC-5.1.x, AC-5.2.x

| # | Task | Status |
|---|------|--------|
| 4.1 | Dashboard stats aggregation — GET /dashboard/stats | [x] |
| 4.2 | Seed data endpoint — POST /admin/seed-data | [x] |
| 4.3 | KB sync trigger — POST /documents/sync | [x] |
| 4.4 | Purchase Order upload — POST /purchase-orders/upload (Admin uploads PO document → stored in DynamoDB for matching) | [x] |
| 4.5 | Goods Receipt upload — POST /goods-receipts/upload (Admin uploads GR document → stored in DynamoDB for three-way match) | [x] |
| 4.6 | Unit tests — dashboard handler | [x] |

---

## Module 5: FRONTEND — React UI (Weeks 1-3)

| # | Task | Status |
|---|------|--------|
| 5.1 | Auth flow — login, protected routes, role context | [x] |
| 5.2 | Invoice upload component — drag-drop, validation | [x] |
| 5.3 | Invoice list + detail views | [x] |
| 5.4 | Chat interface — messages, citations, category filter | [x] |
| 5.5 | Dashboard — stats cards, recent activity | [x] |
| 5.6 | Admin page — document upload, seed data, KB sync | [x] |
