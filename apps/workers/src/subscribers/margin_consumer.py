import logging
from typing import Any
from uuid import UUID

from apps.workers.src.database import api_session_factory
from apps.workers.src.idempotency import run_idempotent
from apps.workers.src.topology import fin_queue, fin_vip_queue, pm_exchange
from db_clients.session import tenant_context
from faststream.rabbit import RabbitRouter
from sqlalchemy import text

logger = logging.getLogger("margin_consumer")

router = RabbitRouter()


@router.subscriber(fin_queue, pm_exchange)
@router.subscriber(fin_vip_queue, pm_exchange)
async def on_time_logged(msg: dict[str, Any]) -> None:
    """Consumidor que procesa eventos TimeLogged.
    
    Actualiza de forma transaccional e idempotente la tabla de proyecciones
    margin_snapshot sumando el costo de las horas registradas al coste devengado.
    """
    logger.info(f"Procesando evento TimeLogged para margen. Msg ID: {msg.get('event_id')}")
    
    tenant_id_str = msg.get("tenant_id")
    project_id_str = msg.get("project_id")
    amount_str = msg.get("amount")
    event_id_str = msg.get("event_id")
    
    if not tenant_id_str or not project_id_str or amount_str is None or not event_id_str:
        logger.error("Campos obligatorios faltantes en el evento TimeLogged. Saltando.")
        return
        
    tenant_id = UUID(tenant_id_str)
    project_id = UUID(project_id_str)
    amount = float(amount_str)
    event_id = UUID(event_id_str)
    
    async with tenant_context(tenant_id), api_session_factory() as session:
        async with session.begin():
            
            async def update_margin() -> None:
                # 1. Recuperar el valor actual del contrato si existe
                contract_res = await session.execute(
                    text("""
                        SELECT COALESCE(contract_value, 0)
                        FROM financial_contracts
                        WHERE project_id = :project_id AND tenant_id = :tenant_id
                    """),
                    {"project_id": project_id, "tenant_id": tenant_id}
                )
                row = contract_res.fetchone()
                contract_value = float(row[0]) if row else 0.0
                
                # 2. Insertar o actualizar acumulando el costo devengado
                await session.execute(
                    text("""
                        INSERT INTO margin_snapshot (tenant_id, project_id, contract_value, cost_devengado, updated_at)
                        VALUES (:tenant_id, :project_id, :contract_value, :amount, now())
                        ON CONFLICT (tenant_id, project_id) DO UPDATE
                        SET cost_devengado = margin_snapshot.cost_devengado + EXCLUDED.cost_devengado,
                            contract_value = EXCLUDED.contract_value,
                            updated_at = now()
                    """),
                    {
                        "tenant_id": tenant_id,
                        "project_id": project_id,
                        "contract_value": contract_value,
                        "amount": amount
                    }
                )
                logger.info(f"Proyección de margen actualizada para proyecto {project_id} con devengo +{amount} (contrato: {contract_value})")

            # Ejecutar el handler con protección de idempotencia
            await run_idempotent(session, event_id, "fin.margin_projection", update_margin)
