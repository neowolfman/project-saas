import os
import pytest
import json
from uuid import UUID, uuid4
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from apps.backend.src.database import api_session_factory
from apps.backend.src.main import app
from apps.backend.src.shared.tenant.provisioning import provision_vip_db, run_alembic_upgrade
from db_clients.session import tenant_context
from httpx import ASGITransport, AsyncClient
from security_utils import create_access_token, hash_password

BASE_URL = "http://testserver"


@pytest.fixture(scope="module")
async def seed_multi_tenancy_data():
    # 1. Generar IDs de inquilinos y usuarios
    t_starter_id = uuid4()
    t_enterprise_id = uuid4()
    t_vip_id = uuid4()
    
    u_starter_id = uuid4()
    u_enterprise_id = uuid4()
    u_vip_id = uuid4()

    # Obtener el DSN administrativo del entorno
    admin_url = os.getenv("DATABASE_URL")
    if not admin_url:
        admin_url = "postgresql+asyncpg://app:change_me_strong_pg_password@postgres:5432/saas"
        
    if admin_url.startswith("postgresql://"):
        admin_url = admin_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif admin_url.startswith("postgresql+psycopg://"):
        admin_url = admin_url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)

    # 2. Provisionar el esquema Enterprise
    schema_name = "tenant_enterprise"
    engine_shared = create_async_engine(admin_url)
    async with engine_shared.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
        await conn.execute(text(f"GRANT USAGE ON SCHEMA {schema_name} TO app_api"))
    
    run_alembic_upgrade(admin_url, schema_name=schema_name)
    
    async with engine_shared.begin() as conn:
        await conn.execute(text(f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA {schema_name} TO app_api"))
        await conn.execute(text(f"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA {schema_name} TO app_api"))
        await conn.execute(text(f"GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA {schema_name} TO app_api"))
        res = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'tenant_enterprise'"))
        print(f"DEBUG Tables in tenant_enterprise: {res.fetchall()}")

    # 3. Provisionar la base de datos física del VIP
    vip_db_name = "saas_vip_test_db"
    await provision_vip_db(vip_db_name)
    
    # Correr migraciones de Alembic en la base de datos VIP
    from sqlalchemy.engine.url import make_url
    url_obj = make_url(admin_url)
    vip_admin_url = url_obj.set(database=vip_db_name).render_as_string(hide_password=False)
    run_alembic_upgrade(vip_admin_url)

    # 4. Insertar inquilinos en la tabla tenants de la base de datos compartida
    async with api_session_factory() as session:
        await session.execute(
            text("""
                INSERT INTO tenants (tenant_id, slug, name, tier, db_target)
                VALUES 
                  (:starter_id, 'starter-slug', 'Starter Tenant', 'starter', 'shared'),
                  (:enterprise_id, 'enterprise-slug', 'Enterprise Tenant', 'enterprise', :enterprise_target),
                  (:vip_id, 'vip-slug', 'VIP Tenant', 'vip', :vip_target)
            """),
            {
                "starter_id": t_starter_id,
                "enterprise_id": t_enterprise_id,
                "vip_id": t_vip_id,
                "enterprise_target": f"schema:{schema_name}",
                "vip_target": f"db:{vip_db_name}",
            }
        )
        await session.commit()

    # 5. Sembrar usuarios dentro de cada contexto de inquilino correspondiente
    # Starter (Shared DB / Shared Schema)
    async with tenant_context(t_starter_id):
        async with api_session_factory() as session:
            pw_hash = hash_password("Password123!")
            await session.execute(
                text("INSERT INTO users (user_id, tenant_id, email, password_hash) VALUES (:id, :tenant_id, 'admin@starter.com', :hash)"),
                {"id": u_starter_id, "tenant_id": t_starter_id, "hash": pw_hash}
            )
            roles_res = await session.execute(text("SELECT role_id, name FROM roles"))
            roles_map = {row[1]: row[0] for row in roles_res.fetchall()}
            await session.execute(
                text("INSERT INTO user_roles (user_id, role_id) VALUES (:user_id, :role_id)"),
                {"user_id": u_starter_id, "role_id": roles_map["Tenant Admin"]}
            )
            await session.commit()

    # Enterprise (Shared DB / Isolated Schema)
    async with tenant_context(t_enterprise_id):
        async with api_session_factory() as session:
            # Insertar registro de tenant en el esquema aislado para satisfacer FKs
            await session.execute(
                text("""
                    INSERT INTO tenants (tenant_id, slug, name, tier, db_target)
                    VALUES (:enterprise_id, 'enterprise-slug', 'Enterprise Tenant', 'enterprise', :enterprise_target)
                """),
                {"enterprise_id": t_enterprise_id, "enterprise_target": f"schema:{schema_name}"}
            )
            pw_hash = hash_password("Password123!")
            await session.execute(
                text("INSERT INTO users (user_id, tenant_id, email, password_hash) VALUES (:id, :tenant_id, 'admin@enterprise.com', :hash)"),
                {"id": u_enterprise_id, "tenant_id": t_enterprise_id, "hash": pw_hash}
            )
            roles_res = await session.execute(text("SELECT role_id, name FROM roles"))
            roles_map = {row[1]: row[0] for row in roles_res.fetchall()}
            await session.execute(
                text("INSERT INTO user_roles (user_id, role_id) VALUES (:user_id, :role_id)"),
                {"user_id": u_enterprise_id, "role_id": roles_map["Tenant Admin"]}
            )
            await session.commit()

    # VIP (Isolated DB)
    async with tenant_context(t_vip_id):
        async with api_session_factory() as session:
            # Insertar registro de tenant en la base de datos VIP para satisfacer FKs
            await session.execute(
                text("""
                    INSERT INTO tenants (tenant_id, slug, name, tier, db_target)
                    VALUES (:vip_id, 'vip-slug', 'VIP Tenant', 'vip', :vip_target)
                """),
                {"vip_id": t_vip_id, "vip_target": f"db:{vip_db_name}"}
            )
            pw_hash = hash_password("Password123!")
            await session.execute(
                text("INSERT INTO users (user_id, tenant_id, email, password_hash) VALUES (:id, :tenant_id, 'admin@vip.com', :hash)"),
                {"id": u_vip_id, "tenant_id": t_vip_id, "hash": pw_hash}
            )
            roles_res = await session.execute(text("SELECT role_id, name FROM roles"))
            roles_map = {row[1]: row[0] for row in roles_res.fetchall()}
            await session.execute(
                text("INSERT INTO user_roles (user_id, role_id) VALUES (:user_id, :role_id)"),
                {"user_id": u_vip_id, "role_id": roles_map["Tenant Admin"]}
            )
            await session.commit()

    # 6. Generar JSON Web Tokens
    from datetime import timedelta
    from apps.backend.src.config import settings

    def make_jwt(user_id: UUID, tenant_id: UUID, email: str, role: str) -> str:
        return create_access_token(
            {"sub": str(user_id), "tenant_id": str(tenant_id), "email": email, "role": role},
            secret_key=settings.JWT_SECRET,
            expires_delta=timedelta(minutes=60),
        )

    starter_jwt = make_jwt(u_starter_id, t_starter_id, "admin@starter.com", "Tenant Admin")
    enterprise_jwt = make_jwt(u_enterprise_id, t_enterprise_id, "admin@enterprise.com", "Tenant Admin")
    vip_jwt = make_jwt(u_vip_id, t_vip_id, "admin@vip.com", "Tenant Admin")

    yield {
        "t_starter_id": t_starter_id,
        "t_enterprise_id": t_enterprise_id,
        "t_vip_id": t_vip_id,
        "starter_jwt": starter_jwt,
        "enterprise_jwt": enterprise_jwt,
        "vip_jwt": vip_jwt,
        "u_starter_id": u_starter_id,
        "u_enterprise_id": u_enterprise_id,
        "u_vip_id": u_vip_id,
    }

    # 7. Limpieza
    async with tenant_context(t_starter_id):
        async with api_session_factory() as session:
            await session.execute(text("DELETE FROM projects"))
            await session.execute(text("DELETE FROM user_roles WHERE user_id = :u"), {"u": u_starter_id})
            await session.execute(text("DELETE FROM users WHERE user_id = :u"), {"u": u_starter_id})
            await session.commit()

    async with tenant_context(t_enterprise_id):
        async with api_session_factory() as session:
            await session.execute(text("DELETE FROM projects"))
            await session.execute(text("DELETE FROM user_roles WHERE user_id = :u"), {"u": u_enterprise_id})
            await session.execute(text("DELETE FROM users WHERE user_id = :u"), {"u": u_enterprise_id})
            await session.execute(text("DELETE FROM tenants WHERE tenant_id = :t"), {"t": t_enterprise_id})
            await session.commit()

    async with tenant_context(t_vip_id):
        async with api_session_factory() as session:
            await session.execute(text("DELETE FROM projects"))
            await session.execute(text("DELETE FROM user_roles WHERE user_id = :u"), {"u": u_vip_id})
            await session.execute(text("DELETE FROM users WHERE user_id = :u"), {"u": u_vip_id})
            await session.execute(text("DELETE FROM tenants WHERE tenant_id = :t"), {"t": t_vip_id})
            await session.commit()

    async with api_session_factory() as session:
        await session.execute(text("DELETE FROM tenants WHERE tenant_id IN (:t1, :t2, :t3)"), {
            "t1": t_starter_id,
            "t2": t_enterprise_id,
            "t3": t_vip_id,
        })
        await session.commit()

    # Eliminar esquema Enterprise
    async with engine_shared.begin() as conn:
        await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))
    await engine_shared.dispose()

    # Eliminar base de datos VIP
    url_obj = make_url(admin_url)
    admin_base_url = url_obj.set(database="postgres").render_as_string(hide_password=False)
    engine_admin = create_async_engine(admin_base_url, isolation_level="AUTOCOMMIT")
    async with engine_admin.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {vip_db_name} WITH (FORCE)"))
    await engine_admin.dispose()


