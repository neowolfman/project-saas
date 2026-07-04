from typing import Callable, Awaitable
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


async def run_idempotent(session: AsyncSession, event_id: UUID, consumer: str, handler: Callable[[], Awaitable[None]]) -> None:
    """Ejecuta un handler transaccional de forma idempotente, previniendo duplicados.
    
    Inserta en processed_events. Si ya existe la tupla (event_id, consumer),
    no realiza ninguna acción y descarta el procesamiento.
    """
    res = await session.execute(
        text("""
            INSERT INTO processed_events (event_id, consumer)
            VALUES (:event_id, :consumer)
            ON CONFLICT DO NOTHING
            RETURNING 1
        """),
        {"event_id": event_id, "consumer": consumer}
    )
    inserted = res.fetchone()
    if inserted is None:
        # Ya procesado -> descartar duplicado
        return
    
    # Ejecuta el callback si se pudo insertar el evento procesado
    await handler()
