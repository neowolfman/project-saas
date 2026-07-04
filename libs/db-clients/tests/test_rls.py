import os
from uuid import uuid4
import pytest
import pytest_asyncio
from sqlalchemy import text
from db_clients.session import (
    create_session_factory,
    tenant_context,
    set_current_tenant,
    _engines_registry,
)

PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "change_me_strong_pg_password")
APP_API_PASSWORD = os.getenv("APP_API_PASSWORD", "change_me_strong_app_api_password")

SUPERUSER_DB_URL = f"postgresql+asyncpg://app:{PG_PASSWORD}@postgres:5432/saas"
API_DB_URL = f"postgresql+asyncpg://app_api:{APP_API_PASSWORD}@postgres:5432/saas"


@pytest.fixture(autouse=True)
def clear_engines_registry():
    """Limpia el registro global de conexiones antes y después de cada test para evitar colisiones de event loops en asyncpg."""
    _engines_registry.clear()
    yield
    # Cerrar motores de base de datos para liberar conexiones
    _engines_registry.clear()


@pytest_asyncio.fixture(scope="module")
async def seed_data():
    """Inserta datos de prueba para dos tenants usando credenciales de superusuario."""
    tenant_a_id = uuid4()
    tenant_b_id = uuid4()
    
    project_a_id = uuid4()
    project_b_id = uuid4()

    factory = create_session_factory(SUPERUSER_DB_URL)
    async with factory() as session:
        # Registrar Tenants
        await session.execute(
            text("INSERT INTO tenants (tenant_id, slug, name, tier) VALUES (:id, :slug, :name, 'starter')"),
            [
                {"id": tenant_a_id, "slug": "tenant-a", "name": "Tenant A"},
                {"id": tenant_b_id, "slug": "tenant-b", "name": "Tenant B"}
            ]
        )
        # Registrar Proyectos
        await session.execute(
            text("INSERT INTO projects (project_id, tenant_id, name, status) VALUES (:id, :tenant_id, :name, 'active')"),
            [
                {"id": project_a_id, "tenant_id": tenant_a_id, "name": "Proyecto de A"},
                {"id": project_b_id, "tenant_id": tenant_b_id, "name": "Proyecto de B"}
            ]
        )
        await session.commit()

    yield {
        "tenant_a_id": tenant_a_id,
        "tenant_b_id": tenant_b_id,
        "project_a_id": project_a_id,
        "project_b_id": project_b_id
    }

    # Limpiar datos después de los tests (usamos una nueva conexión limpia)
    # Volvemos a limpiar para evitar colisiones con el loop que cierra la fixture
    _engines_registry.clear()
    factory = create_session_factory(SUPERUSER_DB_URL)
    async with factory() as session:
        await session.execute(text("DELETE FROM projects WHERE project_id IN (:id_a, :id_b)"), {"id_a": project_a_id, "id_b": project_b_id})
        await session.execute(text("DELETE FROM tenants WHERE tenant_id IN (:id_a, :id_b)"), {"id_a": tenant_a_id, "id_b": tenant_b_id})
        await session.commit()


@pytest.mark.asyncio
async def test_fail_closed_without_tenant(seed_data):
    """Verifica que si no hay un tenant configurado en el contexto, no se puede leer ningún dato (Fail-Closed)."""
    api_session_factory = create_session_factory(API_DB_URL)
    
    set_current_tenant(None)

    async with api_session_factory() as session:
        result = await session.execute(text("SELECT * FROM projects"))
        projects = result.fetchall()
        assert len(projects) == 0


@pytest.mark.asyncio
async def test_tenant_isolation_reads(seed_data):
    """Verifica que el RLS aísle la lectura de datos correctamente para cada tenant."""
    api_session_factory = create_session_factory(API_DB_URL)

    # 1. Probar lecturas de Tenant A
    async with tenant_context(seed_data["tenant_a_id"]):
        async with api_session_factory() as session:
            result = await session.execute(text("SELECT name FROM projects"))
            rows = result.fetchall()
            assert len(rows) == 1
            assert rows[0][0] == "Proyecto de A"

    # 2. Probar lecturas de Tenant B
    async with tenant_context(seed_data["tenant_b_id"]):
        async with api_session_factory() as session:
            result = await session.execute(text("SELECT name FROM projects"))
            rows = result.fetchall()
            assert len(rows) == 1
            assert rows[0][0] == "Proyecto de B"


@pytest.mark.asyncio
async def test_block_cross_tenant_writes(seed_data):
    """Verifica que un tenant no pueda escribir datos en la cuenta de otro tenant (Check Constraint / RLS)."""
    api_session_factory = create_session_factory(API_DB_URL)
    malicious_project_id = uuid4()

    async with tenant_context(seed_data["tenant_a_id"]):
        async with api_session_factory() as session:
            with pytest.raises(Exception):
                await session.execute(
                    text("INSERT INTO projects (project_id, tenant_id, name, status) VALUES (:id, :tenant_id, :name, 'active')"),
                    {"id": malicious_project_id, "tenant_id": seed_data["tenant_b_id"], "name": "Proyecto Malicioso"}
                )
                await session.commit()
