"""Knowledge Base sync service (Module 4 — FR-CROSS-001).

Triggers ingestion of newly uploaded documents into the Amazon Bedrock
Knowledge Base so that invoices, POs, and organizational records become
searchable via the Records Assistant.

Design mirrors the rest of the codebase:
- A real Bedrock ``bedrock-agent`` ``StartIngestionJob`` call in production.
- A no-op fallback in local development (``STAGE=dev`` or the KB is not
  configured with a real ID), returning a deterministic pseudo job id so the
  API contract (HTTP 202 + ``syncJobId``) stays consistent across environments.
"""

import logging
import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings

logger = logging.getLogger(__name__)

# Placeholder / unconfigured KB id sentinels (consistent with chat.py handling).
_PLACEHOLDER_KB_IDS = frozenset({"", "PLACEHOLDER", "NONE", "N/A"})


class KnowledgeBaseSyncError(Exception):
    """Raised when a Knowledge Base ingestion job cannot be started."""


def is_kb_configured() -> bool:
    """Return True only when a real Bedrock Knowledge Base id is configured.

    A real Bedrock KB id looks like ``abc12345-...``; empty strings, common
    placeholders, and very short values are treated as unconfigured.
    """
    kb_id = (settings.KNOWLEDGE_BASE_ID or "").strip()
    if kb_id.upper() in _PLACEHOLDER_KB_IDS:
        return False
    return len(kb_id) >= 8


def start_sync() -> tuple[str, str | None]:
    """Start a Knowledge Base ingestion (sync) job.

    Returns:
        Tuple of ``(message, sync_job_id)``. In local/dev or when the KB is not
        configured, ``sync_job_id`` is a locally generated identifier and the
        message notes that sync is simulated.

    Raises:
        KnowledgeBaseSyncError: If the Bedrock ingestion call fails in a
            configured (production) environment.
    """
    if settings.STAGE == "dev" or not is_kb_configured():
        pseudo_job_id = f"local-sync-{uuid.uuid4().hex[:12]}"
        logger.info(
            "Knowledge base sync simulated (dev / KB not configured)",
            extra={"stage": settings.STAGE, "syncJobId": pseudo_job_id},
        )
        return (
            "Knowledge base sync simulated in the local environment. "
            "Deploy to AWS with a configured Bedrock Knowledge Base to ingest documents.",
            pseudo_job_id,
        )

    data_source_id = (settings.KB_DATA_SOURCE_ID or "").strip()
    if not data_source_id:
        logger.error("KB_DATA_SOURCE_ID is not configured; cannot start ingestion job")
        raise KnowledgeBaseSyncError(
            "Knowledge base data source is not configured."
        )

    try:
        client = boto3.client("bedrock-agent", region_name=settings.AWS_REGION)
        response = client.start_ingestion_job(
            knowledgeBaseId=settings.KNOWLEDGE_BASE_ID.strip(),
            dataSourceId=data_source_id,
        )
        job = response.get("ingestionJob", {})
        sync_job_id = job.get("ingestionJobId")
        logger.info(
            "Knowledge base ingestion job started",
            extra={
                "syncJobId": sync_job_id,
                "knowledgeBaseId": settings.KNOWLEDGE_BASE_ID.strip(),
            },
        )
        return (
            "Knowledge base sync initiated. New documents will be searchable within 5 minutes.",
            sync_job_id,
        )
    except (ClientError, BotoCoreError) as exc:
        logger.error(
            "Failed to start knowledge base ingestion job",
            extra={"error": str(exc)},
        )
        raise KnowledgeBaseSyncError(
            "Failed to start the knowledge base sync. Please try again."
        ) from exc
