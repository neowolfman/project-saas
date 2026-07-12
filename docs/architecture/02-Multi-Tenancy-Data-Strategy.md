# 02 — Multi-Tenancy y Estrategia de Datos

> Especificación original: **§2.1**. Decisiones: **ADR-0005** (multi-tenancy híbrida). Relacionado: `04` (dominio), `10` (infraestructura), `03` (RBAC por tenant).

## 1. Requisitos de aislamiento

La plataforma debe servir simultáneamente a:
- **Starter/Growth:** cientos de tenants pequeños, sensibles al costo, tolerantes a compartir infraestructura.
- **Enterprise:** tenants medianos/grandes con exigencias regulatorias y SLA, pero sin justificar una BBDD física dedicada.
- **VIP/Custom:** pocos tenants de alto valor, con requisitos de aislamiento físico, retención extendida y rendimiento garantizado (recursos VIP, ADR-0014).

Ninguna estrategia única de multi-tenancy optimiza los tres casos. De ahí la decisión de **híbrida**.

## 2. Matriz comparativa de las 4 estrategias

| Estrategia | Costo | Aislamiento | Operación | Escala | ¿Cuándo aplica? |
|---|---|---|---|---|---|
| **Shared DB / Shared Schema** (discriminador `tenant_id`) | Mínimo | Bajo (lógico) | Sencilla (1 migración) | Alta (hasta miles de tenants) | Starter/Growth |
| **Shared DB / Isolated Schema** (un *schema* PG por tenant) | Bajo–Medio | Medio | Media (N *schemas*) | Media | Enterprise (sin dedicada) |
| **Isolated DB** (BBDD física por tenant) | Alto | Máximo | Compleja (N BBDD, N backups) | Baja (decenas) | VIP/Custom |
| **Híbrida** (combinación gobernada por tier) | Óptimo | Proporcional al tier | Media–Compleja | Alta + VIP | **Decisión adoptada** |

### Criterios de evaluación usados
- **Costo:** recursos compartidos vs. dedicados (conexiones, almacenamiento, cómputo).
- **Aislamiento:** riesgo de fuga de datos entre tenants (*noisy neighbor* y exposición).
- **Operación:** esfuerzo de migraciones, backups y monitoreo a escala.
- **Escala:** número de tenants soportable sin rediseño.

## 3. Arquitectura híbrida adoptada (ADR-0005)

```mermaid
flowchart TB
    REQ["Request HTTP<br/>Host: acme.app.com + Header X-Tenant-Id"] --> MW["TenantContextMiddleware"]
    MW --> R["TenantResolver<br/>(subdominio → tenant)"]
    R --> LOOKUP{Tier?}
    LOOKUP -->|Starter / Growth| SHARED["Shared Schema<br/>(discriminador tenant_id)"]
    LOOKUP -->|Enterprise / VIP| POOL["Dynamic Connection Pool"]
    POOL -->|Enterprise| DEDSCHEMA["Shared DB / Isolated Schema"]
    POOL -->|VIP| DEDDB["Isolated DB física<br/>(+ read replicas)"]
```

- **Starter / Growth:** `tenant_id` en cada fila; filtros automáticos a nivel de sesión/repositorio; un único *pool* compartido.
- **Enterprise:** *schema* aislado dentro de la misma BBDD gestionada (`tenant_acme`, `tenant_globex`); el *pool* enruta por *schema*.
- **VIP:** BBDD **física dedicada**, *pool* propio, réplicas de lectura y *workers* exclusivos; en Swarm, nodos dedicados (ADR-0014).

> La elección de destino **no es estática**: el *upgrade* de tier (p. ej. Enterprise→VIP) dispara un *tenant migration job* que mueve datos al nuevo destino sin downtime (ver §6).

## 4. Mecanismo de *routing*

Resolución **dual**: subdominio para humanos/SEO + cabecera para API/móvil (OQ-2 resuelta).

- **Navegador/landing:** `acme.app.com` → el subdominio identifica al tenant.
- **API/móvil/SSR server:** cabecera `X-Tenant-Id: <slug|uuid>`, obligatoria en todo endpoint autenticado.

El `TenantContextMiddleware` (FastAPI) valida la coincidencia **subdominio ↔ cabecera ↔ claim del JWT** y rechaza cualquier discrepancia (previene *cross-tenant access*). El contexto resultante se propaga vía `contextvars` a repositorios, trazas y logs.

