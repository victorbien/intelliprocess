"""IntelliProcess AI — FastAPI Application Entry Point."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from app.config import settings
from app.middleware import CorrelationIdMiddleware, register_exception_handlers
from app.routers import chat, dashboard, documents, invoices

# Configure structured logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(
    title="IntelliProcess AI",
    description="Integrated AP Invoice Agent & Records Search Assistant",
    version="0.1.0",
    docs_url="/docs" if settings.STAGE == "dev" else None,
    redoc_url=None,
)

# Middleware (order matters — outermost first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Correlation-Id"],
)
app.add_middleware(CorrelationIdMiddleware)

# Exception handlers
register_exception_handlers(app)

# Routers
app.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])


@app.get("/health", tags=["system"])
def health_check():
    """Health check endpoint — unauthenticated."""
    return {"status": "healthy", "stage": settings.STAGE}


# AWS Lambda handler via Mangum
handler = Mangum(app, lifespan="off")
