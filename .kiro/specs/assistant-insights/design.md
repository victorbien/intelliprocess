# Design Document

## Overview

The Assistant Insights feature extends the existing IntelliProcess Records Assistant along two independent tracks that share no runtime coupling.

**Part A — Supplier analytics.** Three new Python functions are added to `backend/app/services/tools.py` (`top_suppliers`, `supplier_order_accuracy`, `supplier_lowest_prices`) and registered with the Strands agent in `backend/app/services/agent.py`. Each aggregates invoice data in-process, reusing the existing `DynamoClient` singletons and the `_convert_decimals` helper. On the frontend, `ChatWindow`'s empty state is refactored from a flat chip list into grouped preset question chips driven by a small data structure.

**Part B — Conversation summary and resume.** A new endpoint `POST /chat/sessions/{session_id}/summary` generates an AI summary of a session via `BedrockService.invoke_model` and stores it in `CONVERSATION_TABLE` as a dedicated summary record. Session retrieval is extended so the frontend can find the most recent stored summary. The `ChatDrawer` fires the summary request (fire-and-forget) on close, and on open the chat surfaces a resume prompt plus a collapsible `Summary_Card` whose expander lazily loads the full history via `GET /chat/sessions/{session_id}`.

The design builds directly on the already-implemented `ai-assistant` spec (Strands single-agent architecture, SSE streaming, `BedrockService`, and `CONVERSATION_TABLE` persistence). All code and content are English only. Product-level analysis is out of scope.

## Architecture

```
Frontend (React)                         Backend (FastAPI)                    AWS
────────────────                         ─────────────────                    ───
ChatDrawer                               chat.py router
 ├─ open  ─► getLatestSessionSummary ──► GET  /chat/sessions          ──► DynamoDB (CONVERSATION_TABLE)
 │          (find last summary record)   GET  /chat/sessions/{id}     ──► DynamoDB (CONVERSATION_TABLE)
 ├─ SummaryCard.expand ─► getSession ──► GET  /chat/sessions/{id}     ──► DynamoDB
 └─ close ─► summarizeSession        ──► POST /chat/sessions/{id}/summary
                                          │        │
                                          │        ├─ read turns ─────► DynamoDB
                                          │        ├─ invoke_model ───► BedrockService ─► Bedrock
                                          │        └─ put summary ────► DynamoDB

ChatWindow (EmptyState)                  agent.py  (_build_agent tools=[…])
 └─ grouped preset chips ─► handleSend ─► POST /chat/stream (SSE) ──► AgentService ─► Strands Agent
                                                                        │
                                                                        ├─ top_suppliers            ┐
                                                                        ├─ supplier_order_accuracy  ├─ tools.py ─► DynamoDB
                                                                        └─ supplier_lowest_prices   ┘   (invoice/PO/GR scans)
```

Part A introduces no new endpoints — the analytics tools are invoked by the agent through the existing `/chat` and `/chat/stream` flow. Part B adds one write endpoint and reuses two existing read endpoints.

## Components and Interfaces

### Part A — Supplier analytics tools (`backend/app/services/tools.py`)

All three functions follow the conventions already established in `tools.py`:
- Use the module-level singletons `_invoice_client`, `_po_client`, `_gr_client`.
- Perform a paginated full scan of the invoice table (acceptable at MVP scale), then aggregate in-process by `extraction.vendorName`.
- Guard every access to `extraction` and `matchResult`, both of which may be absent (e.g. `PROCESSING` invoices).
- Run all returned values through `_convert_decimals` so the output is JSON-serialisable.
- Carry docstrings written as LLM tool descriptions (what the tool is for, when to use it, parameters, returns).

A shared private helper collects the full invoice set so each tool does not repeat scan/pagination logic:

```python
def _scan_all_invoices() -> list[dict]:
    """Return every invoice item, paginating the table scan to exhaustion.

    Aggregation tools must observe all records to produce accurate totals.
    """
    response = _invoice_client.table.scan()
    items = response.get("Items", [])
    while "LastEvaluatedKey" in response:
        response = _invoice_client.table.scan(
            ExclusiveStartKey=response["LastEvaluatedKey"]
        )
        items.extend(response.get("Items", []))
    return items
```

#### `top_suppliers`

