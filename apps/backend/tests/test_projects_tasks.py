import json
from uuid import UUID, uuid4

import pytest
from apps.backend.src.database import api_session_factory
from apps.backend.src.main import app
from db_clients.session import tenant_context
from httpx import ASGITransport, AsyncClient
from security_utils import create_access_token, hash_password
from sqlalchemy import text

BASE_URL = "http://testserver"


@pytest.fixture(scope="module")
async def seed_test_data():
    """Registra dos tenants y usuarios de prueba (un Admin de T1, un Dev de T1 y un Admin de T2)."""
    # 1. Crear IDs
    t1_id = uuid4()
    t2_id = uuid4()
    u1_admin_id = uuid4()
    u1_dev_id = uuid4()
    u2_admin_id = uuid4()

    # 2. Insertar en base de datos
    # Sembrar Tenant 1
    async with tenant_context(t1_id):
        async with api_session_factory() as session:
            await session.execute(
                text("INSERT INTO tenants (tenant_id, slug, name, tier) VALUES (:id, :slug, :name, 'starter')"),
                {"id": t1_id, "slug": "t1-projects", "name": "Tenant 1 Projects"},
            )
            pw_hash = hash_password("Password123!")
            await session.execute(
                text("INSERT INTO users (user_id, tenant_id, email, password_hash) VALUES (:id, :tenant_id, :email, :hash)"),
                [
                    {"id": u1_admin_id, "tenant_id": t1_id, "email": "admin@t1.com", "hash": pw_hash},
                    {"id": u1_dev_id, "tenant_id": t1_id, "email": "dev@t1.com", "hash": pw_hash},
                ],
            )
            roles_res = await session.execute(text("SELECT role_id, name FROM roles"))
            roles_map = {row[1]: row[0] for row in roles_res.fetchall()}
            await session.execute(
                text("INSERT INTO user_roles (user_id, role_id) VALUES (:user_id, :role_id)"),
                [
                    {"user_id": u1_admin_id, "role_id": roles_map["Tenant Admin"]},
                    {"user_id": u1_dev_id, "role_id": roles_map["Developer"]},
                ],
            )
            await session.commit()

    # Sembrar Tenant 2
    async with tenant_context(t2_id):
        async with api_session_factory() as session:
            await session.execute(
                text("INSERT INTO tenants (tenant_id, slug, name, tier) VALUES (:id, :slug, :name, 'starter')"),
                {"id": t2_id, "slug": "t2-projects", "name": "Tenant 2 Projects"},
            )
            pw_hash = hash_password("Password123!")
            await session.execute(
                text("INSERT INTO users (user_id, tenant_id, email, password_hash) VALUES (:id, :tenant_id, :email, :hash)"),
                [
                    {"id": u2_admin_id, "tenant_id": t2_id, "email": "admin@t2.com", "hash": pw_hash},
                ],
            )
            roles_res = await session.execute(text("SELECT role_id, name FROM roles"))
            roles_map = {row[1]: row[0] for row in roles_res.fetchall()}
            await session.execute(
                text("INSERT INTO user_roles (user_id, role_id) VALUES (:user_id, :role_id)"),
                [
                    {"user_id": u2_admin_id, "role_id": roles_map["Tenant Admin"]},
                ],
            )
            await session.commit()

    # 3. Generar tokens JWT
    from datetime import timedelta

    from apps.backend.src.config import settings

    def make_jwt(user_id: UUID, tenant_id: UUID, email: str, role: str) -> str:
        return create_access_token(
            {"sub": str(user_id), "tenant_id": str(tenant_id), "email": email, "role": role},
            secret_key=settings.JWT_SECRET,
            expires_delta=timedelta(minutes=60),
        )

    t1_admin_jwt = make_jwt(u1_admin_id, t1_id, "admin@t1.com", "Tenant Admin")
    t1_dev_jwt = make_jwt(u1_dev_id, t1_id, "dev@t1.com", "Developer")
    t2_admin_jwt = make_jwt(u2_admin_id, t2_id, "admin@t2.com", "Tenant Admin")

    yield {
        "t1_id": t1_id,
        "t2_id": t2_id,
        "t1_admin_jwt": t1_admin_jwt,
        "t1_dev_jwt": t1_dev_jwt,
        "t2_admin_jwt": t2_admin_jwt,
        "u1_admin_id": u1_admin_id,
        "u1_dev_id": u1_dev_id,
        "u2_admin_id": u2_admin_id,
    }

    # 4. Limpieza
    async with tenant_context(t1_id):
        async with api_session_factory() as session:
            await session.execute(text("DELETE FROM tasks"))
            await session.execute(text("DELETE FROM projects"))
            await session.execute(text("DELETE FROM user_roles WHERE user_id IN (:u1, :u2)"), {"u1": u1_admin_id, "u2": u1_dev_id})
            await session.execute(text("DELETE FROM users WHERE user_id IN (:u1, :u2)"), {"u1": u1_admin_id, "u2": u1_dev_id})
            await session.commit()

    async with tenant_context(t2_id):
        async with api_session_factory() as session:
            await session.execute(text("DELETE FROM tasks"))
            await session.execute(text("DELETE FROM projects"))
            await session.execute(text("DELETE FROM user_roles WHERE user_id = :u"), {"u": u2_admin_id})
            await session.execute(text("DELETE FROM users WHERE user_id = :u"), {"u": u2_admin_id})
            await session.commit()

    async with api_session_factory() as session:
        await session.execute(text("DELETE FROM tenants WHERE tenant_id IN (:t1, :t2)"), {"t1": t1_id, "t2": t2_id})
        await session.commit()


