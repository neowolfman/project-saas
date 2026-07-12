# 09 — Matriz del Stack Tecnológico

> Especificación original: **§6**. Versiones base: **Python 3.12, Node 20 LTS** (OQ-3 resuelta). Cada fila resume la decisión; el detalle y los *trade-offs* completos están en `ADR-Records.md`.

## 1. Matriz principal

| Componente | Elección | Justificación (clave) | Ventaja competitiva | Alternativas descartadas (por qué) | ADR |
|---|---|---|---|---|---|
| **Lenguaje/ framework backend** | **FastAPI + Python 3.12** async (Pydantic v2, SQLAlchemy 2.0 async + asyncpg, Alembic) | Async nativo, tipado Pydantic v2, OpenAPI automático, gran ecosistema para DDD/FinOps | Contratos OpenAPI autogenerados consumidos por el frontend | NestJS/TS (rompe monorepo poliglota por elección del usuario); Go (DDD más manual) | ADR-0001 |
| **ORM / migraciones** | SQLAlchemy 2.0 async + Alembic | Soporte async, *multi-schema* para tenancy, migraciones programables | Migraciones *tenant-aware* (ver `02`) | Tortoise (menos maduro); SQLModel (capa fina sobre SA) | ADR-0001 |
| **Broker de mensajería** | **RabbitMQ** | DLX maduro, colas prioritarias (VIP), fácil operación en Docker Compose | Semántica Saga/DLX lista para finanzas | NATS (Saga/DLX menos maduro); Kafka (pesado para local); Redis Streams (consumer groups limitados para finanzas) | ADR-0002 |
| **Consumidores async** | **FastStream** | RabbitMQ-native, async, Pydantic, docs AsyncAPI | Contratos de evento tipados + docs | aio-pika (mucho boilerplate); Celery/Dramatiq (síncrono-predominante) | ADR-0003 |
| **BBDD relacional** | **PostgreSQL 16** | Confiabilidad, RLS, replicación lógica (CDC para migraciones de tier) | Aislamiento robusto vía RLS + multi-schema | MySQL (RLS/JSONB más débiles) | ADR-0005 |
| **Series temporales** | **TimescaleDB** | Hypertables para *time logs* y metering, agregados continuos eficientes | Lecturas de dashboards a costos bajos | Particionado manual (operativamente caro); InfluxDB (otro sistema que mantener) | ADR-0007 |
| **Caché** | **Redis / Valkey** (L2) + L1 in-memory | Sesiones, RBAC, dashboards; estructura para colas/Lua | Multi-nivel L1/L2 con invalidación por tenant | Memcached (sin estructuras/persistencia) | ADR-0009 |
| **Búsqueda** | **OpenSearch** | Búsqueda full-text y *facets* sobre tareas/proyectos/logs | Búsqueda multi-tenant con aislamiento por índice | Elasticsearch (licenciamiento) | — |
| **Object Storage** | **MinIO** (S3-compatible) | Contratos y evidencias de auditoría; *object-lock* WORM | Export WORM del audit ledger (SOC2/GDPR) | S3 puro (dependencia cloud cerrada para on-prem); Ceph (pesado) | ADR-0012 |
| **Frontend** | **Next.js (App Router)** + TS + Tailwind + shadcn/ui + Framer Motion + TanStack Query + Zustand | SSG landing + SPA app, SEO, UX rica | Una sola base para marketing y producto | Remix (ecosistema menor para esta escala); CRA (obsoleto) | ADR-0008 |
| **Observabilidad** | **OpenTelemetry** → Prometheus + Loki + Tempo | Estándar neutral, W3C Trace Context, correlación logs↔trazas | Telemetría con `tenant_id`/`tier` end-to-end | Datadog (vendor lock-in y costo); stack Jaeger+Prometheus sin OTel | ADR-0010 |
| **Billing (metering)** | **OpenMeter** | Metering especializado, agregación por ventanas, eventos de uso | Separación metering vs. facturación | Lago (menos especializado en metering bruto); Stripe-only (sin metering) | ADR-0011 |
| **Billing (facturación)** | **Stripe Billing** | Invoicing, *dunning*, impuestos, métodos de pago | Cumplimiento fiscal y pagos maduros | — | ADR-0011 |
| **Identity / SSO** | IdP interno + federación **SAML 2.0 / OIDC** | MFA, SSO empresarial, JWKS rotativo | Aislamiento por tenant + auditoría | Auth0 (costo y lock-in) | — |
| **Secret management** | **HashiCorp Vault** (o AWS Secrets Manager) | Dynamic secrets, rotación de credenciales DB/claves JWT | Sin secretos en imágenes/repos | Secrets en ENV planos (inseguro) | ADR-0013 |
| **Edge / proxy** | **Traefik** | Routing landing `/` + app `/app`, TLS automático, métricas | Configuración declarativa y *labels* Docker/Swarm | Nginx (config manual para DevOps) | — |
| **Monorepo / tooling** | **Nx + `@nxlv/python`** | TS native + Python first-class; caché de tareas, affected | Codegen de contratos unificado | run-commands simple (sin caché); repos separados (sincronía de contratos rota) | ADR-0004 |
| **Codegen de contratos** | **OpenAPI** (FastAPI→clientes TS) + **AsyncAPI** (eventos→Pydantic) | Contratos tipados productor↔consumidor | Cambios rompen en CI, no en producción | Contratos manuales (deriva) | ADR-0004 |
| **Container runtime (dev)** | **Docker Compose** | Stack completo local reproducible | Onboarding sin fricción | Kind/Minikube para dev (pesado) | ADR-0014 |
| **Orquestación (prod)** | **Docker Swarm** | Replicación de servicios, Placement Constraints VIP, rolling updates | Aislamiento físico VIP (noisy neighbor) sin complejidad | Nomad (menos ecosistema para esto) | ADR-0014 |
| **CI/CD** | GitHub Actions / GitLab CI | Integración con webhooks Git y SAST/DAST | Pipeline DevSecOps (ver `13`) | Jenkins (mantenimiento) | — |

