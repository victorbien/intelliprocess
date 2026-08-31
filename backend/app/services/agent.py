"""Strands Agent service - tool registration and agent lifecycle."""

from __future__ import annotations

import logging
import re
from typing import Any, AsyncGenerator

import boto3
from strands import Agent, tool
from strands.models.bedrock import BedrockModel

from app.config import settings
from app.services.bedrock import BedrockService
from app.services.tools import (
    count_invoices_by_status,
    get_invoice_detail,
    query_goods_receipts,
    query_invoices,
    query_purchase_orders,
    supplier_lowest_prices,
    supplier_order_accuracy,
    top_suppliers,
)

logger = logging.getLogger(__name__)


@tool
def search_knowledge_base(query: str, category_filter: str | None = None) -> str:
    """Search the organizational knowledge base for policies, contracts, procedures,
    and guidelines. Use this tool when the user asks about company policy, document
    content, compliance requirements, vendor agreements, or any information that comes
    from stored organizational records rather than live transaction data.

    Args:
        query: The natural-language question or search phrase.
        category_filter: Optional document category to restrict the search (e.g. "policies").
    """
    kb_id = (settings.KNOWLEDGE_BASE_ID or "").strip()
    # Availability is gated purely on whether a real Knowledge Base ID is
    # configured — not on STAGE. This lets the KB work in local dev once a real
    # ID is set, while still degrading gracefully when it is unset/placeholder.
    is_unavailable = (
        not kb_id
        or kb_id.upper() in ("PLACEHOLDER", "NONE", "N/A")
        or len(kb_id) < 8
    )
    if is_unavailable:
        return (
            "Document search is not configured. "
            "Set KNOWLEDGE_BASE_ID to a real Bedrock Knowledge Base ID to enable it."
        )
    svc = BedrockService()
    result = svc.retrieve_and_generate(
        question=query,
        knowledge_base_id=kb_id,
        category_filter=category_filter,
    )
    return result.get("answer", "No relevant information found.")


@tool
def search_s3_vectors(query: str) -> str:
    """Perform semantic similarity search over organizational documents stored in
    S3 Vectors. Use this as a supplemental retrieval path when the knowledge base
    does not return relevant results, or when searching for document fragments by
    semantic meaning rather than keyword match.

    Args:
        query: The natural-language search phrase.
    """
    index = (settings.S3_VECTORS_INDEX or "").strip()
    if not index:
        return (
            "S3 Vectors semantic search is not configured. "
            "Set S3_VECTORS_INDEX in environment variables to enable this feature."
        )
    try:
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

# ── System Prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an intelligent records assistant for the IntelliProcess platform.
You help users query invoices, purchase orders, goods receipts, and organizational documents.

Answering rules:
- Use the available tools to retrieve accurate data before answering.
- If a tool returns an unavailability message, inform the user politely.
- When multiple data sources are relevant, combine them into one coherent answer.

Output formatting (respond in GitHub-flavored Markdown):
- Open with a one-sentence summary of the answer.
- Use bullet points ("- ") for lists of items, facts, or breakdowns.
- Use a Markdown table when comparing several items across the same fields
  (for example, ranking suppliers by amount, or listing invoices with status
  and total).
- Use **bold** for key figures, names, and statuses.
- Format money with a currency symbol and thousands separators (e.g. $10,000.00).
- Keep answers concise; do not pad with filler.

