# 10 — Infraestructura: Docker Compose, Swarm y Escalado

> Especificación original: **§8**. Decisiones: **ADR-0014** (VIP activation en Docker Swarm), **ADR-0010** (observabilidad), **ADR-0012** (MinIO). Relacionado: `09` (stack), `12` (observabilidad), `02` (multi-tenancy), `diagrams/c4-container.mmd`.
>
> **Nota de implementación (2026-07-05):** El `docker-compose.yml` de referencia en este documento describe el **stack objetivo completo** (21 servicios, incluyendo observabilidad, Vault, OpenMeter, etc.). El archivo **operativo** en `infra/docker/docker-compose.yml` implementa actualmente **11 servicios** (subset de Fase 1). Ver [`PROJECT_STATUS.md`](../../PROJECT_STATUS.md) §2.7 para el inventario exacto. La diferencia principal: el compose operativo omite por ahora los servicios de observabilidad (Prometheus, Loki, Tempo, Grafana, OTel Collector), Vault y OpenMeter — se añadirán en Fase 2.

## 1. Filosofía de despliegue

- **Fase 1–2:** operación con **Docker Compose** (entorno reproducible local + primeros clientes).
- **Fase 3+:** orquestación y escalado con **Docker Swarm / Compose** para HA, replicación y **aislamiento físico VIP**.
- El mismo conjunto de imágenes sirve todos los entornos: solo varían el archivo de Compose (con sección `deploy`) y la asignación de nodos del clúster Swarm.

## 2. `docker-compose.yml` (completo)

Redes aisladas: `frontend-net` (solo exponible), `backend-net` (API/workers), `data-net` (BBDD/colas/storage), `obs-net` (observabilidad). Traefik es el único servicio con puertos publicados.

