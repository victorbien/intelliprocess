"""Records Assistant chat endpoints.

Endpoints
---------
POST /chat          Synchronous chat via AgentService (backward compatible).
POST /chat/stream   SSE streaming chat via AgentService.
GET  /chat/sessions List user sessions.
GET  /chat/sessions/{session_id} Session detail.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import StreamingResponse

from app.config import settings
from app.middleware import AppError, CurrentUser, get_current_user
from app.models.schemas import (
    ApiResponse,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatSessionDetail,
    ChatSessionSummary,
    ChatSummaryResponse,
)
from app.services.agent import AgentService
from app.services.bedrock import BedrockService
from app.services.dynamo import DynamoClient

logger = logging.getLogger(__name__)
router = APIRouter()

_conv_db = DynamoClient(settings.CONVERSATION_TABLE)


# -- SSE Helpers ---------------------------------------------------------------


def _sse(event_type: str, payload: dict) -> bytes:
    """Serialize an event dict to SSE data line bytes."""
    data = json.dumps({"type": event_type, **payload})
    return f"data: {data}\n\n".encode()


async def _keepalive_wrapper(gen, interval: int = 15):
    """Wrap an async generator, injecting ping events during idle periods."""
    ping = b'data: {"type": "ping"}\n\n'
    try:
        ait = gen.__aiter__()
        while True:
            try:
                chunk = await asyncio.wait_for(ait.__anext__(), timeout=interval)
                yield chunk
            except asyncio.TimeoutError:
                yield ping
            except StopAsyncIteration:
                break
    except GeneratorExit:
        pass


# -- POST /chat/stream ---------------------------------------------------------


@router.post("/stream")
async def post_chat_stream(
    body: ChatRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """SSE streaming endpoint for the Records Assistant."""
    session_id = body.session_id or str(uuid.uuid4())

    async def event_generator():
        full_answer_parts: list[str] = []
        try:
            async for event in AgentService.stream_answer(
                question=body.question,
                session_id=session_id,
                user=user,
                category_filter=body.category_filter,
            ):
                if event["type"] == "token":
                    full_answer_parts.append(event["content"])
                    yield _sse("token", {"content": event["content"]})
                elif event["type"] == "done":
                    yield _sse("done", {
                        "sessionId": event["sessionId"],
                        "sourceType": event["sourceType"],
                        "citations": event["citations"],
                        "dataSnapshot": event.get("dataSnapshot"),
                    })
                elif event["type"] == "error":
                    yield _sse("error", {"message": event["message"]})
                    return
        except Exception as exc:
            logger.exception("Stream failed for session %s", session_id)
            yield _sse("error", {"message": str(exc)})
            return

        # Persist after done event
        full_answer = "".join(full_answer_parts)
        _persist_both_turns(
            session_id=session_id,
            user_id=user.user_id,
            question=body.question,
            answer=full_answer,
        )

    return StreamingResponse(
        _keepalive_wrapper(event_generator(), interval=15),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# -- POST /chat (backward compatible) -----------------------------------------


@router.post("", response_model=ApiResponse[ChatResponse])
async def post_chat(
    body: ChatRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Submit a question to the Records Assistant (synchronous response)."""
    t_start = time.monotonic()
    session_id = body.session_id or str(uuid.uuid4())

    result = await AgentService.answer(
        question=body.question,
        session_id=session_id,
        user=user,
        category_filter=body.category_filter,
    )

    elapsed_ms = int((time.monotonic() - t_start) * 1000)

    # Persist both turns
    _persist_both_turns(
        session_id=session_id,
        user_id=user.user_id,
        question=body.question,
        answer=result["answer"],
    )

    return ApiResponse(
        data=ChatResponse(
            answer=result["answer"],
            citations=[],
            sessionId=session_id,
            sourceType="agent",
            dataSnapshot=None,
            unavailable=None,
            responseTimeMs=elapsed_ms,
        )
    )


# -- GET /chat/sessions --------------------------------------------------------


