import hashlib
import hmac
import json
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from apps.backend.src.config import settings
from apps.backend.src.database import api_session_factory
from apps.backend.src.main import app
from db_clients.session import tenant_context
from httpx import ASGITransport, AsyncClient
from security_utils import create_access_token, hash_password
from sqlalchemy import text

BASE_URL = "http://testserver"


@pytest.fixture(scope="module")
async def seed_test_data():
    """Siembra inquilinos, usuarios, roles y proyectos para probar Time Tracking y Contratos."""
    t1_id = uuid4()
    t2_id = uuid4()
    u1_admin_id = uuid4()
    u1_dev_id = uuid4()
    u2_admin_id = uuid4()

    # 1. Sembrar Tenant 1
    async with tenant_context(t1_id), api_session_factory() as session:
        await session.execute(
            text("INSERT INTO tenants (tenant_id, slug, name, tier) VALUES (:id, :slug, :name, 'starter')"),
            {"id": t1_id, "slug": "t1-finops", "name": "Tenant 1 FinOps"},
        )
        pw_hash = hash_password("Password123!")
        await session.execute(
            text("INSERT INTO users (user_id, tenant_id, email, password_hash) VALUES (:id, :tenant_id, :email, :hash)"),
            [
                {"id": u1_admin_id, "tenant_id": t1_id, "email": "admin@t1finops.com", "hash": pw_hash},
                {"id": u1_dev_id, "tenant_id": t1_id, "email": "dev@t1finops.com", "hash": pw_hash},
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
        # Crear un proyecto para T1
        p1_id = uuid4()
        await session.execute(
            text("INSERT INTO projects (project_id, tenant_id, name, status) VALUES (:p_id, :t_id, 'Project T1', 'active')"),
            {"p_id": p1_id, "t_id": t1_id},
        )
        # Crear una tarea para P1
        task_res = await session.execute(
            text("""
                INSERT INTO tasks (tenant_id, project_id, title, state, story_points)
                VALUES (:tenant_id, :project_id, 'Task T1', 'todo', 5)
                RETURNING task_id
            """),
            {"tenant_id": t1_id, "project_id": p1_id},
        )
        task_id = task_res.fetchone()[0]
        await session.commit()

    # 2. Sembrar Tenant 2
    async with tenant_context(t2_id), api_session_factory() as session:
        await session.execute(
            text("INSERT INTO tenants (tenant_id, slug, name, tier) VALUES (:id, :slug, :name, 'starter')"),
            {"id": t2_id, "slug": "t2-finops", "name": "Tenant 2 FinOps"},
        )
        await session.execute(
            text("INSERT INTO users (user_id, tenant_id, email, password_hash) VALUES (:id, :tenant_id, :email, :hash)"),
            [
                {"id": u2_admin_id, "tenant_id": t2_id, "email": "admin@t2finops.com", "hash": pw_hash},
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
        # Crear proyecto para T2
        p2_id = uuid4()
        await session.execute(
            text("INSERT INTO projects (project_id, tenant_id, name, status) VALUES (:p_id, :t_id, 'Project T2', 'active')"),
            {"p_id": p2_id, "t_id": t2_id},
        )
        await session.commit()

    # 3. Generar tokens JWT
    def make_jwt(user_id: UUID, tenant_id: UUID, email: str, role: str) -> str:
        return create_access_token(
            {"sub": str(user_id), "tenant_id": str(tenant_id), "email": email, "role": role},
            secret_key=settings.JWT_SECRET,
            expires_delta=timedelta(minutes=60),
        )

    t1_admin_jwt = make_jwt(u1_admin_id, t1_id, "admin@t1finops.com", "Tenant Admin")
    t1_dev_jwt = make_jwt(u1_dev_id, t1_id, "dev@t1finops.com", "Developer")
    t2_admin_jwt = make_jwt(u2_admin_id, t2_id, "admin@t2finops.com", "Tenant Admin")

    yield {
        "t1_id": t1_id,
        "t2_id": t2_id,
        "p1_id": p1_id,
        "p2_id": p2_id,
        "task_id": task_id,
        "t1_admin_jwt": t1_admin_jwt,
        "t1_dev_jwt": t1_dev_jwt,
        "t2_admin_jwt": t2_admin_jwt,
        "u1_admin_id": u1_admin_id,
        "u1_dev_id": u1_dev_id,
        "u2_admin_id": u2_admin_id,
    }

    # 4. Limpieza
    async with tenant_context(t1_id), api_session_factory() as session:
        await session.execute(text("DELETE FROM time_logs"))
        await session.execute(text("DELETE FROM financial_contracts"))
        await session.execute(text("DELETE FROM tasks"))
        await session.execute(text("DELETE FROM projects"))
        await session.execute(text("DELETE FROM user_roles WHERE user_id IN (:u1, :u2)"), {"u1": u1_admin_id, "u2": u1_dev_id})
        await session.execute(text("DELETE FROM users WHERE user_id IN (:u1, :u2)"), {"u1": u1_admin_id, "u2": u1_dev_id})
        await session.commit()

    async with tenant_context(t2_id), api_session_factory() as session:
        await session.execute(text("DELETE FROM time_logs"))
        await session.execute(text("DELETE FROM financial_contracts"))
        await session.execute(text("DELETE FROM projects"))
        await session.execute(text("DELETE FROM user_roles WHERE user_id = :u"), {"u": u2_admin_id})
        await session.execute(text("DELETE FROM users WHERE user_id = :u"), {"u": u2_admin_id})
        await session.commit()

    async with api_session_factory() as session:
        await session.execute(text("DELETE FROM tenants WHERE tenant_id IN (:t1, :t2)"), {"t1": t1_id, "t2": t2_id})
        await session.commit()


@pytest.mark.asyncio
async def test_financial_contracts_crud_and_tenant_isolation(seed_test_data):  # noqa: PLR0915
    """Prueba el ciclo de vida completo de un contrato financiero y su aislamiento RLS."""
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
        h_t2_admin = {
            "Authorization": f"Bearer {seed_test_data['t2_admin_jwt']}",
            "X-Tenant-ID": str(seed_test_data["t2_id"]),
        }

        # 1. Crear contrato (Admin T1) -> Exitoso
        contract_data = {
            "project_id": str(seed_test_data["p1_id"]),
            "contract_value": 15000000.0,
            "margin_target_pct": 35.5,
            "sla_terms": {"uptime": "99.9%", "penalty_pct": 5},
            "window_start": "2026-01-01",
            "window_end": "2026-12-31",
        }
        response = await ac.post("/financial-contracts", json=contract_data, headers=h_t1_admin)
        assert response.status_code == 201
        contract = response.json()
        assert contract["contract_value"] == 15000000.0
        assert contract["margin_target_pct"] == 35.5
        assert contract["sla_terms"]["uptime"] == "99.9%"
        contract_id = contract["contract_id"]

        # Verificar outbox (FinancialContractCreated)
        async with tenant_context(seed_test_data["t1_id"]), api_session_factory() as session:
            outbox_res = await session.execute(
                text("SELECT event_type, payload FROM outbox WHERE event_type = 'FinancialContractCreated' ORDER BY id DESC LIMIT 1"),
            )
            outbox_row = outbox_res.fetchone()
            assert outbox_row is not None
            payload = outbox_row[1]
            assert payload["contract_id"] == contract_id
            assert payload["contract_value"] == 15000000.0

        # 2. Intentar crear contrato con rol Developer (Dev T1) -> 403 Forbidden
        response = await ac.post("/financial-contracts", json=contract_data, headers=h_t1_dev)
        assert response.status_code == 403

        # 3. Listar contratos (Admin T1) -> Debe incluir el contrato
        response = await ac.get("/financial-contracts", headers=h_t1_admin)
        assert response.status_code == 200
        contracts_list = response.json()
        assert len(contracts_list) == 1
        assert contracts_list[0]["contract_id"] == contract_id

        # 4. Listar contratos (Admin T2) -> Retorna lista vacía (aislamiento)
        response = await ac.get("/financial-contracts", headers=h_t2_admin)
        assert response.status_code == 200
        assert len(response.json()) == 0

        # 5. Obtener detalle de contrato
        response = await ac.get(f"/financial-contracts/{contract_id}", headers=h_t1_admin)
        assert response.status_code == 200
        assert response.json()["contract_value"] == 15000000.0

        # 6. Intentar obtener detalle de contrato de T1 desde T2 -> 404 Not Found (RLS)
        response = await ac.get(f"/financial-contracts/{contract_id}", headers=h_t2_admin)
        assert response.status_code == 404

        # 7. Actualizar contrato (Admin T1) -> Exitoso
        update_data = {
            "contract_value": 18000000.0,
            "margin_target_pct": 40.0,
            "sla_terms": {"uptime": "99.95%"},
            "window_start": "2026-01-01",
            "window_end": "2026-12-31",
        }
        response = await ac.put(f"/financial-contracts/{contract_id}", json=update_data, headers=h_t1_admin)
        assert response.status_code == 200
        assert response.json()["contract_value"] == 18000000.0

        # Verificar outbox (FinancialContractUpdated)
        async with tenant_context(seed_test_data["t1_id"]), api_session_factory() as session:
            outbox_res = await session.execute(
                text("SELECT event_type, payload FROM outbox WHERE event_type = 'FinancialContractUpdated' ORDER BY id DESC LIMIT 1"),
            )
            outbox_row = outbox_res.fetchone()
            assert outbox_row is not None
            payload = outbox_row[1]
            assert payload["contract_value"] == 18000000.0

        # 8. Eliminar contrato (Admin T1) -> Exitoso
        response = await ac.delete(f"/financial-contracts/{contract_id}", headers=h_t1_admin)
        assert response.status_code == 204

        # Verificar outbox (FinancialContractDeleted)
        async with tenant_context(seed_test_data["t1_id"]), api_session_factory() as session:
            outbox_res = await session.execute(
                text("SELECT event_type, payload FROM outbox WHERE event_type = 'FinancialContractDeleted' ORDER BY id DESC LIMIT 1"),
            )
            outbox_row = outbox_res.fetchone()
            assert outbox_row is not None


@pytest.mark.asyncio
async def test_time_logs_creation_and_rate_resolution(seed_test_data):
    """Valida el registro de logs de horas, la resolución automática del costo de rol y agregación."""
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

        # 1. Registrar time log como Admin T1 (Rol Tenant Admin: tarifa 50.000 CLP/h)
        log1_data = {
            "project_id": str(seed_test_data["p1_id"]),
            "task_id": seed_test_data["task_id"],
            "hours": 8.0,
            "evidence": "Configuración inicial de pipeline de CI/CD",
        }
        response = await ac.post("/time-logs", json=log1_data, headers=h_t1_admin)
        assert response.status_code == 201
        log1 = response.json()
        assert log1["role_cost"] == 50000.0
        assert log1["amount"] == 400000.0  # 8 * 50000.0

        # Verificar outbox (TimeLogged)
        async with tenant_context(seed_test_data["t1_id"]), api_session_factory() as session:
            outbox_res = await session.execute(
                text("SELECT event_type, payload FROM outbox WHERE event_type = 'TimeLogged' ORDER BY id DESC LIMIT 1"),
            )
            outbox_row = outbox_res.fetchone()
            assert outbox_row is not None
            payload = outbox_row[1]
            assert payload["hours"] == 8.0
            assert payload["role_cost"] == 50000.0
            assert payload["amount"] == 400000.0

        # 2. Registrar time log como Developer T1 (Rol Developer: tarifa 30.000 CLP/h)
        log2_data = {
            "project_id": str(seed_test_data["p1_id"]),
            "hours": 4.5,
            "evidence": "Desarrollo de controladores y tests de integración",
        }
        response = await ac.post("/time-logs", json=log2_data, headers=h_t1_dev)
        assert response.status_code == 201
        log2 = response.json()
        assert log2["role_cost"] == 30000.0
        assert log2["amount"] == 135000.0  # 4.5 * 30000.0

        # 3. Listar time logs con filtros
        response = await ac.get(f"/time-logs?project_id={seed_test_data['p1_id']}", headers=h_t1_admin)
        assert response.status_code == 200
        logs = response.json()
        assert len(logs) == 2

        # Filtrar por usuario Developer
        response = await ac.get(f"/time-logs?user_id={seed_test_data['u1_dev_id']}", headers=h_t1_admin)
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["amount"] == 135000.0

        # 4. Obtener resúmenes (summary) agrupados por Proyecto
        response = await ac.get("/time-logs/summary?group_by=project", headers=h_t1_admin)
        assert response.status_code == 200
        proj_summary = response.json()
        assert len(proj_summary) == 1
        assert proj_summary[0]["label"] == "Project T1"
        assert proj_summary[0]["total_hours"] == 12.5
        assert proj_summary[0]["total_amount"] == 535000.0  # 400000 + 135000

        # Obtener resúmenes agrupados por Usuario
        response = await ac.get("/time-logs/summary?group_by=user", headers=h_t1_admin)
        assert response.status_code == 200
        user_summary = response.json()
        # Admin y Dev deben figurar en la lista con sus montos agregados
        emails = [item["label"] for item in user_summary]
        assert "admin@t1finops.com" in emails
        assert "dev@t1finops.com" in emails


@pytest.mark.asyncio
async def test_git_webhooks_signatures_and_outbox(seed_test_data):
    """Verifica la validación HMAC de webhooks de GitHub y GitLab y su registro en Outbox."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE_URL) as ac:
        tenant_id = seed_test_data["t1_id"]

        # Payload de prueba
        payload_body = {"ref": "refs/heads/main", "commits": [{"id": "abcdef123", "message": "feat: outbox integrations"}]}
        body_bytes = json.dumps(payload_body).encode("utf-8")

        # --- GitHub Webhook ---

        # 1. GitHub con Firma Válida
        secret = settings.GIT_WEBHOOK_SECRET.encode("utf-8")
        signature = hmac.new(secret, body_bytes, hashlib.sha256).hexdigest()
        h_github_valid = {
            "X-Hub-Signature-256": f"sha256={signature}",
            "Content-Type": "application/json",
        }
        response = await ac.post(f"/webhooks/{tenant_id}/git/github", content=body_bytes, headers=h_github_valid)
        assert response.status_code == 202
        res_data = response.json()
        assert res_data["status"] == "accepted"
        event_id = res_data["event_id"]

        # Verificar Outbox event GitEventReceived
        async with tenant_context(tenant_id), api_session_factory() as session:
            outbox_res = await session.execute(
                text("SELECT event_type, payload FROM outbox WHERE aggregate_id = :event_id"),
                {"event_id": UUID(event_id)},
            )
            row = outbox_res.fetchone()
            assert row is not None
            assert row[0] == "GitEventReceived"
            evt_payload = row[1]
            assert evt_payload["provider"] == "github"
            assert evt_payload["payload"]["ref"] == "refs/heads/main"

        # 2. GitHub con Firma Inválida -> 403 Forbidden
        h_github_invalid = {
            "X-Hub-Signature-256": "sha256=invalidsignature1234567890",
            "Content-Type": "application/json",
        }
        response = await ac.post(f"/webhooks/{tenant_id}/git/github", content=body_bytes, headers=h_github_invalid)
        assert response.status_code == 403

        # 3. GitHub sin Firma -> 401 Unauthorized
        response = await ac.post(f"/webhooks/{tenant_id}/git/github", content=body_bytes)
        assert response.status_code == 401

        # --- GitLab Webhook ---

        # 4. GitLab con Token Válido
        h_gitlab_valid = {
            "X-Gitlab-Token": settings.GIT_WEBHOOK_SECRET,
            "Content-Type": "application/json",
        }
        response = await ac.post(f"/webhooks/{tenant_id}/git/gitlab", content=body_bytes, headers=h_gitlab_valid)
        assert response.status_code == 202
        res_data = response.json()
        assert res_data["status"] == "accepted"
        gitlab_event_id = res_data["event_id"]

        # Verificar Outbox event GitEventReceived
        async with tenant_context(tenant_id), api_session_factory() as session:
            outbox_res = await session.execute(
                text("SELECT event_type, payload FROM outbox WHERE aggregate_id = :event_id"),
                {"event_id": UUID(gitlab_event_id)},
            )
            row = outbox_res.fetchone()
            assert row is not None
            assert row[0] == "GitEventReceived"
            evt_payload = row[1]
            assert evt_payload["provider"] == "gitlab"

        # 5. GitLab con Token Inválido -> 403 Forbidden
        h_gitlab_invalid = {
            "X-Gitlab-Token": "invalidgitlabsecrettoken123",
            "Content-Type": "application/json",
        }
        response = await ac.post(f"/webhooks/{tenant_id}/git/gitlab", content=body_bytes, headers=h_gitlab_invalid)
        assert response.status_code == 403

        # 6. GitLab sin Token -> 401 Unauthorized
        response = await ac.post(f"/webhooks/{tenant_id}/git/gitlab", content=body_bytes)
        assert response.status_code == 401