```yaml
# docker-compose.yml
name: saas-pm-finops

x-app-env: &app-env
  ENV: ${ENV:-development}
  LOG_LEVEL: ${LOG_LEVEL:-info}
  OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4317
  OTEL_SERVICE_NAMESPACE: saas
  RABBITMQ_URL: amqp://${RABBITMQ_USER:-guest}:${RABBITMQ_PASSWORD:-guest}@rabbitmq:5672/
  REDIS_URL: redis://redis:6379/0
  VAULT_ADDR: http://vault:8200

networks:
  frontend-net:
    driver: bridge
  backend-net:
    driver: bridge
  data-net:
    driver: bridge
  obs-net:
    driver: bridge

volumes:
  pg-shared-data:
  pg-vip-data:
  tsdb-data:
  redis-data:
  rabbitmq-data:
  minio-data:
  opensearch-data:
  prometheus-data:
  loki-data:
  tempo-data:
  grafana-data:

services:

  # ---------- EDGE ----------
  traefik:
    image: traefik:v3.1
    command:
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--providers.docker.network=frontend-net"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--entrypoints.web.http.redirections.entrypoint.to=websecure"
      - "--entrypoints.web.http.redirections.entrypoint.scheme=https"
      - "--metrics.prometheus=true"
      - "--tracing.otlp=true"
    ports:
      - "80:80"
      - "443:443"
      - "8080:8080"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks: [frontend-net, obs-net]
    healthcheck:
      test: ["CMD", "traefik", "healthcheck", "--ping"]
      interval: 15s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 512M

  # ---------- FRONTEND ----------
  landing:
    image: saas/landing:${TAG:-latest}
    environment:
      <<: *app-env
      NEXT_PUBLIC_API_BASE_URL: https://api.${ROOT_DOMAIN:-app.com}
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.landing.rule=Host(`${ROOT_DOMAIN:-app.com}`)"
      - "traefik.http.routers.landing.entrypoints=websecure"
      - "traefik.http.routers.landing.tls=true"
      - "traefik.http.services.landing.loadbalancer.server.port=3000"
    networks: [frontend-net]
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:3000/api/health"]
      interval: 30s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 384M

  app:
    image: saas/app:${TAG:-latest}
    environment:
      <<: *app-env
      NEXT_PUBLIC_API_BASE_URL: https://api.${ROOT_DOMAIN:-app.com}
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.app.rule=Host(`app.${ROOT_DOMAIN:-app.com}`) || HostRegexp(`{subdomain:[a-z0-9-]+}.${ROOT_DOMAIN:-app.com}`)"
      - "traefik.http.routers.app.entrypoints=websecure"
      - "traefik.http.routers.app.tls=true"
      - "traefik.http.services.app.loadbalancer.server.port=3001"
    networks: [frontend-net, backend-net]
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:3001/api/health"]
      interval: 30s
      timeout: 5s
      retries: 5
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 768M

  # ---------- BACKEND ----------
  backend:
    image: saas/backend:${TAG:-latest}
    environment:
      <<: *app-env
      DATABASE_URL_SHARED: postgresql+asyncpg://${PG_USER:-app}:${PG_PASSWORD:-app}@postgres-shared:5432/saas
      DATABASE_URL_TSDB: postgresql+asyncpg://${PG_USER:-app}:${PG_PASSWORD:-app}@timescaledb:5432/finops
      DATABASE_URL_VIP_KEY: vip_acme
      OPENMETER_API_URL: http://openmeter:8888
      MINIO_ENDPOINT: http://minio:9000
    depends_on:
      postgres-shared: { condition: service_healthy }
      timescaledb: { condition: service_healthy }
      redis: { condition: service_healthy }
      rabbitmq: { condition: service_healthy }
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.backend.rule=Host(`api.${ROOT_DOMAIN:-app.com}`)"
      - "traefik.http.routers.backend.entrypoints=websecure"
      - "traefik.http.routers.backend.tls=true"
      - "traefik.http.services.backend.loadbalancer.server.port=8000"
    networks: [frontend-net, backend-net, data-net, obs-net]
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz').status==200 else 1)"]
      interval: 20s
      timeout: 5s
      retries: 6
      start_period: 30s
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 1G

  workers:
    image: saas/workers:${TAG:-latest}
    command: ["python", "-m", "apps.workers.runner"]
    environment:
      <<: *app-env
      DATABASE_URL_SHARED: postgresql+asyncpg://${PG_USER:-app}:${PG_PASSWORD:-app}@postgres-shared:5432/saas
      DATABASE_URL_TSDB: postgresql+asyncpg://${PG_USER:-app}:${PG_PASSWORD:-app}@timescaledb:5432/finops
      OPENMETER_API_URL: http://openmeter:8888
    depends_on:
      rabbitmq: { condition: service_healthy }
      postgres-shared: { condition: service_healthy }
      timescaledb: { condition: service_healthy }
    networks: [backend-net, data-net, obs-net]
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import asyncio,os; from apps.workers.health import probe; sys.exit(0 if asyncio.run(probe()) else 1)\""]
      interval: 30s
      timeout: 10s
      retries: 5
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 1G

  # ---------- DATA ----------
  postgres-shared:
    image: postgres:16
    environment:
      POSTGRES_USER: ${PG_USER:-app}
      POSTGRES_PASSWORD: ${PG_PASSWORD:-app}
      POSTGRES_DB: saas
    volumes:
      - pg-shared-data:/var/lib/postgresql/data
      - ./infra/postgres/shared.init.sql:/docker-entrypoint-initdb.d/01-init.sql:ro
    networks: [data-net]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${PG_USER:-app} -d saas"]
      interval: 10s
      timeout: 5s
      retries: 10
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 2G

  postgres-vip:
    image: postgres:16
    environment:
      POSTGRES_USER: ${PG_VIP_USER:-vip}
      POSTGRES_PASSWORD: ${PG_VIP_PASSWORD:-vip}
      POSTGRES_DB: vip_tenants
    volumes:
      - pg-vip-data:/var/lib/postgresql/data
    networks: [data-net]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${PG_VIP_USER:-vip} -d vip_tenants"]
      interval: 10s
      timeout: 5s
      retries: 10
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 2G

  timescaledb:
    image: timescale/timescaledb:2.15.2-pg16
    environment:
      POSTGRES_USER: ${PG_USER:-app}
      POSTGRES_PASSWORD: ${PG_PASSWORD:-app}
      POSTGRES_DB: finops
    volumes:
      - tsdb-data:/var/lib/postgresql/data
    networks: [data-net]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${PG_USER:-app} -d finops"]
      interval: 10s
      timeout: 5s
      retries: 10
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 2G

  redis:
    image: valkey/valkey:7.2
    command: ["valkey-server", "--appendonly", "yes", "--maxmemory", "512mb", "--maxmemory-policy", "allkeys-lru"]
    volumes:
      - redis-data:/data
    networks: [data-net, backend-net]
    healthcheck:
      test: ["CMD", "valkey-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 10
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 768M

  rabbitmq:
    image: rabbitmq:3.13-management
    environment:
      RABBITMQ_DEFAULT_USER: ${RABBITMQ_USER:-guest}
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD:-guest}
    volumes:
      - rabbitmq-data:/var/lib/rabbitmq
      - ./infra/rabbitmq/definitions.json:/etc/rabbitmq/definitions.json:ro
    networks: [data-net, backend-net]
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "check_port_connectivity"]
      interval: 15s
      timeout: 10s
      retries: 10
    deploy:
      resources:
        limits:
          cpus: "1.5"
          memory: 1G

  minio:
    image: minio/minio:RELEASE.2024-10-13T13-34-11Z
    command: ["server", "/data", "--console-address", ":9001"]
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minioadmin}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-minioadmin}
    volumes:
      - minio-data:/data
    networks: [data-net]
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 20s
      timeout: 5s
      retries: 10
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1G

  minio-init:
    image: minio/mc:RELEASE.2024-10-02T08-27-28Z
    depends_on:
      minio: { condition: service_healthy }
    entrypoint: >
      /bin/sh -c "
      mc alias set local http://minio:9000 ${MINIO_ROOT_USER:-minioadmin} ${MINIO_ROOT_PASSWORD:-minioadmin} &&
      mc mb -p local/audit-ledger-archive &&
      mc version enable local/audit-ledger-archive &&
      mc retention set COMPLIANCE 2555d local/audit-ledger-archive &&
      mc anonymous set none local/audit-ledger-archive;
      exit 0;
      "
    networks: [data-net]

  opensearch:
    image: opensearchproject/opensearch:2.16.0
    environment:
      discovery.type: single-node
      bootstrap.memory_lock: "true"
      OPENSEARCH_JAVA_OPTS: "-Xms512m -Xmx512m"
      OPENSEARCH_INITIAL_ADMIN_PASSWORD: ${OS_ADMIN_PASSWORD:-StrongPassw0rd!}
    ulimits:
      memlock: { soft: -1, hard: -1 }
    volumes:
      - opensearch-data:/usr/share/opensearch/data
    networks: [data-net]
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS -u admin:${OS_ADMIN_PASSWORD:-StrongPassw0rd!} http://localhost:9200/_cluster/health || exit 1"]
      interval: 20s
      timeout: 10s
      retries: 10
    deploy:
      resources:
        limits:
          cpus: "1.5"
          memory: 1536M

  vault:
    image: hashicorp/vault:1.18
    environment:
      VAULT_DEV_ROOT_TOKEN_ID: ${VAULT_DEV_TOKEN:-root}
      VAULT_DEV_LISTEN_ADDRESS: 0.0.0.0:8200
    cap_add: ["IPC_LOCK"]
    entrypoint: ["vault", "server", "-dev"]
    networks: [data-net, backend-net]
    healthcheck:
      test: ["CMD", "vault", "status"]
      interval: 15s
      timeout: 5s
      retries: 10
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 384M

  openmeter:
    image: openmeter/openmeter:0.31.1
    command: ["serve"]
    environment:
      OTEL_EXPORTER_OTLP_ENDPOINT: http://otel-collector:4317
    networks: [data-net, backend-net, obs-net]
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:8888/healthz || exit 1"]
      interval: 20s
      timeout: 5s
      retries: 10
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 768M

  # ---------- OBSERVABILIDAD ----------
  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.110.0
    command: ["--config=/etc/otel/config.yaml"]
    volumes:
      - ./infra/otel/collector.yaml:/etc/otel/config.yaml:ro
    networks: [obs-net, backend-net]
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 768M

  prometheus:
    image: prom/prometheus:v2.54.1
    volumes:
      - ./infra/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    networks: [obs-net, data-net]
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:9090/-/healthy"]
      interval: 20s
      timeout: 5s
      retries: 10
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1G

  promtail:
    image: grafana/promtail:3.2.0
    volumes:
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - /var/log:/var/log:ro
      - ./infra/promtail/config.yaml:/etc/promtail/config.yaml:ro
    command: ["-config.file=/etc/promtail/config.yaml"]
    networks: [obs-net]
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 384M

  loki:
    image: grafana/loki:3.2.0
    command: ["-config.file=/etc/loki/local-config.yaml"]
    volumes:
      - loki-data:/loki
    networks: [obs-net]
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:3100/ready"]
      interval: 20s
      timeout: 5s
      retries: 10
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1G

  tempo:
    image: grafana/tempo:2.6.0
    command: ["-config.file=/etc/tempo.yaml"]
    volumes:
      - ./infra/tempo/tempo.yaml:/etc/tempo.yaml:ro
      - tempo-data:/var/tempo
    networks: [obs-net]
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:3200/ready"]
      interval: 20s
      timeout: 5s
      retries: 10
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1G

  grafana:
    image: grafana/grafana:11.3.0
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD:-admin}
      GF_AUTH_ANONYMOUS_ENABLED: "false"
    volumes:
      - grafana-data:/var/lib/grafana
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.grafana.rule=Host(`grafana.${ROOT_DOMAIN:-app.com}`)"
      - "traefik.http.routers.grafana.entrypoints=websecure"
      - "traefik.http.routers.grafana.tls=true"
      - "traefik.http.services.grafana.loadbalancer.server.port=3000"
    networks: [frontend-net, obs-net]
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:3000/api/health || exit 1"]
      interval: 20s
      timeout: 5s
      retries: 10
    deploy:
      resources:
        limits:
          cpus: "0.5"
          memory: 512M
```

