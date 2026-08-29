# Implementation Plan: AI Assistant (Strands Agent + SSE Streaming)

## Overview

Replace the keyword-classifier routing in `chat.py` with a Strands Agents single-agent
architecture backed by Amazon Bedrock Claude 3 Sonnet. Add a `POST /chat/stream` SSE
endpoint, implement `BedrockService`, wire all seven tools into the agent, migrate
conversation persistence, and update the frontend `ChatWindow` to consume the SSE
stream with a typewriter effect. The existing `POST /chat` endpoint is preserved
throughout for backward compatibility.

## Tasks

- [x] 1. Add dependencies and extend configuration
  - [x] 1.1 Add `strands-agents` to `backend/requirements.txt`
    - Pin version (e.g. `strands-agents==0.1.*`) so CI is reproducible
    - Add `hypothesis` to `backend/requirements-dev.txt` for property-based tests
    - _Requirements: 1.1, 6.1–6.5_

  - [x] 1.2 Add new `Settings` fields to `app/config.py`
    - Add `S3_VECTORS_INDEX: str = ""`
    - Add `STRANDS_MAX_TOKENS: int = 4096`
    - Add `STRANDS_TEMPERATURE: float = 0.0`
    - All three must have defaults so the app starts with zero config changes
    - _Requirements: 6.1, 6.2, 6.3, 6.5_

  - [x] 1.3 Update `.env.example` with the three new fields
    - Add `S3_VECTORS_INDEX=` with a comment describing the index name or ARN
    - Add `STRANDS_MAX_TOKENS=4096` with a comment
    - Add `STRANDS_TEMPERATURE=0.0` with a comment
    - _Requirements: 6.4_

- [x] 2. Implement `BedrockService` in `app/services/bedrock.py`
  - [x] 2.1 Implement `BedrockService.__init__` and `invoke_model`
    - Initialize `bedrock-runtime` boto3 client using `settings.AWS_REGION`
    - Implement `invoke_model(prompt, max_tokens, temperature) -> str` using
      the Anthropic Claude messages API body format
    - Wrap `ClientError` in a `RuntimeError` with context message; log at `ERROR`
    - _Requirements: 7.1, 7.3, 7.4_

  - [x] 2.2 Implement `BedrockService.retrieve_and_generate`
    - Initialize `bedrock-agent-runtime` boto3 client using `settings.AWS_REGION`
    - Implement `retrieve_and_generate(question, knowledge_base_id, category_filter) -> dict`
    - Apply optional `vectorSearchConfiguration` filter when `category_filter` is provided
    - Return `{"answer": str, "citations": list[dict]}` — normalize citation fields
      (`documentName`, `documentId`, `snippet`, `relevanceScore`)
    - Wrap `ClientError` in `RuntimeError` with context; log at `ERROR`
    - _Requirements: 7.2, 7.3, 7.4_

  - [ ]* 2.3 Write property tests for `BedrockService`
    - **Property 11: `retrieve_and_generate` return shape** — mock `bedrock-agent-runtime`,
      call `retrieve_and_generate` with any `question` and valid KB ID, assert result is a
      `dict` with keys `"answer"` (str) and `"citations"` (list)
    - **Property 12: error wrapping** — for any `ClientError` raised by the boto3 mock,
      assert `invoke_model` and `retrieve_and_generate` raise `RuntimeError` (not return
      `None`) and that `logger.error` is called exactly once
    - **Validates: Requirements 7.2, 7.3**

