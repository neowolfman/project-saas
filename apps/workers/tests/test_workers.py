import asyncio
import json
from uuid import UUID, uuid4

import pytest
from apps.workers.src.database import api_session_factory
from apps.workers.src.runner import app
from apps.workers.src.topology import broker, pm_exchange
from db_clients.session import tenant_context
from faststream.rabbit import TestRabbitBroker
from security_utils import hash_password
from sqlalchemy import text


@pytest.fixture(scope="module")
async def seed_test_data():
    """Siembra inquilinos, usuarios, roles y proyectos para probar el worker daemon."""
    t1_id = uuid4()
    u1_dev_id = uuid4()

    # 1. Sembrar Tenant 1
    slug = f"worker-tenant-{uuid4().hex[:8]}"
    async with tenant_context(t1_id), api_session_factory() as session:
        await session.execute(
            text("INSERT INTO tenants (tenant_id, slug, name, tier) VALUES (:id, :slug, :name, 'starter')"),
            {"id": t1_id, "slug": slug, "name": "Worker Tenant"},
        )
        pw_hash = hash_password("Password123!")
        await session.execute(
            text("INSERT INTO users (user_id, tenant_id, email, password_hash) VALUES (:id, :tenant_id, :email, :hash)"),
            [
                {"id": u1_dev_id, "tenant_id": t1_id, "email": "dev@workertenant.com", "hash": pw_hash},
            ],
        )
        roles_res = await session.execute(text("SELECT role_id, name FROM roles"))
        roles_map = {row[1]: row[0] for row in roles_res.fetchall()}
        await session.execute(
            text("INSERT INTO user_roles (user_id, role_id) VALUES (:user_id, :role_id)"),
            [
                {"user_id": u1_dev_id, "role_id": roles_map["Developer"]},
            ],
        )
        p1_id = uuid4()
        await session.execute(
            text("INSERT INTO projects (project_id, tenant_id, name, status) VALUES (:p_id, :t_id, 'Worker Project', 'active')"),
            {"p_id": p1_id, "t_id": t1_id},
        )
        task_res = await session.execute(
            text("""
                INSERT INTO tasks (tenant_id, project_id, title, state, story_points)
                VALUES (:tenant_id, :project_id, 'Worker Task', 'todo', 5)
                RETURNING task_id
            """),
            {"tenant_id": t1_id, "project_id": p1_id},
        )
        task_id = task_res.fetchone()[0]
        await session.commit()

    yield {
        "t1_id": t1_id,
        "p1_id": p1_id,
        "task_id": task_id,
        "u1_dev_id": u1_dev_id,
    }

    # Teardown de datos sembrados
    async with tenant_context(t1_id), api_session_factory() as session:
        # Obtener IDs de time logs para borrarlos individualmente sin violar RLS/TimescaleDB
        log_ids_res = await session.execute(text("SELECT id FROM time_logs"))
        log_ids = [r[0] for r in log_ids_res.fetchall()]
        if log_ids:
            await session.execute(
                text("DELETE FROM time_logs WHERE id = ANY(:ids)"),
                {"ids": log_ids}
            )
        await session.execute(text("DELETE FROM processed_events"))
        await session.execute(text("DELETE FROM margin_snapshot WHERE tenant_id = :id"), {"id": t1_id})
        await session.execute(text("DELETE FROM financial_contracts WHERE tenant_id = :id"), {"id": t1_id})
        await session.execute(text("DELETE FROM tasks WHERE tenant_id = :id"), {"id": t1_id})
        await session.execute(text("DELETE FROM projects WHERE tenant_id = :id"), {"id": t1_id})
        await session.execute(text("DELETE FROM user_roles WHERE user_id = :id"), {"id": u1_dev_id})
        await session.execute(text("DELETE FROM users WHERE tenant_id = :id"), {"id": t1_id})
        await session.execute(text("DELETE FROM tenants WHERE tenant_id = :id"), {"id": t1_id})
        await session.commit()


