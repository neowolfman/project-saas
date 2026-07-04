from datetime import datetime, UTC
from typing import Any
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, ConfigDict


class DomainEvent(BaseModel):
    """Clase base inmutable para todos los eventos de dominio."""
    model_config = ConfigDict(frozen=True)

    event_id: UUID = Field(default_factory=uuid4)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tenant_id: UUID


class ValueObject(BaseModel):
    """Clase base inmutable para objetos de valor (Value Objects) en DDD."""
    model_config = ConfigDict(frozen=True)


class AggregateRoot:
    """Clase base para raíces de agregado (Aggregate Roots) en DDD."""
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._events: list[DomainEvent] = []
        super().__init__(*args, **kwargs)

    def record_event(self, event: DomainEvent) -> None:
        """Registra un nuevo evento de dominio en el agregado."""
        self._events.append(event)

    def clear_events(self) -> None:
        """Limpia los eventos de dominio registrados."""
        self._events.clear()

    def get_events(self) -> list[DomainEvent]:
        """Obtiene una copia de los eventos de dominio registrados."""
        return list(self._events)
