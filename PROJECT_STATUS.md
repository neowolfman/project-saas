# Project Status — SaaS PM+FinOps

> **Última actualización:** 2026-07-05
> **Estado general:** Fase 1 (MVP) — **80% completado**. Backend, workers, infraestructura y frontend operativos en Docker Compose.

---

## 1. Visión general

Plataforma **SaaS B2B multi-tenant** que converge gestión de proyectos (PM) y operaciones financieras (FinOps). Cada hora trabajada es un evento financiero de primera clase: el motor FinOps convierte evidencia de trabajo (timers, entradas manuales, *commits* de Git) en costo, margen y riesgo de SLA en tiempo real.

| Métrica | Valor |
|---|---|
| Repositorio | `github.com/neowolfman/project-saas` |
| Branch activo | `main` |
| Servicios en compose | 13 (ver §2.7) |
| Tests | Backend + libs Python en verde (`pytest_cache/lastfailed == {}`) |
| Cobertura del SAD | 18 docs + 14 ADRs + 3 diagramas |

---

## 2. Estado por componente

### 2.1 Backend (FastAPI) — ✅ Funcional

| Router | Endpoints | Estado | Tests |
|---|---|---|---|
| `auth` | `POST /auth/register`, `POST /auth/login` | ✅ Onboarding de tenant + login JWT | ✅ |
| `projects` | CRUD completo | ✅ + Outbox | ✅ |
| `tasks` | CRUD completo | ✅ + Outbox | ✅ |
| `time_logs` | `POST`, `GET`, `GET /summary` | ✅ Resolución de costo por rol (CLP) | ✅ |
| `financial_contracts` | CRUD completo | ✅ + Outbox | ✅ |
| `webhooks` | `POST /webhooks/github`, `POST /webhooks/gitlab` | ✅ HMAC-SHA256 (GitHub) + token (GitLab) | ✅ |

**Características transversales:**
- ✅ Middleware de tenant (`X-Tenant-ID` / subdominio) con RLS
- ✅ Anti-tenant-spoofing (JWT tenant_id vs request tenant_id)
- ✅ RBAC con `require_roles([...])`
- ✅ Outbox relay → RabbitMQ (polling 0.2s, batch 50, `FOR UPDATE SKIP LOCKED`)
- ✅ CORS restringido a localhost:3000/3001
- ✅ Healthcheck retorna HTTP 503 si la BD no responde
- ✅ Exposición via Traefik en `api.saas.local`

### 2.2 Workers (FastStream) — ✅ Funcional

| Consumer | Función | Estado | Tests |
|---|---|---|---|
| `git_consumer` | Parsea `Resolves #N [Time: Xh]` en commits, inserta `time_logs`, emite `TimeLogged` | ✅ | ✅ |
| `margin_consumer` | Idempotente: acumula `cost_devengado`, actualiza `margin_snapshot` | ✅ | ✅ |

**Topología RabbitMQ:**
- ✅ Exchange `pm.events` (topic, durable)
- ✅ DLX `pm.dlx` con colas dead-letter
- ✅ Cola prioritaria VIP (`x-max-priority: 10`)
- ✅ Idempotencia via tabla `processed_events` (`ON CONFLICT DO NOTHING`)

### 2.3 Librerías Python — ✅ Funcionales

| Lib | Path | Contenido | Tests |
|---|---|---|---|
| `ddd-core` | `libs/ddd-core/ddd_core/` | `DomainEvent` (frozen, event_id, tenant_id), `AggregateRoot`, `OutboxEvent` | ✅ |
| `db-clients` | `libs/db-clients/db_clients/` | Session factory (pool 10/20), `tenant_context` (contextvars), RLS listener (`app.current_tenant`) | ✅ |
| `security-utils` | `libs/security-utils/security_utils/` | JWT (HS256), bcrypt, HMAC (GitHub/GitLab, constant-time) | ✅ |

### 2.4 Librerías TypeScript — 🟡 Parciales

| Lib | Contenido | Estado |
|---|---|---|
| `ui-tokens` | `tokens.css` (97 líneas), `tokens.json` (DTCG), `formatCLP` | ✅ Completo |
| `design-system` | `TIERS[]` (4 tiers en CLP), tipo `Tier` | 🟡 Solo datos, sin componentes |
| `api-contracts` | 11 interfaces de entidad (Tenant, User, Project, Task, …) | 🟡 Hand-written, sin codegen OpenAPI/AsyncAPI |

