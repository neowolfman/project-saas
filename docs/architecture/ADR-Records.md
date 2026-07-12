# Registros de Decisiones de Arquitectura (ADR)

> Formato **Nygard**: Contexto/Problema · Opciones · Criterios · Decisión · Consecuencias (+/−).
> Numeración `ADR-0001`…`ADR-0014`, alineada con el índice del `README.md`.

---

## ADR-0001 — Backend en FastAPI + Python 3.12 async

**Estado:** Aceptada · **Contexto principal:** `09`, `04`

### Contexto / Problema
Se necesita un backend async, con tipado fuerte, generación de contratos OpenAPI y soporte para DDD/FinOps, dentro de un monorepo poliglota (Python + TS).

### Opciones
1. **FastAPI + Python 3.12** (Pydantic v2, SQLAlchemy 2.0 async + asyncpg, Alembic).
2. NestJS + TypeScript.
3. Go (net/http o fiber) + sqlc.

### Criterios
- Soporte async nativo y ecosistema para FinOps (pandas, numba opcional).
- Tipado y validación (Pydantic v2).
- Generación de OpenAPI automática.
- Ajuste a un monorepo poliglota.

### Decisión
**Opción 1.** Async nativo, OpenAPI autogenerado, ecosistema rico para finanzas/datos. NestJS se descarta por decisión explícita del usuario (rompería el monorepo poliglota TS+Python); Go, por DDD/ORM más manual y menor productividad en este dominio.

### Consecuencias
- **(+)** Contratos OpenAPI consumidos directamente por el frontend (codegen, ADR-0004).
- **(+)** Excelente para lógica financiera/analítica.
- **(−)** El GIL limita CPU-bound puro (mitigado con *workers* y jobs asíncronos).
- **(−)** Python en Nx requiere el puente `@nxlv/python` (ADR-0004).

---

## ADR-0002 — Broker RabbitMQ (DLX + colas prioritarias)

**Estado:** Aceptada · **Contexto principal:** `05`, `10`

### Contexto / Problema
Se requiere mensajería asíncrona con *dead-lettering*, colas prioritarias (VIP), semántica de Saga fiable y operación simple en Docker Compose.

### Opciones
1. **RabbitMQ** (DLX, quorum queues, prioridad).
2. NATS (JetStream).
3. Apache Kafka.
4. Redis Streams.

### Criterios
- Madurez de DLX y colas prioritarias.
- Idoneidad para Saga/Outbox con semántica de mensajería (no solo log).
- Costo de operación local (Docker Compose).

### Decisión
**Opción 1.** RabbitMQ ofrece DLX y prioridad maduros y operación trivial en Compose. NATS tiene Saga/DLX menos maduros; Kafka es pesado para entornos locales; Redis Streams tiene *consumer groups* limitados para casos financieros.

### Consecuencias
- **(+)** DLX y prioridad listos; quorum queues para HA.
- **(+)** Operación simple y observable (management UI).
- **(−)** Throughput inferior a Kafka para volúmenes extremos (aceptable: el cuello es la persistencia financiera, no el broker).

---

## ADR-0003 — Consumidores con FastStream

**Estado:** Aceptada · **Contexto principal:** `05`

### Contexto / Problema
Los consumidores deben ser async, tipados (Pydantic), con documentación AsyncAPI y bajo *boilerplate*.

### Opciones
1. **FastStream** (RabbitMQ-native).
2. aio-pika directo.
3. Celery / Dramatiq.

### Criterios
- Async-first.
- Tipado de eventos + docs.
- *Boilerplate* mínimo.

### Decisión
**Opción 1.** FastStream integra Pydantic, async y AsyncAPI. aio-pika exige demasiado *boilerplate*; Celery/Dramatiq son síncrono-predominantes y chocan con la base async del backend.

### Consecuencias
- **(+)** Contratos de evento tipados y documentados (codegen, ADR-0004).
- **(+)** Mismo stack async que el backend (reutilización de patrones).
- **(−)** Ecosistema más joven (mitigado por madurez subyacente de aio-pika).

---

## ADR-0004 — Monorepo Nx + `@nxlv/python` + codegen de contratos

**Estado:** Aceptada · **Contexto principal:** `15`, `09`

