# SaaS PM+FinOps

> Plataforma **SaaS B2B multi-tenant** de gestión de proyectos de TI con convergencia nativa entre **gestión de proyectos (PM)** y **operaciones financieras (FinOps)**.

[![Status: In Development](https://img.shields.io/badge/status-in%20development-orange)](docs/architecture/00-Executive-Summary.md)
[![Backend: FastAPI](https://img.shields.io/badge/backend-FastAPI%20%2B%20Python%203.12-3776AB)](apps/backend/)
[![Frontend: Next.js](https://img.shields.io/badge/frontend-Next.js%20App%20Router-000000)](apps/landing/)
[![Infra: Docker Compose](https://img.shields.io/badge/infra-Docker%20Compose-326CE5)](infra/docker/)
[![Language: Español](https://img.shields.io/badge/docs-espa%C3%B1ol-yellow)](docs/architecture/README.md)

---

## ✨ Qué es

Una plataforma donde **cada hora trabajada es un evento financiero de primera clase**. El motor FinOps convierte la evidencia del trabajo (timers, entradas manuales y *commits* de Git) en **costo, margen y riesgo de SLA en tiempo real**, integrando de forma nativa lo que hoy vive fragmentado entre Jira/Asana/ClickUp y una hoja de cálculo.

> **Estado del proyecto:** ver [`PROJECT_STATUS.md`](PROJECT_STATUS.md) para el detalle completo de implementación, progreso por fase, deuda técnica y próximos pasos.

## 📦 Estado de implementación

| Componente | Estado | Descripción |
|---|---|---|
| **Backend API (FastAPI)** | ✅ Funcional | 6 routers: auth (register/login + onboarding), projects, tasks, time_logs, financial_contracts, webhooks (GitHub/GitLab). Outbox relay → RabbitMQ. RLS middleware. JWT. |
| **Workers (FastStream)** | ✅ Funcional | `git_consumer` (parsea `Resolves #N [Time: Xh]`), `margin_consumer` (idempotente). DLX + colas prioritarias. |
| **Libs Python** | ✅ Funcional | `ddd-core` (DomainEvent, AggregateRoot, OutboxEvent), `db-clients` (session factory, RLS listener), `security-utils` (jwt, bcrypt, hmac) |
| **Libs TypeScript** | ✅ Parcial | `ui-tokens` (tokens.css/json), `design-system` (TIERS CLP), `api-contracts` (interfaces) |
| **Frontend (Next.js)** | 🚧 Pendiente | `apps/app` y `apps/landing` son marcadores de paquete — pendiente bootstrap con App Router |
| **Base de datos** | ✅ Funcional | Migración 0001: 15 tablas, RLS (FORCE), 2 hypertables TimescaleDB, 2 continuous aggregates, audit ledger hash-chainado |
| **Infraestructura** | ✅ Funcional | Docker Compose: PostgreSQL/TimescaleDB, Valkey, RabbitMQ, MinIO (WORM), OpenSearch, Traefik, migrate service |
| **Documentación (SAD)** | ✅ Completa | 17 docs modulares + 14 ADRs + 3 diagramas (C4 + ERD) |

## 🏛️ Los tres pilares

| Pilar | Descripción |
|---|---|
| **PM + FinOps convergentes** | Margen y SLA derivados de *ledgers* inmutables (Event Sourcing en lo financiero); CRUD ágil en el *core* de PM. |
| **Aislamiento enterprise híbrido** | *Schema* compartido con `tenant_id` (Starter/Growth) + **base de datos dedicada** (Enterprise/VIP), con recursos VIP físicamente aislados en K8s. |
| **Zero-friction para devs** | Registro de horas vía *webhooks* de Git (`Resolves #102 [Time: 2h]`) y onboarding de tenant en caliente, sin abrir la UI. |

## 🧱 Stack tecnológico

| Capa | Tecnología |
|---|---|
| **Backend** | FastAPI · Python 3.12 · Pydantic v2 · SQLAlchemy 2.0 async + asyncpg · Alembic |
| **Mensajería** | RabbitMQ (DLX, colas prioritarias) · FastStream (AsyncAPI) |
| **Datos** | PostgreSQL 16 · TimescaleDB · Redis/Valkey · OpenSearch · MinIO |
| **Frontend** | Next.js (App Router) · TypeScript · Tailwind · shadcn/ui · TanStack Query · Zustand |
| **Observabilidad** | OpenTelemetry → Prometheus + Loki + Tempo + Grafana |
| **Billing** | OpenMeter (metering) + Stripe Billing |
| **Infra** | Docker Compose → Kubernetes · Traefik · Vault |
| **Tooling** | Monorepo Nx + `@nxlv/python` |

## 🚀 Arranque rápido

### Prerrequisitos
- Docker + Docker Compose v2
- Node.js 20 LTS + pnpm 9
- Python 3.12

### Levantar infraestructura

```bash
# Configurar secrets (fail-closed: el stack no arranca sin ellos)
cp infra/docker/.env.example infra/docker/.env
# Editar infra/docker/.env con contraseñas reales

# Validar y levantar
make validate        # valida docker-compose.yml
make infra-build     # construye imágenes (migrate)
make infra-up        # levanta todos los servicios + ejecuta migraciones
make infra-status    # verificar que todo está healthy
```

### Servicios disponibles

| Servicio | URL local | Credenciales |
|---|---|---|
| Traefik Dashboard | http://localhost:8080 | (sin auth, dev only) |
| RabbitMQ Management | http://rabbitmq.saas.local | ver `infra/docker/.env` |
| MinIO Console | http://minio.saas.local | ver `infra/docker/.env` |
| OpenSearch | http://localhost:9200 | (security plugin desactivado en dev) |
| PostgreSQL | localhost:5432 | user `app` / ver `.env` |
| Backend API | http://localhost:8000 (próximamente) | — |

### Comandos útiles

```bash
make help           # lista todos los targets disponibles
make psql           # shell psql directo a la base de datos
make redis-cli      # shell redis-cli
make migrate        # re-ejecutar migraciones
make infra-logs     # tail de logs
make infra-down     # detener servicios
make clean          # detener + limpiar contenedores (preserva volúmenes)
```

## 📚 Documentación de arquitectura (SAD)

El SAD es **modular**: un archivo por dominio + índice + apéndice de ADRs + diagramas, redactado en **español técnico** (código/identificadores en inglés).

**Punto de entrada:** [`docs/architecture/README.md`](docs/architecture/README.md)

### Lectura rápida por interés

| Si te interesa… | Lee |
|---|---|
| La visión y el porqué | [`01-Product-Vision-Differentiation.md`](docs/architecture/01-Product-Vision-Differentiation.md) |
| Cómo se aíslan los tenants | [`02-Multi-Tenancy-Data-Strategy.md`](docs/architecture/02-Multi-Tenancy-Data-Strategy.md) |
| Identidad, RBAC y auditoría | [`03-Identity-Security-RBAC.md`](docs/architecture/03-Identity-Security-RBAC.md) |
| El dominio y CQRS/ES | [`04-Domain-Design-DDD-CQRS.md`](docs/architecture/04-Domain-Design-DDD-CQRS.md) |
| El corazón financiero | [`06-FinOps-TimeTracking-Engine.md`](docs/architecture/06-FinOps-TimeTracking-Engine.md) |
| Infraestructura y despliegue | [`10-Infrastructure-Docker-K8s.md`](docs/architecture/10-Infrastructure-Docker-K8s.md) |
| Billing, metering y tiers | [`14-Billing-Metering-Tiers.md`](docs/architecture/14-Billing-Metering-Tiers.md) |
| Las decisiones (ADRs) | [`ADR-Records.md`](docs/architecture/ADR-Records.md) |

## 🗺️ Roadmap

1. **MVP** — ✅ Backend + infraestructura en Docker Compose. 🚧 Frontend Next.js pendiente.
2. **Multi-tenant estable + metering** (Starter/Enterprise).
3. **Enterprise + VIP en K8s** — recursos dedicados, analítica predictiva de SLA.
4. **HA multi-región** — activa-pasiva, DR probado, RTO/RPO objetivos.

Detalle en [`16-Roadmap-FinOps-Risks.md`](docs/architecture/16-Roadmap-FinOps-Risks.md).

## 📄 Licencia

Por definir. Mientras tanto, todos los derechos reservados.

---

<sub>Documentación en español técnico · código e identificadores en inglés · SAD v1.0</sub>
