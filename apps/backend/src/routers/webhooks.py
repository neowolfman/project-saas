import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from apps.backend.src.config import settings
from apps.backend.src.database import api_session_factory, save_outbox_event
from apps.backend.src.events import GitEventReceived
from db_clients.session import tenant_context
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from security_utils.hmac import verify_github_signature, verify_gitlab_token
from sqlalchemy import text

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/{tenant_id}/git/{provider}", status_code=status.HTTP_202_ACCEPTED)
async def git_webhook(
    tenant_id: UUID,
    provider: str,
    request: Request,
) -> Any:
    """Recibe webhooks de GitHub o GitLab, valida su firma y los escribe transaccionalmente en el Outbox."""
    if provider not in ("github", "gitlab"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Proveedor de Git no soportado. Debe ser 'github' o 'gitlab'.",
        )

    # 1. Validar existencia del Tenant
    async with api_session_factory() as session:
        tenant_res = await session.execute(
            text("SELECT 1 FROM tenants WHERE tenant_id = :tenant_id"),
            {"tenant_id": tenant_id},
        )
        if not tenant_res.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inquilino (tenant) no encontrado.",
            )

    # 2. Leer cuerpo en bytes y validar firma
    body_bytes = await request.body()

    if provider == "github":
        signature_header = request.headers.get("X-Hub-Signature-256")
        if not signature_header:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Falta la cabecera X-Hub-Signature-256 requerida por GitHub.",
            )
        valid = verify_github_signature(body_bytes, signature_header, settings.GIT_WEBHOOK_SECRET)
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Firma HMAC-SHA256 no válida para GitHub.",
            )

    else:  # gitlab
        token_header = request.headers.get("X-Gitlab-Token")
        if not token_header:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Falta la cabecera X-Gitlab-Token requerida por GitLab.",
            )
        valid = verify_gitlab_token(token_header, settings.GIT_WEBHOOK_SECRET)
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token de GitLab no válido.",
            )

    # 3. Intentar parsear el cuerpo como JSON
    try:
        payload_data = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El cuerpo de la petición debe ser un JSON válido.",
        ) from e

    # 4. Registrar transaccionalmente el evento en el Outbox bajo el contexto del tenant
    event_id = uuid4()
    async with tenant_context(tenant_id), api_session_factory() as session:
        event = GitEventReceived(
            tenant_id=tenant_id,
            provider=provider,
            payload=payload_data,
            received_at=datetime.now(UTC).isoformat(),
        )
        # Guardar en outbox con routing_key personalizado
        await save_outbox_event(session, "GitWebhook", event_id, event)
        await session.commit()

    return JSONResponse(
        status_code=202,
        content={
            "status": "accepted",
            "event_id": str(event_id),
        },
    )