```python
def top_suppliers(limit: int = 10) -> dict[str, Any]:
    """Rank suppliers by total invoice spend.

    Use this tool when the user asks which vendors account for the most
    spend or business — for example:
    - "Who are our top suppliers?"
    - "Which vendors do we spend the most with?"
    - "Show me the top 5 suppliers by total invoiced amount."

    Parameters
    ----------
    limit:
        Maximum number of suppliers to return (capped at 10). Defaults to 10.

    Returns
    -------
    dict with keys:
        ``suppliers`` — list of {vendorName, totalAmount, invoiceCount},
                        sorted by totalAmount descending, length <= 10,
        ``count``     — number of suppliers in the ranked list.
    """
```

Aggregation: iterate scanned invoices, skip any without an `extraction` block, group by `extraction.vendorName`, sum `extraction.totalAmount`, and count invoices per vendor. Sort descending by total amount, truncate to `min(limit, 10)`. Empty dataset yields `{"suppliers": [], "count": 0}`.

#### `supplier_order_accuracy`

```python
def supplier_order_accuracy(limit: int = 10) -> dict[str, Any]:
    """Rank suppliers by order accuracy (three-way match rate).

    Use this tool when the user asks which vendors are most reliable against
    purchase orders and goods receipts — for example:
    - "Which suppliers have the best order accuracy?"
    - "Rank vendors by match rate."
    - "Who are our most reliable suppliers?"

    Returns
    -------
    dict with keys:
        ``suppliers`` — list of {vendorName, matchRate, invoicesEvaluated},
                        sorted by matchRate descending, length <= 10,
        ``count``     — number of suppliers in the ranked list.
    """
```

Match-rate computation: an invoice counts toward a supplier only if it has a `matchResult` block. For each such invoice, read `matchResult.poMatch.status` and `matchResult.grMatch.status`; the invoice is treated as a successful match when both statuses equal `"PASS"`. A supplier's `matchRate` is `matched_invoices / invoicesEvaluated`, where `invoicesEvaluated` is the number of that supplier's invoices carrying a `matchResult`. Suppliers with zero evaluated invoices are excluded from the ranking. Empty dataset yields `{"suppliers": [], "count": 0}`.

#### `supplier_lowest_prices`

```python
def supplier_lowest_prices() -> dict[str, Any]:
    """Compare suppliers by average pricing.

    Use this tool when the user asks which vendors are cheapest or wants a
    price comparison — for example:
    - "Which suppliers have the lowest prices?"
    - "Compare vendors by average invoice amount."
    - "What's the average line-item price per supplier?"

    Returns
    -------
    dict with keys:
        ``suppliers`` — list of {vendorName, avgInvoiceAmount, avgUnitPrice},
        ``count``     — number of suppliers reported.
    """
```

For each supplier (grouped from invoices that have an `extraction` block):
- `avgInvoiceAmount` = mean of `extraction.totalAmount` across that supplier's invoices.
- `avgUnitPrice` = mean of `unitPrice` across every entry of `extraction.lineItems` for that supplier. If the supplier has no line items at all, `avgUnitPrice` is `None` (JSON `null`).

Both averages are returned together in a single response object per supplier.

### Part A — Agent registration (`backend/app/services/agent.py`)

`_build_agent()` imports the three new functions and appends them to the `tools=[…]` list:

```python
from app.services.tools import (
    query_invoices,
    count_invoices_by_status,
    get_invoice_detail,
    query_purchase_orders,
    query_goods_receipts,
    top_suppliers,            # new
    supplier_order_accuracy,  # new
    supplier_lowest_prices,   # new
)
# … tools=[…, top_suppliers, supplier_order_accuracy, supplier_lowest_prices]
```

Because the tools are plain callables, the `@tool` decorator is unnecessary — Strands wraps them via docstring like the existing data tools. No prompt change is required; the system prompt already instructs the agent to format results conversationally.

### Part A — Grouped preset chips (`frontend/src/components/chat/ChatWindow.tsx`)

The flat `EXAMPLE_QUESTIONS` array is replaced by a grouped data structure, and `EmptyState` renders each group as a heading followed by vertically stacked buttons.

