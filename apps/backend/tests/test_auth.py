from uuid import uuid4

import pytest
from apps.backend.src.database import api_session_factory
from apps.backend.src.main import app
from db_clients.session import _engines_registry, tenant_context
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

BASE_URL = "http://testserver"




@pytest.mark.asyncio
async def test_auth_onboarding_and_login_flow():
    """Valida el flujo de onboarding (registro de nuevo tenant/admin), login y seguridad."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as ac:
        unique_suffix = str(uuid4())[:8]
        slug = f"test-tenant-{unique_suffix}"
        email = f"admin@{slug}.com"
        password = "superSecretPassword123"

        # 1. Registrar inquilino y administrador
        reg_payload = {
            "slug": slug,
            "name": f"Test Tenant {unique_suffix}",
            "tier": "starter",
            "email": email,
            "password": password,
            "full_name": "Administrador Test",
        }

        response = await ac.post("/auth/register", json=reg_payload)
        assert response.status_code == 201

        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == email
        assert data["user"]["role"] == "Tenant Admin"

        tenant_id = data["user"]["tenant_id"]
        user_id = data["user"]["user_id"]

        # 2. Intentar registrar el mismo slug (debe dar error 400)
        response_dup = await ac.post("/auth/register", json=reg_payload)
        assert response_dup.status_code == 400
        assert "ya está en uso" in response_dup.json()["detail"]

        # 3. Autenticación exitosa (Login) sin subdominio (pasando slug en el body)
        login_payload = {
            "email": email,
            "password": password,
            "slug": slug,
        }
        response_login = await ac.post("/auth/login", json=login_payload)
        assert response_login.status_code == 200
        assert "access_token" in response_login.json()
        assert response_login.json()["user"]["user_id"] == user_id

        # 4. Autenticación con contraseña incorrecta (debe dar error 401)
        login_payload_wrong = {
            "email": email,
            "password": "wrongPassword",
            "slug": slug,
        }
        response_wrong = await ac.post("/auth/login", json=login_payload_wrong)
        assert response_wrong.status_code == 401

        # 5. Limpieza de datos creados en el test
        async with tenant_context(tenant_id):
            async with api_session_factory() as session:
                await session.execute(text("DELETE FROM user_roles WHERE user_id = :id"), {"id": user_id})
                await session.execute(text("DELETE FROM users WHERE user_id = :id"), {"id": user_id})
                await session.commit()

        async with api_session_factory() as session:
            await session.execute(text("DELETE FROM tenants WHERE tenant_id = :id"), {"id": tenant_id})
            await session.commit()


@pytest.mark.asyncio
async def test_tenant_context_middleware_and_rls():
    """Valida que el middleware resuelva el tenant de las peticiones HTTP y aplique RLS."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as ac:

        # 1. Acceso sin Tenant (Fail-Closed) en ruta protegida
        resp_no_tenant = await ac.get("/projects/test")
        assert resp_no_tenant.status_code == 400
        assert "Acceso denegado" in resp_no_tenant.json()["detail"]

        # 2. Crear dos tenants temporales directamente en base de datos
        t1_id = uuid4()
        t2_id = uuid4()

        async with api_session_factory() as session:
            await session.execute(
                text("INSERT INTO tenants (tenant_id, slug, name, tier) VALUES (:id, :slug, :name, 'starter')"),
                [
                    {"id": t1_id, "slug": "tenant-1", "name": "Tenant 1"},
                    {"id": t2_id, "slug": "tenant-2", "name": "Tenant 2"},
                ],
            )
            await session.commit()

        # 3. Crear proyectos en contexto aislado
        async with tenant_context(t1_id):
            async with api_session_factory() as session:
                await session.execute(
                    text("INSERT INTO projects (tenant_id, name, status) VALUES (:tenant_id, 'Proyecto Tenant 1', 'active')"),
                    {"tenant_id": t1_id},
                )
                await session.commit()

        async with tenant_context(t2_id):
            async with api_session_factory() as session:
                await session.execute(
                    text("INSERT INTO projects (tenant_id, name, status) VALUES (:tenant_id, 'Proyecto Tenant 2', 'active')"),
                    {"tenant_id": t2_id},
                )
                await session.commit()

        # 4. Probar peticiones HTTP aislando con X-Tenant-ID
        # Petición Tenant 1
        resp_t1 = await ac.get("/projects/test", headers={"X-Tenant-ID": str(t1_id)})
        assert resp_t1.status_code == 200
        projects_t1 = resp_t1.json()
        assert len(projects_t1) == 1
        assert projects_t1[0]["name"] == "Proyecto Tenant 1"

        # Petición Tenant 2
        resp_t2 = await ac.get("/projects/test", headers={"X-Tenant-ID": str(t2_id)})
        assert resp_t2.status_code == 200
        projects_t2 = resp_t2.json()
        assert len(projects_t2) == 1
        assert projects_t2[0]["name"] == "Proyecto Tenant 2"

        # 5. Probar resolución automática por subdominio
        # Host: tenant-1.localhost
        resp_sub = await ac.get("/projects/test", headers={"host": "tenant-1.localhost"})
        assert resp_sub.status_code == 200
        projects_sub = resp_sub.json()
        assert len(projects_sub) == 1
        assert projects_sub[0]["name"] == "Proyecto Tenant 1"

        # 6. Limpiar datos de base de datos
        async with tenant_context(t1_id):
            async with api_session_factory() as session:
                await session.execute(text("DELETE FROM projects WHERE tenant_id = :t1"), {"t1": t1_id})
                await session.commit()

        async with tenant_context(t2_id):
            async with api_session_factory() as session:
                await session.execute(text("DELETE FROM projects WHERE tenant_id = :t2"), {"t2": t2_id})
                await session.commit()

        async with api_session_factory() as session:
            await session.execute(text("DELETE FROM tenants WHERE tenant_id IN (:t1, :t2)"), {"t1": t1_id, "t2": t2_id})
            await session.commit()
