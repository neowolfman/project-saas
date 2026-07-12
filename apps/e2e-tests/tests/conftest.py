import os
import uuid
import pytest
import pytest_asyncio
import httpx
from sqlalchemy import text
from db_clients.session import create_session_factory, tenant_context

# Load .env file automatically
def load_env_file():
    for env_path in ["/app/infra/docker/.env", "../../infra/docker/.env"]:
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        value = value.strip("'\"")
                        if key not in os.environ:
                            os.environ[key] = value
            break

load_env_file()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://app:change_me_strong_pg_password@postgres:5432/saas"
).replace("postgresql+psycopg://", "postgresql+asyncpg://")

@pytest.fixture(scope="session")
def superuser_session_factory():
    return create_session_factory(DATABASE_URL)

@pytest_asyncio.fixture(scope="session")
async def api_client():
    # Route via Traefik gateway using Host header
    async with httpx.AsyncClient(
        base_url="http://saas-traefik",
        headers={"Host": "api.saas.local"},
        timeout=15.0
    ) as client:
        yield client

@pytest_asyncio.fixture
async def test_tenant(api_client, superuser_session_factory):
    # Register a new tenant via API
    tenant_slug = f"e2e-tenant-{uuid.uuid4().hex[:8]}"
    admin_email = f"admin@{tenant_slug}.com"
    dev_email = f"dev@{tenant_slug}.com"
    password = "Password123!"

    # 1. Register Tenant
    register_payload = {
        "slug": tenant_slug,
        "name": "E2E Test Tenant",
        "email": admin_email,
        "password": password,
        "full_name": "E2E Admin"
    }
    
    resp = await api_client.post("/auth/register", json=register_payload)
    assert resp.status_code == 201
    tenant_data = resp.json()
    tenant_id_str = tenant_data["user"]["tenant_id"]
    tenant_id = uuid.UUID(tenant_id_str)
    admin_token = tenant_data["access_token"]

    yield {
        "tenant_id": tenant_id,
        "tenant_slug": tenant_slug,
        "admin_email": admin_email,
        "dev_email": dev_email,
        "password": password,
        "admin_token": admin_token
    }

    # Teardown: Delete all data for this tenant
    # Using superuser session to bypass/work with RLS
    async with tenant_context(tenant_id), superuser_session_factory() as session:
        # Delete time logs first
        log_ids_res = await session.execute(text("SELECT id FROM time_logs"))
        log_ids = [r[0] for r in log_ids_res.fetchall()]
        if log_ids:
            await session.execute(
                text("DELETE FROM time_logs WHERE id = ANY(:ids)"),
                {"ids": log_ids}
            )
        
        # Delete other entities
        await session.execute(text("DELETE FROM processed_events"))
        await session.execute(text("DELETE FROM margin_snapshot WHERE tenant_id = :id"), {"id": tenant_id})
        await session.execute(text("DELETE FROM financial_contracts WHERE tenant_id = :id"), {"id": tenant_id})
        await session.execute(text("DELETE FROM tasks WHERE tenant_id = :id"), {"id": tenant_id})
        await session.execute(text("DELETE FROM projects WHERE tenant_id = :id"), {"id": tenant_id})
        await session.execute(text("DELETE FROM user_roles WHERE user_id IN (SELECT user_id FROM users WHERE tenant_id = :id)"), {"id": tenant_id})
        await session.execute(text("DELETE FROM users WHERE tenant_id = :id"), {"id": tenant_id})
        await session.commit()
        
    # Delete tenant itself (outside tenant_context since it deletes the tenant row)
    async with superuser_session_factory() as session:
        await session.execute(text("DELETE FROM tenants WHERE tenant_id = :id"), {"id": tenant_id})
        await session.commit()