@router.get("/sessions", response_model=ApiResponse[list[ChatSessionSummary]])
async def list_sessions(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: int = Query(10, ge=1, le=50),
):
    """Return the current user's recent chat sessions ordered by last activity."""
    try:
        response = _conv_db.table.query(
            IndexName="GSI-UserSessions",
            KeyConditionExpression=Key("userId").eq(user.user_id),
            ScanIndexForward=False,  # most-recent first
            Limit=limit * 10,  # fetch more keys than needed; we group below
        )
        items = response.get("Items", [])
    except ClientError as e:
        logger.error("Failed to query sessions for user %s: %s", user.user_id[:6], str(e))
        raise AppError("Failed to retrieve sessions.", status_code=500)

    # Group by sessionId and take the most-recent timestamp per session
    seen: dict[str, str] = {}  # sessionId -> most-recent timestamp
    for item in items:
        sid = item["sessionId"]
        ts = item["timestamp"]
        if sid not in seen or ts > seen[sid]:
            seen[sid] = ts

    # Sort sessions by last activity descending and cap at limit
    sorted_sessions = sorted(seen.items(), key=lambda x: x[1], reverse=True)[:limit]

    summaries: list[ChatSessionSummary] = []
    for session_id, last_ts in sorted_sessions:
        # Fetch the first user message for the preview and count messages
        try:
            detail_resp = _conv_db.table.query(
                KeyConditionExpression=Key("sessionId").eq(session_id),
                ScanIndexForward=True,
                Limit=100,
            )
            msgs = detail_resp.get("Items", [])
        except ClientError:
            msgs = []

        # Separate the stored summary record (if any) from conversation turns.
        turns = [m for m in msgs if m.get("role") != "summary"]
        summary_item = next(
            (m for m in msgs if m.get("role") == "summary"), None
        )

        first_msg = next(
            (m["content"] for m in turns if m.get("role") == "user"), ""
        )
        summaries.append(
            ChatSessionSummary(
                sessionId=session_id,
                firstMessage=first_msg[:120],
                lastActivity=last_ts,
                messageCount=len(turns),
                summary=summary_item.get("content") if summary_item else None,
                summaryGeneratedAt=(
                    summary_item.get("generatedAt") if summary_item else None
                ),
            )
        )

    return ApiResponse(data=summaries)


# -- GET /chat/sessions/{session_id} -------------------------------------------


