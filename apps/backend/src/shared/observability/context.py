import contextvars
from dataclasses import dataclass
from uuid import UUID

@dataclass(frozen=True)
class TraceContext:
    trace_id: str
    span_id: str
    tenant_id: UUID | None
    tier_level: str | None

trace_ctx: contextvars.ContextVar[TraceContext | None] = contextvars.ContextVar("trace_ctx", default=None)
