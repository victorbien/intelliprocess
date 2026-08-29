# Implementation Plan: Assistant Insights

## Overview

This plan implements the Assistant Insights feature across two independent tracks. Part A adds three supplier analytics tools to the existing Strands agent and refactors the chat empty state into grouped preset question chips. Part B adds conversation summary generation on drawer close and a resume experience with a collapsible summary card on drawer open.

All backend code is Python (FastAPI + boto3, `AWS_REGION = ap-southeast-2`); all frontend code is TypeScript/React. Every task builds on the existing `ai-assistant` implementation (Strands agent, SSE streaming, `BedrockService`, `CONVERSATION_TABLE`). All code and content are English only — no non-English characters.

## Tasks

- [ ] 1. Add supplier analytics tools to `tools.py`
  - [x] 1.1 Add the `_scan_all_invoices` helper
    - In `backend/app/services/tools.py`, add a private `_scan_all_invoices() -> list[dict]` that scans `_invoice_client.table` and paginates on `LastEvaluatedKey` until exhausted, returning every invoice item
    - Log and re-raise `ClientError` consistent with `query_invoices`
    - _Requirements: 1.3, 2.4, 3.4_

  - [x] 1.2 Implement `top_suppliers`
    - Add `top_suppliers(limit: int = 10) -> dict[str, Any]` with an LLM tool-description docstring covering purpose, examples, params, returns
    - Iterate `_scan_all_invoices()`, skip invoices with no `extraction` block, group by `extraction.vendorName`, sum `extraction.totalAmount`, count invoices per vendor
    - Sort suppliers by `totalAmount` descending, truncate to `min(limit, 10)`; return `{ "suppliers": [{vendorName, totalAmount, invoiceCount}], "count": N }`
    - Return `{ "suppliers": [], "count": 0 }` for an empty/no-extraction dataset
    - Run the output through `_convert_decimals`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 4.3_

  - [ ]* 1.3 Write property tests for `top_suppliers`
    - **Property 1: Top suppliers are capped and ranked by spend** — Validates Requirements 1.1
    - **Property 2: Top-supplier totals and counts are accurate** — Validates Requirements 1.2
    - **Property 3: Invoices without extraction are excluded from spend** — Validates Requirements 1.3
    - Mock `_scan_all_invoices`; generate invoice sets with varied vendors, amounts, and `Decimal` values; minimum 100 iterations; tag `Feature: assistant-insights`

  - [ ]* 1.4 Write unit test for `top_suppliers` empty dataset
    - Assert empty/no-extraction input returns `{ "suppliers": [], "count": 0 }`
    - _Requirements: 1.4_

  - [x] 1.5 Implement `supplier_order_accuracy`
    - Add `supplier_order_accuracy(limit: int = 10) -> dict[str, Any]` with an LLM tool-description docstring
    - Group by `extraction.vendorName`; count an invoice toward a supplier only when it has a `matchResult` block (`invoicesEvaluated`); treat an invoice as matched when `matchResult.threeWayMatch` equals `"PASS"` (the authoritative overall verdict; poMatch/grMatch use "MATCHED"/"CONFIRMED")
    - Compute `matchRate = matched / invoicesEvaluated`, excluding suppliers with zero evaluated invoices; guard against zero denominators
    - Sort by `matchRate` descending, truncate to `min(limit, 10)`; return `{ "suppliers": [{vendorName, matchRate, invoicesEvaluated}], "count": N }`; empty dataset returns `{ "suppliers": [], "count": 0 }`
    - Run the output through `_convert_decimals`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 4.3_

  - [ ]* 1.6 Write property tests for `supplier_order_accuracy`
    - **Property 4: Order-accuracy results are capped and ranked by match rate** — Validates Requirements 2.1
    - **Property 5: Match rate and evaluated count are computed correctly** — Validates Requirements 2.2, 2.3
    - **Property 6: Invoices without a match result are excluded from accuracy** — Validates Requirements 2.4
    - Mock `_scan_all_invoices`; vary `matchResult` presence and PASS/FAIL statuses; minimum 100 iterations

  - [ ]* 1.7 Write unit test for `supplier_order_accuracy` empty dataset
    - Assert no-`matchResult` input returns `{ "suppliers": [], "count": 0 }`
    - _Requirements: 2.5_

  - [x] 1.8 Implement `supplier_lowest_prices`
    - Add `supplier_lowest_prices() -> dict[str, Any]` with an LLM tool-description docstring
    - Group invoices that have an `extraction` block by `vendorName`; compute `avgInvoiceAmount` as the mean of `extraction.totalAmount` and `avgUnitPrice` as the mean of `unitPrice` across all `extraction.lineItems` entries
    - Report `avgUnitPrice = None` (JSON `null`) for suppliers with no line items; guard against zero denominators
    - Return `{ "suppliers": [{vendorName, avgInvoiceAmount, avgUnitPrice}], "count": N }` and run through `_convert_decimals`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 4.3_

  - [ ]* 1.9 Write property tests for `supplier_lowest_prices`
    - **Property 7: Lowest-prices reports both correct averages per supplier** — Validates Requirements 3.1, 3.2, 3.3
    - **Property 8: Invoices without extraction are excluded from averages** — Validates Requirements 3.4
    - **Property 9: Suppliers with no line items report null average unit price** — Validates Requirements 3.5
    - Mock `_scan_all_invoices`; vary line-item presence and unit prices; minimum 100 iterations

  - [ ]* 1.10 Write property test for JSON-serialisable analytics output
    - **Property 10: Analytics results are JSON-serialisable with no Decimals** — Validates Requirements 4.3
    - Assert each of the three tool results contains no `Decimal` and serialises with `json.dumps`

