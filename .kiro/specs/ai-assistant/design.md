# Design Document: AI Assistant (Strands Agent + SSE Streaming)

## Overview

This document describes the architecture for upgrading the IntelliProcess Records Assistant from its current keyword-classifier + static-routing implementation to a **Strands Agents single-agent** architecture with **Server-Sent Events (SSE) streaming**. The new design replaces `intent.py` and the routing logic in `chat.py` with an autonomous LLM-driven agent backed by Amazon Bedrock Claude 3 Sonnet, while preserving full backward compatibility with the existing `POST /chat` endpoint and `CONVERSATION_TABLE` persistence.

---

## Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend                            │
│                                                         │
│  ChatWindow.tsx                                         │
│    │  fetch POST /chat/stream                           │
│    │  ReadableStream + SSE parser                       │
│    │  Typewriter token accumulation                     │
│    └──► streamChatMessage() in api.ts                   │
└─────────────────────────────────────────────────────────┘
                           │  HTTP SSE  (text/event-stream)
                           ▼
┌─────────────────────────────────────────────────────────┐
│                     Backend                             │
│                                                         │
│  POST /chat/stream  ──►  AgentService.stream_answer()   │
│  POST /chat         ──►  AgentService.answer()   (compat)│
│                                                         │
│  AgentService                                           │
│    ├── Strands Agent (Claude 3 Sonnet via Bedrock)      │
│    └── Registered Tools:                               │
│         ├── query_invoices (DynamoDB)                   │
│         ├── count_invoices_by_status (DynamoDB)         │
│         ├── get_invoice_detail (DynamoDB)               │
│         ├── query_purchase_orders (DynamoDB)            │
│         ├── query_goods_receipts (DynamoDB)             │
│         ├── search_knowledge_base (Bedrock KB)          │
│         └── search_s3_vectors (S3 Vectors)              │
│                                                         │
│  BedrockService                                         │
│    ├── invoke_model()                                   │
│    └── retrieve_and_generate()                          │
│                                                         │
│  DynamoDB CONVERSATION_TABLE  (unchanged schema)        │
└─────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Single agent replaces the classifier**: The Strands Agent uses Claude's native function-calling to decide which tools to invoke. There is no upstream intent classifier — the LLM interprets every question from scratch.

2. **SSE streaming via FastAPI `StreamingResponse`**: The `/chat/stream` endpoint wraps an `async` generator that yields SSE-formatted bytes. This lets the frontend render tokens as they arrive without polling.

3. **`POST /chat` is preserved unchanged**: The existing synchronous endpoint calls `AgentService.answer()` which runs the agent without streaming. Frontend clients that haven't migrated yet continue to work.

4. **Dev-mode fallback**: When `STAGE=dev` or AWS credentials are absent, the agent tools return mock/unavailable responses without calling real AWS services. No code change is required to switch between dev and production behavior.

5. **Persistence after streaming**: Conversation turns are written to DynamoDB *after* the `done` SSE event is pushed. A failure in persistence never affects the already-delivered stream.

---

## Components

### Backend

#### `app/services/agent.py` (new)

The central piece. Implements `AgentService`, which:

- Instantiates a Strands `Agent` at startup using `settings.BEDROCK_MODEL_ID`.
- Registers all seven tools described in the Requirements.
- Exposes `stream_answer(question, session_id, user, category_filter)` — an `async` generator yielding SSE event dicts.
- Exposes `answer(question, session_id, user, category_filter)` — non-streaming wrapper (for backward compat).

```python
# app/services/agent.py

from strands import Agent
from strands.models.bedrock import BedrockModel

from app.config import settings
from app.services.tools import (
    count_invoices_by_status,
    get_invoice_detail,
    query_goods_receipts,
    query_invoices,
    query_purchase_orders,
)

def _build_agent() -> Agent:
    """Initialize the Strands Agent with all registered tools."""
    if not settings.BEDROCK_MODEL_ID:
        raise RuntimeError(
            "BEDROCK_MODEL_ID is not configured. "
            "Set it in .env or environment variables."
        )
    model = BedrockModel(
        model_id=settings.BEDROCK_MODEL_ID,
        region_name=settings.AWS_REGION,
        max_tokens=settings.STRANDS_MAX_TOKENS,
        temperature=settings.STRANDS_TEMPERATURE,
    )
    return Agent(
        model=model,
        tools=[
            query_invoices,
            count_invoices_by_status,
            get_invoice_detail,
            query_purchase_orders,
            query_goods_receipts,
            search_knowledge_base,   # defined below in agent.py
            search_s3_vectors,       # defined below in agent.py
        ],
        system_prompt=_SYSTEM_PROMPT,
    )

# Module-level singleton — initialized once at import time.
_agent: Agent | None = None

def get_agent() -> Agent:
    global _agent
    if _agent is None:
        _agent = _build_agent()
    return _agent
```

