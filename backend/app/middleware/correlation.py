"""Correlation ID middleware — attaches a request ID for distributed tracing."""

import uuid
import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware that reads or generates an X-Correlation-Id header.

    - If the incoming request has X-Correlation-Id, it is reused.
    - Otherwise, a new UUID is generated.
    - The correlation ID is stored on request.state and returned in response headers.
    """

    HEADER_NAME = "X-Correlation-Id"

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Read from request or generate new
        correlation_id = request.headers.get(self.HEADER_NAME) or str(uuid.uuid4())

        # Attach to request state for use in route handlers and logging
        request.state.correlation_id = correlation_id

        # Process request
        response = await call_next(request)

        # Attach to response headers
        response.headers[self.HEADER_NAME] = correlation_id

        return response
