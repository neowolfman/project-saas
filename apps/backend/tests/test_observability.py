"""
Integration tests for the observability stack:
- W3CTracingMiddleware injects X-Trace-ID header
- JSON structured logging contains trace_id and tenant_id
- /metrics endpoint responds with Prometheus data
- RabbitMQ trace injection/extraction helpers work correctly
"""
import json
import logging
import re
import pytest

from httpx import AsyncClient, ASGITransport
from apps.backend.src.main import app
from apps.backend.src.shared.observability.inject import inject_trace_headers
from apps.backend.src.shared.observability.context import trace_ctx, TraceContext


# ---------------------------------------------------------------------------
# Middleware tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_w3c_tracing_middleware_generates_trace_id():
    """W3CTracingMiddleware debe generar un trace_id y exponerlo en X-Trace-ID."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    trace_id = response.headers.get("x-trace-id")
    assert trace_id is not None, "X-Trace-ID header should be present"
    assert re.fullmatch(r"[0-9a-f]{32}", trace_id), f"Expected 32-char hex, got: {trace_id}"


@pytest.mark.asyncio
async def test_w3c_tracing_middleware_propagates_traceparent():
    """W3CTracingMiddleware debe propagar el trace_id del header traceparent entrante."""
    existing_trace_id = "a" * 32
    existing_span_id = "b" * 16
    traceparent = f"00-{existing_trace_id}-{existing_span_id}-01"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health", headers={"traceparent": traceparent})
    assert response.status_code == 200
    assert response.headers.get("x-trace-id") == existing_trace_id


# ---------------------------------------------------------------------------
# Metrics endpoint test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_metrics_endpoint_is_accessible():
    """/metrics debe exponer métricas en formato Prometheus."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", follow_redirects=True
    ) as client:
        response = await client.get("/metrics/")
    assert response.status_code == 200
    # Prometheus text format uses HELP and TYPE lines
    assert b"# HELP" in response.content or b"# TYPE" in response.content, (
        "/metrics did not return Prometheus format"
    )


# ---------------------------------------------------------------------------
# JSON Logging tests
# ---------------------------------------------------------------------------

def test_json_formatter_outputs_valid_json(caplog):
    """JsonFormatter debe producir líneas JSON válidas."""
    from apps.backend.src.shared.observability.logging import JsonFormatter
    import io

    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello observability",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    parsed = json.loads(output)
    assert parsed["level"] == "INFO"
    assert parsed["msg"] == "hello observability"
    assert parsed["logger"] == "test.logger"


def test_json_formatter_injects_trace_context():
    """JsonFormatter debe inyectar trace_id/span_id cuando hay un TraceContext activo."""
    from apps.backend.src.shared.observability.logging import JsonFormatter

    ctx = TraceContext(trace_id="a" * 32, span_id="b" * 16, tenant_id=None, tier_level=None)
    token = trace_ctx.set(ctx)
    try:
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.DEBUG,
            pathname=__file__,
            lineno=1,
            msg="trace injection test",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["trace_id"] == "a" * 32
        assert parsed["span_id"] == "b" * 16
    finally:
        trace_ctx.reset(token)


# ---------------------------------------------------------------------------
# RabbitMQ trace header helpers
# ---------------------------------------------------------------------------

def test_inject_trace_headers_adds_traceparent():
    """inject_trace_headers debe agregar el header traceparent con el trace_id actual."""
    ctx = TraceContext(trace_id="c" * 32, span_id="d" * 16, tenant_id=None, tier_level=None)
    token = trace_ctx.set(ctx)
    try:
        headers = inject_trace_headers({})
        assert "traceparent" in headers
        assert f"cc-{'c' * 32}-{'d' * 16}" in headers["traceparent"] or \
               headers["traceparent"] == f"00-{'c' * 32}-{'d' * 16}-01"
    finally:
        trace_ctx.reset(token)


def test_extract_trace_headers_parses_traceparent():
    """extract_trace_headers debe parsear correctamente el header traceparent."""
    from apps.workers.src.shared.observability.extract import extract_trace_headers

    trace_id = "e" * 32
    span_id = "f" * 16
    headers = {
        "traceparent": f"00-{trace_id}-{span_id}-01",
        "x-tenant-id": "123e4567-e89b-12d3-a456-426614174000",
    }
    ctx = extract_trace_headers(headers)
    assert ctx.trace_id == trace_id
    assert ctx.span_id == span_id
    assert ctx.tenant_id == "123e4567-e89b-12d3-a456-426614174000"


def test_extract_trace_headers_handles_missing_gracefully():
    """extract_trace_headers debe retornar None para campos faltantes."""
    from apps.workers.src.shared.observability.extract import extract_trace_headers

    ctx = extract_trace_headers({})
    assert ctx.trace_id is None
    assert ctx.span_id is None
    assert ctx.tenant_id is None
