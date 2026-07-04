import json
from datetime import date
from typing import Any
from uuid import UUID, uuid4

from apps.backend.src.database import api_session_factory, save_outbox_event
from apps.backend.src.dependencies import require_roles, require_tenant_access
from apps.backend.src.events import (
    FinancialContractCreated,
    FinancialContractDeleted,
    FinancialContractUpdated,
)
from db_clients.session import tenant_context
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

router = APIRouter(prefix="/financial-contracts", tags=["Financial Contracts"])


class FinancialContractCreate(BaseModel):
    project_id: UUID | None = None
    contract_value: float = Field(..., ge=0, description="Monto del contrato")
    margin_target_pct: float = Field(..., ge=0, le=100, description="Margen meta en porcentaje")
    sla_terms: dict[str, Any] = Field(default_factory=dict, description="Cláusulas de SLA en JSON")
    window_start: date | None = None
    window_end: date | None = None


class FinancialContractUpdate(BaseModel):
    contract_value: float = Field(..., ge=0)
    margin_target_pct: float = Field(..., ge=0, le=100)
    sla_terms: dict[str, Any] = Field(default_factory=dict)
    window_start: date | None = None
    window_end: date | None = None


class FinancialContractResponse(BaseModel):
    contract_id: UUID
    tenant_id: UUID
    project_id: UUID | None
    contract_value: float
    margin_target_pct: float
    sla_terms: dict[str, Any]
    window_start: date | None
    window_end: date | None


@router.post("", response_model=FinancialContractResponse, status_code=status.HTTP_201_CREATED)
async def create_contract(
    payload: FinancialContractCreate,
    tenant_id: UUID = Depends(require_tenant_access),
    _role_ok: dict[str, Any] = Depends(require_roles(["Tenant Admin", "PM"])),
) -> Any:
    """Crea un contrato financiero asociado a un proyecto del inquilino actual."""
    contract_id = uuid4()

    async with tenant_context(tenant_id), api_session_factory() as session:
        # Si se especifica un proyecto, verificar que exista en el tenant
        if payload.project_id:
            proj_res = await session.execute(
                text("SELECT name FROM projects WHERE project_id = :project_id"),
                {"project_id": payload.project_id},
            )
            if not proj_res.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="El proyecto especificado no existe o no pertenece a este tenant",
                )

        await session.execute(
            text("""
                INSERT INTO financial_contracts (
                    contract_id, tenant_id, project_id, contract_value,
                    margin_target_pct, sla_terms, window_start, window_end
                )
                VALUES (
                    :contract_id, :tenant_id, :project_id, :contract_value,
                    :margin_target_pct, :sla_terms, :window_start, :window_end
                )
            """),
            {
                "contract_id": contract_id,
                "tenant_id": tenant_id,
                "project_id": payload.project_id,
                "contract_value": payload.contract_value,
                "margin_target_pct": payload.margin_target_pct,
                "sla_terms": json.dumps(payload.sla_terms),
                "window_start": payload.window_start,
                "window_end": payload.window_end,
            },
        )

        # Generar evento Outbox
        event = FinancialContractCreated(
            tenant_id=tenant_id,
            contract_id=contract_id,
            project_id=payload.project_id,
            contract_value=payload.contract_value,
            margin_target_pct=payload.margin_target_pct,
            sla_terms=payload.sla_terms,
        )
        # Usar contract_id como aggregate_id
        await save_outbox_event(session, "FinancialContract", contract_id, event)
        await session.commit()

        return {
            "contract_id": contract_id,
            "tenant_id": tenant_id,
            "project_id": payload.project_id,
            "contract_value": payload.contract_value,
            "margin_target_pct": payload.margin_target_pct,
            "sla_terms": payload.sla_terms,
            "window_start": payload.window_start,
            "window_end": payload.window_end,
        }


@router.get("", response_model=list[FinancialContractResponse])
async def list_contracts(
    tenant_id: UUID = Depends(require_tenant_access),
    _role_ok: dict[str, Any] = Depends(require_roles(["Tenant Admin", "PM"])),
) -> Any:
    """Lista todos los contratos financieros del tenant actual."""
    async with tenant_context(tenant_id), api_session_factory() as session:
        result = await session.execute(
            text("""
                SELECT contract_id, tenant_id, project_id, contract_value,
                       margin_target_pct, sla_terms, window_start, window_end
                FROM financial_contracts
                WHERE tenant_id = :tenant_id
            """),
            {"tenant_id": tenant_id},
        )
        rows = result.fetchall()
        return [
            {
                "contract_id": r[0],
                "tenant_id": r[1],
                "project_id": r[2],
                "contract_value": float(r[3]),
                "margin_target_pct": float(r[4]),
                "sla_terms": r[5] if isinstance(r[5], dict) else {},
                "window_start": r[6],
                "window_end": r[7],
            }
            for r in rows
        ]


