from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from apps.backend.src.database import api_session_factory, save_outbox_event
from apps.backend.src.dependencies import get_current_user, require_tenant_access
from apps.backend.src.events import TimeLogged
from db_clients.session import tenant_context
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

router = APIRouter(prefix="/time-logs", tags=["Time Tracking"])

# Diccionario de tarifas estándar por hora en CLP según el rol del usuario
DEFAULT_ROLE_RATES = {
    "SuperAdmin": 60000.0,
    "Tenant Admin": 50000.0,
    "PM": 45000.0,
    "Scrum Master": 40000.0,
    "Product Owner": 40000.0,
    "Developer": 30000.0,
    "QA": 25000.0,
    "Cliente Externo": 0.0,
    "Auditor": 0.0,
}


class TimeLogCreate(BaseModel):
    project_id: UUID
    task_id: int | None = None
    hours: float = Field(..., gt=0, description="Cantidad de horas registradas")
    evidence: str = Field(..., description="Evidencia o descripción del trabajo realizado")
    source_ref: str | None = Field(None, description="Referencia de origen (ej: hash de commit de Git)")
    logged_at: datetime | None = Field(None, description="Fecha/hora del log. Por defecto now()")


class TimeLogResponse(BaseModel):
    id: int
    tenant_id: UUID
    user_id: UUID
    project_id: UUID
    task_id: int | None
    hours: float
    role_cost: float
    amount: float
    evidence: str
    source_ref: str | None
    logged_at: datetime


class TimeLogSummaryItem(BaseModel):
    label: str  # ID o nombre del proyecto / usuario
    total_hours: float
    total_amount: float


@router.post("", response_model=TimeLogResponse, status_code=status.HTTP_201_CREATED)
async def create_time_log(
    payload: TimeLogCreate,
    tenant_id: UUID = Depends(require_tenant_access),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> Any:
    """Registra horas de trabajo para un proyecto y tarea, resolviendo el costo de rol automáticamente."""
    user_id = UUID(str(current_user["sub"]))

    async with tenant_context(tenant_id), api_session_factory() as session:
        # 1. Verificar que el proyecto exista en este tenant
        proj_res = await session.execute(
            text("SELECT name FROM projects WHERE project_id = :project_id"),
            {"project_id": payload.project_id},
        )
        if not proj_res.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El proyecto especificado no existe o no pertenece a este tenant",
            )

        # 2. Verificar que la tarea exista y pertenezca al mismo proyecto si se provee task_id
        if payload.task_id is not None:
            task_res = await session.execute(
                text("SELECT state FROM tasks WHERE task_id = :task_id AND project_id = :project_id"),
                {"task_id": payload.task_id, "project_id": payload.project_id},
            )
            if not task_res.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La tarea especificada no pertenece al proyecto provisto",
                )

        # 3. Obtener los roles del usuario para resolver el costo por hora
        role_res = await session.execute(
            text("""
                SELECT r.name
                FROM roles r
                JOIN user_roles ur ON r.role_id = ur.role_id
                WHERE ur.user_id = :user_id
            """),
            {"user_id": user_id},
        )
        roles = [row[0] for row in role_res.fetchall()]

        role_cost = 30000.0  # Por defecto tarifa de Developer
        if roles:
            rates = [DEFAULT_ROLE_RATES.get(r, 30000.0) for r in roles]
            role_cost = max(rates)

        amount = payload.hours * role_cost
        logged_at = payload.logged_at or datetime.now(UTC)

        # 4. Insertar en la hypertable time_logs
        insert_res = await session.execute(
            text("""
                INSERT INTO time_logs (
                    tenant_id, user_id, project_id, task_id, hours,
                    role_cost, amount, evidence, source_ref, logged_at
                )
                VALUES (
                    :tenant_id, :user_id, :project_id, :task_id, :hours,
                    :role_cost, :amount, :evidence, :source_ref, :logged_at
                )
                RETURNING id, logged_at
            """),
            {
                "tenant_id": tenant_id,
                "user_id": user_id,
                "project_id": payload.project_id,
                "task_id": payload.task_id,
                "hours": payload.hours,
                "role_cost": role_cost,
                "amount": amount,
                "evidence": payload.evidence,
                "source_ref": payload.source_ref,
                "logged_at": logged_at,
            },
        )
        row = insert_res.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No se pudo registrar el log de tiempo",
            )

        time_log_id, actual_logged_at = row[0], row[1]

        # 5. Generar evento de dominio TimeLogged e insertar en outbox
        event = TimeLogged(
            tenant_id=tenant_id,
            time_log_id=time_log_id,
            user_id=user_id,
            project_id=payload.project_id,
            task_id=payload.task_id,
            hours=payload.hours,
            role_cost=role_cost,
            amount=amount,
            evidence=payload.evidence,
            source_ref=payload.source_ref,
        )
        await save_outbox_event(session, "TimeLog", payload.project_id, event)
        await session.commit()

        return {
            "id": time_log_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "project_id": payload.project_id,
            "task_id": payload.task_id,
            "hours": payload.hours,
            "role_cost": role_cost,
            "amount": amount,
            "evidence": payload.evidence,
            "source_ref": payload.source_ref,
            "logged_at": actual_logged_at,
        }


