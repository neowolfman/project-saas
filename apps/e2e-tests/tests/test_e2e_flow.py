import os
import hmac
import hashlib
import json
import uuid
import asyncio
import pytest
from sqlalchemy import text
from db_clients.session import tenant_context
from security_utils import hash_password

@pytest.mark.asyncio
async def test_complete_e2e_flow(test_tenant, api_client, superuser_session_factory):
    tenant_id = test_tenant["tenant_id"]
    tenant_slug = test_tenant["tenant_slug"]
    admin_token = test_tenant["admin_token"]
    dev_email = test_tenant["dev_email"]
    
    headers = {
        "X-Tenant-ID": str(tenant_id),
        "Authorization": f"Bearer {admin_token}",
    }

    # 1. Seed Developer user in database
    dev_id = uuid.uuid4()
    async with tenant_context(tenant_id), superuser_session_factory() as session:
        pw_hash = hash_password("Password123!")
        await session.execute(
            text("INSERT INTO users (user_id, tenant_id, email, password_hash) VALUES (:id, :tenant_id, :email, :hash)"),
            {"id": dev_id, "tenant_id": tenant_id, "email": dev_email, "hash": pw_hash}
        )
        
        # Get role ID of Developer
        roles_res = await session.execute(text("SELECT role_id FROM roles WHERE name = 'Developer'"))
        dev_role_id = roles_res.fetchone()[0]
        
        # Assign Developer role
        await session.execute(
            text("INSERT INTO user_roles (user_id, role_id) VALUES (:user_id, :role_id)"),
            {"user_id": dev_id, "role_id": dev_role_id}
        )
        await session.commit()

    # 2. Create Project via API
    proj_resp = await api_client.post("/projects", json={
        "name": "E2E Integration Project",
        "lead_user_id": str(dev_id)
    }, headers=headers)
    assert proj_resp.status_code == 201
    proj_data = proj_resp.json()
    project_id = uuid.UUID(proj_data["project_id"])

    # 3. Create Task via API
    task_resp = await api_client.post("/tasks", json={
        "project_id": str(project_id),
        "title": "E2E Test Task",
        "assignee_user_id": str(dev_id),
        "story_points": 5,
        "client_visible": True
    }, headers=headers)
    assert task_resp.status_code == 201
    task_data = task_resp.json()
    task_id = task_data["task_id"]

    # 4. Create Financial Contract via API
    contract_resp = await api_client.post("/financial-contracts", json={
        "project_id": str(project_id),
        "contract_value": 1000000.0,
        "margin_target_pct": 35.0,
        "sla_terms": {"response_time_h": 2}
    }, headers=headers)
    assert contract_resp.status_code == 201

    # 5. Trigger Git Webhook
    commit_hash = uuid.uuid4().hex
    webhook_payload = {
        "commits": [
            {
                "id": commit_hash,
                "message": f"feat: implement system outbox. Resolves #{task_id} [Time: 4.5]",
                "author": {
                    "email": dev_email
                }
            }
        ]
    }
    
    body_bytes = json.dumps(webhook_payload).encode("utf-8")
    
    # Calculate GitHub HMAC signature
    git_webhook_secret = os.getenv("GIT_WEBHOOK_SECRET", "change_me_git_webhook_secret").encode("utf-8")
    signature = hmac.new(git_webhook_secret, body_bytes, hashlib.sha256).hexdigest()
    
    webhook_headers = {
        "X-Hub-Signature-256": f"sha256={signature}",
        "Content-Type": "application/json",
    }
    
    # Call Webhook
    webhook_resp = await api_client.post(
        f"/webhooks/{tenant_id}/git/github",
        content=body_bytes,
        headers=webhook_headers
    )
    assert webhook_resp.status_code == 202
    webhook_data = webhook_resp.json()
    assert webhook_data["status"] == "accepted"

    # 6. Poll for Async Worker processing
    # The outbox relay scans every 0.2s, and workers consume in real time.
    # We poll every 0.5s up to 10s (20 attempts).
    success = False
    for _ in range(20):
        # We can check via API /time-logs
        logs_resp = await api_client.get(f"/time-logs?project_id={project_id}", headers=headers)
        if logs_resp.status_code == 200:
            logs = logs_resp.json()
            if len(logs) > 0:
                # Found the time log!
                log = logs[0]
                assert float(log["hours"]) == 4.5
                assert float(log["role_cost"]) == 30000.0
                assert float(log["amount"]) == 135000.0
                assert log["evidence"] == f"git:commit:{commit_hash}"
                success = True
                break
        await asyncio.sleep(0.5)

    assert success, "E2E timeout waiting for time log to be created by worker"

    # 7. Verify Margin Snapshot in database
    async with tenant_context(tenant_id), superuser_session_factory() as session:
        res = await session.execute(
            text("SELECT contract_value, cost_devengado, margin_pct FROM margin_snapshot WHERE project_id = :project_id"),
            {"project_id": project_id}
        )
        row = res.fetchone()
        assert row is not None
        assert float(row[0]) == 1000000.0  # contract_val
        assert float(row[1]) == 135000.0   # cost devengado
        # margin = (1000000 - 135000) / 1000000 = 86.5%
        assert float(row[2]) == 86.5

    # 8. Idempotency test: Resend the exact same commit webhook
    webhook_resp_dup = await api_client.post(
        f"/webhooks/{tenant_id}/git/github",
        content=body_bytes,
        headers=webhook_headers
    )
    assert webhook_resp_dup.status_code == 202
    
    # Wait a bit for potential processing
    await asyncio.sleep(1.0)
    
    # Verify no duplicate time logs were created
    logs_resp_dup = await api_client.get(f"/time-logs?project_id={project_id}", headers=headers)
    assert logs_resp_dup.status_code == 200
    logs_dup = logs_resp_dup.json()
    assert len(logs_dup) == 1
    
    # Verify margin snapshot cost was not increased
    async with tenant_context(tenant_id), superuser_session_factory() as session:
        res = await session.execute(
            text("SELECT cost_devengado FROM margin_snapshot WHERE project_id = :project_id"),
            {"project_id": project_id}
        )
        row = res.fetchone()
        assert float(row[0]) == 135000.0