**Note**: The module-level singleton is initialized lazily on first request (not at import time) so that unit tests can patch `settings` before the agent is built.

#### `app/services/agent.py` — Tool Functions

The two new tools live in `agent.py` alongside the agent factory:

```python
def search_knowledge_base(query: str, category_filter: str | None = None) -> str:
    """Search the organizational knowledge base for policies, contracts, procedures,
    and guidelines. Use this tool when the user asks about company policy, document
    content, compliance requirements, vendor agreements, or any information that comes
    from stored organizational records rather than live transaction data.

    Parameters
    ----------
    query         : The natural-language question or search phrase.
    category_filter: Optional document category to restrict the search (e.g. "policies").
    """
    kb_id = (settings.KNOWLEDGE_BASE_ID or "").strip()
    is_unavailable = (
        settings.STAGE == "dev"
        or not kb_id
        or kb_id.upper() in ("PLACEHOLDER", "NONE", "N/A")
        or len(kb_id) < 8
    )
    if is_unavailable:
        return (
            "Document search is not available in the local development environment. "
            "Please deploy to AWS with a configured Bedrock Knowledge Base."
        )
    from app.services.bedrock import BedrockService
    svc = BedrockService()
    result = svc.retrieve_and_generate(
        question=query,
        knowledge_base_id=kb_id,
        category_filter=category_filter,
    )
    return result.get("answer", "No relevant information found.")


def search_s3_vectors(query: str) -> str:
    """Perform semantic similarity search over organizational documents stored in
    S3 Vectors. Use this as a supplemental retrieval path when the knowledge base
    does not return relevant results, or when searching for document fragments by
    semantic meaning rather than keyword match.

    Parameters
    ----------
    query : The natural-language search phrase.
    """
    index = (settings.S3_VECTORS_INDEX or "").strip()
    if not index:
        return (
            "S3 Vectors semantic search is not configured. "
            "Set S3_VECTORS_INDEX in environment variables to enable this feature."
        )
    # Production: call S3 Vectors query API
    try:
        import boto3
        client = boto3.client("s3vectors", region_name=settings.AWS_REGION)
        response = client.query_vectors(
            indexName=index,
            queryText=query,
            topK=5,
        )
        fragments = [r.get("text", "") for r in response.get("results", [])]
        return "\n\n".join(fragments) if fragments else "No similar documents found."
    except Exception as exc:
        logger.exception("S3 Vectors query failed")
        return f"Semantic search temporarily unavailable: {exc}"
```

#### `app/routers/chat.py` — Updated

The router is refactored to use `AgentService` instead of `_handle_structured` / `_handle_document` / `classify`. The existing `POST /chat` handler calls `agent_service.answer()`. A new `POST /chat/stream` handler wraps the async generator in `StreamingResponse`.

```python
# POST /chat/stream
@router.post("/stream")
async def post_chat_stream(
    body: ChatRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
):
    session_id = body.session_id or str(uuid.uuid4())

    async def event_generator():
        full_answer_parts: list[str] = []
        citations: list = []
        source_type = "agent"
        data_snapshot = None

        try:
            agent = get_agent()
            async for event in agent.stream_async(body.question):
                if event.get("type") == "text_delta":
                    token = event["content"]
                    full_answer_parts.append(token)
                    yield _sse("token", {"content": token})

            full_answer = "".join(full_answer_parts)

            yield _sse("done", {
                "sessionId": session_id,
                "sourceType": source_type,
                "citations": citations,
                "dataSnapshot": data_snapshot,
            })

        except Exception as exc:
            logger.exception("Agent stream failed for session %s", session_id)
            yield _sse("error", {"message": str(exc)})
            return

        # Persist AFTER the done event
        _persist_both_turns(session_id, user, body.question, full_answer, source_type, citations)

    return StreamingResponse(
        _keepalive_wrapper(event_generator(), interval=15),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

#### SSE Helper Functions

```python
import json