### 2.5 Frontend (Next.js) — ✅ Operativo

| App | Estado | Descripción |
|---|---|---|
| `apps/landing` | ✅ Funcional | Landing page completa: hero, features (3 pilares), ROI calculator interactivo (CLP), pricing (4 tiers), CTA, footer. Tema FinOps dark con design tokens. Hot reload via Docker. |
| `apps/app` | ✅ Funcional | Dashboard shell: sidebar de navegación, top bar con search + tenant selector, 4 KPI cards, tabla de margen por proyecto (color-coded), activity feed. TanStack Query + Zustand configurados. |

**Características:**
- ✅ Next.js 14 App Router en ambos apps
- ✅ Tailwind CSS con design tokens FinOps dark (`@saas/ui-tokens`)
- ✅ Hot reload via Docker Compose (volume mounts)
- ✅ Routing via Traefik (`saas.local` → landing, `app.saas.local` → dashboard)
- ✅ Acceso directo en puertos 3001 (landing) y 3002 (app)
- ✅ Precios y ROI calculator en CLP con tabular numerals

### 2.6 Base de datos — ✅ Funcional

**Migración `0001_initial_schema.py`** (451 líneas):
- ✅ 15 tablas (con `GENERATED ALWAYS AS IDENTITY`, `CITEXT` para emails)
- ✅ 2 hypertables TimescaleDB (`time_logs` por `logged_at`, `usage_meters` por `window_start`)
- ✅ 2 continuous aggregates (`margin_daily`, `usage_daily`) + políticas de retención
- ✅ 1 view (`v_active_projects`)
- ✅ RLS `ENABLE` + `FORCE` en 10 tablas con política `tenant_isolation`
- ✅ Audit ledger hash-chainado (`append_audit_event` con advisory lock + digest)
- ✅ 3 funciones `SECURITY DEFINER` (`set_tenant`, `append_audit_event`, `enqueue_sla_eval`)
- ✅ Grants a rol no-superuser `app_api` (DML-only)
- ✅ Trigger `set_updated_at` en `tasks`
- ✅ `downgrade()` completo (drop en orden correcto)

**Rol de runtime:** `app_api` (no-superuser, DML-only) creado via init script `infra/postgres/01-create-app-role.sh`.

### 2.7 Infraestructura — ✅ Operativa

**Stack de 13 servicios en Docker Compose:**

| Servicio | Imagen | Red | Healthcheck | Traefik |
|---|---|---|---|---|
| `postgres` | `timescale/timescaledb:2.15.2-pg16` | data + gateway | `pg_isready` | — |
| `redis` | `valkey/valkey:7.2` | data + gateway | `valkey-cli ping` | — |
| `rabbitmq` | `rabbitmq:3.13-management-alpine` | data + gateway | `rabbitmq-diagnostics ping` | `rabbitmq.saas.local:15672` |
| `minio` | `minio/minio:RELEASE.2024-10-13…` | data + gateway | `mc ready local` | `minio.saas.local:9000/9001` |
| `minio-init` | `minio/mc:RELEASE.2024-10-02…` | data + gateway | One-shot: bucket WORM COMPLIANCE 2555d | — |
| `migrate` | Build (apps/backend/Dockerfile) | data + gateway | One-shot: `alembic upgrade head` | — |
| `dev-runner` | Build (apps/backend/Dockerfile) | data + gateway | Dev shell (`tail -f /dev/null`) | — |
| `backend` | Build (apps/backend/Dockerfile) | data + gateway | `GET /health` (503 si BD caída) | **`api.saas.local:8000`** |
| `workers` | Build (apps/backend/Dockerfile) | data | — (sin healthcheck) | — |
| **`landing`** | Build (apps/landing/Dockerfile) | gateway | `GET /` (Next.js dev) | **`saas.local:3000`** (port 3001) |
| **`app`** | Build (apps/landing/Dockerfile) | gateway | `GET /` (Next.js dev) | **`app.saas.local:3000`** (port 3002) |
| `opensearch` | `opensearchproject/opensearch:2.17.0` | data | `_cluster/health` | — |
| `traefik` | `traefik:3.2.0` | data + gateway | `traefik healthcheck --ping` | Dashboard `:8080` |

