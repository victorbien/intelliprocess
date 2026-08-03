"""Intent classification for the Records Assistant.

``classify()`` is the single public entry point. It returns the intent,
extracted parameters, and a confidence score.

Architecture note
-----------------
The module is split into two layers:

1. ``_classify_heuristic()`` — keyword-based, no external calls, works locally.
2. ``_classify_llm()``       — placeholder for future Bedrock Claude call.

``classify()`` selects the active backend based on ``settings.STAGE`` and
``settings.KNOWLEDGE_BASE_ID``. When Bedrock is unavailable (local dev),
the heuristic path is used unconditionally. Swapping in the LLM backend later
requires only updating ``classify()`` — callers never change.

Dev fallback rule
-----------------
When ``STAGE=dev`` and heuristic confidence is below the threshold, the
function falls back to ``structured_query`` (not ``document_search``) because
document search cannot run without a real Bedrock Knowledge Base.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_CONFIDENCE_THRESHOLD = 0.6

# Intent identifiers — kept as module-level constants so callers can import
# them for comparisons instead of using bare strings.
INTENT_STRUCTURED = "structured_query"
INTENT_DOCUMENT = "document_search"
INTENT_HYBRID = "hybrid"

# ── Keyword dictionaries ──────────────────────────────────────────────────────

# Words that strongly signal a structured / transactional question.
# Short tokens that are common substrings (e.g. "po" inside "policy") are
# excluded here and matched separately using word-boundary regexes in
# _score_keywords_wb below.
_STRUCTURED_KEYWORDS: list[str] = [
    "invoice", "invoices", "escalated", "approved", "rejected", "processing",
    "uploaded", "pending", "approval", "status", "count", "how many", "total",
    "amount", "vendor", "purchase order", "goods receipt", "match",
    "three.way", "three way", "payment", "due", "overdue", "receipt",
    "acme", "techparts", "supplies",
]

# Short tokens matched with word-boundary regexes (not plain substring)
_STRUCTURED_WORD_TOKENS: list[str] = ["po", "gr"]

# Words that strongly signal a document / knowledge-base question
_DOCUMENT_KEYWORDS: list[str] = [
    "policy", "policies", "contract", "contracts", "procedure", "procedures",
    "guideline", "guidelines", "regulation", "compliance", "rule", "rules",
    "what is", "what are", "explain", "describe", "definition", "how to",
    "travel", "reimbursement", "expense", "procurement", "manual", "handbook",
    "agreement", "terms", "clause", "section", "document", "documents",
]

# Regex patterns for extracting named parameters from the question text
_PARAM_PATTERNS: dict[str, str] = {
    # e.g. "ESCALATED invoices", "invoices with status approved"
    "status": r"\b(ESCALATED|APPROVED|REJECTED|PROCESSING|UPLOADED|ERROR)\b",
    # e.g. "from Acme", "vendor TechParts", "acme invoices"
    "vendor_name": r"(?:from|vendor|by|for)\s+([A-Za-z][A-Za-z0-9 &.]+?)(?:\s+invoices?|\s+vendor|\s*$|[,?])",
    # e.g. "over $10,000", "more than 5000", "above 10000"
    "amount_min": r"(?:over|above|more\s+than|greater\s+than|exceeds?)\s+\$?([\d,]+)",
    # e.g. "under $1000", "less than 500", "below 2000"
    "amount_max": r"(?:under|below|less\s+than)\s+\$?([\d,]+)",
    # e.g. "PO-2024-0456", "purchase order PO-2024-0456"
    "po_number": r"\bPO-\d{4}-\d{4}\b",
}

# Vendor aliases found directly by name without a leading keyword
_VENDOR_DIRECT: list[str] = [
    "acme", "techparts", "unknown supplies",
]


# ── Public API ────────────────────────────────────────────────────────────────

def classify(question: str) -> dict[str, Any]:
    """Classify a natural-language question for the Records Assistant.

    Returns a dict with:
        ``intent``     — one of ``structured_query``, ``document_search``,
                         or ``hybrid``.
        ``params``     — dict of extracted parameters (vendor_name, status,
                         amount_min, amount_max, po_number). Only keys with
                         non-None values are included.
        ``confidence`` — float 0.0–1.0. ``None`` when the LLM path is used
                         (confidence is embedded in the LLM response instead).

    The function never raises. On any internal error it returns a safe
    ``document_search`` result with confidence 0.0.
    """
    try:
        use_heuristic = settings.STAGE == "dev" or not settings.KNOWLEDGE_BASE_ID
        if use_heuristic:
            return _classify_heuristic(question)
        return _classify_llm(question)
    except Exception:
        logger.exception("Intent classification failed; defaulting to document_search")
        return {"intent": INTENT_DOCUMENT, "params": {}, "confidence": 0.0}


# ── Heuristic classifier ──────────────────────────────────────────────────────

def _classify_heuristic(question: str) -> dict[str, Any]:
    """Keyword-based intent classifier — no network calls."""
    q_lower = question.lower()

    structured_score = _score_structured(q_lower)
    document_score = _score_keywords(q_lower, _DOCUMENT_KEYWORDS)

    # Determine intent
    if structured_score > 0 and document_score > 0:
        intent = INTENT_HYBRID
        raw_confidence = min(
            _normalise(structured_score, _STRUCTURED_KEYWORDS + _STRUCTURED_WORD_TOKENS),
            _normalise(document_score, _DOCUMENT_KEYWORDS),
        )
    elif structured_score >= document_score and structured_score > 0:
        intent = INTENT_STRUCTURED
        raw_confidence = _normalise(structured_score, _STRUCTURED_KEYWORDS + _STRUCTURED_WORD_TOKENS)
    elif document_score > 0:
        intent = INTENT_DOCUMENT
        raw_confidence = _normalise(document_score, _DOCUMENT_KEYWORDS)
    else:
        # No signal at all
        intent = INTENT_DOCUMENT
        raw_confidence = 0.0

    confidence = round(min(raw_confidence, 1.0), 3)

    # Dev fallback: low-confidence → prefer structured_query so the user gets
    # *some* answer rather than an "unavailable" document-search response.
    if confidence < _CONFIDENCE_THRESHOLD and settings.STAGE == "dev":
        intent = INTENT_STRUCTURED
        logger.debug(
            "Low-confidence intent (%s, %.2f) — falling back to structured_query in dev",
            intent, confidence,
        )

    params = _extract_params(question)

    logger.debug(
        "Heuristic classification: intent=%s confidence=%.3f params=%s",
        intent, confidence, params,
    )
    return {"intent": intent, "params": params, "confidence": confidence}


def _score_keywords(text: str, keywords: list[str]) -> int:
    """Count how many keywords (or phrases) appear in *text*."""
    return sum(1 for kw in keywords if kw in text)


def _score_structured(text: str) -> int:
    """Score for structured intent: plain keywords + word-boundary tokens."""
    score = _score_keywords(text, _STRUCTURED_KEYWORDS)
    score += sum(
        1 for tok in _STRUCTURED_WORD_TOKENS
        if re.search(rf"\b{re.escape(tok)}\b", text)
    )
    return score


def _normalise(score: int, keyword_list: list[str]) -> float:
    """Map a raw keyword count to a 0–1 confidence using a simple log-like curve.

    One hit  → 0.65 (above threshold)
    Two hits → 0.80
    Three+   → approaches 1.0
    """
    if score <= 0:
        return 0.0
    # Each additional hit adds diminishing returns
    return min(0.55 + score * 0.15, 1.0)


def _extract_params(question: str) -> dict[str, Any]:
    """Extract structured parameters from the question text using regex."""
    params: dict[str, Any] = {}
    q_upper = question.upper()
    q_lower = question.lower()

    # Status — match canonical enum values
    m = re.search(_PARAM_PATTERNS["status"], q_upper)
    if m:
        params["status"] = m.group(1).upper()

    # Vendor name — keyword-led pattern
    m = re.search(_PARAM_PATTERNS["vendor_name"], question, re.IGNORECASE)
    if m:
        params["vendor_name"] = m.group(1).strip()
    else:
        # Direct mention of known vendor names
        for alias in _VENDOR_DIRECT:
            if alias in q_lower:
                params["vendor_name"] = alias
                break

    # Amount thresholds
    m = re.search(_PARAM_PATTERNS["amount_min"], question, re.IGNORECASE)
    if m:
        try:
            params["amount_min"] = float(m.group(1).replace(",", ""))
        except ValueError:
            pass

    m = re.search(_PARAM_PATTERNS["amount_max"], question, re.IGNORECASE)
    if m:
        try:
            params["amount_max"] = float(m.group(1).replace(",", ""))
        except ValueError:
            pass

    # PO number
    m = re.search(_PARAM_PATTERNS["po_number"], question, re.IGNORECASE)
    if m:
        params["po_number"] = m.group(0).upper()

    return params


# ── LLM classifier (future) ───────────────────────────────────────────────────

# Intent classification prompt — stored here so it can be updated without
# touching routing logic.  The LLM must return:
#   {"intent": "<structured_query|document_search|hybrid>", "confidence": <0-1>}
INTENT_CLASSIFICATION_PROMPT = """\
You are an intent classifier for a corporate records assistant. Classify the \
user question into exactly one of three categories:

