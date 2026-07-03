# 05 — Arquitectura Orientada a Eventos

> Especificación original: **§5.2**. Decisiones: **ADR-0002** (RabbitMQ), **ADR-0003** (FastStream). Relacionado: `04` (dominio), `14` (billing).

## 1. Topología de RabbitMQ

La mensajería es la **columna vertebral** de la comunicación asíncrona. RabbitMQ se eligió (ADR-0002) por su semántica madura de **DLX** (*Dead-Letter Exchange*), **colas prioritarias** (VIP) y operación sencilla en Docker Compose.

### Exchanges y colas por dominio
```mermaid
flowchart LR
    subgraph Core["Exchange: pm.events (topic)"]
        direction TB
        QPM[pm.project_execution]
        QFIN[fin.time_logged]
        QBIL[billing.usage]
    end
    subgraph DLX["Dead-Letter Exchange: pm.dlx"]
        QDLX[*.dlq]
    end
    subgraph VIP["Colas prioritarias VIP"]
        QVIPFIN[fin.time_logged.vip<br/>x-max-priority=10]
        QVIPBIL[billing.usage.vip<br/>x-max-priority=10]
    end
    PUB["Publicadores<br/>(relay Outbox)"] --> Core
    Core --> QPM & QFIN & QBIL
    Core --> QVIPFIN & QVIPBIL
    QPM -. fallo .-> DLX
    QFIN -. fallo .-> DLX
    QBIL -. fallo .-> DLX
```

- **Exchange principal** `pm.events` tipo *topic*: *routing key* `pm.project_execution.task.closed`, `fin.time_logged.recorded`, `billing.usage.metered`.
- **Dead-Letter Exchange** `pm.dlx`: todo mensaje fallido (tras N reintentos) termina en su **DLQ** para inspección/reproceso, con `x-death` header para diagnóstico.
- **Colas prioritarias VIP:** `x-max-priority=10`; los *workers* VIP consumen primero los eventos de tenants VIP (ver ADR-0014).

### Declaración de colas (referencia)
```python
# apps/workers/src/topology.py
from faststream import RabbitBroker
from faststream.rabbit import RabbitExchange, RabbitQueue, ExchangeType

broker = RabbitBroker("amqp://guest:guest@rabbitmq:5672/")

pm_exchange = RabbitExchange("pm.events", type=ExchangeType.TOPIC, durable=True)
dlx_exchange = RabbitExchange("pm.dlx", type=ExchangeType.TOPIC, durable=True)

# Cola normal con DLX
fin_queue = RabbitQueue(
    "fin.time_logged",
    durable=True,
    routing_key="fin.time_logged.*",
    arguments={
        "x-dead-letter-exchange": "pm.dlx",
        "x-dead-letter-routing-key": "fin.time_logged.dead",
    },
)

# Cola prioritaria VIP
fin_vip_queue = RabbitQueue(
    "fin.time_logged.vip",
    durable=True,
    routing_key="fin.time_logged.vip.*",
    arguments={
        "x-max-priority": 10,
        "x-dead-letter-exchange": "pm.dlx",
        "x-dead-letter-routing-key": "fin.time_logged.vip.dead",
    },
)
```

## 2. Contratos de eventos (AsyncAPI + Pydantic)

Los eventos se definen una sola vez en **AsyncAPI** (`libs/api-contracts`), y el *codegen* genera los *schemas* Pydantic consumidos por **FastStream** (ADR-0003). Esto garantiza productor↔consumidor tipados.

```python
# libs/api-contracts/gen/fin_events.py  (generado, referencia de uso)
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field


class TimeLoggedEvent(BaseModel):
    event_id: UUID
    tenant_id: UUID
    tier: str = Field(pattern="^(starter|growth|enterprise|vip)$")
    user_id: UUID
    project_id: UUID
    task_id: UUID
    hours: Decimal = Field(gt=0, max_digits=5, decimal_places=2)
    role_cost_per_hour: Decimal
    evidence: str  # 'manual' | 'timer' | 'git:commit' | 'git:pr'
    occurred_at: datetime
```

