# =============================================================================
# SaaS PM+FinOps — Backend + Workers + Libs Python (multi-stage)
#
# Build context: REPO ROOT (no apps/backend/), para poder incluir las libs
# Python (ddd_core, db_clients, security_utils) que el backend importa.
#
# Uso:
#   docker build -t saas-backend -f apps/backend/Dockerfile .
#   # o via docker-compose: el servicio 'backend', 'workers' y 'migrate'
#   # comparten esta imagen con diferentes ENTRYPOINT/COMMAND.
# =============================================================================

# ── Stage 1: Builder — instala dependencias en un venv ──────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY apps/backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt


# ── Stage 2: Production — runtime liviano non-root ──────────────────────────
FROM python:3.12-slim AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    # PYTHONPATH permite resolver imports absolutos:
    #   - /app                    → apps.backend.src.*, apps.workers.src.*
    #   - /app/libs/ddd-core      → ddd_core.*
    #   - /app/libs/db-clients    → db_clients.*
    #   - /app/libs/security-utils→ security_utils.*
    PYTHONPATH="/app:/app/libs/ddd-core:/app/libs/db-clients:/app/libs/security-utils"

RUN groupadd --system --gid 1001 appuser \
 && useradd  --system --uid 1001 --gid appuser --home-dir /app appuser

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

# — Backend source (FastAPI app + migraciones) —
COPY --chown=appuser:appuser apps/backend/src/      apps/backend/src/
COPY --chown=appuser:appuser apps/backend/migrations/ apps/backend/migrations/
COPY --chown=appuser:appuser apps/backend/tests/    apps/backend/tests/

# — Workers source (FastStream consumers) —
COPY --chown=appuser:appuser apps/workers/src/      apps/workers/src/
COPY --chown=appuser:appuser apps/workers/tests/    apps/workers/tests/

# — Python libraries (DDD core, DB clients, Security utils) —
COPY --chown=appuser:appuser libs/ddd-core/ddd_core/         libs/ddd-core/ddd_core/
COPY --chown=appuser:appuser libs/ddd-core/tests/            libs/ddd-core/tests/
COPY --chown=appuser:appuser libs/db-clients/db_clients/     libs/db-clients/db_clients/
COPY --chown=appuser:appuser libs/db-clients/tests/          libs/db-clients/tests/
COPY --chown=appuser:appuser libs/security-utils/security_utils/ libs/security-utils/security_utils/
COPY --chown=appuser:appuser libs/security-utils/tests/      libs/security-utils/tests/

USER appuser

# Default entrypoint: python. Override en docker-compose según servicio.
ENTRYPOINT ["python"]
