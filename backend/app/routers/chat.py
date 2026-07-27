"""Records Assistant chat endpoints."""

from fastapi import APIRouter

router = APIRouter()


# POST /chat - Submit a natural language question (RAG)
# GET /chat/sessions - List user's chat sessions
# GET /chat/sessions/{session_id} - Get session conversation history