```python
# apps/workers/src/subscribers/fin_subscriber.py
from faststream import RabbitRouter
from .topology import broker, pm_exchange, fin_queue, fin_vip_queue
from gen.fin_events import TimeLoggedEvent

router = RabbitRouter()


@router.subscriber(fin_queue, pm_exchange)
async def on_time_logged(msg: TimeLoggedEvent) -> None:
    # Idempotencia + actualización de proyección de margen (ver §4 y archivo 06)
    await handle_time_logged(msg, is_vip=False)


@router.subscriber(fin_vip_queue, pm_exchange)
async def on_time_logged_vip(msg: TimeLoggedEvent) -> None:
    await handle_time_logged(msg, is_vip=True)
```

## 3. Outbox Pattern (doble escritura segura)

Publicar un evento **y** mutar la BBDD en dos pasos rompe atomicidad: si el *publish* falla, el evento se pierde; si la mutación falla, se publica un evento fantasma. El **Outbox** resuelve esto escribiendo el evento en una **tabla `outbox` dentro de la misma transacción** del cambio de dominio; un proceso **relay** lo publica al broker y lo marca como enviado.

```sql
CREATE TABLE outbox (
    id           BIGSERIAL PRIMARY KEY,
    aggregate    TEXT NOT NULL,            -- 'financial_ledger'
    aggregate_id UUID NOT NULL,
    event_type   TEXT NOT NULL,            -- 'fin.time_logged.recorded'
    payload      JSONB NOT NULL,
    headers      JSONB NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ
);
CREATE INDEX idx_outbox_unpublished ON outbox (created_at) WHERE published_at IS NULL;
```

```python
# apps/backend/src/shared/outbox/relay.py
import asyncio, json
from datetime import datetime, UTC

POLL_INTERVAL = 0.2
BATCH = 200

async def run_outbox_relay(db, publisher) -> None:
    while True:
        async with db.begin():
            rows = await db.fetch(
                """SELECT id, event_type, payload, headers
                     FROM outbox
                    WHERE published_at IS NULL
                    ORDER BY id
                    LIMIT $1 FOR UPDATE SKIP LOCKED""", BATCH)
            for r in rows:
                await publisher.publish(
                    payload=json.loads(r["payload"]),
                    routing_key=r["event_type"],
                    headers=json.loads(r["headers"]),
                )
                await db.execute(
                    "UPDATE outbox SET published_at = $1 WHERE id = $2",
                    datetime.now(UTC), r["id"])
        await asyncio.sleep(POLL_INTERVAL)
```

> `FOR UPDATE SKIP LOCKED` permite múltiples *relay workers* en paralelo sin contender. El *ordering* causal por tenant se preserva con una cola/partición por `aggregate_id` (ver §6).

## 4. Idempotencia (no duplicar cargos)

La red entrega mensajes **al menos una vez**; los reintentos y redespachos son inevitables. Cada handler verifica un **event_id procesado** antes de actuar. Esto es **crítico en billing/metering**: procesar dos veces el mismo `billing.usage.metered` duplica el cargo.

```sql
CREATE TABLE processed_events (
    event_id    UUID PRIMARY KEY,
    consumer    TEXT NOT NULL,          -- 'fin.margin_projection'
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (event_id, consumer)
);
```

```python
# apps/workers/src/shared/idempotency.py
async def run_idempotent(tx, event_id: UUID, consumer: str, handler):
    inserted = await tx.execute(
        "INSERT INTO processed_events (event_id, consumer) VALUES ($1, $2) "
        "ON CONFLICT DO NOTHING", event_id, consumer)
    if inserted == "INSERT 0 0":
        return  # ya procesado -> descartar duplicado
    await handler(tx)
```

