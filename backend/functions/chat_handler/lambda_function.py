"""ChatHandler Lambda entry point.

Serves the FastAPI application (from the shared layer) via Mangum.
API Gateway routes /chat and /chat/* to this function.

NOTE: This module is intentionally NOT named ``app`` — the FastAPI package
imported below is also called ``app`` (provided by the shared layer). A handler
file named ``app.py`` would shadow that package and break ``from app.main``.
"""

from app.main import handler as lambda_handler

__all__ = ["lambda_handler"]