- [x] 3. Create `app/services/agent.py` — AgentService and tool registration
  - [x] 3.1 Implement `search_knowledge_base` and `search_s3_vectors` tool functions
    - `search_knowledge_base(query, category_filter=None) -> str`: check `STAGE`,
      `KNOWLEDGE_BASE_ID` validity (empty / placeholder / len < 8), return unavailability
      string without raising; otherwise call `BedrockService.retrieve_and_generate`
    - `search_s3_vectors(query) -> str`: check `S3_VECTORS_INDEX`, return unavailability
      string if empty; otherwise call `boto3.client("s3vectors").query_vectors` with
      `topK=5`; wrap any exception into a string instead of raising
    - Both functions must have docstrings written as LLM tool descriptions (natural
      language, explaining when Claude should call them)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ]* 3.2 Write property tests for graceful degradation tools
    - **Property 1: `search_knowledge_base` graceful degradation** — use `hypothesis`,
      for any `KNOWLEDGE_BASE_ID` that is empty, `"PLACEHOLDER"`, `"NONE"`, `"N/A"`,
      or has `len < 8`, assert the function returns a non-empty string and does not
      raise; run across random `query` strings
    - **Property 2: `search_s3_vectors` graceful degradation** — for any falsy or empty
      `S3_VECTORS_INDEX`, assert the function returns a non-empty string and does not
      raise; run across random `query` strings
    - **Validates: Requirements 2.3, 2.4**

  - [x] 3.3 Implement `_build_agent` factory and `get_agent` singleton
    - Instantiate `BedrockModel` with `model_id`, `region_name`, `max_tokens`,
      `temperature` from settings
    - Register all seven tools: the five DynamoDB tools imported from `tools.py`
      plus `search_knowledge_base` and `search_s3_vectors` defined in this module
    - Raise `RuntimeError` with a clear message if `BEDROCK_MODEL_ID` is empty
    - Use a module-level `_agent: Agent | None = None` singleton initialized lazily
      by `get_agent()` (not at import time, so tests can patch settings first)
    - _Requirements: 1.1, 1.2, 1.3, 1.6_

  - [x] 3.4 Implement `AgentService.stream_answer` async generator
    - Accept `(question, session_id, user, category_filter=None)`
    - Call `get_agent()`, then iterate `agent.stream_async(question)`
    - For each event where `event["type"] == "text_delta"`, yield
      `{"type": "token", "content": event["content"]}`
    - After the loop, yield `{"type": "done", "sessionId": session_id, "sourceType": "agent",
      "citations": [], "dataSnapshot": None}`
    - On any exception, yield `{"type": "error", "message": str(exc)}` and return
    - _Requirements: 1.4, 3.2, 3.3, 3.4_

  - [x] 3.5 Implement `AgentService.answer` blocking wrapper
    - Collect all tokens from `stream_answer` into a single string
    - Return a `dict` compatible with the `ChatResponse` schema:
      `{"answer": str, "citations": [], "source_type": "agent"}`
    - _Requirements: 3.5 (backward compat for `POST /chat`)_

- [x] 4. Implement SSE helpers and `POST /chat/stream` endpoint in `app/routers/chat.py`
  - [x] 4.1 Add `_sse` serializer and `_keepalive_wrapper` to `chat.py`
    - `_sse(event_type, payload) -> bytes`: serialize to `data: {JSON}\n\n` bytes
    - `_keepalive_wrapper(gen, interval=15)`: async generator that injects
      `data: {"type": "ping"}\n\n` every `interval` seconds using `asyncio.wait_for`
      or a concurrent ping task; never drops real events
    - _Requirements: 3.1, 3.6_

  - [ ]* 4.2 Write property tests for SSE serialization
    - **Property 3: token event serialization** — for any non-empty `token` string,
      assert `_sse("token", {"content": token})` round-trips to `{"type": "token",
      "content": token}` exactly
    - **Property 4: done event required fields** — for any `sessionId`, `sourceType`,
      `citations` list, and optional `dataSnapshot`, assert the serialized done event
      parses to a dict containing all four keys: `type`, `sessionId`, `sourceType`,
      `citations`
    - **Validates: Requirements 3.2, 3.3**

  - [x] 4.3 Add `POST /chat/stream` route using `StreamingResponse`
    - Import and use `AgentService.stream_answer` as the event source
    - Generate a new UUID session ID when `body.session_id` is empty
      (UUID4 format: `xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx`)
    - Wrap the generator with `_keepalive_wrapper`
    - Set headers: `Content-Type: text/event-stream`, `Cache-Control: no-cache`,
      `X-Accel-Buffering: no`
    - Apply the same `get_current_user` Cognito auth dependency as `POST /chat`
    - Accept the same `ChatRequest` body (`question`, `sessionId`, `categoryFilter`)
    - _Requirements: 3.1, 3.7, 4.5_

  - [ ]* 4.4 Write property test for UUID session generation
    - **Property 7: UUID session generation for absent sessionId** — for any request
      where `session_id` is `None`, assert the generated session ID matches the UUID4
      regex pattern
    - **Validates: Requirements 4.5**

