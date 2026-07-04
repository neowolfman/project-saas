from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from apps.backend.src.database import api_session_factory, save_outbox_event
from apps.backend.src.dependencies import require_roles, require_tenant_access
from apps.backend.src.events import ProjectCreated, ProjectDeleted, ProjectUpdated
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

router = APIRouter(prefix="/projects", tags=["projects"])


# --- Modelos de Petición y Respuesta ---

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    lead_user_id: UUID | None = None


class ProjectUpdate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    status: str = Field("active", pattern="^(active|inactive|archived)$")
    lead_user_id: UUID | None = None


class ProjectResponse(BaseModel):
    project_id: UUID
    name: str
    status: str
    lead_user_id: UUID | None
    created_at: datetime


# --- Endpoints ---

@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    tenant_id: UUID = Depends(require_tenant_access),
) -> list[dict[str, Any]]:
    """Lista todos los proyectos pertenecientes al tenant actual."""
    async with api_session_factory() as session:
        result = await session.execute(
            text("SELECT project_id, name, status, lead_user_id, created_at FROM projects"),
        )
        rows = result.fetchall()
        return [
            {
                "project_id": row[0],
                "name": row[1],
                "status": row[2],
                "lead_user_id": row[3],
                "created_at": row[4],
            }
            for row in rows
        ]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    tenant_id: UUID = Depends(require_tenant_access),
    current_user: dict[str, Any] = Depends(require_roles(["Tenant Admin", "PM"])),
) -> Any:
    """Crea un nuevo proyecto y registra el evento correspondiente en el Outbox."""
    project_id = uuid4()
    async with api_session_factory() as session:
        # 1. Insertar el proyecto obteniendo su fecha de creación
        result = await session.execute(
            text("""
                INSERT INTO projects (project_id, tenant_id, name, lead_user_id, status)
                VALUES (:project_id, :tenant_id, :name, :lead_user_id, 'active')
                RETURNING created_at
            """),
            {
                "project_id": project_id,
                "tenant_id": tenant_id,
                "name": body.name,
                "lead_user_id": body.lead_user_id,
            },
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No se pudo registrar el proyecto en la base de datos.",
            )
        created_at = row[0]

        # 2. Registrar el evento de dominio en Outbox
        event = ProjectCreated(
            tenant_id=tenant_id,
            project_id=project_id,
            name=body.name,
            status="active",
            lead_user_id=body.lead_user_id,
        )
        await save_outbox_event(session, "Project", project_id, event)
        await session.commit()

    return {
        "project_id": project_id,
        "name": body.name,
        "status": "active",
        "lead_user_id": body.lead_user_id,
        "created_at": created_at,
    }


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    tenant_id: UUID = Depends(require_tenant_access),
) -> Any:
    """Obtiene los detalles de un proyecto específico."""
    async with api_session_factory() as session:
        result = await session.execute(
            text("""
                SELECT project_id, name, status, lead_user_id, created_at
                FROM projects WHERE project_id = :project_id
            """),
            {"project_id": project_id},
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proyecto no encontrado.",
            )
        return {
            "project_id": row[0],
            "name": row[1],
            "status": row[2],
            "lead_user_id": row[3],
            "created_at": row[4],
        }


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    tenant_id: UUID = Depends(require_tenant_access),
    current_user: dict[str, Any] = Depends(require_roles(["Tenant Admin", "PM"])),
) -> Any:
    """Actualiza la información de un proyecto existente y registra el evento en el Outbox."""
    async with api_session_factory() as session:
        # 1. Modificar el registro
        result = await session.execute(
            text("""
                UPDATE projects
                SET name = :name, status = :status, lead_user_id = :lead_user_id
                WHERE project_id = :project_id
                RETURNING created_at
            """),
            {
                "project_id": project_id,
                "name": body.name,
                "status": body.status,
                "lead_user_id": body.lead_user_id,
            },
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proyecto no encontrado.",
            )
        created_at = row[0]

        # 2. Registrar el evento de dominio en Outbox
        event = ProjectUpdated(
            tenant_id=tenant_id,
            project_id=project_id,
            name=body.name,
            status=body.status,
            lead_user_id=body.lead_user_id,
        )
        await save_outbox_event(session, "Project", project_id, event)
        await session.commit()

    return {
        "project_id": project_id,
        "name": body.name,
        "status": body.status,
        "lead_user_id": body.lead_user_id,
        "created_at": created_at,
    }


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    tenant_id: UUID = Depends(require_tenant_access),
    current_user: dict[str, Any] = Depends(require_roles(["Tenant Admin", "PM"])),
) -> None:
    """Elimina un proyecto y registra el evento en el Outbox."""
    async with api_session_factory() as session:
        # 1. Borrar el registro
        result = await session.execute(
            text("DELETE FROM projects WHERE project_id = :project_id RETURNING 1"),
            {"project_id": project_id},
        )
        if not result.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proyecto no encontrado.",
            )

        # 2. Registrar el evento de dominio en Outbox
        event = ProjectDeleted(
            tenant_id=tenant_id,
            project_id=project_id,
        )
        await save_outbox_event(session, "Project", project_id, event)
        await session.commit()