```python
# apps/backend/src/shared/tenant/middleware.py
import re
from contextvars import ContextVar
from dataclasses import dataclass

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

tenant_ctx: ContextVar["TenantContext | None"] = ContextVar("tenant_ctx", default=None)
_SUBDOMAIN_RE = re.compile(r"^(?P<slug>[a-z0-9-]+)\.app\.com$")


@dataclass(frozen=True)
class TenantContext:
    tenant_id: str          # uuid
    slug: str               # acme
    tier: str               # starter | growth | enterprise | vip
    db_target: str          # shared | schema:<name> | db:<dsn_key>
    is_vip: bool


class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1) Resolver por subdominio
        host = request.headers.get("host", "")
        m = _SUBDOMAIN_RE.match(host)
        slug = m.group("slug") if m else None

        # 2) Cabecera X-Tenant-Id (autoritativa para API)
        header_tenant = request.headers.get("x-tenant-id")
        if header_tenant:
            slug = header_tenant

        if not slug:
            raise HTTPException(status_code=400, detail="tenant.not_resolved")

        # 3) Cargar metadata del tenant (L1 cache, ver archivo 11)
        registry = request.app.state.tenant_registry
        tenant = await registry.resolve(slug)
        if tenant is None:
            raise HTTPException(status_code=404, detail="tenant.not_found")

        # 4) Cruzar con el claim del JWT si la ruta está autenticada
        user = getattr(request.state, "user", None)
        if user is not None and user.tenant_id != tenant.tenant_id:
            # Prevención de cross-tenant access
            raise HTTPException(status_code=403, detail="tenant.mismatch")

        token = tenant_ctx.set(TenantContext(
            tenant_id=tenant.tenant_id,
            slug=tenant.slug,
            tier=tenant.tier,
            db_target=tenant.db_target,
            is_vip=(tenant.tier == "vip"),
        ))
        try:
            return await call_next(request)
        finally:
            tenant_ctx.reset(token)
```

## 5. *Connection pooling* dinámico

El motor de BBDD decide, en tiempo de ejecución, qué conexión usar según `tenant_ctx.db_target`. Para Starter/Growth se usa un *pool* compartido con aislamiento lógico; para VIP, un *pool* dedicado por BBDD.

```python
# apps/backend/src/shared/db/session.py
from sqlalchemy.ext.asyncio import (
    AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine,
)
from sqlalchemy import text
from .middleware import tenant_ctx

# Pool compartido (Starter/Growth) — shared schema
_shared_engine: AsyncEngine = create_async_engine(
    "postgresql+asyncpg://app:***@pg.shared:5432/saas",
    pool_size=20, max_overflow=40, pool_pre_ping=True,
)
_shared_sessions = async_sessionmaker(_shared_engine, expire_on_commit=False)

# Pools dedicados VIP — cargados bajo demanda y cacheados
_vip_engines: dict[str, AsyncEngine] = {}
_vip_sessions: dict[str, async_sessionmaker] = {}


def get_vip_session_maker(dsn_key: str) -> async_sessionmaker:
    if dsn_key not in _vip_engines:
        dsn = _resolve_dsn(dsn_key)  # desde Vault / config de tenant
        engine = create_async_engine(
            dsn, pool_size=10, max_overflow=20, pool_pre_ping=True,
        )
        _vip_engines[dsn_key] = engine
        _vip_sessions[dsn_key] = async_sessionmaker(engine, expire_on_commit=False)
    return _vip_sessions[dsn_key]


async def current_session() -> AsyncSession:
    """Abre una sesión SQLAlchemy adecuada al tenant en contexto."""
    ctx = tenant_ctx.get()
    if ctx is None:
        raise RuntimeError("tenant.context_missing")

    # VIP / DB dedicada: pool propio de la BBDD física del tenant
    if ctx.is_vip or ctx.db_target.startswith("db:"):
        dsn_key = ctx.db_target.split(":", 1)[1]
        return get_vip_session_maker(dsn_key)()

    session = _shared_sessions()

    # Enterprise: shared DB con schema aislado -> search_path en la MISMA
    # conexión de la sesión (SET LOCAL dura lo que dura la transacción).
    if ctx.db_target.startswith("schema:"):
        schema_name = ctx.db_target.split(":", 1)[1]
        await session.execute(text(f'SET LOCAL search_path TO "{schema_name}", public'))

    return session
```