**Seguridad del stack:**
- ✅ Secrets fail-closed (`${VAR:?...}`) — el stack no arranca sin todos los secrets
- ✅ `--forwarded-allow-ips=10.20.0.0/24` (solo gateway-net confiable)
- ✅ CORS en una sola capa (backend, no duplicado en Traefik)
- ✅ MinIO bucket WORM con Object Lock + retención COMPLIANCE 2555d
- ✅ RLS FORCE en BD — incluso el superuser está sujeto a políticas
- ✅ Non-root container (`appuser` UID 1001)
- ✅ Rate limiting general (100/s) + auth (5/min) via Traefik
- ✅ Security headers via Traefik middleware

---

## 3. Cómo levantar el stack

```bash
# 1. Configurar secrets
cp infra/docker/.env.example infra/docker/.env
# Editar infra/docker/.env con valores reales

# 2. Construir imágenes
make infra-build

# 3. Levantar todo (migraciones se ejecutan automáticamente)
make infra-up

# 4. Verificar
make infra-status
curl -H "Host: api.saas.local" http://localhost/health
# Expected: {"status":"healthy","database":"connected"}
```

**Servicios accesibles:**

| URL | Servicio |
|---|---|
| `http://api.saas.local` | Backend API (via Traefik) |
| `http://localhost:8080/dashboard/` | Traefik Dashboard |
| `http://rabbitmq.saas.local` | RabbitMQ Management |
| `http://minio.saas.local` | MinIO Console |
| `http://localhost:9200` | OpenSearch |

> **Nota:** Añadir entradas a `/etc/hosts` para los dominios `.saas.local`:
> ```
> 127.0.0.1 api.saas.local rabbitmq.saas.local minio.saas.local
> ```

---

## 4. Progreso del roadmap

### Fase 1 — MVP (Docker Compose)

| Item | Estado | Notas |
|---|---|---|
| Infraestructura Docker Compose | ✅ | 11 servicios, healthchecks, resource limits |
| Migración inicial (schema + RLS) | ✅ | 0001: 15 tablas, hypertables, caggs, RLS FORCE |
| Backend API (auth, PM CRUD, webhooks) | ✅ | 6 routers, JWT, RBAC, outbox relay |
| Workers (git_consumer, margin_consumer) | ✅ | FastStream, DLX, colas prioritarias, idempotencia |
| RLS multi-tenant enforcement | ✅ | App + BD (defensa en profundidad) |
| Audit ledger hash-chainado | ✅ | `append_audit_event` con advisory lock |
| Traefik gateway + routing | ✅ | api.saas.local, middlewares, rate limiting |
| Libs Python (ddd-core, db-clients, security-utils) | ✅ | Tests en verde |
| Design tokens FinOps dark | ✅ | tokens.css/json, formatCLP |
| **Landing page (Next.js)** | ✅ | Hero, features, ROI calculator, pricing, CTA — FinOps dark |
| **Dashboard app (Next.js)** | ✅ | Sidebar, KPIs, tabla margen, activity feed |
| **Tests E2E (backend + BD + RLS)** | 🚧 | Pendiente suite integración Docker |

**Progreso F1: ~85%**

### Fase 2 — Multi-tenant estable + metering

| Item | Estado | Notas |
|---|---|---|
| Multi-tenancy híbrida (schema + DB dedicada) | 🟡 | Schema compartido funcional; DB dedicada pendiente |
| Metering (OpenMeter) | ❌ | No iniciado |
| Billing (Stripe) | ❌ | No iniciado |
| Observabilidad básica (OTel → Prom/Loki/Tempo) | ❌ | OTel SDK importado pero no instrumentado |
| Staging cloud | ❌ | No iniciado |

**Progreso F2: ~10%**

### Fase 3 — Enterprise + VIP en K8s

| Item | Estado |
|---|---|
| Migración a Kubernetes | ❌ |
| Recursos VIP dedicados | ❌ |
| Analítica predictiva SLA | ❌ |
| HPA por cola (KEDA) | ❌ |