### Contexto / Problema
Coordinar frontend TS y backend Python con contratos (HTTP/eventos) sincronizados, caché de tareas y *affected builds*, evitando la deriva de interfaces.

### Opciones
1. **Nx + `@nxlv/python`** con codegen OpenAPI/AsyncAPI.
2. `run-commands` simple (Nx sin plugin Python).
3. Repositorios separados por app.

### Criterios
- First-class para TS y Python.
- Codegen de contratos unificado.
- Caché y *affected*.

### Decisión
**Opción 1.** Nx + `@nxlv/python` da tratamiento nativo a Python; los contratos OpenAPI/AsyncAPI son el puente controlado entre ambos mundos. `run-commands` carece de integración profunda; los repos separados rompen la sincronía de contratos.

### Consecuencias
- **(+)** Contratos tipados en ambos lados; los cambios rompen en CI, no en producción.
- **(+)** Caché/affected aceleran CI.
- **(−)** Complejidad del puente Nx↔Python (documentada en `15`).
- **(−)** Curva de Nx para el equipo.

---

## ADR-0005 — Multi-tenancy híbrida (shared schema + DB dedicada)

**Estado:** Aceptada · **Contexto principal:** `02`

### Contexto / Problema
Atender desde Starter (sensible a costo) hasta VIP (aislamiento físico) sin mantener productos distintos.

### Opciones
1. **Híbrida** (shared schema `tenant_id` + DB dedicada VIP + schema aislado Enterprise).
2. Shared DB/shared schema única.
3. DB aislada por tenant para todos.

### Criterios
- Costo proporcional al aislamiento requerido.
- Escala (cientos de Starter, pocos VIP).
- Riesgo de fuga de aislamiento.

### Decisión
**Opción 1.** El aislamiento caro se paga solo en VIP/Enterprise; Starter/Growth comparten infraestructura con RLS + `tenant_id`. Una única estrategia no optimiza los tres casos.

### Consecuencias
- **(+)** Costo óptimo y aislamiento proporcional.
- **(−)** Complejidad de *routing* y migraciones de tier (resuelta en `02`).
- **(−)** Requiere *connection pooling* dinámico y RLS como red de seguridad.

---

## ADR-0006 — CQRS selectivo + Event Sourcing solo en ledgers

**Estado:** Aceptada · **Contexto principal:** `04`

### Contexto / Problema
Cargas asimétricas (pocas escrituras → mucha lectura de dashboards) y necesidad de inmutabilidad/auditoría en finanzas y metering, sin sobre-ingeniar todo el sistema.

### Opciones
1. **CQRS selectivo + ES solo en ledgers** (PM core = CRUD + eventos).
2. CRUD uniforme para todo.
3. CQRS + ES completos en todo el sistema.

### Criterios
- Contención en lecturas de dashboards.
- Inmutabilidad/auditoría por dominio.
- Costo de complejidad para equipo mediano.

### Decisión
**Opción 1.** CQRS donde hay asimetría real; Event Sourcing **solo** en ledgers (financiero, auditoría, metering). CRUD uniforme contendería en picos; ES completo multiplica complejidad sin valor en *tasks/sprints*.

### Consecuencias
- **(+)** Dashboards escalan en proyecciones; trazabilidad exacta donde se necesita.
- **(−)** Dos estilos coexistentes (mitigados con *scaffolds* en `15`).
- **(−)** Las proyecciones pueden desfasarse (mitigado con *replay* y reconciliación, `16`).

---

## ADR-0007 — Series temporales con TimescaleDB

**Estado:** Aceptada · **Contexto principal:** `06`, `14`

### Contexto / Problema
*Time logs* y metering son series temporales de alta cardinalidad que exigen inserciones rápidas y agregaciones por ventanas eficientes.

### Opciones
1. **TimescaleDB** (hypertables + continuous aggregates).
2. Particionado manual en PG.
3. InfluxDB.

### Criterios
- Inserciones y agregados eficientes.
- Operación unificada (mismo motor PG).
- Costo de mantener un segundo sistema.

### Decisión
**Opción 1.** TimescaleDB reusa el ecosistema PostgreSQL (RLS, replicación lógica, operadores) y aporta hypertables/agregados continuos. El particionado manual es caro operativamente; InfluxDB añade un sistema y un paradigma extra que mantener.