- [ ] 2. Register the analytics tools with the agent
  - [x] 2.1 Import and register the three tools in `_build_agent`
    - In `backend/app/services/agent.py`, extend the `from app.services.tools import (...)` block with `top_suppliers`, `supplier_order_accuracy`, `supplier_lowest_prices`
    - Append the three callables to the `tools=[...]` list passed to `Agent(...)`
    - _Requirements: 4.1, 4.2_

  - [ ]* 2.2 Write unit test for tool registration
    - Assert the three tools are present in the agent's tool set / import surface
    - _Requirements: 4.1_

- [ ] 3. Checkpoint - backend analytics
  - Ensure all backend tests pass, ask the user if questions arise.

- [ ] 4. Refactor the chat empty state into grouped preset chips
  - [x] 4.1 Replace the flat example list with grouped presets in `ChatWindow.tsx`
    - In `frontend/src/components/chat/ChatWindow.tsx`, define `interface PresetQuestionGroup { group: string; questions: string[] }` and a `PRESET_QUESTION_GROUPS` array containing a `"Suppliers"` group and an `"Invoices"` group
    - Update `EmptyState` to map over `PRESET_QUESTION_GROUPS`, rendering a heading per group and one button per question, listed vertically beneath its heading
    - Each button's `onClick` calls `onSelect(question)` which routes into the existing `handleSend`; no change to send/stream logic
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ]* 4.2 Write property test for preset rendering
    - **Property 11: Preset groups render completely** — Validates Requirements 5.2
    - **Property 12: Selecting a preset submits its exact text** — Validates Requirements 5.3
    - Assert every group heading and every question button renders, and clicking a button submits its exact text

- [ ] 5. Add backend summary schemas and endpoint (Part B)
  - [x] 5.1 Add summary schemas in `schemas.py`
    - Add `ChatSummaryResponse` with `sessionId`, `summary`, `generatedAt` (alias config `populate_by_name` / `serialize_by_alias`)
    - Add optional `summary: str | None = None` and `summaryGeneratedAt` fields to `ChatSessionSummary`
    - _Requirements: 6.3, 7.2_

  - [x] 5.2 Add `_persist_summary` and the summary endpoint in `chat.py`
    - Add `_persist_summary(session_id, user_id, summary) -> str` writing an item with `role="summary"` and sort key `f"zzz-summary#{generated_at}"` to `CONVERSATION_TABLE`; return `generated_at`
    - Add `POST /chat/sessions/{session_id}/summary`: load ordered turns (owner-checked as in `get_session`), 404 when no user/assistant turns exist, build a summarization prompt, call `BedrockService().invoke_model(prompt, max_tokens=512)`, then persist via `_persist_summary` and return `ChatSummaryResponse`
    - On model failure, propagate `AppError(500)` and perform no table writes (generate-first, persist-on-success)
    - _Requirements: 6.2, 6.3, 6.5_

  - [x] 5.3 Filter summary items from turn readers in `chat.py`
    - Update `get_session` to exclude `role == "summary"` items from the returned `messages`
    - Update `list_sessions` grouping to route any `role == "summary"` item's `content` into the `summary`/`summaryGeneratedAt` fields and exclude it from `messageCount`
    - _Requirements: 6.3, 7.2_

  - [ ]* 5.4 Write property test for summary storage round-trip
    - **Property 13: Summary storage round-trip** — Validates Requirements 6.3
    - Mock DynamoDB; store then retrieve the latest summary and assert text matches the session

  - [ ]* 5.5 Write property test for failed-summary invariance
    - **Property 14: Failed summary generation leaves conversation turns unchanged** — Validates Requirements 6.5
    - Simulate `invoke_model` failure; assert no summary item is written and turns are identical before/after

