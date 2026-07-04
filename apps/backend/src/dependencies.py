from typing import Any
from uuid import UUID

from apps.backend.src.config import settings
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError
from security_utils import decode_access_token

security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict[str, Any]:
    """Extrae y decodifica el token JWT de la cabecera Authorization."""
    token = credentials.credentials
    try:
        return decode_access_token(token, settings.JWT_SECRET, [settings.JWT_ALGORITHM])
    except ExpiredSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token de acceso ha expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acceso no válido.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def require_tenant_access(
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> UUID:
    """Verifica que el tenant_id de la petición coincida exactamente con el del token JWT.

    Previene ataques de suplantación de tenant (Tenant Spoofing).
    Retorna el tenant_id verificado.
    """
    request_tenant_id = getattr(request.state, "tenant_id", None)
    if not request_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Acceso denegado. No se especificó el contexto de inquilino (tenant).",
        )

    user_tenant_id_str = current_user.get("tenant_id")
    if not user_tenant_id_str or str(user_tenant_id_str) != str(request_tenant_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. No tiene permisos para acceder a los recursos de este inquilino.",
        )

    return request_tenant_id


def require_roles(allowed_roles: list[str]) -> Any:
    """Filtra el acceso a los endpoints basándose en los roles del usuario."""
    def dependency(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        user_role = current_user.get("role")
        if not user_role or user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado. Rol insuficiente. Se requiere uno de: {', '.join(allowed_roles)}.",
            )
        return current_user
    return dependency
