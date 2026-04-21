"""FastAPI middleware: OpenTelemetry tracing for every HTTP request."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.trace import StatusCode
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from src.telemetry.setup import get_tracer

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

_tracer = get_tracer(__name__)


class TracingMiddleware(BaseHTTPMiddleware):
    """Create an OTel span per request; inject trace_id into response headers."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        span_name = f"{request.method} {request.url.path}"

        with _tracer.start_as_current_span(span_name) as span:
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.url", str(request.url))

            start = time.perf_counter()
            response = await call_next(request)
            duration = time.perf_counter() - start

            span.set_attribute("http.status_code", response.status_code)
            span.set_attribute("http.duration_s", round(duration, 6))

            if response.status_code >= 500:
                span.set_status(StatusCode.ERROR, f"HTTP {response.status_code}")

            # Propagate trace id so callers can correlate logs.
            span_ctx = trace.get_current_span().get_span_context()
            if span_ctx.trace_id:
                response.headers["X-Trace-Id"] = format(span_ctx.trace_id, "032x")

        return response