```typescript
interface PresetQuestionGroup {
  group: string;
  questions: string[];
}

const PRESET_QUESTION_GROUPS: PresetQuestionGroup[] = [
  {
    group: "Suppliers",
    questions: [
      "Who are our top suppliers by spend?",
      "Which suppliers have the best order accuracy?",
      "Which suppliers have the lowest prices?",
    ],
  },
  {
    group: "Invoices",
    questions: [
      "How many invoices are escalated?",
      "Show me Acme invoices",
      "Which invoices exceed $10,000?",
    ],
  },
];
```

`EmptyState` maps over `PRESET_QUESTION_GROUPS`, rendering a heading (`<h4>`) per group and one `<button>` per question. Each button's `onClick` calls `onSelect(question)`, which routes into the existing `handleSend`. No change to send/stream logic.

### Part B — Summary endpoint (`backend/app/routers/chat.py`)

New model in `schemas.py`:

```python
class ChatSummaryResponse(BaseModel):
    session_id: str = Field(..., alias="sessionId")
    summary: str
    generated_at: str = Field(..., alias="generatedAt")
    model_config = {"populate_by_name": True, "serialize_by_alias": True}
```

New endpoint:

```python
@router.post("/sessions/{session_id}/summary",
             response_model=ApiResponse[ChatSummaryResponse])
async def summarize_session(session_id, user):
    # 1. Load ordered turns for the session (owner-checked, as in get_session).
    # 2. If no user/assistant turns exist -> 404 (endpoint is not called by the
    #    frontend for empty sessions; this guards direct/edge calls).
    # 3. Build a summarization prompt from the transcript.
    # 4. summary = BedrockService().invoke_model(prompt, max_tokens=512).
    #    On failure -> propagate as AppError (500); DO NOT write anything.
    # 5. Persist a summary record via _persist_summary(); leave turns untouched.
    # 6. Return {sessionId, summary, generatedAt}.
```

**Summary storage model.** The summary is stored as a distinct item in `CONVERSATION_TABLE` sharing the session partition key, marked by `role = "summary"`. Using a reserved sort-key timestamp keeps it separable from conversation turns and lets existing turn readers ignore it by filtering on `role`.

```python
def _persist_summary(session_id: str, user_id: str, summary: str) -> str:
    generated_at = _utcnow()
    _conv_db.put_item({
        "sessionId": session_id,
        "timestamp": f"zzz-summary#{generated_at}",  # sorts after normal turns
        "userId": user_id,
        "role": "summary",
        "content": summary,
        "generatedAt": generated_at,
    })
    return generated_at
```

The reserved-prefix timestamp (`zzz-summary#…`) guarantees the summary sorts after ordinary ISO-8601 turn timestamps so it never interleaves with history. Turn-reading endpoints (`get_session`, `list_sessions`) filter out `role == "summary"` items so message history and previews are unaffected.

**Failure semantics (Req 6.5).** The order of operations — generate first, persist only on success — guarantees that a model failure leaves `CONVERSATION_TABLE` exactly as it was: no summary item is written and no existing turn is modified or deleted.

### Part B — Summary retrieval

`get_session` already returns full history via `GET /chat/sessions/{session_id}`; it is updated only to exclude `role == "summary"` items from the `messages` list, so the expander shows conversation turns only.

To let the frontend discover the latest summary, `list_sessions` (`GET /chat/sessions`) is extended so each `ChatSessionSummary` optionally carries the stored summary text and its timestamp:

```python
class ChatSessionSummary(BaseModel):
    session_id: str = Field(..., alias="sessionId")
    first_message: str = Field(..., alias="firstMessage")
    last_activity: str = Field(..., alias="lastActivity")
    message_count: int = Field(..., alias="messageCount")
    summary: str | None = None                     # new
    summary_generated_at: str | None = Field(None, alias="summaryGeneratedAt")  # new
```

When grouping session items, any `role == "summary"` item contributes its `content` to `summary` and is excluded from `messageCount`. The frontend reads `sessions[0]` (most recent) to decide whether a resume prompt and `Summary_Card` should appear.

### Part B — Frontend API helpers (`frontend/src/services/api.ts`)