@router.get("", response_model=list[TimeLogResponse])
async def list_time_logs(
    project_id: UUID | None = None,
    user_id: UUID | None = None,
    task_id: int | None = None,
    tenant_id: UUID = Depends(require_tenant_access),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> Any:
    """Obtiene los registros de tiempo filtrados por proyecto, usuario o tarea en el tenant actual."""
    async with tenant_context(tenant_id), api_session_factory() as session:
        query = """
            SELECT id, tenant_id, user_id, project_id, task_id,
                   hours, role_cost, amount, evidence, source_ref, logged_at
            FROM time_logs
            WHERE tenant_id = :tenant_id
        """
        params: dict[str, Any] = {"tenant_id": tenant_id}

        if project_id:
            query += " AND project_id = :project_id"
            params["project_id"] = project_id
        if user_id:
            query += " AND user_id = :user_id"
            params["user_id"] = user_id
        if task_id:
            query += " AND task_id = :task_id"
            params["task_id"] = task_id

        query += " ORDER BY logged_at DESC"
        result = await session.execute(text(query), params)
        rows = result.fetchall()

        return [
            {
                "id": r[0],
                "tenant_id": r[1],
                "user_id": r[2],
                "project_id": r[3],
                "task_id": r[4],
                "hours": float(r[5]),
                "role_cost": float(r[6]),
                "amount": float(r[7]),
                "evidence": r[8],
                "source_ref": r[9],
                "logged_at": r[10],
            }
            for r in rows
        ]


@router.get("/summary", response_model=list[TimeLogSummaryItem])
async def get_time_logs_summary(
    group_by: str = "project",
    tenant_id: UUID = Depends(require_tenant_access),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> Any:
    """Retorna un resumen de horas y costos devengados agrupado por 'project' o 'user'."""
    if group_by not in ("project", "user"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El parámetro group_by debe ser 'project' o 'user'",
        )

    async with tenant_context(tenant_id), api_session_factory() as session:
        if group_by == "project":
            query = """
                SELECT p.name, COALESCE(SUM(t.hours), 0), COALESCE(SUM(t.amount), 0)
                FROM projects p
                LEFT JOIN time_logs t ON p.project_id = t.project_id
                WHERE p.tenant_id = :tenant_id
                GROUP BY p.name
            """
        else:
            query = """
                SELECT u.email, COALESCE(SUM(t.hours), 0), COALESCE(SUM(t.amount), 0)
                FROM users u
                LEFT JOIN time_logs t ON u.user_id = t.user_id
                WHERE u.tenant_id = :tenant_id
                GROUP BY u.email
            """

        result = await session.execute(text(query), {"tenant_id": tenant_id})
        rows = result.fetchall()

        return [
            {
                "label": r[0],
                "total_hours": float(r[1]),
                "total_amount": float(r[2]),
            }
            for r in rows
        ]