> Los repositorios inyectan `current_session()` y operan de forma agnóstica al destino físico. Para Starter/Growth, un *Query Event* de SQLAlchemy inyecta automáticamente `WHERE tenant_id = :ctx_tenant_id` y un RLS (*Row-Level Security*) de PostgreSQL actúa como **cinturón de seguridad** ante errores de aplicación.

**Row-Level Security como red de protección (shared schema):**
```sql
-- Aplicado a toda tabla con tenant_id (migración Alembic)
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON projects
  USING (tenant_id = current_setting('app.current_tenant', true)::uuid);

-- La app establece la variable de sesión por request:
-- SET LOCAL app.current_tenant = '<uuid>';
```

## 6. Migraciones *zero-downtime*

Las migraciones de **esquema** (todos los tiers) siguen **expand/contract**, y los cambios disruptivos se despliegan en **dos releases** (blue-green por tenant):

1. **Expand:** añadir columnas/tablas nuevas opcionales; ambos lectores (viejo/nuevo) coexisten.
2. **Migrate (backfill):** poblar los nuevos campos de forma asíncrona por *batch* de tenants.
3. **Switch:** mover lectores/escritores a la nueva versión (código nuevo desplegado).
4. **Contract:** eliminar lo viejo solo cuando ningún lector lo usa.

Para **cambio de tier / cambio de destino físico** (p. ej. Enterprise→VIP), se ejecuta un *tenant migration job* que:
- crea el destino (BBDD/schema) y aplica migraciones pendientes;
- copia datos con **CDC** (replicación lógica de PG o *trigger*-based) mientras la app sigue escribiendo en el origen;
- alcanza *catch-up*, pausa escrituras del tenant < 1 s (write-lock corto) y conmuta `db_target` en el *tenant registry*;
- valida conteos y *checksums* y marca el origen como *deprecated*.

```mermaid
sequenceDiagram
    participant Sched as MigrationScheduler
    participant Src as Origen (shared)
    participant CDC as CDC/Replicación
    participant Dst as Destino (dedicado)
    participant Reg as TenantRegistry
    Sched->>Dst: 1) provisiona destino + Alembic
    Sched->>CDC: 2) inicia replicación origen→destino
    CDC-->>Dst: copia continua (catch-up)
    Sched->>Src: 3) write-lock corto (<1s)
    Sched->>Reg: 4) conmuta db_target → db:vip_acme
    Sched->>Dst: 5) valida checksums
    Sched->>Src: 6) marca origen deprecated
```

## 7. Migraciones de esquema (Alembic) con conciencia de multi-tenancy

- **Shared schema:** una sola migración aplica a la BBDD compartida.
- **Isolated schema:** Alembic itera sobre la lista de *schemas* activos y aplica el *upgrade* a cada uno de forma idempotente.
- **Isolated DB:** un *runner* paraleliza por BBDD dedicada, con reintentos y telemetría por tenant.

```python
# apps/backend/migrations/tenant_aware_runner.py (esquema)
import asyncio
from alembic.config import Config
from alembic import command

async def upgrade_all_tenants(tenants: list[dict]) -> None:
    sem = asyncio.Semaphore(8)  # concurrencia acotada

    async def run(tenant: dict) -> None:
        async with sem:
            cfg = Config("alembic.ini")
            cfg.set_main_option("sqlalchemy.url", tenant["dsn"])
            cfg.set_main_option("version_table_schema", tenant.get("schema", "public"))
            # expand/contract: solo 'expand' en esta pasada
            await asyncio.to_thread(command.upgrade, cfg, "head")

    await asyncio.gather(*(run(t) for t in tenants))
```

## 8. Implicaciones operativas

- **Backups y PITR (ADR-0014/PITR):** la BBDD compartida tiene un PITR único; cada BBDD VIP tiene su propio PITR y retención extendida (RPO más agresivo). Ver `10`.
- **Observabilidad:** toda métrica/log lleva `tenant_id` y `tier` para detectar *noisy neighbor* (ver `12`).
- **Caché invalidada por tenant:** ver `11`.
- **Pruebas de aislamiento:** suite obligatoria que verifica, por cada endpoint, que un token de tenant A no accede datos de tenant B (ver `13`).

El modelo de datos subyacente a esta estrategia se detalla en `diagrams/erd-core.mmd` y el mapeo dominio→tablas en `04`.