```typescript
export interface ChatSessionSummaryItem {
  sessionId: string;
  firstMessage: string;
  lastActivity: string;
  messageCount: number;
  summary?: string;
  summaryGeneratedAt?: string;
}

export interface ChatSessionDetailData {
  sessionId: string;
  messages: ChatMessageItem[];
}

// POST /chat/sessions/{id}/summary — fire-and-forget on drawer close.
export async function summarizeSession(sessionId: string): Promise<void>;

// GET /chat/sessions/{id} — full message history for the expander.
export async function getSession(sessionId: string): Promise<ChatSessionDetailData>;

// GET /chat/sessions — returns most recent session incl. stored summary.
export async function getLatestSessionSummary(): Promise<ChatSessionSummaryItem | null>;
```

`summarizeSession` swallows errors (fire-and-forget); a failed summary must never surface a user-facing error on close.

### Part B — Drawer close/open and Summary Card

- **Close (Req 6.1, 6.4):** `ChatDrawer` needs the active `sessionId` and the current message count from `ChatWindow`. `ChatWindow` lifts `sessionId` and message state up (or exposes them via a callback/ref) so the drawer's `onClose` can, when the message list is non-empty and a `sessionId` exists, call `summarizeSession(sessionId)` before invoking the parent `onClose`. When the message list is empty, the summary request is skipped.
- **Open (Req 7.1–7.3):** on open, `ChatWindow` calls `getLatestSessionSummary()`. If a summary exists, it renders the resume prompt text exactly "Hello! Do you want to continue the last conversation?" and a `Summary_Card` at the top of the message area.
- **Summary Card (Req 7.2–7.4):** a new `SummaryCard.tsx` shows the summary text by default with the full history collapsed. Activating the "view full history" expander calls `getSession(sessionId)`, then renders the returned turns as `MessageBubble`s beneath the summary.
- **Global availability (Req 7.5):** `FloatingChatButton` + `ChatDrawer` already mount in the application shell, making the drawer reachable on every page; no structural change beyond confirming the shell placement.

## Data Models

### Invoice record (existing, read-only for Part A)

```
{
  documentId: str,
  status: str,
  extraction?: {
    vendorName?: str,
    totalAmount?: number,
    lineItems?: [ { unitPrice?: number, ... }, ... ],
  },
  matchResult?: {
    poMatch?: { status?: str },   # "PASS" | "FAIL" | ...
    grMatch?: { status?: str },
    threeWayMatch?: str,
  },
}
```

### Analytics tool outputs (Part A)

```
top_suppliers          -> { suppliers: [{ vendorName, totalAmount, invoiceCount }], count }
supplier_order_accuracy-> { suppliers: [{ vendorName, matchRate, invoicesEvaluated }], count }
supplier_lowest_prices -> { suppliers: [{ vendorName, avgInvoiceAmount, avgUnitPrice|null }], count }
```

### CONVERSATION_TABLE summary item (Part B)

```
{
  sessionId: str,                       # partition key (shared with turns)
  timestamp: "zzz-summary#<ISO-8601>",  # sort key; sorts after turns
  userId: str,
  role: "summary",
  content: str,                         # the AI-generated summary
  generatedAt: str,                     # ISO-8601
}
```

## Error Handling

- **Analytics tools:** DynamoDB `ClientError` during scans is logged (`logger.exception`) and re-raised, matching existing `query_invoices` behavior. Missing `extraction`/`matchResult`/`lineItems` keys are treated as "no data" and skip that record rather than raising. Division for match rate and averages guards against zero denominators (excluded from output, not `0/0`).
- **Summary endpoint:** ownership is enforced as in `get_session` (403 on mismatch). An empty session returns 404. `BedrockService.invoke_model` failure raises `RuntimeError`, surfaced as an `AppError(500)`; no table writes occur, so conversation turns remain unchanged (Req 6.5).
- **Frontend:** `summarizeSession` is fire-and-forget and swallows all errors so closing the drawer never blocks or shows an error. `getLatestSessionSummary` returning `null` (no prior session or no summary) simply suppresses the resume prompt and card. Expander load failures show an inline message and leave the summary visible.

## Testing Strategy

**Dual approach.** Property-based tests cover the analytics aggregation logic and the summary storage invariants; example-based unit tests cover fixed scenarios (empty datasets, specific UI content, wiring) and edge cases.

