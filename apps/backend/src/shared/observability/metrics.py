from prometheus_client import Counter, Histogram, make_asgi_app
from fastapi import FastAPI

# Custom Business Metrics
FIN_OPS = Counter(
    "saas_financial_ops_total",
    "Total financial operations registered",
    labelnames=("tenant_id", "tier", "kind"),
)

SLA_RISK = Counter(
    "saas_sla_risk_alerts_total",
    "Total SLA risk alerts issued",
    labelnames=("tenant_id", "tier", "level"),
)

HTTP_LATENCY = Histogram(
    "saas_http_request_duration_seconds",
    "HTTP request latency in seconds",
    labelnames=("route", "method", "status"),
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

def record_financial_op(tenant_id: str, tier: str, kind: str) -> None:
    """Helper to record a financial operation metric increment."""
    FIN_OPS.labels(tenant_id=tenant_id, tier=tier, kind=kind).inc()

def record_sla_risk(tenant_id: str, tier: str, level: str) -> None:
    """Helper to record an SLA risk alert metric increment."""
    SLA_RISK.labels(tenant_id=tenant_id, tier=tier, level=level).inc()

def setup_metrics(app: FastAPI) -> None:
    """Mounts the Prometheus /metrics endpoint into the FastAPI application."""
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)
