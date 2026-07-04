from datetime import datetime, UTC
from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field
from .base import DomainEvent


class OutboxEvent(BaseModel):
    """Representa un evento en la tabla Outbox para entrega garantizada."""
    id: int | None = None
    aggregate: str
    aggregate_id: UUID
    tenant_id: UUID | None
    event_type: str
    payload: dict[str, Any]
    headers: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    published_at: datetime | None = None


def from_domain_event(aggregate_name: str, aggregate_id: UUID, event: DomainEvent, headers: dict[str, Any] | None = None) -> OutboxEvent:
    """Convierte un evento de dominio en un registro de OutboxEvent."""
    payload = event.model_dump(mode="json")
    
    return OutboxEvent(
        aggregate=aggregate_name,
        aggregate_id=aggregate_id,
        tenant_id=event.tenant_id,
        event_type=event.__class__.__name__,
        payload=payload,
        headers=headers or {}
    )