- [ ] 6. Checkpoint - backend summary
  - Ensure all backend tests pass, ask the user if questions arise.

- [ ] 7. Add frontend API helpers for summary and resume
  - [x] 7.1 Add summary/session helpers in `api.ts`
    - In `frontend/src/services/api.ts`, add `ChatSessionSummaryItem` and `ChatSessionDetailData` interfaces
    - Add `summarizeSession(sessionId): Promise<void>` (POST, fire-and-forget, swallows all errors)
    - Add `getSession(sessionId): Promise<ChatSessionDetailData>` (GET full history)
    - Add `getLatestSessionSummary(): Promise<ChatSessionSummaryItem | null>` returning the most recent session including its stored summary, or `null`
    - _Requirements: 6.1, 7.2, 7.4_

- [ ] 8. Create the SummaryCard component
  - [x] 8.1 Implement `SummaryCard.tsx`
    - Create `frontend/src/components/chat/SummaryCard.tsx` displaying the summary text by default with full history collapsed
    - Add a "view full history" expander that lazily calls `getSession(sessionId)` and renders returned turns as `MessageBubble`s beneath the summary
    - Show an inline error message on load failure while keeping the summary visible
    - _Requirements: 7.2, 7.3, 7.4_

  - [ ]* 8.2 Write unit test for SummaryCard default state
    - Assert the summary shows by default and history is collapsed until the expander is activated
    - _Requirements: 7.3, 7.4_

- [ ] 9. Wire drawer close/open behavior
  - [x] 9.1 Expose session state from `ChatWindow` and fire summary on close
    - Lift `sessionId` and message-count/state from `ChatWindow` so `ChatDrawer` can access them (callback or ref)
    - On `ChatDrawer` close, when a `sessionId` exists and the message list is non-empty, call `summarizeSession(sessionId)` before invoking parent `onClose`; skip the request when the message list is empty
    - _Requirements: 6.1, 6.4_

  - [x] 9.2 Render resume prompt and SummaryCard on open
    - On open, `ChatWindow` calls `getLatestSessionSummary()`; when a summary exists, render the resume prompt text exactly `"Hello! Do you want to continue the last conversation?"` and mount `SummaryCard` at the top of the message area; suppress both when it returns `null`
    - _Requirements: 7.1, 7.2, 7.3_

  - [x] 9.3 Confirm global drawer availability
    - Verify `FloatingChatButton` + `ChatDrawer` mount in the application shell so the drawer is reachable on every page (confirm placement; no structural change expected)
    - _Requirements: 7.5_

  - [ ]* 9.4 Write unit tests for close/open wiring
    - Assert summary fires on close only when messages exist and a session id is set (Req 6.1, 6.4); assert resume prompt and card appear on open when a summary exists (Req 7.1, 7.4)
    - _Requirements: 6.1, 6.4, 7.1, 7.4_

- [ ] 10. Final checkpoint - frontend and integration
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional (property-based and unit tests) and can be skipped for a faster MVP.
- Each task references specific requirements clauses for traceability.
- Property tests validate the universal correctness properties defined in the design; unit tests cover fixed scenarios and edge cases.
- Part A (tasks 1-4) and Part B (tasks 5-9) share no runtime coupling and can be developed largely in parallel, subject to the file-conflict ordering in the dependency graph.
- All code and content are English only; `AWS_REGION` is `ap-southeast-2`.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "4.1", "5.1", "7.1"] },
    { "id": 1, "tasks": ["1.2", "1.5", "1.8", "4.2", "5.2", "8.1"] },
    { "id": 2, "tasks": ["1.3", "1.4", "1.6", "1.7", "1.9", "1.10", "2.1", "5.3", "8.2", "9.1"] },
    { "id": 3, "tasks": ["2.2", "5.4", "5.5", "9.2", "9.3"] },
    { "id": 4, "tasks": ["9.4"] }
  ]
}
```
