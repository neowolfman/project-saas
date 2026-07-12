"""
Helpers for injecting W3C Trace Context headers into outgoing RabbitMQ messages.
Enables trace continuity from the backend publisher to background workers.
"""
from apps.backend.src.shared.observability.context import trace_ctx
from db_clients.session import get_current_tenant_id


def inject_trace_headers(headers: dict) -> dict:
    """
    Injects traceparent and tenant_id into message headers.
    Call this before publishing any event to RabbitMQ.
    """
    ctx = trace_ctx.get()
    if ctx:
        headers["traceparent"] = f"00-{ctx.trace_id}-{ctx.span_id}-01"

    tenant_id = get_current_tenant_id()
    if tenant_id:
        headers["x-tenant-id"] = str(tenant_id)

    return headers
