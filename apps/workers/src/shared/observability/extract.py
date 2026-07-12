"""
Helpers for extracting W3C Trace Context headers from incoming RabbitMQ messages.
Enables workers to continue the distributed trace started by the backend.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class IncomingTraceContext:
    trace_id: str | None
    span_id: str | None
    tenant_id: str | None


def extract_trace_headers(headers: dict) -> IncomingTraceContext:
    """
    Extracts traceparent and tenant_id from incoming RabbitMQ message headers.
    Returns an IncomingTraceContext with the extracted values (any may be None).
    """
    trace_id: str | None = None
    span_id: str | None = None

    traceparent = headers.get("traceparent", "")
    if traceparent:
        parts = traceparent.split("-")
        if len(parts) == 4 and len(parts[1]) == 32 and len(parts[2]) == 16:
            trace_id = parts[1]
            span_id = parts[2]

    tenant_id = headers.get("x-tenant-id") or None

    return IncomingTraceContext(trace_id=trace_id, span_id=span_id, tenant_id=tenant_id)
