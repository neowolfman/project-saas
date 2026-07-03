# Documento de Arquitectura de Software (SAD) — Plataforma SaaS PM+FinOps

> **Estado:** Versión 1.0 — referencia de arquitectura para el equipo de ingeniería.
> **Idioma:** redacción técnica en **español**; código, identificadores, YAML, SQL y configuración en **inglés**.
> **Alcance:** DOCUMENTACIÓN. El código incluido es ilustrativo y de referencia; no constituye un repositorio ejecutable.

---

## 1. Cómo leer este SAD

Este documento es **modular**: un archivo por dominio o capacidad transversal, más un índice (este `README`), un apéndice consolidado de Decisiones de Arquitectura (`ADR-Records.md`) y un conjunto de diagramas Mermaid.

**Flujo de lectura sugerido para un ingeniero nuevo:**

1. `00-Executive-Summary.md` — visión, principios y alcance.
2. `09-Technology-Stack-Matrix.md` — qué tecnologías y por qué (con alternativas descartadas).
3. `ADR-Records.md` — las 14 decisiones bloqueadas que rigen el resto del documento.
4. Los archivos temáticos `01`…`16` según el área de trabajo.
5. `diagrams/` — vistas C4 (Contexto, Contenedores) y modelo entidad-relación del core.

Cada archivo temático referencia los ADRs relevantes con el formato `ADR-00NN` y, cuando corresponde, enlaza diagramas en `diagrams/`.

---

## 2. Índice de archivos

| Archivo | Capacidad | Especificación original (sección) |
|---|---|---|
| `00-Executive-Summary.md` | Resumen ejecutivo: visión, pilares, principios, alcance | §0 (intro) |
| `01-Product-Vision-Differentiation.md` | Visión de producto y diferenciación | §1 |
| `02-Multi-Tenancy-Data-Strategy.md` | Multi-tenancy híbrido y estrategia de datos | §2.1 |
| `03-Identity-Security-RBAC.md` | Identidad, seguridad, RBAC/ABAC, audit ledger | §2.2, §3 |
| `04-Domain-Design-DDD-CQRS.md` | Diseño de dominio (DDD), CQRS selectivo, Event Sourcing en ledgers | §5.1 |
| `05-Event-Driven-Architecture.md` | Arquitectura orientada a eventos (RabbitMQ + FastStream) | §5.2 |
| `06-FinOps-TimeTracking-Engine.md` | Motor FinOps y registro de horas, webhook de Git | §2.3 |
| `07-Predictive-Analytics-SLA.md` | Analítica predictiva y riesgo de SLA | §2.4 |
| `08-Frontend-DesignSystem-Landing.md` | Frontend, design system, landing y onboarding | §3 |
| `09-Technology-Stack-Matrix.md` | Matriz del stack tecnológico | §6 |
| `10-Infrastructure-Docker-K8s.md` | Infraestructura Docker Compose y migración a K8s | §8 |
| `11-Caching-Performance.md` | Caché multi-nivel y rendimiento | §9 |
| `12-Observability-Telemetry.md` | Observabilidad y telemetría | §10 |
| `13-Security-DevSecOps.md` | Seguridad aplicada y DevSecOps | §11 |
| `14-Billing-Metering-Tiers.md` | Billing, metering y matriz de tiers | §4 |
| `15-Monorepo-Structure.md` | Estructura del monorepo (Nx) | §12 |
| `16-Roadmap-FinOps-Risks.md` | Roadmap, FinOps de plataforma y riesgos | §13 |
| `ADR-Records.md` | Decisiones de arquitectura (ADR-0001…ADR-0014) | transversal |
| `diagrams/c4-context.mmd` | Diagrama C4 Nivel 1 (Contexto) | transversal |
| `diagrams/c4-container.mmd` | Diagrama C4 Nivel 2 (Contenedores) | transversal |
| `diagrams/erd-core.mmd` | Modelo entidad-relación del dominio core | transversal |

> Diagramas de secuencia adicionales (webhook de Git, saga de billing, flujo de onboarding) están embebidos como bloques Mermaid dentro de `06`, `05` y `08` respectivamente.

---

## 3. Mapa bidireccional: especificación original ↔ archivos del SAD

La especificación original contiene 14 secciones. La siguiente tabla garantiza cobertura total (sin huecos).

| Sección spec original | Tema | Archivo(s) del SAD |
|---|---|---|
| §1 | Visión y diferenciación de producto | `01` |
| §2.1 | Multi-tenancy | `02` |
| §2.2 | Identidad y seguridad (RBAC) | `03` |
| §2.3 | FinOps y time tracking | `06` |
| §2.4 | Analítica predictiva / SLA | `07` |
| §3 | Landing y frontend | `08` |
| §4 | Billing y metering | `14` |
| §5.1 | DDD / CQRS | `04` |
| §5.2 | Event-driven | `05` |
| §6 | Stack tecnológico | `09` |
| §8 | Infraestructura Docker/K8s | `10` |
| §9 | Caché | `11` |
| §10 | Observabilidad | `12` |
| §11 | Seguridad / DevSecOps | `13` |
| §12 | Monorepo | `15` |
| §13 | Roadmap y riesgos | `16` |

Las decisiones técnicas transversales (§7 implícita, stack y elecciones) se materializan como ADRs en `ADR-Records.md` y se referencian desde cada archivo temático.

---

## 4. Glosario

Términos **sobrecargados** o propios del dominio. Su uso es consistente en todo el SAD.