### Notas del compose
- **Aislamiento de red:** `frontend-net` solo la exponen Traefik, landing, app y grafana; el backend une `frontend-net`+`backend-net`+`data-net`+`obs-net`; las BBDD solo en `data-net`.
- **Healthchecks reales** por servicio (pg_isready, valkey-cli, rabbitmq-diagnostics, mc ready, endpoints `/healthz`).
- **`deploy.resources.limits`** en todos los servicios (mitiga *noisy neighbor* ya en Compose).
- **`minio-init`** crea el bucket WORM `audit-ledger-archive` con retención *COMPLIANCE* 2555d (~7 años) — sustento del audit ledger (`03`).
- **Vault en modo dev** es referencia para local; en producción se usa HA con almacenamientoConsul/KMS.

## 3. Escalado y Aislamiento en Producción con Docker (Swarm / Compose)

### Mapeo contenedor → tipo de servicio Swarm

| Servicio Compose | Tipo de Servicio Swarm | Motivo |
|---|---|---|
| traefik | **Replicated** (puertos expuestos) | *Edge* con balanceo, escalable |
| landing, app | **Replicated** | Sin estado, escalado horizontal |
| backend | **Replicated** | Sin estado (sesión persistente en Redis) |
| workers | **Replicated** | Sin estado, escalado según profundidad de cola |
| postgres-shared, postgres-vip, timescaledb | **Replicated (1 sola réplica)** + Constraints | Con estado. Restringido a un nodo específico con volumen local/SAN persistente |
| redis | **Replicated (1 sola réplica)** (o Redis Sentinel) | Cache/Store en memoria con persistencia en disco |
| rabbitmq | **Replicated** (Clúster Swarm de RabbitMQ) | Cola de mensajería tolerante a fallos |
| minio | **Replicated** / Modo Distribuido | Almacenamiento de objetos S3 WORM |
| opensearch | **Replicated** (Clúster) | Nodos de datos con almacenamiento persistente |
| vault | **Replicated** | Servidor de secretos de alta disponibilidad |
| otel-collector, promtail | **Global** (1 instancia por nodo) | Recolector de telemetría corriendo de forma nativa en cada nodo |
| prometheus, loki, tempo, grafana | **Replicated** | Stack de telemetría y visualización |

