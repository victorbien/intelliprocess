"""Records Assistant chat endpoints.

Endpoints
---------
POST /chat
    Classify the question, route to the correct data source, persist both
    turns, and return a structured response.

GET /chat/sessions
    Return the current user's recent sessions, ordered by most-recent activity.

GET /chat/sessions/{session_id}
    Return full message history for one session (owner only).
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from app.config import settings
from app.middleware import AppError, CurrentUser, get_current_user
from app.models.schemas import (
    ApiResponse,
    ChatRequest,
    ChatResponse,
    ChatSessionDetail,
    ChatSessionSummary,
    ChatMessage,
)
from app.services.dynamo import DynamoClient
from app.services.intent import (
    INTENT_DOCUMENT,
    INTENT_HYBRID,
    INTENT_STRUCTURED,
    classify,
)
from app.services.tools import (
    count_invoices_by_status,
    get_invoice_detail,
    query_goods_receipts,
    query_invoices,
    query_purchase_orders,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_conv_db = DynamoClient(settings.CONVERSATION_TABLE)


# ── POST /chat ────────────────────────────────────────────────────────────────


@router.post("", response_model=ApiResponse[ChatResponse])
async def post_chat(
    body: ChatRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Submit a natural-language question to the Records Assistant.

    The endpoint classifies the question, routes to the appropriate handler,
    persists both turns to the conversation table, and returns the answer.
    """
    t_start = time.monotonic()
    session_id = body.session_id or str(uuid.uuid4())
    question = body.question

    # ── Classify intent ───────────────────────────────────────────────────────
    classification = classify(question)
    intent: str = classification["intent"]
    params: dict[str, Any] = classification["params"]
    confidence: float | None = classification["confidence"]

    logger.info(
        "Chat request classified",
        extra={
            "userId": user.user_id[:6] + "****",
            "sessionId": session_id,
            "intent": intent,
            "confidence": confidence,
        },
    )

    # ── Route to handler ──────────────────────────────────────────────────────
    if intent == INTENT_STRUCTURED:
        answer, data_snapshot, citations = _handle_structured(
            question, params, user
        )
        source_type = INTENT_STRUCTURED
        unavailable = None
    elif intent == INTENT_HYBRID:
        # Hybrid: try structured first, document search may be unavailable
        struct_answer, data_snapshot, citations = _handle_structured(
            question, params, user
        )
        doc_answer, doc_unavailable = _handle_document(question, body.category_filter)
        if doc_unavailable:
            answer = struct_answer
            source_type = INTENT_STRUCTURED
            unavailable = None
        else:
            answer = f"{struct_answer}\n\n{doc_answer}"
            source_type = INTENT_HYBRID
            unavailable = None
    else:
        # document_search
        answer, doc_unavailable = _handle_document(question, body.category_filter)
        data_snapshot = None
        citations = []
        source_type = INTENT_DOCUMENT
        unavailable = True if doc_unavailable else None

    elapsed_ms = int((time.monotonic() - t_start) * 1000)

    # ── Persist both turns ────────────────────────────────────────────────────
    now = _utcnow()
    _persist_turn(
        session_id=session_id,
        user_id=user.user_id,
        role="user",
        content=question,
        intent=intent,
        timestamp=now,
    )
    _persist_turn(
        session_id=session_id,
        user_id=user.user_id,
        role="assistant",
        content=answer,
        intent=intent,
        timestamp=_utcnow(),  # slightly after user turn
        citations=[c.model_dump(by_alias=True) for c in citations],
        source_type=source_type,
    )

    return ApiResponse(
        data=ChatResponse(
            answer=answer,
            citations=citations,
            sessionId=session_id,
            sourceType=source_type,
            dataSnapshot=data_snapshot,
            unavailable=unavailable,
            responseTimeMs=elapsed_ms,
        )
    )


# ── GET /chat/sessions ────────────────────────────────────────────────────────


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

        first_msg = next(
            (m["content"] for m in msgs if m.get("role") == "user"), ""
        )
        summaries.append(
            ChatSessionSummary(
                sessionId=session_id,
                firstMessage=first_msg[:120],
                lastActivity=last_ts,
                messageCount=len(msgs),
            )
        )

    return ApiResponse(data=summaries)


