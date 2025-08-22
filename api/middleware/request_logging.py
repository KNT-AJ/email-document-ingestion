"""Request logging middleware for FastAPI."""

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from utils.logging import get_request_logger

logger = get_request_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log HTTP requests and responses with correlation IDs."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and add logging context."""
        # Generate a unique request ID
        request_id = str(uuid.uuid4())

        # Start timing the request
        start_time = time.time()

        # Add request ID to logging context
        try:
            import structlog
            structlog.contextvars.bind_contextvars(request_id=request_id)
        except ImportError:
            # Fallback if structlog is not available
            pass

        # Log the incoming request
        logger.info(
            "Request started",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            query_params=str(request.url.query),
            user_agent=request.headers.get("user-agent", "unknown"),
            client_host=request.client.host if request.client else "unknown",
        )

        try:
            # Process the request
            response = await call_next(request)

            # Calculate response time
            response_time_ms = round((time.time() - start_time) * 1000, 2)

            # Log the response
            logger.info(
                "Request completed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                response_time_ms=response_time_ms,
                content_length=response.headers.get("content-length", "unknown"),
            )

            # Add request ID to response headers for debugging
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # Calculate response time even for errors
            response_time_ms = round((time.time() - start_time) * 1000, 2)

            # Log the error
            logger.error(
                "Request failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                error=str(e),
                error_type=type(e).__name__,
                response_time_ms=response_time_ms,
                exc_info=True,
            )

            # Re-raise the exception
            raise