- [x] 5. Migrate conversation persistence to the new architecture
  - [x] 5.1 Add `_persist_both_turns` helper to `chat.py`
    - Extract a single helper that writes user and assistant turns back-to-back
    - Use `intent="agent"` for all records written by the new endpoint
    - Match the exact field set of the existing `_persist_turn`:
      `sessionId`, `timestamp`, `userId`, `role`, `content`, `intent`,
      `citations` (optional), `source_type` (optional)
    - Log `DynamoClient.put_item` failures at `ERROR` level; never re-raise
    - Call this helper in the SSE generator **after** the `done` event is yielded
    - _Requirements: 4.1, 4.2, 4.3_

  - [ ]* 5.2 Write property tests for conversation persistence
    - **Property 5: persistence round-trip** — using a moto-backed DynamoDB table,
      call `_persist_both_turns` with any `question`/`answer` pair, then query
      `CONVERSATION_TABLE` by `session_id`; assert at least two records exist with
      the correct `role` and `content` values and all required fields present
    - **Property 6: DynamoDB failure does not propagate** — patch
      `DynamoClient.put_item` to raise an arbitrary exception; assert
      `_persist_both_turns` does not raise and returns `None`
    - **Validates: Requirements 4.1, 4.3**

- [x] 6. Refactor `POST /chat` to use `AgentService` (backward compatibility)
  - [x] 6.1 Replace `_handle_structured` / `_handle_document` / `classify` calls in
    `post_chat` with `AgentService.answer`
    - Remove imports of `classify`, `INTENT_DOCUMENT`, `INTENT_HYBRID`,
      `INTENT_STRUCTURED` from `chat.py`
    - Keep `intent.py` in the repository — add a deprecation comment at the top
      of the file; do not delete it
    - `source_type` in the persisted record and response is set to `"agent"`
    - All other `ChatResponse` fields (`citations`, `dataSnapshot`, `unavailable`,
      `responseTimeMs`) remain in the response schema; fill `citations=[]`,
      `dataSnapshot=None`, `unavailable=None` from the blocking agent answer
    - _Requirements: 1.4, 1.5, 3.5_

- [x] 7. Checkpoint — backend integration
  - Ensure all pytest tests pass: `pytest backend/tests/ -x`
  - Confirm `POST /chat` still returns a valid `ChatResponse` (backward compat)
  - Confirm `POST /chat/stream` returns `text/event-stream` with `token` and
    `done` events when called with mock credentials
  - Ask the user if questions arise before continuing to the frontend.

- [x] 8. Add `streamChatMessage` to `frontend/src/services/api.ts`
  - [x] 8.1 Define SSE event TypeScript interfaces
    - `SseTokenEvent`, `SseDoneEvent`, `SseErrorEvent`, `SsePingEvent`, `SseEvent`
      union type
    - Extend `ChatCitation` if needed to cover fields returned by `done` event
    - _Requirements: 5.1, 5.5_

  - [x] 8.2 Implement `streamChatMessage` async generator function
    - Signature: `async function* streamChatMessage(question, sessionId?, categoryFilter?, signal?): AsyncGenerator<SseEvent>`
    - Use `fetch` (not axios) with `POST /chat/stream`, passing `Authorization`
      header from the same auth token source used by the existing axios instance
    - Parse the `ReadableStream` with `response.body.getReader()` and
      `TextDecoder`, buffering on `\n\n` boundaries
    - Skip malformed `data:` lines silently; yield typed `SseEvent` objects
    - Throw a descriptive `Error` when `response.ok` is `false`
    - Keep `sendChatMessage` (axios) unchanged for backward compatibility
    - _Requirements: 5.1, 5.5_