# ── GET /chat/sessions/{session_id} ──────────────────────────────────────────


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
    ]

    return ApiResponse(data=ChatSessionDetail(sessionId=session_id, messages=messages))


# ── Handlers ──────────────────────────────────────────────────────────────────


def _handle_structured(
    question: str,
    params: dict[str, Any],
    user: CurrentUser,
) -> tuple[str, dict[str, Any] | None, list]:
    """Route a structured_query to the appropriate tool(s) and format an answer."""
    from app.models.enums import UserRole

    q_lower = question.lower()

    # Determine user scope for invoice queries
    user_scope = (
        user.user_id
        if not user.has_role(UserRole.FINANCE_MANAGER, UserRole.ADMIN)
        else None
    )

    # ── PO lookup ────────────────────────────────────────────────────────────
    po_number = params.get("po_number")
    if po_number or any(k in q_lower for k in ("purchase order", " po ", "po-")):
        result = query_purchase_orders(po_number=po_number)
        if result["count"] == 0:
            answer = f"No purchase orders found{_po_qualifier(po_number)}."
        else:
            pos = result["purchase_orders"]
            lines = [
                f"- {p['poNumber']}: {p.get('vendorName', 'Unknown')} — "
                f"{p.get('status', 'Unknown')} — ${_fmt(p.get('totalAmount', 0))}"
                for p in pos[:10]
            ]
            answer = (
                f"Found {result['count']} purchase order(s)"
                f"{_po_qualifier(po_number)}:\n" + "\n".join(lines)
            )
            # If there's a PO, also show GRs
            if po_number:
                gr_result = query_goods_receipts(po_number)
                if gr_result["count"] > 0:
                    gr_status = "complete" if gr_result["all_complete"] else "pending"
                    answer += (
                        f"\n\nGoods receipt for {po_number}: "
                        f"{gr_result['count']} receipt(s), status: {gr_status}."
                    )
        snapshot = {"purchase_orders": result["count"]}
        return answer, snapshot, []

    # ── Goods receipt lookup ─────────────────────────────────────────────────
    if any(k in q_lower for k in ("goods receipt", " gr ", "gr-", "received", "delivery")):
        if po_number:
            result = query_goods_receipts(po_number)
            if result["count"] == 0:
                answer = f"No goods receipts found for {po_number}."
            else:
                status_word = "complete" if result["all_complete"] else "pending"
                answer = (
                    f"Found {result['count']} goods receipt(s) for {po_number}. "
                    f"All receipts are {status_word}."
                )
            snapshot = {"po_number": po_number, "receipts": result["count"]}
            return answer, snapshot, []

    # ── "how many" / count questions ─────────────────────────────────────────
    if any(k in q_lower for k in ("how many", "count", "total number", "number of")):
        # If a specific status was extracted, use query_invoices for accuracy
        status = params.get("status")
        if status:
            result = query_invoices(
                status=status,
                vendor_name=_scope_vendor(params, user_scope),
            )
            answer = (
                f"There are {result['count']} invoice(s) with status {status}."
            )
            if result["total_amount"] > 0:
                answer += f" Total amount: ${_fmt(result['total_amount'])}."
            snapshot = {
                "status": status,
                "count": result["count"],
                "total_amount": result["total_amount"],
            }
        else:
            # Return full status breakdown
            counts = count_invoices_by_status()
            total = sum(counts.values())
            lines = [f"  {s}: {n}" for s, n in sorted(counts.items())]
            answer = f"There are {total} invoice(s) in total:\n" + "\n".join(lines)
            snapshot = {"counts_by_status": counts, "total": total}
        return answer, snapshot, []

    # ── Invoice queries (with optional status / vendor / amount) ─────────────
    status = params.get("status")
    vendor_name = params.get("vendor_name")
    amount_min = params.get("amount_min")
    amount_max = params.get("amount_max")

    # Apply user scope: AP clerks only see their own invoices
    # tools.query_invoices handles uploadedBy filtering via GSI-UserDate when
    # status is None; when status is set it fetches by GSI then filters below.
    result = query_invoices(
        status=status,
        vendor_name=vendor_name,
        amount_min=amount_min,
        amount_max=amount_max,
    )

    # For AP_CLERK, filter results to own invoices
    if user_scope:
        result["invoices"] = [
            inv for inv in result["invoices"]
            if inv.get("uploadedBy") == user_scope
        ]
        result["count"] = len(result["invoices"])
        result["total_amount"] = sum(
            float(inv.get("extraction", {}).get("totalAmount", 0) or 0)
            for inv in result["invoices"]
        )

    if result["count"] == 0:
        answer = "No invoices found matching your criteria."
    else:
        qualifier_parts: list[str] = []
        if status:
            qualifier_parts.append(f"status {status}")
        if vendor_name:
            qualifier_parts.append(f"vendor containing '{vendor_name}'")
        if amount_min:
            qualifier_parts.append(f"amount ≥ ${_fmt(amount_min)}")
        if amount_max:
            qualifier_parts.append(f"amount ≤ ${_fmt(amount_max)}")
        qualifier = f" ({', '.join(qualifier_parts)})" if qualifier_parts else ""

        answer = (
            f"Found {result['count']} invoice(s){qualifier}. "
            f"Total amount: ${_fmt(result['total_amount'])}."
        )

        # Show up to 5 invoice summaries
        preview = result["invoices"][:5]
        if preview:
            lines = []
            for inv in preview:
                ext = inv.get("extraction") or {}
                vendor = ext.get("vendorName", "Unknown vendor")
                amount = ext.get("totalAmount", 0) or 0
                lines.append(
                    f"  - {inv.get('fileName', inv['documentId'])}: "
                    f"{vendor} — ${_fmt(amount)} — {inv['status']}"
                )
            answer += "\n\n" + "\n".join(lines)
            if result["count"] > 5:
                answer += f"\n  … and {result['count'] - 5} more."

    snapshot = {
        "count": result["count"],
        "total_amount": result["total_amount"],
        "filters": {k: v for k, v in {
            "status": status,
            "vendor_name": vendor_name,
            "amount_min": amount_min,
            "amount_max": amount_max,
        }.items() if v is not None},
    }
    return answer, snapshot, []