def _sse(event_type: str, payload: dict) -> bytes:
    """Serialize a dict to an SSE data line."""
    data = json.dumps({"type": event_type, **payload})
    return f"data: {data}\n\n".encode()

async def _keepalive_wrapper(gen, interval: int = 15):
    """Wrap an async generator, inserting ping events every `interval` seconds."""
    import asyncio
    async for chunk in gen:
        yield chunk
    # The keepalive is injected during idle gaps in a real implementation
    # using asyncio.wait_for or a concurrent ping task.
```

#### `app/services/bedrock.py` — Full Implementation

```python
# app/services/bedrock.py

import json
import logging
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)


class BedrockService:
    """Wrapper for Amazon Bedrock runtime and Knowledge Base operations."""

    def __init__(self):
        self._runtime = boto3.client(
            "bedrock-runtime", region_name=settings.AWS_REGION
        )
        self._agent_runtime = boto3.client(
            "bedrock-agent-runtime", region_name=settings.AWS_REGION
        )

    def invoke_model(
        self, prompt: str, max_tokens: int = 1024, temperature: float = 0.0
    ) -> str:
        """Invoke the configured Bedrock model and return the text response.

        Parameters
        ----------
        prompt      : Full prompt string sent to the model.
        max_tokens  : Maximum tokens in the response.
        temperature : Sampling temperature (0.0 = deterministic).

        Returns
        -------
        str: The model's text output.

        Raises
        ------
        RuntimeError: Wrapping the original ClientError with context.
        """
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        })
        try:
            response = self._runtime.invoke_model(
                modelId=settings.BEDROCK_MODEL_ID,
                contentType="application/json",
                accept="application/json",
                body=body,
            )
            result = json.loads(response["body"].read())
            return result["content"][0]["text"]
        except ClientError as exc:
            logger.error(
                "BedrockService.invoke_model failed: %s",
                exc.response["Error"]["Code"],
                exc_info=True,
            )
            raise RuntimeError(
                f"Bedrock invoke_model failed: {exc.response['Error']['Message']}"
            ) from exc

    def retrieve_and_generate(
        self,
        question: str,
        knowledge_base_id: str,
        category_filter: str | None = None,
    ) -> dict[str, Any]:
        """Query Bedrock Knowledge Base with retrieve-and-generate.

        Parameters
        ----------
        question           : Natural-language question.
        knowledge_base_id  : The Bedrock KB ID.
        category_filter    : Optional metadata filter on document category.

        Returns
        -------
        dict with keys ``answer`` (str) and ``citations`` (list[dict]).

        Raises
        ------
        RuntimeError: Wrapping the original ClientError.
        """
        kwargs: dict[str, Any] = {
            "input": {"text": question},
            "retrieveAndGenerateConfiguration": {
                "type": "KNOWLEDGE_BASE",
                "knowledgeBaseConfiguration": {
                    "knowledgeBaseId": knowledge_base_id,
                    "modelArn": f"arn:aws:bedrock:{settings.AWS_REGION}::foundation-model/{settings.BEDROCK_MODEL_ID}",
                },
            },
        }
        if category_filter:
            kwargs["retrieveAndGenerateConfiguration"]["knowledgeBaseConfiguration"][
                "retrievalConfiguration"
            ] = {
                "vectorSearchConfiguration": {
                    "filter": {
                        "equals": {"key": "category", "value": category_filter}
                    }
                }
            }
        try:
            response = self._agent_runtime.retrieve_and_generate(**kwargs)
            output = response.get("output", {}).get("text", "")
            citations_raw = response.get("citations", [])
            citations = [
                {
                    "documentName": ref.get("location", {})
                        .get("s3Location", {}).get("uri", "").split("/")[-1],
                    "documentId": ref.get("metadata", {}).get("x-amz-bedrock-kb-source-uri", ""),
                    "snippet": ref.get("content", {}).get("text", ""),
                    "relevanceScore": ref.get("score", 0.0),
                }
                for citation in citations_raw
                for ref in citation.get("retrievedReferences", [])
            ]
            return {"answer": output, "citations": citations}
        except ClientError as exc:
            logger.error(
                "BedrockService.retrieve_and_generate failed: %s",
                exc.response["Error"]["Code"],
                exc_info=True,
            )
            raise RuntimeError(
                f"Bedrock retrieve_and_generate failed: {exc.response['Error']['Message']}"
            ) from exc