### Consecuencias
- **(+)** Un motor para relacional + series temporales.
- **(+)** Agregados continuos reducen costo de lectura.
- **(−)** Requiere afinar *chunk size* y retención.

---

## ADR-0008 — Frontend Next.js App Router

**Estado:** Aceptada · **Contexto principal:** `08`

### Contexto / Problema
Una sola base para landing (SSG/SEO) y app (SPA autenticada, tiempo real), con UX rica y SEO fuerte.

### Opciones
1. **Next.js (App Router)** + TS + Tailwind + shadcn/ui + Framer Motion + TanStack Query + Zustand.
2. Remix.
3. CRA/Vite puro.

### Criterios
- SSG/ISR para SEO + SPA para producto.
- Ecosistema y rendimiento.
- App Router (RSC/streaming).

### Decisión
**Opción 1.** Next.js cubre landing (SSG/ISR) y app (SPA) en un monorepo. Remix tiene menor ecosistema a esta escala; CRA está obsoleto.

### Consecuencias
- **(+)** SEO + UX en una base.
- **(+)** RSC/streaming y *image optimization*.
- **(−)** Complejidad de App Router (mitigada con convenciones del monorepo).

---

## ADR-0009 — Caché multi-nivel L1 (in-memory) + L2 (Redis/Valkey)

**Estado:** Aceptada · **Contexto principal:** `11`

### Contexto / Problema
Reducir carga de BBDD para lecturas altas (RBAC, dashboards) con invalidación dirigida por tenant y sin perder coherencia de seguridad.

### Opciones
1. **L1 in-memory + L2 Redis/Valkey** (invalidación por evento).
2. Solo Redis.
3. Solo in-memory.

### Criterios
- Latencia (L1) + coherencia entre réplicas (L2).
- Invalidación por tenant.
- Mitigación de stampede/avalanche.

### Decisión
**Opción 1.** L1 para datos calientes/eventuales (flags, catálogos) y L2 para estado compartido (sesiones, RBAC, snapshots). Solo Redis añade un salto de red para todo; solo in-memory pierde coherencia entre réplicas.

### Consecuencias
- **(+)** Latencia baja y coherencia controlada.
- **(+)** Invalidación por evento garantiza revocación rápida de permisos.
- **(−)** Complejidad de invalidación L1↔L2 (resuelta en `11`).

---

## ADR-0010 — Observabilidad OpenTelemetry (Prometheus + Loki + Tempo)

**Estado:** Aceptada · **Contexto principal:** `12`, `10`

### Contexto / Problema
Observabilidad neutral de proveedor, con correlación métrica↔log↔traza y etiquetas multi-tenant (`tenant_id`, `tier`).

### Opciones
1. **OpenTelemetry** → Prometheus + Loki + Tempo.
2. Datadog (SaaS cerrado).
3. Jaeger + Prometheus sin OTel.

### Criterios
- Neutralidad y portabilidad (on-prem/cloud).
- Correlación por `trace_id`.
- Costo y *lock-in*.

### Decisión
**Opción 1.** OTel es estándar neutral y une los tres pilares con correlación W3C. Datadog implica *lock-in* y costo creciente; el stack sin OTel no estandariza la instrumentación.

### Consecuencias
- **(+)** Portable y correlacionado end-to-end (incluido a través del broker).
- **(−)** Requiere operar tres *backends* (mitigado con Grafana unificado).

---

## ADR-0011 — Billing: OpenMeter (metering) + Stripe (facturación)

**Estado:** Aceptada · **Contexto principal:** `14`

### Contexto / Problema
Monetización por consumo: medir uso fino y facturarlo, sin duplicar cargos y con madurez fiscal/pagos. (OQ-1 resuelta.)

### Opciones
1. **OpenMeter (metering) + Stripe Billing (facturación).**
2. Stripe-only.
3. Lago (todo en uno).

### Criterios
- Metering bruto y deduplicable.
- Madurez fiscal/pagos e impuestos.
- Separación de responsabilidades.

### Decisión
**Opción 1.** OpenMeter aporta metering especializado (agregación por ventanas, deduplicación); Stripe, facturación y pagos maduros. Stripe-only carece de metering fino; Lago es menos maduro en metering bruto.