Never reveal your internal reasoning. Do NOT output any <thinking> tags, chain
of thought, tool-selection commentary, or planning text. Return only the final
user-facing answer.
"""

# ── Agent Singleton ───────────────────────────────────────────────────────────

_agent: Agent | None = None


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
            top_suppliers,
            supplier_order_accuracy,
            supplier_lowest_prices,
            search_knowledge_base,
            search_s3_vectors,
        ],
        system_prompt=_SYSTEM_PROMPT,
    )


def get_agent() -> Agent:
    """Return the singleton Agent instance, creating it on first call."""
    global _agent
    if _agent is None:
        _agent = _build_agent()
    return _agent


# ── Thinking-tag filter ───────────────────────────────────────────────────────


class _ThinkingFilter:
    """Streaming filter that removes <thinking>...</thinking> blocks.

    The model is instructed not to emit thinking tags, but some models still do.
    Because a tag can be split across streamed tokens, this filter keeps a small
    buffer and only releases text that is guaranteed to be outside a thinking
    block and not part of a partial tag.
    """

    _OPEN = "<thinking>"
    _CLOSE = "</thinking>"

    def __init__(self) -> None:
        self._buf = ""
        self._in_thinking = False

    def feed(self, chunk: str) -> str:
        """Add a chunk and return text safe to emit now."""
        self._buf += chunk
        out: list[str] = []

        while self._buf:
            if self._in_thinking:
                idx = self._buf.find(self._CLOSE)
                if idx == -1:
                    # Still inside a thinking block; keep only a possible
                    # partial closing tag at the tail.
                    self._buf = self._keep_partial_tail(self._buf, self._CLOSE)
                    break
                self._buf = self._buf[idx + len(self._CLOSE):]
                self._in_thinking = False
            else:
                idx = self._buf.find(self._OPEN)
                if idx == -1:
                    # No opening tag; emit everything except a possible partial
                    # opening tag at the tail.
                    safe = self._keep_partial_tail(self._buf, self._OPEN)
                    emit = self._buf[: len(self._buf) - len(safe)]
                    if emit:
                        out.append(emit)
                    self._buf = safe
                    break
                out.append(self._buf[:idx])
                self._buf = self._buf[idx + len(self._OPEN):]
                self._in_thinking = True

        return "".join(out)

    def flush(self) -> str:
        """Return any remaining safe text at end of stream."""
        if self._in_thinking:
            return ""
        remaining = self._buf
        self._buf = ""
        return remaining

    @staticmethod
    def _keep_partial_tail(text: str, tag: str) -> str:
        """Return the tail of text that could be the start of `tag`."""
        max_keep = min(len(tag) - 1, len(text))
        for k in range(max_keep, 0, -1):
            if tag.startswith(text[-k:]):
                return text[-k:]
        return ""


def _strip_thinking(text: str) -> str:
    """Remove complete <thinking>...</thinking> blocks from a full string."""
    return re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL).strip()


# ── AgentService ──────────────────────────────────────────────────────────────


class AgentService:
    """High-level service wrapping the Strands Agent for chat endpoints."""

    @staticmethod
    async def stream_answer(
        question: str,
        session_id: str,
        user: Any,
        category_filter: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Yield SSE event dicts: token events during inference, done on completion.

        Uses Strands Agent's ``stream_async`` to iterate over streamed events.
        Text chunks (events containing a ``data`` key) are forwarded as token
        events, with any ``<thinking>`` blocks filtered out across token
        boundaries. After the stream completes, a ``done`` event is emitted with
        session metadata. On any exception, an ``error`` event is yielded.
        """
        thinking = _ThinkingFilter()
        try:
            agent = get_agent()
            async for event in agent.stream_async(question):
                # Strands emits text chunks via the "data" key
                if "data" in event:
                    clean = thinking.feed(event["data"])
                    if clean:
                        yield {"type": "token", "content": clean}

            tail = thinking.flush()
            if tail:
                yield {"type": "token", "content": tail}

            yield {
                "type": "done",
                "sessionId": session_id,
                "sourceType": "agent",
                "citations": [],
                "dataSnapshot": None,
            }
        except Exception as exc:
            logger.exception("Agent stream failed for session %s", session_id)
            yield {"type": "error", "message": str(exc)}

    @staticmethod
    async def answer(
        question: str,
        session_id: str,
        user: Any,
        category_filter: str | None = None,
    ) -> dict:
        """Blocking wrapper that collects tokens and returns a ChatResponse-compatible dict.

        Iterates over all events from ``stream_answer``, concatenates token content,
        and returns the assembled answer with empty citations and source_type='agent'.
        """
        parts: list[str] = []
        async for event in AgentService.stream_answer(
            question, session_id, user, category_filter
        ):
            if event["type"] == "token":
                parts.append(event["content"])
        answer = _strip_thinking("".join(parts))
        return {"answer": answer, "citations": [], "source_type": "agent"}
