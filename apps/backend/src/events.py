from uuid import UUID

from ddd_core.base import DomainEvent


class ProjectCreated(DomainEvent):
    """Evento emitido al crear un proyecto."""

    project_id: UUID
    name: str
    status: str
    lead_user_id: UUID | None


class ProjectUpdated(DomainEvent):
    """Evento emitido al actualizar un proyecto."""

    project_id: UUID
    name: str
    status: str
    lead_user_id: UUID | None


class ProjectDeleted(DomainEvent):
    """Evento emitido al eliminar un proyecto."""

    project_id: UUID


class TaskCreated(DomainEvent):
    """Evento emitido al crear una tarea."""

    task_id: int
    project_id: UUID
    title: str
    state: str
    assignee_user_id: UUID | None
    story_points: int | None
    client_visible: bool


class TaskUpdated(DomainEvent):
    """Evento emitido al actualizar una tarea."""

    task_id: int
    project_id: UUID
    title: str
    state: str
    assignee_user_id: UUID | None
    story_points: int | None
    client_visible: bool


class TaskDeleted(DomainEvent):
    """Evento emitido al eliminar una tarea."""

    task_id: int
