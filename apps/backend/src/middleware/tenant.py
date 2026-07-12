from typing import cast
from uuid import UUID

from apps.backend.src.database import api_session_factory
from db_clients.session import tenant_context
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint,
    ) -> Response:
        path = request.url.path

        # Rutas globales excluidas de la obligatoriedad del contexto de inquilinos
        global_paths = {
            "/auth/register",
            "/auth/login",
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/favicon.ico",
        }

        is_global = path in global_paths or path.startswith(("/docs", "/webhooks"))

        tenant_id_str = request.headers.get("X-Tenant-ID")
        subdomain = self._get_subdomain(request)

        tenant_uuid: UUID | None = None

        # 1. Intentar resolver por Cabecera X-Tenant-ID
        if tenant_id_str:
            try:
                tenant_uuid = UUID(tenant_id_str)
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Formato de X-Tenant-ID inválido. Debe ser un UUID válido."},
                )

        # 2. Si no hay cabecera, intentar resolver por Subdominio
        elif subdomain and subdomain not in ("www", "api"):
            tenant_uuid = await self._resolve_tenant_by_slug(subdomain)
            if not tenant_uuid and not is_global:
                return JSONResponse(
                    status_code=404,
                    content={"detail": f"Tenant con subdominio '{subdomain}' no encontrado."},
                )

        # 3. Validar existencia del Tenant si se obtuvo el UUID
        if tenant_uuid:
            exists = await self._validate_tenant_exists(tenant_uuid)
            if not exists:
                return JSONResponse(
                    status_code=404,
                    content={"detail": "El inquilino (tenant) especificado no existe."},
                )

            # Inyectar el tenant_id en el estado de la request
            request.state.tenant_id = tenant_uuid

            # Ejecutar dentro del contexto de tenant para aplicar RLS automáticamente
            async with tenant_context(tenant_uuid):
                return await call_next(request)

        # 4. Si no se resolvió ningún Tenant y es una ruta protegida -> Fail-Closed
        if not is_global:
            return JSONResponse(
                status_code=400,
                content={
                    "detail": "Acceso denegado. Se requiere cabecera 'X-Tenant-ID' o subdominio de inquilino.",
                },
            )

        # Si es ruta global y no hay tenant context, ejecutar de forma global
        return await call_next(request)

    def _get_subdomain(self, request: Request) -> str | None:
        """Extrae el subdominio desde la cabecera Host."""
        host = request.headers.get("host", "")
        # Separar el puerto si existe
        host_name = host.split(":")[0]
        parts = host_name.split(".")

        # Caso localhost (ej. tenant-a.localhost)
        if parts[-1] == "localhost":
            if len(parts) > 1:
                return parts[0]
            return None

        # Caso dominio regular (ej. tenant-a.saas.local o tenant-a.neowolfman.dev)
        min_subdomain_parts = 3
        if len(parts) >= min_subdomain_parts:
            return parts[0]

        return None

    async def _resolve_tenant_by_slug(self, slug: str) -> UUID | None:
        """Busca un tenant en la base de datos a partir de su slug y retorna su tenant_id."""
        async with api_session_factory() as session:
            result = await session.execute(
                text("SELECT tenant_id FROM tenants WHERE slug = :slug"),
                {"slug": slug},
            )
            row = result.fetchone()
            if row:
                return cast(UUID, row[0])
        return None

    async def _validate_tenant_exists(self, tenant_id: UUID) -> bool:
        """Verifica que el UUID del tenant realmente exista en la tabla tenants."""
        async with api_session_factory() as session:
            result = await session.execute(
                text("SELECT 1 FROM tenants WHERE tenant_id = :tenant_id"),
                {"tenant_id": tenant_id},
            )
            return result.fetchone() is not None
