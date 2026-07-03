"""initial core schema: tables, hypertables, RLS, views, procedures

Revision ID: 0001
Revises:
Create Date: 2026-07-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext;")

    op.execute("""
    CREATE TABLE roles (
        role_id     INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        name        TEXT NOT NULL UNIQUE,
        description TEXT
    );
    """)
    op.execute("""
    INSERT INTO roles (name, description) VALUES
        ('SuperAdmin',      'Operacion de plataforma (break-glass)'),
        ('Tenant Admin',    'Administrador del tenant'),
        ('PM',              'Project Manager'),
        ('Scrum Master',    'Scrum Master'),
        ('Product Owner',   'Product Owner'),
        ('Developer',       'Desarrollador'),
        ('QA',              'Control de calidad'),
        ('Cliente Externo', 'Cliente invitado del tenant'),
        ('Auditor',         'Auditor de solo lectura');
    """)

    op.execute("""
    CREATE TABLE tenants (
        tenant_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        slug       TEXT NOT NULL UNIQUE,
        name       TEXT NOT NULL,
        tier       TEXT NOT NULL DEFAULT 'starter'
                   CHECK (tier IN ('starter','growth','enterprise','vip')),
        db_target  TEXT NOT NULL DEFAULT 'shared',
        region     TEXT,
        status     TEXT NOT NULL DEFAULT 'active',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """)

    op.execute("""
    CREATE TABLE users (
        user_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id     UUID NOT NULL REFERENCES tenants(tenant_id),
        email         CITEXT NOT NULL,
        password_hash TEXT NOT NULL,
        mfa_enabled   BOOLEAN NOT NULL DEFAULT FALSE,
        status        TEXT NOT NULL DEFAULT 'active',
        created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (tenant_id, email)
    );
    """)

    op.execute("""
    CREATE TABLE user_roles (
        user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        role_id INTEGER NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,
        PRIMARY KEY (user_id, role_id)
    );
    """)

    op.execute("""
    CREATE TABLE projects (
        project_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id    UUID NOT NULL REFERENCES tenants(tenant_id),
        lead_user_id UUID REFERENCES users(user_id),
        name         TEXT NOT NULL,
        status       TEXT NOT NULL DEFAULT 'active',
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """)

    op.execute("""
    CREATE TABLE tasks (
        task_id          BIGINT GENERATED ALWAYS AS IDENTITY,
        tenant_id        UUID NOT NULL REFERENCES tenants(tenant_id),
        project_id       UUID NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
        assignee_user_id UUID REFERENCES users(user_id),
        title            TEXT NOT NULL,
        state            TEXT NOT NULL DEFAULT 'todo',
        story_points     INTEGER,
        client_visible   BOOLEAN NOT NULL DEFAULT FALSE,
        updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (task_id)
    );
    """)

    op.execute("""
    CREATE TABLE time_logs (
        id          BIGINT GENERATED ALWAYS AS IDENTITY,
        tenant_id   UUID NOT NULL REFERENCES tenants(tenant_id),
        user_id     UUID REFERENCES users(user_id),
        project_id  UUID NOT NULL REFERENCES projects(project_id),
        task_id     BIGINT REFERENCES tasks(task_id) ON DELETE SET NULL,
        hours       NUMERIC(5,2) NOT NULL CHECK (hours > 0),
        role_cost   NUMERIC(10,2) NOT NULL,
        amount      NUMERIC(12,2) NOT NULL,
        evidence    TEXT NOT NULL,
        source_ref  TEXT,
        logged_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (id, logged_at)
    );
    """)

    op.execute("""
    CREATE TABLE financial_contracts (
        contract_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id         UUID NOT NULL REFERENCES tenants(tenant_id),
        project_id        UUID REFERENCES projects(project_id),
        contract_value    NUMERIC(14,2) NOT NULL DEFAULT 0,
        margin_target_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
        sla_terms         JSONB NOT NULL DEFAULT '{}'::jsonb
                          CHECK (jsonb_typeof(sla_terms) = 'object'),
        window_start      DATE,
        window_end        DATE
    );
    """)

    op.execute("""
    CREATE TABLE invoices (
        invoice_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id   UUID NOT NULL REFERENCES tenants(tenant_id),
        contract_id UUID REFERENCES financial_contracts(contract_id),
        subtotal    NUMERIC(14,2) NOT NULL DEFAULT 0,
        tax         NUMERIC(14,2) NOT NULL DEFAULT 0,
        total       NUMERIC(14,2) NOT NULL DEFAULT 0,
        currency    TEXT NOT NULL DEFAULT 'CLP',
        status      TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft','issued','paid','failed')),
        issued_at   TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """)

    op.execute("""
    CREATE TABLE usage_meters (
        id           BIGINT GENERATED ALWAYS AS IDENTITY,
        tenant_id    UUID NOT NULL REFERENCES tenants(tenant_id),
        meter_code   TEXT NOT NULL,
        quantity     NUMERIC(18,4) NOT NULL,
        window_start TIMESTAMPTZ NOT NULL,
        window_end   TIMESTAMPTZ NOT NULL,
        recorded_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (id, window_start)
    );
    """)

    op.execute("""
    CREATE TABLE audit_log (
        seq         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        event_id    UUID NOT NULL UNIQUE,
        tenant_id   UUID NOT NULL REFERENCES tenants(tenant_id),
        actor_id    UUID,
        action      TEXT NOT NULL,
        resource    TEXT NOT NULL,
        resource_id TEXT,
        outcome     TEXT NOT NULL CHECK (outcome IN ('success','denied','error')),
        metadata    JSONB NOT NULL DEFAULT '{}'::jsonb
                    CHECK (jsonb_typeof(metadata) = 'object'),
        occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        prev_hash   BYTEA NOT NULL,
        event_hash  BYTEA NOT NULL
    );
    """)

    op.execute("""
    CREATE TABLE outbox (
        id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        aggregate    TEXT NOT NULL,
        aggregate_id UUID NOT NULL,
        tenant_id    UUID,
        event_type   TEXT NOT NULL,
        payload      JSONB NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
        headers      JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        published_at TIMESTAMPTZ
    );
    """)

    op.execute("""
    CREATE TABLE processed_events (
        event_id     UUID NOT NULL,
        consumer     TEXT NOT NULL,
        processed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (event_id, consumer)
    );
    """)

    op.execute("""
    CREATE TABLE margin_snapshot (
        tenant_id      UUID NOT NULL REFERENCES tenants(tenant_id),
        project_id     UUID NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
        contract_value NUMERIC(14,2) NOT NULL DEFAULT 0,
        cost_devengado NUMERIC(14,2) NOT NULL DEFAULT 0,
        margin_pct     NUMERIC(7,2) GENERATED ALWAYS AS
            (CASE WHEN contract_value = 0 THEN 0
                  ELSE ((contract_value - cost_devengado) / contract_value) * 100
             END) STORED,
        updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (tenant_id, project_id)
    );
    """)

    op.execute("""
    CREATE TABLE sla_risk_snapshot (
        tenant_id    UUID NOT NULL REFERENCES tenants(tenant_id),
        project_id   UUID NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
        p_breach     NUMERIC(4,3) NOT NULL DEFAULT 0,
        level        TEXT NOT NULL DEFAULT 'ok'
                      CHECK (level IN ('ok','warn','high','critical')),
        burn_rate    NUMERIC(8,4) NOT NULL DEFAULT 0,
        drift        NUMERIC(6,3) NOT NULL DEFAULT 1,
        evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (tenant_id, project_id)
    );
    """)

    op.execute("""
    CREATE TABLE sla_eval_queue (
        id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        tenant_id   UUID NOT NULL REFERENCES tenants(tenant_id),
        project_id  UUID NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
        priority    INTEGER NOT NULL DEFAULT 0,
        status      TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','running','done','failed')),
        enqueued_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """)

    op.execute("CREATE INDEX idx_users_tenant        ON users (tenant_id);")
    op.execute("CREATE INDEX idx_projects_tenant     ON projects (tenant_id);")
    op.execute("CREATE INDEX idx_tasks_tenant        ON tasks (tenant_id);")
    op.execute("CREATE INDEX idx_tasks_project       ON tasks (project_id);")
    op.execute("CREATE INDEX idx_tasks_assignee      ON tasks (assignee_user_id);")
    op.execute("CREATE INDEX idx_user_roles_role      ON user_roles (role_id);")
    op.execute("CREATE INDEX idx_contracts_tenant    ON financial_contracts (tenant_id);")
    op.execute("CREATE INDEX idx_contracts_project   ON financial_contracts (project_id);")
    op.execute("CREATE INDEX idx_invoices_tenant     ON invoices (tenant_id);")
    op.execute("CREATE INDEX idx_invoices_contract   ON invoices (contract_id);")

    op.execute("CREATE INDEX idx_timelogs_tenant_project ON time_logs (tenant_id, project_id, logged_at DESC);")
    op.execute("CREATE INDEX idx_timelogs_user           ON time_logs (user_id);")
    op.execute("CREATE INDEX idx_timelogs_task           ON time_logs (task_id);")
    op.execute("CREATE INDEX idx_usage_tenant_window     ON usage_meters (tenant_id, meter_code, window_start DESC);")

    op.execute("CREATE INDEX idx_outbox_unpublished ON outbox (created_at) WHERE published_at IS NULL;")
    op.execute("CREATE INDEX idx_outbox_aggregate    ON outbox (aggregate, aggregate_id);")
    op.execute("CREATE INDEX idx_audit_tenant_time   ON audit_log (tenant_id, occurred_at DESC);")
    op.execute("CREATE INDEX idx_audit_metadata_gin  ON audit_log USING gin (metadata);")
    op.execute("CREATE INDEX idx_sla_risk_level      ON sla_risk_snapshot (level, evaluated_at DESC);")
    op.execute("CREATE INDEX idx_sla_queue_pending   ON sla_eval_queue (priority DESC, enqueued_at) WHERE status = 'pending';")

    op.execute("SELECT create_hypertable('time_logs', 'logged_at', migrate_data => TRUE, if_not_exists => TRUE);")
    op.execute("SELECT create_hypertable('usage_meters', 'window_start', migrate_data => TRUE, if_not_exists => TRUE);")

    op.execute("""
    CREATE MATERIALIZED VIEW margin_daily WITH (timescaledb.continuous) AS
    SELECT time_bucket('1 day', logged_at) AS day,
           tenant_id, project_id,
           sum(amount) AS cost_devengado,
           count(*)    AS entries
    FROM time_logs
    GROUP BY day, tenant_id, project_id
    WITH NO DATA;
    """)
    op.execute("""
    CREATE MATERIALIZED VIEW usage_daily WITH (timescaledb.continuous) AS
    SELECT time_bucket('1 day', window_start) AS day,
           tenant_id, meter_code,
           sum(quantity) AS total
    FROM usage_meters
    GROUP BY day, tenant_id, meter_code
    WITH NO DATA;
    """)
    op.execute("""
    CREATE VIEW v_active_projects AS
    SELECT project_id, tenant_id, lead_user_id, name, status, created_at
    FROM projects
    WHERE status = 'active';
    """)

    for tbl in ("users", "projects", "tasks", "time_logs",
                "financial_contracts", "invoices", "usage_meters",
                "margin_snapshot", "sla_risk_snapshot"):
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"""
        CREATE POLICY tenant_isolation ON {tbl}
            USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);
        """)

    op.execute("ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;")
    op.execute("""
    CREATE POLICY tenant_audit_read ON audit_log
        FOR SELECT
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid);
    """)
    op.execute("REVOKE UPDATE, DELETE ON audit_log FROM PUBLIC;")

    op.execute("""
    CREATE OR REPLACE FUNCTION set_tenant(p_tenant uuid) RETURNS void
    LANGUAGE sql AS $$
        SELECT set_config('app.current_tenant', p_tenant::text, true);
    $$;
    """)
    op.execute("""
    CREATE OR REPLACE FUNCTION append_audit_event(
        p_tenant     uuid,
        p_actor      uuid,
        p_action     text,
        p_resource   text,
        p_resource_id text,
        p_outcome    text,
        p_metadata   jsonb
    ) RETURNS bigint
    LANGUAGE plpgsql SECURITY DEFINER AS $$
    DECLARE
        v_prev  bytea;
        v_hash  bytea;
        v_event uuid := gen_random_uuid();
        v_seq   bigint;
    BEGIN
        SELECT event_hash INTO v_prev FROM audit_log ORDER BY seq DESC LIMIT 1;
        IF v_prev IS NULL THEN
            v_prev := decode('', 'hex');
        END IF;
        v_hash := digest(
            v_prev || convert_to(json_build_object(
                'event_id', v_event, 'tenant_id', p_tenant, 'actor_id', p_actor,
                'action', p_action, 'resource', p_resource, 'resource_id', p_resource_id,
                'outcome', p_outcome, 'metadata', p_metadata
            )::text, 'UTF8'),
            'sha256'
        );
        INSERT INTO audit_log (event_id, tenant_id, actor_id, action, resource,
                               resource_id, outcome, metadata, prev_hash, event_hash)
        VALUES (v_event, p_tenant, p_actor, p_action, p_resource, p_resource_id,
                p_outcome, p_metadata, v_prev, v_hash)
        RETURNING seq INTO v_seq;
        RETURN v_seq;
    END;
    $$;
    """)
    op.execute("""
    CREATE OR REPLACE FUNCTION enqueue_sla_eval(
        p_project  uuid,
        p_tenant   uuid,
        p_priority integer
    ) RETURNS bigint
    LANGUAGE plpgsql SECURITY DEFINER AS $$
    DECLARE v_id bigint;
    BEGIN
        INSERT INTO sla_eval_queue (tenant_id, project_id, priority)
        VALUES (p_tenant, p_project, p_priority)
        RETURNING id INTO v_id;
        RETURN v_id;
    END;
    $$;
    """)
    op.execute("""
    CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger
    LANGUAGE plpgsql AS $$
    BEGIN
        NEW.updated_at := now();
        RETURN NEW;
    END;
    $$;
    """)
    op.execute("""
    CREATE TRIGGER trg_tasks_updated_at
        BEFORE UPDATE ON tasks
        FOR EACH ROW
        WHEN (OLD.* IS DISTINCT FROM NEW.*)
        EXECUTE FUNCTION set_updated_at();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_tasks_updated_at ON tasks;")
    op.execute("DROP VIEW IF EXISTS v_active_projects;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS margin_daily;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS usage_daily;")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at();")
    op.execute("DROP FUNCTION IF EXISTS enqueue_sla_eval(uuid, uuid, integer);")
    op.execute("DROP FUNCTION IF EXISTS append_audit_event(uuid, uuid, text, text, text, text, jsonb);")
    op.execute("DROP FUNCTION IF EXISTS set_tenant(uuid);")
    op.execute("""
    DROP TABLE IF EXISTS
        sla_eval_queue, sla_risk_snapshot, margin_snapshot,
        processed_events, outbox, audit_log, usage_meters,
        invoices, financial_contracts, time_logs, tasks,
        projects, user_roles, users, tenants, roles
    CASCADE;
    """)