```

#### `app/config.py` — New Fields

Three fields added to the `Settings` class:

```python
# Amazon S3 Vectors
S3_VECTORS_INDEX: str = ""          # index name or ARN

# Strands Agent tuning
STRANDS_MAX_TOKENS: int = 4096
STRANDS_TEMPERATURE: float = 0.0
```

### Frontend

#### `src/services/api.ts` — `streamChatMessage`

A new function is added alongside the existing `sendChatMessage` (which is preserved for backward compatibility):

```typescript
export interface SseTokenEvent {
  type: "token";
  content: string;
}

export interface SseDoneEvent {
  type: "done";
  sessionId: string;
  sourceType: string;
  citations: ChatCitation[];
  dataSnapshot?: Record<string, unknown>;
}

export interface SseErrorEvent {
  type: "error";
  message: string;
}

export interface SsePingEvent {
  type: "ping";
}

export type SseEvent = SseTokenEvent | SseDoneEvent | SseErrorEvent | SsePingEvent;

export async function* streamChatMessage(
  question: string,
  sessionId?: string,
  categoryFilter?: string,
  signal?: AbortSignal
): AsyncGenerator<SseEvent> {
  const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
  const body: Record<string, string> = { question };
  if (sessionId) body.sessionId = sessionId;
  if (categoryFilter) body.categoryFilter = categoryFilter;

  const response = await fetch(`${BASE_URL}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      // Auth header injected by an interceptor or passed explicitly
    },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(`Stream request failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() ?? "";

    for (const block of lines) {
      const dataLine = block.split("\n").find((l) => l.startsWith("data: "));
      if (!dataLine) continue;
      try {
        const event = JSON.parse(dataLine.slice(6)) as SseEvent;
        yield event;
      } catch {
        // Malformed event — skip
      }
    }
  }
}
```

#### `src/components/chat/ChatWindow.tsx` — SSE Consumption

The `handleSend` function is rewritten to use `streamChatMessage`. Key changes:

- An `AbortController` is created per request and stored in a `ref` so the drawer's `onClose` can call `abort()`.
- The assistant `Message` is added with empty `content` immediately, then each `token` event appends to it via a functional `setMessages` update.
- On `done`, the message is updated with `citations`, `dataSnapshot`, and `sessionId`.
- On `error` or caught exception, the error banner is shown and `loading` is set to `false`.

```typescript
// Simplified ChatWindow handleSend logic

const abortRef = useRef<AbortController | null>(null);

async function handleSend(question: string) {
  const trimmed = question.trim();
  if (!trimmed || loading) return;

  setError(null);
  setInput("");
  setLoading(true);

  const userMsg: Message = { id: crypto.randomUUID(), role: "user", content: trimmed };
  setMessages((prev) => [...prev, userMsg]);

  const assistantId = crypto.randomUUID();
  setMessages((prev) => [...prev, { id: assistantId, role: "assistant", content: "" }]);

  const controller = new AbortController();
  abortRef.current = controller;

  try {
    for await (const event of streamChatMessage(trimmed, sessionId, undefined, controller.signal)) {
      if (event.type === "token") {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, content: m.content + event.content } : m
          )
        );
      } else if (event.type === "done") {
        if (!sessionId) setSessionId(event.sessionId);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, citations: event.citations, dataSnapshot: event.dataSnapshot }
              : m
          )
        );
      } else if (event.type === "error") {
        setError(event.message);
      }
    }
  } catch (err) {
    if ((err as Error).name !== "AbortError") {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  } finally {
    setLoading(false);
    abortRef.current = null;
    textareaRef.current?.focus();
  }
}
```

The `ChatDrawer` passes an `onAbort` callback or, alternatively, `ChatWindow` exposes the `abortRef` cleanup via a `useEffect` tied to the drawer's `open` prop:

```typescript
// Inside ChatWindow — abort on drawer close
useEffect(() => {
  return () => {
    abortRef.current?.abort();
  };
}, []);
```

---

## Data Models

### SSE Event Schema

All events share the envelope `{ "type": "<event_type>", ...payload }`:

| Event type | Fields | Description |
|---|---|---|
| `token` | `content: string` | Incremental text fragment from Agent |
| `done` | `sessionId`, `sourceType`, `citations[]`, `dataSnapshot?` | Final metadata after answer complete |
| `error` | `message: string` | Agent or infrastructure error |
| `ping` | _(none)_ | Keep-alive, sent every 15 s |

### CONVERSATION_TABLE Record (unchanged)

```
sessionId   : string (PK)
timestamp   : string (SK, ISO-8601 UTC)
userId      : string
role        : "user" | "assistant"
content     : string
intent      : string (set to "agent" for all new records)
source_type : string | null
citations   : list[dict] | null
```

### New Settings Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `S3_VECTORS_INDEX` | `str` | `""` | S3 Vectors index name or ARN |
| `STRANDS_MAX_TOKENS` | `int` | `4096` | Max output tokens per agent invocation |
| `STRANDS_TEMPERATURE` | `float` | `0.0` | Sampling temperature; 0.0 = deterministic |

---

## Interfaces

### `AgentService.stream_answer()`

```python
async def stream_answer(
    question: str,
    session_id: str,
    user: CurrentUser,
    category_filter: str | None = None,
) -> AsyncGenerator[dict, None]:
    """
    Yield SSE event dicts: token events during inference,
    a done event on completion, or an error event on failure.
    """