| Término | Definición operativa en este SAD |
|---|---|
| **Tenant** | Organización cliente (empresa B2B) que contrata la plataforma. Es la unidad de aislamiento lógico y de facturación. Un tenant agrupa a muchos usuarios. |
| **Usuario** | Persona autenticada que pertenece a un tenant. Tiene exactamente un rol dentro del tenant (uno de los 9 roles del sistema). |
| **Cliente externo** | Usuario de tipo colaborador invitado por un tenant (p. ej. un cliente final del tenant que consulta avance o aprueba entregables). Permisos acotados y de solo lectura por defecto. |
| **Tier** | Nivel comercial/operativo del tenant: **Starter**, **Growth**, **Enterprise** o **VIP/Custom**. Determina el modelo de aislamiento de datos, los límites de recursos y la activación de recursos VIP. |
| **VIP resource** | Recurso de infraestructura reservado y dedicado a un tenant VIP: base de datos aislada, réplicas de lectura, workers exclusivos, nodos K8s dedicados (Node Affinity/Taint), colas prioritarias y retención de logs extendida. |
| **Meter / Metering** | Unidad medible de consumo de un recurso facturable (p. ej. `api.calls`, `storage.gb`, `ai.tokens`, `tracked.hours.vip`). El pipeline de metering captura, agrega y persiste el uso para facturación. |
| **Ledger** | Registro contable o de auditoría **append-only** e inmutable (tamper-evident). Se aplica Event Sourcing exclusivamente sobre ledgers (financiero, auditoría, metering). |
| **Audit ledger** | Ledger específico de auditoría de seguridad: eventos de identidad, accesos y cambios críticos, con encadenamiento por hash y export WORM a MinIO. |
| **FinOps** | Disciplina de convergencia entre **gestión de proyectos (PM)** y **operaciones financieras**: imputar costo real (horas×costo por rol) a tareas/contratos y proyectar margen y SLA en tiempo real. |
| **Burn rate** | Velocidad de consumo de presupuesto/ capacidad respecto al tiempo. Se usa para predecir quiebres de SLA o sobrecostos. |
| **Outbox** | Patrón de doble escritura transaccional: persistir un evento en una tabla `outbox` en la misma transacción del cambio de estado, y un proceso *relay* lo publica al broker. Garantiza entrega sin pérdida. |
| **Saga** | Patrón de coordinación de transacciones distribuidas mediante una secuencia de eventos locales con compensaciones. En esta plataforma se usa *orchestration* para billing y aprobaciones. |
| **Idempotency key** | Identificador único enviado por el cliente (cabecera `Idempotency-Key`) que permite al servidor detectar y descartar reintentos duplicados, crítico para no duplicar cargos. |
| **Zero-friction (dev)** | Principio de experiencia: el developer no abre la UI para registrar trabajo; el sistema captura evidencia (commits, PRs, webhooks) y la convierte en registros verificables. |
| **Connection pool dinámico** | Conjunto de conexiones a BBDD resoluble en tiempo de ejecución según el tenant (pool compartido para Starter/Growth, pool dedicado para VIP). |
| **PITR** | *Point-In-Time Recovery*: restauración de base de datos a un instante arbitrario a partir de backups + WAL. Define el RPO alcanzable. |
| **RTO / RPO** | *Recovery Time Objective* / *Recovery Point Objective*: objetivo de tiempo de recuperación y de pérdida máxima de datos admisible tras un desastre. |
| **White-labeling** | Personalización automática de la apariencia (colores, tipografía, logo) de la app por tenant a partir de sus *design tokens*. |

---

## 5. Convenciones del documento

- **ADRs:** formato Nygard (Contexto/Problema, Opciones ≥3, Criterios, Decisión, Consecuencias +/−). Numerados `ADR-0001`…`ADR-0014`.
- **Diagramas:** Mermaid. Modelo C4 (Context, Container) y ERD con PKs/FKs/tipos.
- **Código de referencia:** Python 3.12 / TypeScript. Sin `// TODO`, sin truncados, sin "sigue el mismo patrón". Cada bloque es completo y autocontenido para el concepto ilustrado.
- **Versiones base:** Python **3.12**, Node **20 LTS** (ver `09-Technology-Stack-Matrix.md`).

---

## 6. Resumen de decisiones bloqueadas (índice de ADRs)

| ADR | Decisión | Archivo principal |
|---|---|---|
| ADR-0001 | Backend FastAPI + Python 3.12 async | `09`, `04` |
| ADR-0002 | Broker RabbitMQ (DLX, colas prioritarias) | `05` |
| ADR-0003 | Consumidores FastStream | `05` |
| ADR-0004 | Monorepo Nx + `@nxlv/python` + codegen OpenAPI/AsyncAPI | `15` |
| ADR-0005 | Multi-tenancy híbrida | `02` |
| ADR-0006 | CQRS selectivo + Event Sourcing solo en ledgers | `04` |
| ADR-0007 | Series temporales TimescaleDB | `06`, `14` |
| ADR-0008 | Frontend Next.js App Router | `08` |
| ADR-0009 | Caché multi-nivel L1/L2 (Redis/Valkey) | `11` |
| ADR-0010 | Observabilidad OpenTelemetry (Prometheus + Loki + Tempo) | `12` |
| ADR-0011 | Billing OpenMeter (metering) + Stripe (facturación) | `14` |
| ADR-0012 | Object Storage MinIO (S3-compatible, WORM) | `03`, `13` |
| ADR-0013 | Audit ledger append-only + hash chaining | `03` |
| ADR-0014 | VIP resource activation en K8s (Node Affinity/Taints) | `10`, `14` |