@pytest.mark.asyncio
async def test_git_consumer_workflow(seed_test_data):
    """Verifica que el git consumer procesa los commits y guarda el log de tiempo en la hypertable."""
    async with TestRabbitBroker(broker) as test_broker:
        git_payload = {
            "event_id": str(uuid4()),
            "tenant_id": str(seed_test_data["t1_id"]),
            "provider": "github",
            "payload": {
                "commits": [
                    {
                        "id": "a1b2c3d4e5f6g7h8i9j0",
                        "message": "Implement feature. Resolves #{} [Time: 3.5]".format(seed_test_data["task_id"]),
                        "author": {
                            "email": "dev@workertenant.com"
                        }
                    }
                ]
            }
        }

        # Publicar el evento
        await test_broker.publish(
            git_payload,
            routing_key="git.events.received",
            exchange=pm_exchange
        )

        # Esperar un poco a que el worker asíncrono procese la petición en segundo plano
        await asyncio.sleep(0.5)

        # Verificar en base de datos que se haya creado el time log
        async with tenant_context(seed_test_data["t1_id"]), api_session_factory() as session:
            res = await session.execute(
                text("SELECT hours, role_cost, amount, evidence FROM time_logs WHERE task_id = :task_id"),
                {"task_id": seed_test_data["task_id"]}
            )
            row = res.fetchone()
            assert row is not None
            assert float(row[0]) == 3.5
            assert float(row[1]) == 30000.0  # Developer role rate
            assert float(row[2]) == 105000.0  # 3.5 * 30000
            assert row[3] == "git:commit:a1b2c3d4e5f6g7h8i9j0"

            # Verificar que se haya registrado en el outbox transaccional
            outbox_res = await session.execute(
                text("SELECT event_type, payload FROM outbox WHERE event_type = 'TimeLogged' ORDER BY id DESC LIMIT 1")
            )
            outbox_row = outbox_res.fetchone()
            assert outbox_row is not None
            assert outbox_row[0] == "TimeLogged"
            payload = outbox_row[1] if isinstance(outbox_row[1], dict) else json.loads(outbox_row[1])
            assert payload["hours"] == 3.5
            assert payload["amount"] == 105000.0


@pytest.mark.asyncio
async def test_margin_consumer_and_idempotency_workflow(seed_test_data):
    """Verifica que el margin consumer actualiza la proyección e implementa idempotencia."""
    # 1. Crear proyecto dedicado y contrato financiero
    p2_id = uuid4()
    contract_id = uuid4()
    async with tenant_context(seed_test_data["t1_id"]), api_session_factory() as session:
        async with session.begin():
            await session.execute(
                text("INSERT INTO projects (project_id, tenant_id, name, status) VALUES (:p_id, :t_id, 'Margin Project', 'active')"),
                {"p_id": p2_id, "t_id": seed_test_data["t1_id"]},
            )
            await session.execute(
                text("""
                    INSERT INTO financial_contracts (contract_id, tenant_id, project_id, contract_value, margin_target_pct, sla_terms, window_start, window_end)
                    VALUES (:contract_id, :tenant_id, :project_id, 10000000.0, 35.0, '{}', '2026-01-01', '2026-12-31')
                """),
                {
                    "contract_id": contract_id,
                    "tenant_id": seed_test_data["t1_id"],
                    "project_id": p2_id
                }
            )

    async with TestRabbitBroker(broker) as test_broker:
        event_id = uuid4()
        time_logged_payload = {
            "event_id": str(event_id),
            "tenant_id": str(seed_test_data["t1_id"]),
            "project_id": str(p2_id),
            "amount": 250000.0,
        }

        # 2. Publicar el primer mensaje
        await test_broker.publish(
            time_logged_payload,
            routing_key="fin.time_logged.recorded",
            exchange=pm_exchange
        )

        await asyncio.sleep(0.5)

        # Verificar proyección en base de datos
        async with tenant_context(seed_test_data["t1_id"]), api_session_factory() as session:
            res = await session.execute(
                text("SELECT contract_value, cost_devengado, margin_pct FROM margin_snapshot WHERE project_id = :project_id"),
                {"project_id": p2_id}
            )
            row = res.fetchone()
            assert row is not None
            assert float(row[0]) == 10000000.0
            assert float(row[1]) == 250000.0
            assert float(row[2]) == 97.5  # (10M - 250K)/10M * 100 = 97.5%

        # 3. Publicar el mismo mensaje de nuevo para probar la idempotencia
        await test_broker.publish(
            time_logged_payload,
            routing_key="fin.time_logged.recorded",
            exchange=pm_exchange
        )

        await asyncio.sleep(0.5)

        # Verificar que el cost_devengado NO se incrementó dos veces
        async with tenant_context(seed_test_data["t1_id"]), api_session_factory() as session:
            res = await session.execute(
                text("SELECT cost_devengado FROM margin_snapshot WHERE project_id = :project_id"),
                {"project_id": p2_id}
            )
            row = res.fetchone()
            assert row is not None
            assert float(row[0]) == 250000.0  # Sigue siendo 250k (idempotencia exitosa)

