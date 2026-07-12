import secrets
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response
from apps.backend.src.shared.observability.context import trace_ctx, TraceContext
from apps.backend.src.shared.observability.metrics import HTTP_LATENCY

class W3CTracingMiddleware(BaseHTTPMiddleware):
    """Middleware that extracts or generates W3C trace IDs and propagates them in context."""
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.perf_counter()
        
        traceparent = request.headers.get("traceparent", "")
        trace_id, span_id = self._parse_traceparent(traceparent)
        if not trace_id:
            trace_id, span_id = self._new_ids()

        ctx = TraceContext(
            trace_id=trace_id,
            span_id=span_id,
            tenant_id=None,
            tier_level=None
        )
        token = trace_ctx.set(ctx)

        try:
            response = await call_next(request)
            
            # Record HTTP latency metrics
            path = request.url.path
            if path not in ("/metrics", "/health"):
                duration = time.perf_counter() - start_time
                HTTP_LATENCY.labels(
                    route=path,
                    method=request.method,
                    status=response.status_code
                ).observe(duration)
                
            response.headers["X-Trace-ID"] = trace_id
            return response
        finally:
            trace_ctx.reset(token)

    def _parse_traceparent(self, tp: str) -> tuple[str, str]:
        parts = tp.split("-")
        if len(parts) == 4 and len(parts[1]) == 32 and len(parts[2]) == 16:
            return parts[1], parts[2]
        return "", ""

    def _new_ids(self) -> tuple[str, str]:
        return secrets.token_hex(16), secrets.token_hex(8)