@router.get(
    "/sessions/{session_id}",
    response_model=ApiResponse[ChatSessionDetail],
)
async def get_session(
    session_id: Annotated[str, Path(min_length=1, max_length=64)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Return the full message history for a session (owner only)."""
    try:
        response = _conv_db.table.query(
            KeyConditionExpression=Key("sessionId").eq(session_id),
            ScanIndexForward=True,
        )
        items = response.get("Items", [])
    except ClientError as e:
        logger.error("Failed to fetch session %s: %s", session_id, str(e))
        raise AppError("Failed to retrieve session.", status_code=500)

    if not items:
        raise AppError("Session not found.", status_code=404)

    # Ownership check — every turn stores userId; check the first one
    if items[0].get("userId") != user.user_id:
        raise AppError("Insufficient permissions for this action.", status_code=403)

    messages = [
        ChatMessage(
            role=item["role"],
            content=item["content"],
            timestamp=item["timestamp"],
            citations=item.get("citations"),
            sourceType=item.get("source_type"),
        )
        for item in items
        if item.get("role") != "summary"
    ]

    return ApiResponse(data=ChatSessionDetail(sessionId=session_id, messages=messages))


# -- POST /chat/sessions/{session_id}/summary ----------------------------------


@router.post(
    "/sessions/{session_id}/summary",
    response_model=ApiResponse[ChatSummaryResponse],
)
async def summarize_session(
    session_id: Annotated[str, Path(min_length=1, max_length=64)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Generate and store an AI summary of a session (owner only).

    Loads the session's conversation turns, generates a summary via
    ``BedrockService.invoke_model``, and persists it as a dedicated summary
    record. The summary is generated first and persisted only on success, so a
    model failure leaves ``CONVERSATION_TABLE`` unchanged (Req 6.5).
    """
    try:
        response = _conv_db.table.query(
            KeyConditionExpression=Key("sessionId").eq(session_id),
            ScanIndexForward=True,
        )
        items = response.get("Items", [])
    except ClientError as e:
        logger.error("Failed to fetch session %s: %s", session_id, str(e))
        raise AppError("Failed to retrieve session.", status_code=500)

    if not items:
        raise AppError("Session not found.", status_code=404)

    # Ownership check — every turn stores userId; check the first one
    if items[0].get("userId") != user.user_id:
        raise AppError("Insufficient permissions for this action.", status_code=403)

    # Consider only user/assistant conversation turns for the transcript.
    turns = [item for item in items if item.get("role") in ("user", "assistant")]
    if not turns:
        raise AppError("Session has no messages to summarize.", status_code=404)

    transcript = "\n".join(
        f"{turn.get('role')}: {turn.get('content', '')}" for turn in turns
    )
    prompt = (
        "Summarize the following conversation between a user and the "
        "Records Assistant. Capture the key questions asked and the main "
        "information or answers provided, in a few concise sentences.\n\n"
        f"{transcript}"
    )

    # Generate first; persist only on success (Req 6.5).
    summary = BedrockService().invoke_model(prompt, max_tokens=512)

    generated_at = _persist_summary(
        session_id=session_id,
        user_id=user.user_id,
        summary=summary,
    )

    return ApiResponse(
        data=ChatSummaryResponse(
            sessionId=session_id,
            summary=summary,
            generatedAt=generated_at,
        )
    )


# -- Persistence ---------------------------------------------------------------


def _persist_both_turns(
    session_id: str,
    user_id: str,
    question: str,
    answer: str,
) -> None:
    """Write user and assistant turns to CONVERSATION_TABLE. Failures logged only."""
    now = _utcnow()
    _persist_turn(
        session_id=session_id,
        user_id=user_id,
        role="user",
        content=question,
        intent="agent",
        timestamp=now,
    )
    _persist_turn(
        session_id=session_id,
        user_id=user_id,
        role="assistant",
        content=answer,
        intent="agent",
        timestamp=_utcnow(),
        source_type="agent",
    )


def _persist_summary(session_id: str, user_id: str, summary: str) -> str:
    """Write a conversation summary record to CONVERSATION_TABLE.

    The summary is stored as a distinct item sharing the session partition key,
    marked by ``role = "summary"``. Its sort key uses the reserved prefix
    ``zzz-summary#`` so it sorts after ordinary ISO-8601 turn timestamps and
    never interleaves with conversation history.

    Returns
    -------
    str
        The ISO-8601 generation timestamp associated with the summary.
    """
    generated_at = _utcnow()
    _conv_db.put_item(
        {
            "sessionId": session_id,
            "timestamp": f"zzz-summary#{generated_at}",
            "userId": user_id,
            "role": "summary",
            "content": summary,
            "generatedAt": generated_at,
        }
    )
    return generated_at


def _persist_turn(
    session_id: str,
    user_id: str,
    role: str,
    content: str,
    intent: str,
    timestamp: str,
    citations: list | None = None,
    source_type: str | None = None,
) -> None:
    """Write a single conversation turn to CONVERSATION_TABLE.

    Failures are logged but do not surface to the caller — a persistence
    hiccup should not fail the chat response.
    """
    item: dict[str, Any] = {
        "sessionId": session_id,
        "timestamp": timestamp,
        "userId": user_id,
        "role": role,
        "content": content,
        "intent": intent,
    }
    if citations:
        item["citations"] = citations
    if source_type:
        item["source_type"] = source_type

    try:
        _conv_db.put_item(item)
    except Exception:
        logger.error(
            "Failed to persist conversation turn",
            extra={"sessionId": session_id, "role": role},
            exc_info=True,
        )


# -- Helpers -------------------------------------------------------------------


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()