### Manifiestos de referencia (ejemplo de Stack Swarm para VIP)
```yaml
# infra/docker/docker-compose.prod-vip.yml
version: "3.8"
services:
  backend-vip-acme:
    image: saas/backend:latest
    networks:
      - data-net
      - frontend-net
    deploy:
      replicas: 3
      placement:
        constraints:
          - node.labels.workloadclass == vip
          - node.labels.tenant == vip-acme
      resources:
        limits:
          cpus: '2.0'
          memory: 1024M
        reservations:
          cpus: '0.5'
          memory: 512M
      restart_policy:
        condition: on-failure
    environment:
      DATABASE_URL_VIP: "postgresql+asyncpg://vip-acme-db:5432/vip_acme"
```
```bash
# Comando de aprovisionamiento y aislamiento de nodos en Docker Engine / Swarm
docker node update --label-add workloadclass=vip node-vip-01
docker node update --label-add tenant=vip-acme node-vip-01
```

## 4. VIP resource activation en Docker Swarm / Compose (ADR-0014)

| Recurso VIP | Mecanismo Docker Swarm / Compose |
|---|---|
| DB aislada | Contenedor de PostgreSQL exclusivo en red aislada + volumen dedicado (ver `02`) |
| Réplicas de lectura | Contenedor de lectura de PG configurado como réplica física (async streaming) |
| Nodos dedicados | **Placement Constraints** (`node.labels.workloadclass == vip`) para aislar contenedores |
| *Workers* exclusivos | **Services** Swarm independientes escuchando a colas prioritarias específicas (`05`) |
| Colas prioritarias | `x-max-priority=10` en RabbitMQ + workers VIP dedicados |
| Retención logs extendida | Recolección de logs por Promtail (filtrado por labels de Docker) y retención en Loki de 7 años |

