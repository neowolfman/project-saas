import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange
from sqlalchemy import text

logger = logging.getLogger("outbox_relay")

POLL_INTERVAL = 0.2
BATCH_SIZE = 50

# Exchange principal pm.events
pm_exchange = RabbitExchange("pm.events", type=ExchangeType.TOPIC, durable=True)


async def get_tenant_tier(session: Any, tenant_id: UUID) -> str:
    """Obtiene el tier del tenant desde la base de datos."""
    res = await session.execute(
        text("SELECT tier FROM tenants WHERE tenant_id = :tenant_id"),
        {"tenant_id": tenant_id}
    )
    row = res.fetchone()
    if row:
        return str(row[0])
    return "starter"


async def resolve_routing_key(session: Any, event_type: str, tenant_id: UUID | None) -> str:
    """Resuelve la routing key en base al tipo de evento y el tier del tenant."""
    if event_type == "TimeLogged" and tenant_id:
        tier = await get_tenant_tier(session, tenant_id)
        return "fin.time_logged.vip.recorded" if tier == "vip" else "fin.time_logged.recorded"

    routing_keys = {
        "GitEventReceived": "git.events.received",
        "FinancialContractCreated": "fin.financial_contract.created",
        "FinancialContractUpdated": "fin.financial_contract.updated",
        "FinancialContractDeleted": "fin.financial_contract.deleted",
    }
    return routing_keys.get(event_type, f"event.{event_type.lower()}")


async def run_outbox_relay(session_factory: Any, broker: RabbitBroker) -> None:
    """Bucle infinito que procesa y publica eventos pendientes en la tabla outbox."""
    logger.info("Outbox Relay iniciado y escuchando...")
    while True:
        try:
            async with session_factory() as session, session.begin():
                    # Obtener eventos no publicados
                    res = await session.execute(
                        text("""
                            SELECT id, event_type, tenant_id, payload, headers
                            FROM outbox
                            WHERE published_at IS NULL
                            ORDER BY id
                            LIMIT :limit
                            FOR UPDATE SKIP LOCKED
                        """),
                        {"limit": BATCH_SIZE}
                    )
                    rows = res.fetchall()

                    if rows:
                        for row in rows:
                            row_id, event_type, tenant_id, payload_stored, headers_stored = row

                            # Los datos en PostgreSQL JSONB pueden venir como dict o str según configuración
                            payload = payload_stored if isinstance(payload_stored, dict) else json.loads(payload_stored)
                            headers = headers_stored if isinstance(headers_stored, dict) else json.loads(headers_stored)

                            # Resolver la routing key
                            routing_key = await resolve_routing_key(session, event_type, tenant_id)

                            # Publicar al broker
                            await broker.publish(
                                message=payload,
                                routing_key=routing_key,
                                exchange=pm_exchange,
                                headers=headers,
                            )

                            # Marcar como publicado
                            await session.execute(
                                text("UPDATE outbox SET published_at = :published_at WHERE id = :id"),
                                {"published_at": datetime.now(UTC), "id": row_id}
                            )
                            logger.info(f"Evento {event_type} (id: {row_id}) publicado con routing key {routing_key}")

        except asyncio.CancelledError:
            logger.info("Outbox Relay cancelado.")
            break
        except Exception as e:
            logger.error(f"Error en Outbox Relay: {e}", exc_info=True)

        await asyncio.sleep(POLL_INTERVAL)