**Progreso F3: 0%**

### Fase 4 — HA multi-región

| Item | Estado |
|---|---|
| Activa-pasiva multi-AZ | ❌ |
| PITR + DR probado | ❌ |
| Cost attribution maduro | ❌ |

**Progreso F4: 0%**

---

## 5. Deuda técnica conocida

| ID | Descripción | Severidad | Acción |
|---|---|---|---|
| TD-1 | `pnpm install` nunca ejecutado — `node_modules/` no existe | Media | Ejecutar antes de trabajo frontend |
| TD-2 | `apps/backend/.dockerignore` es código muerto (build context = repo root) | Baja | Eliminar archivo |
| TD-3 | Codegen OpenAPI/AsyncAPI no implementado (`tools/codegen-*.ts` referencian specs inexistentes) | Media | Crear specs o remover tools |
| TD-4 | Sin `__init__.py` en source trees Python (PEP 420 implícito) | Baja | Funciona pero frágil para tooling/IDE |
| TD-5 | Traefik dashboard sin auth (`--api.insecure=true`) | Media | Añadir BasicAuth en prod |
| TD-6 | Docker socket montado en Traefik sin proxy | Media | Usar `tecnativa/docker-socket-proxy` en prod |
| TD-7 | OpenSearch con security plugin desactivado (`DISABLE_SECURITY_PLUGIN=true`) | Baja | Aceptar para dev; activar en prod |

---

## 6. Arquitectura de servicios (diagrama)

```
                    ┌──────────────────────────────────────────────────┐
                    │                   INTERNET                        │
                    └──────────────────────┬───────────────────────────┘
                                           │ :80 / :443
                    ┌──────────────────────▼───────────────────────────┐
                    │              TRAEFIK 3.2 (gateway)                │
                    │  api.saas.local ──► backend:8000                  │
                    │  rabbitmq.saas.local ──► rabbitmq:15672           │
                    │  minio.saas.local ──► minio:9000/9001             │
                    │  Middlewares: security-headers, ratelimit         │
                    └──────┬───────────┬───────────┬───────────┬───────┘
                           │           │           │           │
            ┌──────────────▼──┐ ┌──────▼────┐ ┌────▼────┐ ┌────▼─────┐
            │  BACKEND (uv)   │ │  WORKERS  │ │ RABBITMQ│ │  MINIO   │
            │  FastAPI API    │ │ FastStream│ │  3.13   │ │  WORM    │
            │  :8000          │ │ consumers │ │ +mgmt   │ │  bucket  │
            │  6 routers      │ │ git+margin│ │         │ │          │
            │  JWT + RBAC     │ │           │ │         │ │          │
            └──────┬──────────┘ └─────┬─────┘ └─────────┘ └──────────┘
                   │                  │
            ┌──────▼──────────────────▼─────┐ ┌──────────────┐
            │  POSTGRESQL 16 + TimescaleDB  │ │  VALKEY 7.2  │
            │  15 tablas + RLS + hypertables│ │  (Redis-fork)│
            │  + continuous aggregates      │ │  cache + RL  │
            └───────────────────────────────┘ └──────────────┘
                   │
            ┌──────▼──────────┐
            │   OPENSEARCH    │
            │   2.17 (single) │
            │   search + anal │
            └─────────────────┘
```

---

## 7. Próximos pasos recomendados (priorizados)

1. **Frontend Next.js** — Bootstrap `apps/landing` y `apps/app` con App Router, Tailwind, tema FinOps dark
2. **Tests E2E** — Suite de integración que valide backend + BD + RLS + outbox end-to-end en Docker
3. **Codegen contratos** — Implementar OpenAPI spec → `libs/api-contracts/gen/` y AsyncAPI spec → eventos tipados
4. **Observabilidad** — Instrumentar OTel en backend (traces, metrics) + deploy de Prom/Loki/Tempo/Grafana
5. **CI/CD** — Pipeline GitHub Actions: lint + typecheck + test + build + security scan

---

> Documento mantenido manualmente. Actualizar después de cada sesión de desarrollo significativa.
> SAD de referencia completa: [`docs/architecture/`](docs/architecture/README.md)