@pytest.mark.asyncio
async def test_hybrid_multi_tenancy_isolation(seed_multi_tenancy_data):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as ac:
        
        # Cabeceras
        h_starter = {
            "Authorization": f"Bearer {seed_multi_tenancy_data['starter_jwt']}",
            "X-Tenant-ID": str(seed_multi_tenancy_data['t_starter_id']),
        }
        h_enterprise = {
            "Authorization": f"Bearer {seed_multi_tenancy_data['enterprise_jwt']}",
            "X-Tenant-ID": str(seed_multi_tenancy_data['t_enterprise_id']),
        }
        h_vip = {
            "Authorization": f"Bearer {seed_multi_tenancy_data['vip_jwt']}",
            "X-Tenant-ID": str(seed_multi_tenancy_data['t_vip_id']),
        }

        # 1. Crear proyecto en Starter (DB compartida / Esquema público)
        res_starter = await ac.post("/projects", json={"name": "Starter Project"}, headers=h_starter)
        assert res_starter.status_code == 201
        
        # 2. Crear proyecto en Enterprise (DB compartida / Esquema aislado)
        res_enterprise = await ac.post("/projects", json={"name": "Enterprise Project"}, headers=h_enterprise)
        assert res_enterprise.status_code == 201

        # 3. Crear proyecto en VIP (DB dedicada física)
        res_vip = await ac.post("/projects", json={"name": "VIP Project"}, headers=h_vip)
        assert res_vip.status_code == 201

        # 4. Listar proyectos y verificar aislamiento de datos a nivel API
        # Starter solo ve Starter Project
        list_starter = await ac.get("/projects", headers=h_starter)
        assert list_starter.status_code == 200
        assert len(list_starter.json()) == 1
        assert list_starter.json()[0]["name"] == "Starter Project"

        # Enterprise solo ve Enterprise Project
        list_enterprise = await ac.get("/projects", headers=h_enterprise)
        assert list_enterprise.status_code == 200
        assert len(list_enterprise.json()) == 1
        assert list_enterprise.json()[0]["name"] == "Enterprise Project"

        # VIP solo ve VIP Project
        list_vip = await ac.get("/projects", headers=h_vip)
        assert list_vip.status_code == 200
        assert len(list_vip.json()) == 1
        assert list_vip.json()[0]["name"] == "VIP Project"

        # 5. Inspeccionar la base de datos compartida y aislada a bajo nivel para asegurar el aislamiento físico
        admin_url = os.getenv("DATABASE_URL")
        if not admin_url:
            admin_url = "postgresql+asyncpg://app:change_me_strong_pg_password@postgres:5432/saas"
            
        if admin_url.startswith("postgresql://"):
            admin_url = admin_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif admin_url.startswith("postgresql+psycopg://"):
            admin_url = admin_url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)

        engine_shared = create_async_engine(admin_url)
        
        # Verificar que el esquema public de la base de datos saas solo contenga el proyecto de Starter
        async with engine_shared.connect() as conn:
            res = await conn.execute(text("SELECT name FROM public.projects"))
            rows = res.fetchall()
            names = [r[0] for r in rows]
            assert "Starter Project" in names
            assert "Enterprise Project" not in names
            assert "VIP Project" not in names

            # Verificar que el esquema tenant_enterprise contenga el proyecto de Enterprise
            res_schema = await conn.execute(text("SELECT name FROM tenant_enterprise.projects"))
            rows_schema = res_schema.fetchall()
            names_schema = [r[0] for r in rows_schema]
            assert "Enterprise Project" in names_schema
            assert "Starter Project" not in names_schema
            assert "VIP Project" not in names_schema
            
        await engine_shared.dispose()

        # Verificar que la base de datos saas_vip_test_db contenga el proyecto VIP
        from sqlalchemy.engine.url import make_url
        url_obj = make_url(admin_url)
        vip_admin_url = url_obj.set(database="saas_vip_test_db").render_as_string(hide_password=False)
        
        engine_vip = create_async_engine(vip_admin_url)
        async with engine_vip.connect() as conn:
            res_vip_db = await conn.execute(text("SELECT name FROM public.projects"))
            rows_vip = res_vip_db.fetchall()
            names_vip = [r[0] for r in rows_vip]
            assert "VIP Project" in names_vip
            assert "Starter Project" not in names_vip
            assert "Enterprise Project" not in names_vip
            
        await engine_vip.dispose()