- **Property tests** (backend, on `tools.py` with mocked scans; and summary persistence with a mocked DynamoDB): minimum 100 iterations each, tagged `Feature: assistant-insights, Property {n}: {text}`. Inputs are generated invoice sets with varied vendor names, amounts, line items, `matchResult` presence, and `Decimal` values.
- **Unit / example tests:** empty-dataset returns (Req 1.4, 2.5), tool registration (Req 4.1), preset group content "Suppliers"/"Invoices" (Req 5.4), resume prompt text (Req 7.1), card default state (Req 7.3), close/open wiring (Req 6.1, 6.2, 6.4, 7.4), and global mount (Req 7.5).
- **Frontend tests:** render the grouped empty state and assert every heading and question button appears (Req 5.2) and that clicking a button submits its exact text (Req 5.3).

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Top suppliers are capped and ranked by spend

*For any* set of invoices, `top_suppliers` returns at most 10 suppliers whose `totalAmount` values form a non-increasing sequence.

**Validates: Requirements 1.1**

### Property 2: Top-supplier totals and counts are accurate

*For any* set of invoices, each supplier returned by `top_suppliers` has a `totalAmount` equal to the sum of `extraction.totalAmount` over that supplier's invoices with an extraction block, and an `invoiceCount` equal to the number of those invoices.

**Validates: Requirements 1.2**

### Property 3: Invoices without extraction are excluded from spend

*For any* set of invoices, adding or removing invoices that have no `extraction` block does not change any supplier's `totalAmount` or `invoiceCount` in the `top_suppliers` result.

**Validates: Requirements 1.3**

### Property 4: Order-accuracy results are capped and ranked by match rate

*For any* set of invoices, `supplier_order_accuracy` returns at most 10 suppliers whose `matchRate` values form a non-increasing sequence.

**Validates: Requirements 2.1**

### Property 5: Match rate and evaluated count are computed correctly

*For any* set of invoices, each supplier returned by `supplier_order_accuracy` has an `invoicesEvaluated` equal to the number of that supplier's invoices carrying a `matchResult`, and a `matchRate` equal to the fraction of those invoices whose `matchResult.poMatch.status` and `matchResult.grMatch.status` both equal `"PASS"`.

**Validates: Requirements 2.2, 2.3**

### Property 6: Invoices without a match result are excluded from accuracy

*For any* set of invoices, adding or removing invoices that have no `matchResult` does not change any supplier's `matchRate` or `invoicesEvaluated` in the `supplier_order_accuracy` result.

**Validates: Requirements 2.4**

### Property 7: Lowest-prices reports both correct averages per supplier

*For any* set of invoices, each supplier returned by `supplier_lowest_prices` has an `avgInvoiceAmount` equal to the mean of `extraction.totalAmount` over that supplier's invoices with an extraction block, and an `avgUnitPrice` equal to the mean of `unitPrice` over all line items of those invoices.

**Validates: Requirements 3.1, 3.2, 3.3**

### Property 8: Invoices without extraction are excluded from averages

*For any* set of invoices, adding or removing invoices that have no `extraction` block does not change any supplier's `avgInvoiceAmount` or `avgUnitPrice` in the `supplier_lowest_prices` result.

**Validates: Requirements 3.4**

### Property 9: Suppliers with no line items report null average unit price

*For any* set of invoices, any supplier whose invoices collectively contain no line items has an `avgUnitPrice` of `null` in the `supplier_lowest_prices` result.

**Validates: Requirements 3.5**

### Property 10: Analytics results are JSON-serialisable with no Decimals

*For any* set of invoices, the result of each analytics tool (`top_suppliers`, `supplier_order_accuracy`, `supplier_lowest_prices`) contains no `Decimal` values and can be serialised with `json.dumps` without error.

**Validates: Requirements 4.3**

### Property 11: Preset groups render completely

*For any* configuration of Preset_Question_Groups, the rendered empty state contains every group's heading and a button for every question in every group.

**Validates: Requirements 5.2**

### Property 12: Selecting a preset submits its exact text

*For any* preset question button rendered in the empty state, activating that button submits the button's exact text as the chat question.

**Validates: Requirements 5.3**

### Property 13: Summary storage round-trip

*For any* session identifier and generated summary text, storing the summary and then retrieving the latest summary for that session returns the same summary text associated with that session.

**Validates: Requirements 6.3**

### Property 14: Failed summary generation leaves conversation turns unchanged

*For any* session, if summary generation fails, the set of conversation turns stored for that session after the failed request is identical to the set before it, and no summary item is written.

**Validates: Requirements 6.5**
