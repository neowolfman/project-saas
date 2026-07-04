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


class TimeLogged(DomainEvent):
    """Evento emitido al registrar horas de trabajo (Time Tracking)."""

    time_log_id: int
    user_id: UUID
    project_id: UUID
    task_id: int | None
    hours: float
    role_cost: float
    amount: float
    evidence: str
    source_ref: str | None


class FinancialContractCreated(DomainEvent):
    """Evento emitido al crear un contrato financiero."""

    contract_id: UUID
    project_id: UUID | None
    contract_value: float
    margin_target_pct: float
    sla_terms: dict


class FinancialContractUpdated(DomainEvent):
    """Evento emitido al actualizar un contrato financiero."""

    contract_id: UUID
    project_id: UUID | None
    contract_value: float
    margin_target_pct: float
    sla_terms: dict


class FinancialContractDeleted(DomainEvent):
    """Evento emitido al eliminar un contrato financiero."""

    contract_id: UUID


class GitEventReceived(DomainEvent):
    """Evento emitido al recibir un webhook válido de Git (GitHub/GitLab)."""

    provider: str
    payload: dict
    received_at: str