```

### `AgentService.answer()`

```python
def answer(
    question: str,
    session_id: str,
    user: CurrentUser,
    category_filter: str | None = None,
) -> dict:
    """
    Blocking wrapper that collects all tokens and returns a
    ChatResponse-compatible dict. Used by POST /chat.
    """
```

### `POST /chat/stream` Request

Same schema as `POST /chat` (`ChatRequest`):

```json
{
  "question": "How many escalated invoices are there?",
  "sessionId": "uuid-optional",
  "categoryFilter": "policies"
}
```

### `POST /chat/stream` Response Stream

```
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache

data: {"type": "token", "content": "There are "}

data: {"type": "token", "content": "2 escalated "}

data: {"type": "token", "content": "invoices."}

data: {"type": "done", "sessionId": "abc-123", "sourceType": "agent", "citations": [], "dataSnapshot": {"count": 2}}

```

---

## Error Handling

| Scenario | Behavior |
|---|---|
| `BEDROCK_MODEL_ID` empty at startup | `_build_agent()` raises `RuntimeError`; app startup fails with a clear log message |
| Agent invocation raises `ClientError` | `BedrockService` wraps and re-raises as `RuntimeError`; the SSE generator catches it and yields an `error` event |
| DynamoDB persistence fails | Error is logged at `ERROR` level; stream has already completed and is unaffected |
| Client disconnects mid-stream | FastAPI's `StreamingResponse` propagates the `GeneratorExit`; the async generator terminates cleanly |
| `search_knowledge_base` called in dev mode | Returns fixed unavailability string; the Agent includes this in the final answer |
| `search_s3_vectors` called without index configured | Returns fixed unavailability string |
| SSE stream idle > 15 s | A `ping` event is injected to prevent proxy/load-balancer timeouts |
| Frontend `AbortController.abort()` called | `fetch` raises `AbortError`; the `catch` block in `handleSend` checks `err.name !== "AbortError"` to avoid showing a spurious error banner |

---

## Dev Mode Strategy

When `STAGE=dev` or `USE_MOCKS=true`, the existing `dev_mock.py` activates moto and seeds DynamoDB tables. The Agent's DynamoDB tools (`query_invoices`, etc.) call the moto-backed DynamoDB and return real-looking data. The two document tools (`search_knowledge_base`, `search_s3_vectors`) return fixed unavailability strings because there is no moto equivalent for Bedrock KB or S3 Vectors.

The Strands Agent itself calls Bedrock for LLM inference. In dev mode, callers that don't have Bedrock credentials can either:

1. Set `STAGE=dev` and rely on the mock LLM stub (to be added to `dev_mock.py`), or
2. Provide real `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` credentials with Bedrock access.

A future `dev_mock.py` extension can intercept `bedrock-runtime` with moto (once moto supports `invoke_model`) to provide a fully offline dev experience.

---

## Migration Path

1. **Backend first**: `AgentService` and `POST /chat/stream` are deployed on the `assistant` branch. The existing `POST /chat` endpoint continues to work unchanged — frontend clients are unaffected.

2. **Frontend opt-in**: `streamChatMessage` is added to `api.ts`. `ChatWindow` is switched to use it. The old `sendChatMessage` is kept in `api.ts` until the cut-over is confirmed stable.

3. **`intent.py` preservation**: The file is kept in the repository with a deprecation comment but is no longer imported from `chat.py`. This avoids breaking any internal tools that may reference the module directly.

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Graceful degradation for unconfigured Knowledge Base

*For any* value of `KNOWLEDGE_BASE_ID` that is empty, a known placeholder string (`"PLACEHOLDER"`, `"NONE"`, `"N/A"`), or shorter than 8 characters, calling `search_knowledge_base` with any query string should return a non-empty string (not raise an exception) that communicates unavailability.

**Validates: Requirements 2.3, 2.6**

---

### Property 2: Graceful degradation for unconfigured S3 Vectors index

*For any* falsy or empty value of `S3_VECTORS_INDEX`, calling `search_s3_vectors` with any query string should return a non-empty string (not raise an exception) that communicates the feature is unconfigured.

**Validates: Requirements 2.4**

---

### Property 3: SSE token event serialization preserves content

*For any* non-empty string `token`, the SSE serialization of a token event (`_sse("token", {"content": token})`) should produce a byte string that, when decoded and parsed as JSON, yields an object with `type == "token"` and `content == token` exactly.

**Validates: Requirements 3.2**

---

### Property 4: SSE done event contains all required fields

*For any* combination of `sessionId` (non-empty string), `sourceType` (non-empty string), `citations` (list of zero or more dicts), and optional `dataSnapshot`, the SSE serialization of a done event should produce parseable JSON containing all four keys: `type`, `sessionId`, `sourceType`, and `citations`.

**Validates: Requirements 3.3**

---

### Property 5: Conversation persistence round-trip

*For any* valid `question`/`answer` pair and non-empty `session_id`, after `_persist_both_turns` writes to DynamoDB, querying the `CONVERSATION_TABLE` with that `session_id` should return at least two records: one with `role == "user"` and `content == question`, and one with `role == "assistant"` and `content == answer`. All required fields (`sessionId`, `timestamp`, `userId`, `role`, `content`, `intent`) must be present in each record.

**Validates: Requirements 4.1, 4.5**

---

### Property 6: DynamoDB persistence failure does not propagate to stream

*For any* exception type raised by `DynamoClient.put_item`, the SSE generator (after the `done` event has been yielded) should complete without raising. The caller should not observe an exception from the generator itself.

**Validates: Requirements 4.3**

---

### Property 7: UUID session generation for absent sessionId

*For any* request where `session_id` is `None`, the `session_id` produced internally (and returned in the `done` event) should match the UUID4 format (`xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx`).

**Validates: Requirements 4.5**

---

### Property 8: Token accumulation in ChatWindow

*For any* sequence of N `token` SSE events with content strings `[t1, t2, ..., tN]`, after all events have been processed by the ChatWindow state reducer, the assistant message's `content` field should equal `t1 + t2 + ... + tN` (exact concatenation, preserving order).

**Validates: Requirements 5.2**

---

### Property 9: Error event propagation to UI

*For any* error message string `msg`, after the ChatWindow processes an SSE `error` event with that message, the displayed error banner should contain `msg` and the loading state should be `false`.

**Validates: Requirements 5.4**

---

### Property 10: Fetch abort on drawer close

*For any* active SSE stream (represented by a live `AbortController`), calling `abort()` on the controller should set `loading` to `false` and should not set a user-visible error message (the `AbortError` is swallowed intentionally).

**Validates: Requirements 5.7**

---

### Property 11: BedrockService retrieve_and_generate return shape

*For any* `question` string and valid `knowledge_base_id` (when backed by a mock `bedrock-agent-runtime`), the return value of `BedrockService.retrieve_and_generate()` should always be a dict containing both `"answer"` (a string) and `"citations"` (a list).

**Validates: Requirements 7.2**

---

### Property 12: BedrockService error wrapping

*For any* `ClientError` raised by the underlying boto3 client, calling `invoke_model` or `retrieve_and_generate` should raise an exception (specifically a `RuntimeError`) rather than returning `None` or swallowing the error. The `logger.error` function should be called exactly once per failure.

**Validates: Requirements 7.3**