- "structured_query": questions about invoice counts, amounts, statuses, \
vendors, purchase orders, or goods receipts. These are answered from live \
transaction data.
  Examples:
    "How many invoices are escalated?" → structured_query
    "What is the total amount approved this month?" → structured_query
    "Show me invoices from Acme over $5000." → structured_query

- "document_search": questions about policies, contracts, procedures, \
guidelines, or the content of named documents. Answered from the knowledge base.
  Examples:
    "What is the travel reimbursement policy?" → document_search
    "What does the vendor contract with Acme say about payment terms?" → document_search
    "Explain the procurement approval procedure." → document_search

- "hybrid": questions that require BOTH live transaction data AND document \
content to answer.
  Examples:
    "Does the TechParts invoice exceed the procurement approval threshold?" → hybrid
    "Is the Acme invoice compliant with the vendor contract terms?" → hybrid
    "What is the approved amount for PO-2024-0456 and what does policy say about it?" → hybrid

Respond ONLY with a JSON object. Do not include any other text.
Format: {{"intent": "<category>", "confidence": <0.0 to 1.0>}}

User question: {question}
"""


def _classify_llm(question: str) -> dict[str, Any]:
    """LLM-based intent classifier using Amazon Bedrock Claude.

    Not called in local dev (STAGE=dev or KNOWLEDGE_BASE_ID unset).
    Falls back to heuristic if the LLM response cannot be parsed.
    """
    import json as _json

    try:
        import boto3
        from botocore.exceptions import ClientError

        client = boto3.client("bedrock-runtime", region_name=settings.AWS_REGION)
        prompt = INTENT_CLASSIFICATION_PROMPT.format(question=question)

        response = client.invoke_model(
            modelId=settings.BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=_json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 64,
                "messages": [{"role": "user", "content": prompt}],
            }),
        )

        body = _json.loads(response["body"].read())
        text = body["content"][0]["text"].strip()
        result = _json.loads(text)

        intent = result.get("intent", "")
        confidence = float(result.get("confidence", 0.0))

        if intent not in (INTENT_STRUCTURED, INTENT_DOCUMENT, INTENT_HYBRID):
            raise ValueError(f"Unrecognised intent from LLM: {intent!r}")
        if confidence < _CONFIDENCE_THRESHOLD:
            intent = INTENT_DOCUMENT  # safe fallback in production

        params = _extract_params(question)
        return {"intent": intent, "params": params, "confidence": None}

    except Exception:
        logger.exception("LLM classifier failed; falling back to heuristic")
        return _classify_heuristic(question)
