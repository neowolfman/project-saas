from datetime import datetime
from typing import Any
from uuid import UUID

from apps.backend.src.database import api_session_factory, save_outbox_event
from apps.backend.src.dependencies import require_roles, require_tenant_access
from apps.backend.src.events import TaskCreated, TaskDeleted, TaskUpdated
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

router = APIRouter(prefix="/tasks", tags=["tasks"])


# --- Modelos de Petición y Respuesta ---

class TaskCreate(BaseModel):
    project_id: UUID
    title: str = Field(..., min_length=3, max_length=150)
    assignee_user_id: UUID | None = None
    story_points: int | None = Field(None, ge=0)
    client_visible: bool = False


class TaskUpdate(BaseModel):
    title: str = Field(..., min_length=3, max_length=150)
    state: str = Field("todo", pattern="^(todo|inprogress|review|done)$")
    assignee_user_id: UUID | None = None
    story_points: int | None = Field(None, ge=0)
    client_visible: bool = False


class TaskResponse(BaseModel):
    task_id: int
    project_id: UUID
    assignee_user_id: UUID | None
    title: str
    state: str
    story_points: int | None
    client_visible: bool
    updated_at: datetime


# --- Endpoints ---

@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    project_id: UUID | None = None,
    assignee_user_id: UUID | None = None,
    tenant_id: UUID = Depends(require_tenant_access),
) -> list[dict[str, Any]]:
    """Lista las tareas correspondientes al inquilino, permitiendo filtros opcionales."""
    query = """
        SELECT task_id, project_id, assignee_user_id, title, state, story_points, client_visible, updated_at
        FROM tasks WHERE 1=1
    """
    params: dict[str, Any] = {}

    if project_id:
        query += " AND project_id = :project_id"
        params["project_id"] = project_id
    if assignee_user_id:
        query += " AND assignee_user_id = :assignee_user_id"
        params["assignee_user_id"] = assignee_user_id

    async with api_session_factory() as session:
        result = await session.execute(text(query), params)
        rows = result.fetchall()
        return [
            {
                "task_id": row[0],
                "project_id": row[1],
                "assignee_user_id": row[2],
                "title": row[3],
                "state": row[4],
                "story_points": row[5],
                "client_visible": row[6],
                "updated_at": row[7],
            }
            for row in rows
        ]


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreate,
    tenant_id: UUID = Depends(require_tenant_access),
    current_user: dict[str, Any] = Depends(require_roles(["Tenant Admin", "PM", "Developer", "Scrum Master"])),
) -> Any:
    """Crea una nueva tarea vinculada a un proyecto verificado y registra el evento en el Outbox."""
    async with api_session_factory() as session:
        # 1. Validar que el proyecto pertenezca al tenant (respetando RLS)
        proj_res = await session.execute(
            text("SELECT 1 FROM projects WHERE project_id = :project_id"),
            {"project_id": body.project_id},
        )
        if not proj_res.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El proyecto especificado no existe o no tiene acceso a él.",
            )

        # 2. Insertar la tarea
        result = await session.execute(
            text("""
                INSERT INTO tasks (tenant_id, project_id, assignee_user_id, title, story_points, client_visible, state)
                VALUES (:tenant_id, :project_id, :assignee_user_id, :title, :story_points, :client_visible, 'todo')
                RETURNING task_id, updated_at
            """),
            {
                "tenant_id": tenant_id,
                "project_id": body.project_id,
                "assignee_user_id": body.assignee_user_id,
                "title": body.title,
                "story_points": body.story_points,
                "client_visible": body.client_visible,
            },
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No se pudo registrar la tarea en la base de datos.",
            )
        task_id, updated_at = row

        # 3. Registrar el evento en el Outbox
        event = TaskCreated(
            tenant_id=tenant_id,
            task_id=task_id,
            project_id=body.project_id,
            title=body.title,
            state="todo",
            assignee_user_id=body.assignee_user_id,
            story_points=body.story_points,
            client_visible=body.client_visible,
        )
        await save_outbox_event(session, "Task", UUID(int=task_id), event)
        await session.commit()

    return {
        "task_id": task_id,
        "project_id": body.project_id,
        "assignee_user_id": body.assignee_user_id,
        "title": body.title,
        "state": "todo",
        "story_points": body.story_points,
        "client_visible": body.client_visible,
        "updated_at": updated_at,
    }


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    tenant_id: UUID = Depends(require_tenant_access),
) -> Any:
    """Obtiene los detalles de una tarea específica."""
    async with api_session_factory() as session:
        result = await session.execute(
            text("""
                SELECT task_id, project_id, assignee_user_id, title, state, story_points, client_visible, updated_at
                FROM tasks
                WHERE task_id = :task_id
            """),
            {"task_id": task_id},
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tarea no encontrada.",
            )
        return {
            "task_id": row[0],
            "project_id": row[1],
            "assignee_user_id": row[2],
            "title": row[3],
            "state": row[4],
            "story_points": row[5],
            "client_visible": row[6],
            "updated_at": row[7],
        }


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    body: TaskUpdate,
    tenant_id: UUID = Depends(require_tenant_access),
    current_user: dict[str, Any] = Depends(require_roles(["Tenant Admin", "PM", "Developer", "Scrum Master"])),
) -> Any:
    """Actualiza la información de una tarea existente y registra el evento en el Outbox."""
    async with api_session_factory() as session:
        # 1. Modificar el registro
        result = await session.execute(
            text("""
                UPDATE tasks
                SET title = :title, state = :state, assignee_user_id = :assignee_user_id,
                    story_points = :story_points, client_visible = :client_visible, updated_at = now()
                WHERE task_id = :task_id
                RETURNING project_id, updated_at
            """),
            {
                "task_id": task_id,
                "title": body.title,
                "state": body.state,
                "assignee_user_id": body.assignee_user_id,
                "story_points": body.story_points,
                "client_visible": body.client_visible,
            },
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tarea no encontrada.",
            )
        project_id, updated_at = row

        # 2. Registrar el evento de dominio en Outbox
        event = TaskUpdated(
            tenant_id=tenant_id,
            task_id=task_id,
            project_id=project_id,
            title=body.title,
            state=body.state,
            assignee_user_id=body.assignee_user_id,
            story_points=body.story_points,
            client_visible=body.client_visible,
        )
        await save_outbox_event(session, "Task", UUID(int=task_id), event)
        await session.commit()

    return {
        "task_id": task_id,
        "project_id": project_id,
        "assignee_user_id": body.assignee_user_id,
        "title": body.title,
        "state": body.state,
        "story_points": body.story_points,
        "client_visible": body.client_visible,
        "updated_at": updated_at,
    }


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    tenant_id: UUID = Depends(require_tenant_access),
    current_user: dict[str, Any] = Depends(require_roles(["Tenant Admin", "PM", "Developer", "Scrum Master"])),
) -> None:
    """Elimina una tarea y registra el evento en el Outbox."""
    async with api_session_factory() as session:
        # 1. Borrar el registro
        result = await session.execute(
            text("DELETE FROM tasks WHERE task_id = :task_id RETURNING 1"),
            {"task_id": task_id},
        )
        if not result.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tarea no encontrada.",
            )

        # 2. Registrar el evento de dominio en Outbox
        event = TaskDeleted(
            tenant_id=tenant_id,
            task_id=task_id,
        )
        await save_outbox_event(session, "Task", UUID(int=task_id), event)
        await session.commit()
