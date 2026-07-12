import json
import logging
from typing import Any
from apps.backend.src.shared.observability.context import trace_ctx
from db_clients.session import get_current_tenant_id, _tenant_metadata_cache

class JsonFormatter(logging.Formatter):
    """Custom logging formatter that outputs JSON with trace context correlation."""
    def format(self, record: logging.LogRecord) -> str:
        ctx = trace_ctx.get()
        tenant_id = get_current_tenant_id()
        
        tier_level = None
        if tenant_id and tenant_id in _tenant_metadata_cache:
            tier_level = _tenant_metadata_cache[tenant_id].get("tier")

        payload: dict[str, Any] = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "trace_id": ctx.trace_id if ctx else None,
            "span_id": ctx.span_id if ctx else None,
            "tenant_id": str(tenant_id) if tenant_id else None,
            "tier_level": tier_level,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)

def configure_logging(level: str = "INFO") -> None:
    """Configures the root logger to output JSON structured logs to stdout."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    
    root = logging.getLogger()
    # Remove any existing handlers
    for h in list(root.handlers):
        root.removeHandler(h)
        
    root.addHandler(handler)
    root.setLevel(level)
