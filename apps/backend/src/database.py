import json
from typing import Any
from uuid import UUID

from apps.backend.src.config import settings
from db_clients.session import create_session_factory
from ddd_core.base import DomainEvent
from ddd_core.outbox import from_domain_event
from sqlalchemy import text

# Factoría de sesión asíncrona global utilizando el DSN del rol app_api
api_session_factory = create_session_factory(settings.db_url)


async def save_outbox_event(session: Any, aggregate_name: str, aggregate_id: UUID, event: DomainEvent) -> None:
    """Registra de forma transaccional un evento de dominio en la tabla outbox."""
    outbox_event = from_domain_event(aggregate_name, aggregate_id, event)
    await session.execute(
        text("""
            INSERT INTO outbox (aggregate, aggregate_id, tenant_id, event_type, payload, headers)
            VALUES (:aggregate, :aggregate_id, :tenant_id, :event_type, :payload, :headers)
        """),
        {
            "aggregate": outbox_event.aggregate,
            "aggregate_id": outbox_event.aggregate_id,
            "tenant_id": outbox_event.tenant_id,
            "event_type": outbox_event.event_type,
            "payload": json.dumps(outbox_event.payload),
            "headers": json.dumps(outbox_event.headers),
        },
    )
