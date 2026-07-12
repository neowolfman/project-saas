import logging
import re
from typing import Any
from uuid import UUID

from apps.backend.src.events import TimeLogged
from apps.workers.src.database import api_session_factory, save_outbox_event
from apps.workers.src.topology import git_queue, pm_exchange
from db_clients.session import tenant_context
from faststream.rabbit import RabbitRouter
from sqlalchemy import text

logger = logging.getLogger("git_consumer")

router = RabbitRouter()

# Regex to match: Resolves #<id> [Time: <hours>]
commit_regex = re.compile(r"resolves\s+#(\d+)\s+\[time:\s*([\d\.]+)\]", re.IGNORECASE)

DEFAULT_ROLE_RATES = {
    "SuperAdmin": 60000.0,
    "Tenant Admin": 50000.0,
    "PM": 45000.0,
    "Scrum Master": 40000.0,
    "Product Owner": 40000.0,
    "Developer": 30000.0,
    "QA": 25000.0,
}


@router.subscriber(git_queue, pm_exchange)
async def on_git_event(msg: dict[str, Any]) -> None:
    """Consumidor que procesa los webhooks de Git.
    
    Busca commits con la nomenclatura 'Resolves #XX [Time: YY]' para
    registrar de manera automática logs de horas trabajadas.
    """
    logger.info(f"Procesando evento de Git recibido. Msg ID: {msg.get('event_id')}")
    
    tenant_id_str = msg.get("tenant_id")
    if not tenant_id_str:
        logger.error("El mensaje de Git no contiene tenant_id. Saltando.")
        return
        
    tenant_id = UUID(tenant_id_str)
    provider = msg.get("provider", "unknown")
    payload = msg.get("payload", {})
    commits = payload.get("commits", [])
    
    if not commits:
        logger.info("El webhook de Git no contiene commits. Saltando.")
        return
        
    for commit in commits:
        message = commit.get("message", "")
        commit_hash = commit.get("id", "")
        author_email = commit.get("author", {}).get("email", "")
        
        if not message or not author_email:
            continue
            
        # Buscar matches en el mensaje del commit
        matches = commit_regex.findall(message)
        if not matches:
            continue
            
        logger.info(f"Encontrados {len(matches)} tags de tiempo en el commit {commit_hash[:8]}")
        
        for task_id_str, hours_str in matches:
            try:
                task_id = int(task_id_str)
                hours = float(hours_str)
            except ValueError:
                logger.error(f"Error parseando valores del commit: {task_id_str}, {hours_str}")
                continue
                
            # Ejecutar operaciones en el contexto de base de datos del tenant
            async with tenant_context(tenant_id), api_session_factory() as session:
                async with session.begin():
                    # 0. Verificar si el commit ya fue procesado para evitar duplicados
                    evidence = f"git:commit:{commit_hash}"
                    dup_res = await session.execute(
                        text("SELECT 1 FROM time_logs WHERE evidence = :evidence AND tenant_id = :tenant_id LIMIT 1"),
                        {"evidence": evidence, "tenant_id": tenant_id}
                    )
                    if dup_res.fetchone():
                        logger.info(f"El commit {commit_hash[:8]} ya fue procesado previamente. Saltando.")
                        continue

                    # 1. Resolver el usuario por su email
                    user_res = await session.execute(
                        text("SELECT user_id FROM users WHERE LOWER(email) = LOWER(:email) AND tenant_id = :tenant_id"),
                        {"email": author_email, "tenant_id": tenant_id}
                    )
                    user_row = user_res.fetchone()
                    if not user_row:
                        logger.warning(f"No se encontró un usuario con email {author_email} en el tenant {tenant_id}. Saltando.")
                        continue
                        
                    user_id = user_row[0]
                    
                    # 2. Verificar que la tarea exista y obtener su project_id
                    task_res = await session.execute(
                        text("SELECT project_id FROM tasks WHERE task_id = :task_id AND tenant_id = :tenant_id"),
                        {"task_id": task_id, "tenant_id": tenant_id}
                    )
                    task_row = task_res.fetchone()
                    if not task_row:
                        logger.warning(f"No se encontró la tarea #{task_id} en el tenant {tenant_id}. Saltando.")
                        continue
                        
                    project_id = task_row[0]
                    
                    # 3. Resolver la tarifa del rol del usuario
                    roles_res = await session.execute(
                        text("""
                            SELECT r.name 
                            FROM roles r
                            JOIN user_roles ur ON ur.role_id = r.role_id
                            WHERE ur.user_id = :user_id
                        """),
                        {"user_id": user_id}
                    )
                    user_roles = [row[0] for row in roles_res.fetchall()]
                    
                    role_cost = 30000.0  # Tarifa por defecto de Developer
                    if user_roles:
                        rates = [DEFAULT_ROLE_RATES.get(r, 0.0) for r in user_roles]
                        if rates:
                            max_rate = max(rates)
                            if max_rate > 0.0:
                                role_cost = max_rate
                                
                    amount = hours * role_cost
                    evidence = f"git:commit:{commit_hash}"
                    source_ref = f"{provider}:{commit_hash[:8]}"
                    
                    # 4. Insertar el Time Log en base de datos (TimescaleDB)
                    time_log_res = await session.execute(
                        text("""
                            INSERT INTO time_logs (user_id, project_id, task_id, tenant_id, hours, role_cost, amount, evidence, source_ref, logged_at)
                            VALUES (:user_id, :project_id, :task_id, :tenant_id, :hours, :role_cost, :amount, :evidence, :source_ref, now())
                            RETURNING id
                        """),
                        {
                            "user_id": user_id,
                            "project_id": project_id,
                            "task_id": task_id,
                            "tenant_id": tenant_id,
                            "hours": hours,
                            "role_cost": role_cost,
                            "amount": amount,
                            "evidence": evidence,
                            "source_ref": source_ref
                        }
                    )
                    time_log_row = time_log_res.fetchone()
                    if not time_log_row:
                        logger.error("No se pudo insertar el time log.")
                        continue
                    time_log_id = time_log_row[0]
                    
                    # 5. Registrar el evento TimeLogged en el outbox transaccional
                    event = TimeLogged(
                        tenant_id=tenant_id,
                        time_log_id=time_log_id,
                        user_id=user_id,
                        project_id=project_id,
                        task_id=task_id,
                        hours=hours,
                        role_cost=role_cost,
                        amount=amount,
                        evidence=evidence,
                        source_ref=source_ref
                    )
                    
                    await save_outbox_event(session, "TimeLog", project_id, event)
                    logger.info(f"Time Log {time_log_id} registrado automáticamente por commit {commit_hash[:8]} para usuario {user_id}")