## 2. Versiones y soporte (OQ-3)

| Tiempo de ejecución | Versión | Justificación |
|---|---|---|
| **Python** | **3.12** | Mejoras de rendimiento, *exception groups*, *task groups* (async robusto), soporte LTS del ecosistema (Pydantic v2, SQLAlchemy 2.0) |
| **Node.js** | **20 LTS** | LTS activo, rendimiento, soporte de Next.js 14+ |
| **PostgreSQL** | 16 | RLS, replicación lógica, performance JSONB |
| **RabbitMQ** | 3.13 / 4.x | *Streams*, colas prioritarias/quorum estables |
| **Redis/Valkey** | 7.x | ACL, persistencia AOF/RDB |

## 3. Profundidad de código por archivo (OQ-4 resuelta)

Convención del SAD: **1–2 *snippets* representativos por concepto arquitectónico**, completos y autocontenidos, no aplicaciones enteras. El objetivo es ilustrar el patrón de forma verificable, no duplicar el repositorio.

## 4. Consideraciones transversales
- **Poliglotismo gobernado:** Python (backend/workers) y TS (frontend) coexisten vía contratos generados (ADR-0004); el `@nxlv/python` da a Python tratamiento de *first-class* en Nx.
- **Neutralidad de nube:** las elecciones (PG, MinIO, OTel, Traefik) son portables on-prem/cloud, alineadas con la promesa Docker Compose y Swarm.
- **Costo de operación:** cada componente añadido (OpenSearch, Tempo) se justifica por una capacidad diferenciadora; los opcionales (OpenSearch) pueden posponerse por fase (`16`).

El detalle de infraestructura (cómo se ensamblan estos componentes) está en `10`; la organización del monorepo en `15`.