@pytest.mark.asyncio
async def test_projects_crud_and_tenant_isolation(seed_test_data):
    """Valida la creación, lectura, actualización y aislamiento RLS de proyectos."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as ac:

        # Cabeceras comunes
        h_t1_admin = {
            "Authorization": f"Bearer {seed_test_data['t1_admin_jwt']}",
            "X-Tenant-ID": str(seed_test_data["t1_id"]),
        }
        h_t2_admin = {
            "Authorization": f"Bearer {seed_test_data['t2_admin_jwt']}",
            "X-Tenant-ID": str(seed_test_data["t2_id"]),
        }

        # 1. Obtener lista inicial de proyectos de Tenant 1 (debe estar vacía)
        resp_list = await ac.get("/projects", headers=h_t1_admin)
        assert resp_list.status_code == 200
        assert len(resp_list.json()) == 0

        # 2. Crear proyecto en Tenant 1
        payload_proj = {"name": "Proyecto Delta Core", "lead_user_id": str(seed_test_data["u1_admin_id"])}
        resp_create = await ac.post("/projects", json=payload_proj, headers=h_t1_admin)
        assert resp_create.status_code == 201
        proj_data = resp_create.json()
        assert proj_data["name"] == "Proyecto Delta Core"
        proj_id = UUID(proj_data["project_id"])

        # 3. Verificar que se haya registrado en el outbox transaccionalmente
        async with api_session_factory() as session:
            outbox_res = await session.execute(
                text("SELECT aggregate, aggregate_id, event_type, payload FROM outbox WHERE aggregate_id = :id"),
                {"id": proj_id},
            )
            outbox_row = outbox_res.fetchone()
            assert outbox_row is not None
            assert outbox_row[0] == "Project"
            assert outbox_row[2] == "ProjectCreated"
            payload_stored = outbox_row[3]
            if isinstance(payload_stored, str):
                payload_stored = json.loads(payload_stored)
            assert payload_stored["name"] == "Proyecto Delta Core"

        # 4. Verificar aislamiento: Tenant 2 no puede listar el proyecto de Tenant 1
        resp_list_t2 = await ac.get("/projects", headers=h_t2_admin)
        assert resp_list_t2.status_code == 200
        assert len(resp_list_t2.json()) == 0

        # 5. Intentar leer detalle del proyecto de Tenant 1 desde Tenant 2 (debe dar 404 debido a RLS)
        resp_detail_t2 = await ac.get(f"/projects/{proj_id}", headers=h_t2_admin)
        assert resp_detail_t2.status_code == 404

        # 6. Actualizar proyecto en Tenant 1
        payload_update = {"name": "Proyecto Delta Core V2", "status": "active", "lead_user_id": str(seed_test_data["u1_admin_id"])}
        resp_update = await ac.put(f"/projects/{proj_id}", json=payload_update, headers=h_t1_admin)
        assert resp_update.status_code == 200
        assert resp_update.json()["name"] == "Proyecto Delta Core V2"

        # 7. Validar evento de actualización en outbox
        async with api_session_factory() as session:
            outbox_res = await session.execute(
                text("SELECT event_type FROM outbox WHERE aggregate_id = :id ORDER BY id DESC LIMIT 1"),
                {"id": proj_id},
            )
            assert outbox_res.fetchone()[0] == "ProjectUpdated"


@pytest.mark.asyncio
async def test_tenant_spoofing_prevention(seed_test_data):
    """Verifica que el endpoint rechace peticiones donde la cabecera X-Tenant-ID no coincida con el JWT."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as ac:

        # Token de Tenant 1, pero intentando consultar recursos declarando X-Tenant-ID de Tenant 2
        spoofed_headers = {
            "Authorization": f"Bearer {seed_test_data['t1_admin_jwt']}",
            "X-Tenant-ID": str(seed_test_data["t2_id"]),
        }

        response = await ac.get("/projects", headers=spoofed_headers)
        assert response.status_code == 403
        assert "No tiene permisos" in response.json()["detail"]