### Consecuencias
- **(+)** Precisión de metering + robustez fiscal.
- **(+)** Cada pieza reemplazable de forma aislada.
- **(−)** Dos sistemas que integrar (orquestados por la Saga de billing, `05`).

---

## ADR-0012 — Object Storage MinIO (S3-compatible, WORM)

**Estado:** Aceptada · **Contexto principal:** `03`, `10`

### Contexto / Problema
Almacenar contratos y evidencias de auditoría con retención inmutable (SOC2/GDPR) y portabilidad on-prem/cloud.

### Opciones
1. **MinIO** (S3-compatible, *object-lock* WORM).
2. AWS S3 puro.
3. Ceph.

### Criterios
- Object-lock/WORM para retención inmutable.
- Portabilidad (no atarse a un cloud).
- Costo y operación.

### Decisión
**Opción 1.** MinIO ofrece WORM (*COMPLIANCE mode*), S3-compatibilidad y portabilidad. S3 puro cierra la salida on-prem; Ceph es pesado para este alcance.

### Consecuencias
- **(+)** WORM auditable y portable.
- **(+)** Mismo cliente S3 para dev/prod.
- **(−)** Requiere operar el cluster MinIO en producción (HA/erasure-coding).

---

## ADR-0013 — Audit ledger append-only + hash chaining + secretos en Vault

**Estado:** Aceptada · **Contexto principal:** `03`

### Contexto / Problema
Auditoría *tamper-evident* para SOC2/GDPR y gestión segura de secretos/claves.

### Opciones
1. **Audit ledger append-only + hash chaining** + Vault (o AWS Secrets Manager).
2. Tabla de logs editable/normal.
3. Secretos en variables de entorno.

### Criterios
- Inmutabilidad verificable.
- Retención y export WORM.
- Rotación y dynamic secrets.

### Decisión
**Opción 1.** El ledger append-only con encadenamiento por hash permite detectar alteraciones; el export WORM a MinIO da retención extendida; Vault aporta dynamic secrets y rotación. Una tabla normal es alterable; ENV planos son inseguros.

### Consecuencias
- **(+)** Trazabilidad y cumplimiento verificables.
- **(+)** Rotación automática reduce riesgo de credenciales.
- **(−)** Costo de verificar la cadena y operar Vault (mitigado con jobs programados, `12`).

---

## ADR-0014 — VIP resource activation en Docker Swarm (Placement Constraints)

**Estado:** Aceptada · **Contexto principal:** `10`, `14`

### Contexto / Problema
Garantizar aislamiento físico y rendimiento a tenants VIP (mitigar *noisy neighbor*) cumpliendo SLA 99,99 %, escalando workers según profundidad de cola de RabbitMQ y con DR probado, sin la sobrecarga operativa y complejidad de Kubernetes.

### Opciones
1. **Docker Swarm con Placement Constraints + recursos dedicados + auto-escalado de workers por script/API + PITR/DR.**
2. Compartir todo y solo *soft limits* en Docker Compose.
3. Migración a Kubernetes con Node Affinity/Taints y KEDA.

### Criterios
- Aislamiento físico (noisy neighbor) y límites de CPU/memoria.
- Elasticidad (escalado de workers por profundidad de cola/métricas).
- Complejidad operativa y uniformidad de stack tecnológico.
- Operabilidad unificada y DR.

### Decisión
**Opción 1.** Docker Swarm permite reutilizar la sintaxis de Docker Compose (sección `deploy`) agregando restricciones de placement (`constraints`) para aislar contenedores VIP en nodos físicos dedicados. El escalado de workers se gestiona mediante un script de monitoreo que consulta la profundidad de colas de RabbitMQ y escala los servicios a través de la API de Swarm (`docker service scale`). Esto cumple con las exigencias de aislamiento de los tiers VIP sin la sobrecarga y complejidad operativa de Kubernetes.

### Consecuencias
- **(+)** SLA VIP sostenible y noisy neighbor eliminado.
- **(+)** Curva de aprendizaje mínima al mantener la misma base de herramientas de Docker.
- **(+)** Escalado reactivo de workers ante picos de carga (webhooks).
- **(−)** La elasticidad en Swarm es menos nativa que en KEDA/K8s y requiere scripts auxiliares de orquestación y monitoreo.