- [x] 9. Update `ChatWindow.tsx` for SSE streaming
  - [x] 9.1 Add `AbortController` ref and drawer-close abort logic
    - Add `abortRef = useRef<AbortController | null>(null)`
    - In the `useEffect` cleanup (component unmount), call `abortRef.current?.abort()`
    - _Requirements: 5.7_

  - [x] 9.2 Rewrite `handleSend` to consume `streamChatMessage`
    - Create a new `AbortController` per send, store in `abortRef`
    - Add an empty assistant `Message` (with a stable `id`) immediately after the
      user message so the typewriter effect starts rendering right away
    - For `type === "token"`: use a functional `setMessages` update to append
      `event.content` to the correct assistant message by its `id`
    - For `type === "done"`: update the assistant message with `citations`,
      `dataSnapshot`; set `sessionId` if it was absent
    - For `type === "error"`: call `setError(event.message)`; set `loading = false`
    - Catch `AbortError` silently; surface all other errors in the error banner
    - Disable the send button (`canSend`) while the stream is active (same as
      existing `loading` flag)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.6_

  - [ ]* 9.3 Write Vitest unit tests for `ChatWindow` SSE consumption
    - Mock `streamChatMessage` to yield a controlled sequence of token, done, and
      error events
    - **Property 8: token accumulation** — for N token events with contents
      `[t1…tN]`, assert the assistant message's final `content === t1 + … + tN`
    - **Property 9: error event propagation** — for an error event with any `msg`,
      assert the error banner shows `msg` and `loading` is `false`
    - **Property 10: AbortController on unmount** — assert `abort()` is called when
      the component unmounts during an active stream; no error banner is shown
    - _Requirements: 5.2, 5.4, 5.7_

- [x] 10. Add dev-mode mock fallback for Strands Agent in `dev_mock.py`
  - [x] 10.1 Add a mock LLM stub to `dev_mock.py` for offline development
    - When `STAGE=dev` and `USE_MOCKS=True`, patch `BedrockModel` (or the
      underlying `bedrock-runtime` client via moto) to return a canned streaming
      response so developers without Bedrock credentials can test the SSE flow
    - The stub should yield two or three token events then a done event, simulating
      a real agent response
    - _Requirements: 1.6 (dev fallback), Design Dev Mode Strategy_

- [x] 11. Final checkpoint — full stack
  - Ensure all backend tests pass: `pytest backend/tests/ -x`
  - Ensure all frontend tests pass: `npx vitest --run`
  - Confirm typewriter rendering works end-to-end in the dev environment
  - Confirm `GET /chat/sessions` and `GET /chat/sessions/{session_id}` still work
    without modification
  - Ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP delivery
- Property tests use `hypothesis` (backend) and Vitest (frontend)
- `intent.py` is preserved with a deprecation comment — it is never deleted
- `sendChatMessage` in `api.ts` is preserved — new code uses `streamChatMessage`
- The `intent` field in new `CONVERSATION_TABLE` records is always `"agent"`
- All `_persist_turn` / `_persist_both_turns` failures are logged only — they
  never affect the already-delivered stream response
- S3 Vectors requires the `s3vectors` boto3 service name; verify availability in the
  pinned `boto3==1.35.*` version before task 3.1 is executed

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["2.1", "2.2"] },
    { "id": 2, "tasks": ["2.3", "3.1"] },
    { "id": 3, "tasks": ["3.2", "3.3"] },
    { "id": 4, "tasks": ["3.4", "3.5"] },
    { "id": 5, "tasks": ["4.1", "5.1"] },
    { "id": 6, "tasks": ["4.2", "4.3", "5.2"] },
    { "id": 7, "tasks": ["4.4", "6.1"] },
    { "id": 8, "tasks": ["8.1"] },
    { "id": 9, "tasks": ["8.2"] },
    { "id": 10, "tasks": ["9.1", "9.2"] },
    { "id": 11, "tasks": ["9.3", "10.1"] }
  ]
}
```