@pytest.mark.asyncio
async def test_role_based_access_control(seed_test_data):
    """Verifica que el rol Developer no pueda crear ni eliminar proyectos."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as ac:

        h_t1_dev = {
            "Authorization": f"Bearer {seed_test_data['t1_dev_jwt']}",
            "X-Tenant-ID": str(seed_test_data["t1_id"]),
        }
        h_t1_admin = {
            "Authorization": f"Bearer {seed_test_data['t1_admin_jwt']}",
            "X-Tenant-ID": str(seed_test_data["t1_id"]),
        }

        # 1. Dev intenta crear proyecto (debe retornar 403)
        payload = {"name": "Proyecto Dev Prohibido"}
        resp_create = await ac.post("/projects", json=payload, headers=h_t1_dev)
        assert resp_create.status_code == 403

        # 2. Admin crea un proyecto para validar la eliminación
        resp_admin_create = await ac.post("/projects", json={"name": "Proyecto Temp"}, headers=h_t1_admin)
        proj_id = resp_admin_create.json()["project_id"]

        # 3. Dev intenta eliminar el proyecto (debe retornar 403)
        resp_delete_dev = await ac.delete(f"/projects/{proj_id}", headers=h_t1_dev)
        assert resp_delete_dev.status_code == 403

        # 4. Admin elimina el proyecto exitosamente
        resp_delete_admin = await ac.delete(f"/projects/{proj_id}", headers=h_t1_admin)
        assert resp_delete_admin.status_code == 204


@pytest.mark.asyncio
async def test_tasks_crud_and_outbox(seed_test_data):
    """Valida el ciclo de vida completo de las tareas y el registro de eventos en el Outbox."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as ac:

        h_t1_admin = {
            "Authorization": f"Bearer {seed_test_data['t1_admin_jwt']}",
            "X-Tenant-ID": str(seed_test_data["t1_id"]),
        }
        h_t1_dev = {
            "Authorization": f"Bearer {seed_test_data['t1_dev_jwt']}",
            "X-Tenant-ID": str(seed_test_data["t1_id"]),
        }

        # 1. Crear un proyecto base
        resp_proj = await ac.post("/projects", json={"name": "Proyecto Tareas"}, headers=h_t1_admin)
        proj_id = UUID(resp_proj.json()["project_id"])

        # 2. Crear tarea vinculada al proyecto (hecho por Developer)
        payload_task = {
            "project_id": str(proj_id),
            "title": "Implementar endpoints de tareas",
            "assignee_user_id": str(seed_test_data["u1_dev_id"]),
            "story_points": 5,
            "client_visible": False,
        }
        resp_task = await ac.post("/tasks", json=payload_task, headers=h_t1_dev)
        assert resp_task.status_code == 201
        task_data = resp_task.json()
        assert task_data["title"] == "Implementar endpoints de tareas"
        task_id = task_data["task_id"]

        # 3. Validar inserción en outbox de la tarea creada
        async with api_session_factory() as session:
            outbox_res = await session.execute(
                text("SELECT aggregate, event_type, payload FROM outbox WHERE aggregate = 'Task' ORDER BY id DESC LIMIT 1"),
            )
            outbox_row = outbox_res.fetchone()
            assert outbox_row is not None
            assert outbox_row[1] == "TaskCreated"
            payload_stored = outbox_row[2]
            if isinstance(payload_stored, str):
                payload_stored = json.loads(payload_stored)
            assert payload_stored["title"] == "Implementar endpoints de tareas"

        # 4. Listar tareas y filtrar por project_id
        resp_list = await ac.get(f"/tasks?project_id={proj_id}", headers=h_t1_dev)
        assert resp_list.status_code == 200
        assert len(resp_list.json()) == 1
        assert resp_list.json()[0]["task_id"] == task_id

        # 5. Actualizar la tarea (ej. marcar como inprogress)
        payload_update = {
            "title": "Implementar endpoints de tareas - En curso",
            "state": "inprogress",
            "assignee_user_id": str(seed_test_data["u1_dev_id"]),
            "story_points": 5,
            "client_visible": True,
        }
        resp_update = await ac.put(f"/tasks/{task_id}", json=payload_update, headers=h_t1_dev)
        assert resp_update.status_code == 200
        assert resp_update.json()["state"] == "inprogress"

        # 6. Eliminar tarea
        resp_delete = await ac.delete(f"/tasks/{task_id}", headers=h_t1_dev)
        assert resp_delete.status_code == 204

        # 7. Validar evento de eliminación en outbox
        async with api_session_factory() as session:
            outbox_res = await session.execute(
                text("SELECT event_type FROM outbox WHERE aggregate = 'Task' ORDER BY id DESC LIMIT 1"),
            )
            assert outbox_res.fetchone()[0] == "TaskDeleted"

        # 8. Limpiar proyecto
        await ac.delete(f"/projects/{proj_id}", headers=h_t1_admin)