### Mitigación de *noisy neighbor*
- **CPU/memoria:** Limitación explícita mediante `deploy.resources.limits` en Docker Compose/Swarm.
- **Red:** Redes overlay independientes y aisladas para cada tenant VIP.
- **Discos IOPS:** Montajes directos sobre volúmenes SSD de alta velocidad en hosts locales restringidos.

## 5. Escalado de Servicios (Autoscaling)

- **Backend/landing/app:** Escalado reactivo controlando el clúster a través del Docker Socket / API de Swarm (`docker service update --replicas=X`) basándose en métricas de Prometheus.
- **Workers:** Escalado automatizado por **profundidad de cola RabbitMQ** (por ejemplo, mediante un script en bash/python en cron que consulte la API de RabbitMQ y ejecute `docker service scale saas_workers=X` ante picos de webhook).

```bash
# Ejemplo de script de auto-escalado simple basado en RabbitMQ
QUEUE_LENGTH=$(curl -s -u guest:guest http://rabbitmq:15672/api/queues/%2f/fin.time_logged | jq '.messages')
if [ "$QUEUE_LENGTH" -gt 500 ]; then
  docker service scale saas_workers=10
elif [ "$QUEUE_LENGTH" -lt 50 ]; then
  docker service scale saas_workers=2
fi
```

## 6. Backups, PITR y DR

| Tipo | Mecanismo | RPO | RTO |
|---|---|---|---|
| **BBDD (full + WAL)** | *base backup* diario + archivo WAL continuo (pgBackRest / WAL-G) | **≤ 5 min** (PITR) | ≤ 1 h |
| **TimescaleDB** | *base backup* + WAL; *continuous aggregates* rederivables | ≤ 15 min | ≤ 2 h |
| **MinIO** | *versioning* + *replication* cross-region (VIP a bucket dedicado) | ≈ 0 (replicado) | ≤ 30 min |
| **Config/secretos** | GitOps (repo) + Vault *snapshots* | ≈ 0 | ≤ 15 min |
| **RTO/RPO objetivos** | Multi-AZ activa-pasiva (Fase 4, `16`) | **RPO ≤ 5 min** | **RTO ≤ 1 h** |

### Estrategia de DR
- **Activa-pasiva multi-AZ** en Fase 4: la región *standby* recibe replicación de PG (async streaming) y de MinIO; *failover* documentado y *game-day* trimestral.
- **Runbooks:** *restore* PITR point-in-time, *failover* de RabbitMQ quorum, rehydración de proyecciones desde ledgers (replay de eventos, `04`).

## 7. Referencias a diagramas
- Vista de contenedores y sistemas externos: `diagrams/c4-container.mmd`.
- Topología de red y servicios externos (Git/IdP/Stripe): `diagrams/c4-context.mmd`.

El detalle de telemetría que alimenta HPA y observabilidad está en `12`; los pipelines de seguridad que protegen estas imágenes, en `13`.
