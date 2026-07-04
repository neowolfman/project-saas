from uuid import uuid4
from typing import Any
import pytest
from pydantic import ValidationError
from ddd_core.base import DomainEvent, ValueObject, AggregateRoot
from ddd_core.outbox import from_domain_event


# 1. Definición de clases de prueba para DDD
class DummyDomainEvent(DomainEvent):
    event_name: str
    amount: float


class Coordinates(ValueObject):
    x: int
    y: int


class DummyAggregate(AggregateRoot):
    def __init__(self, aggregate_id: Any = None) -> None:
        super().__init__()
        self.id = aggregate_id or uuid4()


def test_domain_event_immutability_and_defaults() -> None:
    """Verifica que los eventos de dominio sean inmutables y generen UUID/timestamps automáticamente."""
    tenant_id = uuid4()
    event = DummyDomainEvent(tenant_id=tenant_id, event_name="test_event", amount=150.5)

    assert event.event_id is not None
    assert event.occurred_at is not None
    assert event.tenant_id == tenant_id
    assert event.event_name == "test_event"
    assert event.amount == 150.5

    # Intentar mutar el evento debe lanzar ValidationError/TypeError debido a model_config frozen=True
    with pytest.raises(ValidationError):
        event.event_name = "new_name"  # type: ignore


def test_value_object_equality_and_immutability() -> None:
    """Verifica que los objetos de valor posean igualdad estructural y sean inmutables."""
    c1 = Coordinates(x=10, y=20)
    c2 = Coordinates(x=10, y=20)
    c3 = Coordinates(x=15, y=20)

    # Igualdad estructural (por valor)
    assert c1 == c2
    assert c1 != c3

    # Inmutabilidad
    with pytest.raises(ValidationError):
        c1.x = 99  # type: ignore


def test_aggregate_root_event_lifecycle() -> None:
    """Verifica que el AggregateRoot registre, retorne y limpie eventos de dominio."""
    aggregate = DummyAggregate()
    tenant_id = uuid4()
    
    event1 = DummyDomainEvent(tenant_id=tenant_id, event_name="event_1", amount=10.0)
    event2 = DummyDomainEvent(tenant_id=tenant_id, event_name="event_2", amount=20.0)

    # Registrar eventos
    aggregate.record_event(event1)
    aggregate.record_event(event2)

    events = aggregate.get_events()
    assert len(events) == 2
    assert events[0] == event1
    assert events[1] == event2

    # Limpiar eventos
    aggregate.clear_events()
    assert len(aggregate.get_events()) == 0


def test_outbox_event_mapping() -> None:
    """Verifica la conversión correcta de DomainEvent a OutboxEvent."""
    tenant_id = uuid4()
    aggregate_id = uuid4()
    
    event = DummyDomainEvent(tenant_id=tenant_id, event_name="sale_completed", amount=99.99)
    outbox = from_domain_event(
        aggregate_name="DummyAggregate",
        aggregate_id=aggregate_id,
        event=event,
        headers={"correlation_id": "test-123"}
    )

    assert outbox.aggregate == "DummyAggregate"
    assert outbox.aggregate_id == aggregate_id
    assert outbox.tenant_id == tenant_id
    assert outbox.event_type == "DummyDomainEvent"
    assert outbox.headers == {"correlation_id": "test-123"}
    assert outbox.payload["event_name"] == "sale_completed"
    assert outbox.payload["amount"] == 99.99
    assert outbox.created_at is not None
    assert outbox.published_at is None