@router.get("/{contract_id}", response_model=FinancialContractResponse)
async def get_contract(
    contract_id: UUID,
    tenant_id: UUID = Depends(require_tenant_access),
    _role_ok: dict[str, Any] = Depends(require_roles(["Tenant Admin", "PM"])),
) -> Any:
    """Obtiene el detalle de un contrato financiero específico."""
    async with tenant_context(tenant_id), api_session_factory() as session:
        result = await session.execute(
            text("""
                SELECT contract_id, tenant_id, project_id, contract_value,
                       margin_target_pct, sla_terms, window_start, window_end
                FROM financial_contracts
                WHERE contract_id = :contract_id AND tenant_id = :tenant_id
            """),
            {"contract_id": contract_id, "tenant_id": tenant_id},
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El contrato financiero especificado no existe o no tiene permisos",
            )

        return {
            "contract_id": row[0],
            "tenant_id": row[1],
            "project_id": row[2],
            "contract_value": float(row[3]),
            "margin_target_pct": float(row[4]),
            "sla_terms": row[5] if isinstance(row[5], dict) else {},
            "window_start": row[6],
            "window_end": row[7],
        }


@router.put("/{contract_id}", response_model=FinancialContractResponse)
async def update_contract(
    contract_id: UUID,
    payload: FinancialContractUpdate,
    tenant_id: UUID = Depends(require_tenant_access),
    _role_ok: dict[str, Any] = Depends(require_roles(["Tenant Admin", "PM"])),
) -> Any:
    """Actualiza un contrato financiero existente."""
    async with tenant_context(tenant_id), api_session_factory() as session:
        # Verificar existencia del contrato
        check_res = await session.execute(
            text("""
                SELECT project_id FROM financial_contracts
                WHERE contract_id = :contract_id AND tenant_id = :tenant_id
            """),
            {"contract_id": contract_id, "tenant_id": tenant_id},
        )
        check_row = check_res.fetchone()
        if not check_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El contrato financiero especificado no existe o no tiene permisos",
            )

        project_id = check_row[0]

        await session.execute(
            text("""
                UPDATE financial_contracts
                SET contract_value = :contract_value,
                    margin_target_pct = :margin_target_pct,
                    sla_terms = :sla_terms,
                    window_start = :window_start,
                    window_end = :window_end
                WHERE contract_id = :contract_id AND tenant_id = :tenant_id
            """),
            {
                "contract_id": contract_id,
                "tenant_id": tenant_id,
                "contract_value": payload.contract_value,
                "margin_target_pct": payload.margin_target_pct,
                "sla_terms": json.dumps(payload.sla_terms),
                "window_start": payload.window_start,
                "window_end": payload.window_end,
            },
        )

        # Generar evento Outbox
        event = FinancialContractUpdated(
            tenant_id=tenant_id,
            contract_id=contract_id,
            project_id=project_id,
            contract_value=payload.contract_value,
            margin_target_pct=payload.margin_target_pct,
            sla_terms=payload.sla_terms,
        )
        await save_outbox_event(session, "FinancialContract", contract_id, event)
        await session.commit()

        return {
            "contract_id": contract_id,
            "tenant_id": tenant_id,
            "project_id": project_id,
            "contract_value": payload.contract_value,
            "margin_target_pct": payload.margin_target_pct,
            "sla_terms": payload.sla_terms,
            "window_start": payload.window_start,
            "window_end": payload.window_end,
        }


@router.delete("/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contract(
    contract_id: UUID,
    tenant_id: UUID = Depends(require_tenant_access),
    _role_ok: dict[str, Any] = Depends(require_roles(["Tenant Admin", "PM"])),
) -> None:
    """Elimina un contrato financiero existente."""
    async with tenant_context(tenant_id), api_session_factory() as session:
        check_res = await session.execute(
            text("""
                SELECT 1 FROM financial_contracts
                WHERE contract_id = :contract_id AND tenant_id = :tenant_id
            """),
            {"contract_id": contract_id, "tenant_id": tenant_id},
        )
        if not check_res.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El contrato financiero especificado no existe o no tiene permisos",
            )

        await session.execute(
            text("DELETE FROM financial_contracts WHERE contract_id = :contract_id AND tenant_id = :tenant_id"),
            {"contract_id": contract_id, "tenant_id": tenant_id},
        )

        # Generar evento Outbox
        event = FinancialContractDeleted(tenant_id=tenant_id, contract_id=contract_id)
        await save_outbox_event(session, "FinancialContract", contract_id, event)
        await session.commit()