### Idempotency-Key en HTTP (cliente→API)
Para operaciones de cliente que deben ser exactamente una vez (p. ej. "cobrar/confirmar"), se exige la cabecera `Idempotency-Key`; el servidor la guarda con el resultado y lo devuelve en reintentos:

```python
# apps/backend/src/shared/idempotency/http.py
from fastapi import Header, HTTPException

async def idempotency_key(x_idempotency_key: str | None = Header(None)) -> str:
    if not x_idempotency_key:
        raise HTTPException(422, "idempotency_key.required")
    return x_idempotency_key
```

## 5. Saga Pattern (orchestration)

Los flujos multi-servicio que requieren consistencia (p. ej. facturación: medir uso → generar factura → cobrar → activar/desactivar recursos) se coordinan con **Saga por *orchestration***: un *orchestrator* emite comandos, escucha resultados y ejecuta **compensaciones** ante fallos. Se prefiere *orchestration* sobre *choreography* porque el flujo de billing es centralizado, auditable y con compensaciones claras.

### Saga de billing (diagrama de secuencia)
```mermaid
sequenceDiagram
    participant C as Cron/Trigger
    participant ORC as BillingOrchestrator
    participant MET as Metering (OpenMeter)
    participant STR as Stripe
    participant LED as Financial Ledger
    participant NOT as Notifications
    C->>ORC: start billing cycle (tenant)
    ORC->>MET: fetch aggregated usage (window)
    MET-->>ORC: usage totals
    ORC->>LED: append InvoiceIssued (ES)
    ORC->>STR: create invoice + charge
    alt charge OK
        STR-->>ORC: paid
        ORC->>LED: append PaymentSettled
        ORC->>NOT: invoice.paid
    else charge fails
        STR-->>ORC: declined
        ORC->>LED: append PaymentFailed
        ORC->>NOT: invoice.failed (retry/compensate)
        ORC->>ORC: schedule retry / dunning
    end
```

### Esqueleto del orquestador
```python
# apps/workers/src/billing/orchestrator.py
from enum import Enum, auto

class BillingStep(Enum):
    FETCH_USAGE = auto(); PERSIST_INVOICE = auto(); CHARGE = auto(); SETTLE = auto()


async def orchestrate_billing(tenant_id, window, services):
    s = services
    usage = await s.metering.fetch_usage(tenant_id, window)        # FETCH_USAGE
    await s.ledger.append_invoice_issued(tenant_id, usage)          # PERSIST_INVOICE
    result = await s.stripe.charge(tenant_id, usage.total)          # CHARGE
    if result.ok:
        await s.ledger.append_payment_settled(tenant_id, result.id)  # SETTLE
        await s.notifications.notify("invoice.paid", tenant_id)
    else:
        await s.ledger.append_payment_failed(tenant_id, result.reason)
        await s.dunning.schedule_retry(tenant_id)                   # COMPENSACIÓN
```

> El estado de la saga se **persiste** (máquina de estados por `tenant_id`+`cycle`), de modo que un *crash* del *worker* reanuda desde el último paso confirmado, sin duplicar el cargo (gracias a la idempotencia de §4).

## 6. Orden y particionado causal

El orden causal **por agregado** (p. ej. los eventos de un mismo contrato financiero) se preserva enrutando por *routing key* que incluye el `aggregate_id`, de forma que el mismo *consumer* (cola particionada) procesa la secuencia. Entre agregados distintos no se requiere orden global.

## 7. Observabilidad de la mensajería
Todo mensaje lleva en `headers` el `trace_id` (W3C) y `tenant_id`, propagado por FastStream. Métricas clave (ver `12`): `rabbitmq.queue.depth`, `outbox.lag_seconds`, `consumer.dlq.messages`, `saga.step.duration`. El detalle del *time tracking* —el productor de eventos más voluminoso— se trata en `06`.