def _handle_document(
    question: str,
    category_filter: str | None,
) -> tuple[str, bool]:
    """Handle a document_search intent.

    Returns (answer_text, is_unavailable).
    When running in dev mode or KNOWLEDGE_BASE_ID is not a real KB ID
    (empty, unset, or placeholder), returns a polite unavailable message.
    """
    kb_id = (settings.KNOWLEDGE_BASE_ID or "").strip()
    # Treat empty strings, "PLACEHOLDER", and any non-UUID-like value < 8 chars
    # as unconfigured. A real Bedrock KB ID looks like "abc12345-...".
    is_placeholder = not kb_id or kb_id.upper() in ("PLACEHOLDER", "NONE", "N/A") or len(kb_id) < 8
    if settings.STAGE == "dev" or is_placeholder:
        return (
            "Document search is not available in the local development environment. "
            "Please deploy to AWS with a configured Bedrock Knowledge Base to use "
            "this feature.",
            True,
        )

    # Production path — delegate to Bedrock service
    try:
        from app.services.bedrock import BedrockService  # noqa: PLC0415
        client = BedrockService()
        result = client.retrieve_and_generate(
            question=question,
            knowledge_base_id=kb_id,
            category_filter=category_filter,
        )
        return result.get("answer", "No relevant information found."), False
    except Exception:
        logger.exception("Bedrock retrieve_and_generate failed")
        raise AppError(
            "The AI service is temporarily unavailable. Please try again in a few seconds.",
            status_code=503,
        )


# ── Persistence ───────────────────────────────────────────────────────────────


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
        logger.exception(
            "Failed to persist conversation turn",
            extra={"sessionId": session_id, "role": role},
        )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fmt(value: float | int | None) -> str:
    """Format a numeric amount with commas and 2 decimal places."""
    if value is None:
        return "0.00"
    return f"{float(value):,.2f}"


def _po_qualifier(po_number: str | None) -> str:
    return f" for {po_number}" if po_number else ""


def _scope_vendor(params: dict, user_scope: str | None) -> str | None:
    """Return vendor_name param, or None if not present."""
    return params.get("vendor_name")
