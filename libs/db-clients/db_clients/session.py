import contextvars
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any
from uuid import UUID
from sqlalchemy import event, text
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine

# Variables de contexto asíncronas para el Tenant ID, esquema y DSN dinámico
_tenant_id_var: contextvars.ContextVar[UUID | None] = contextvars.ContextVar("tenant_id", default=None)
_schema_name_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("schema_name", default=None)
_tenant_dsn_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("tenant_dsn", default=None)

# Registro global para reutilizar motores de base de datos (connection pools)
_engines_registry: dict[str, AsyncEngine] = {}

# Cache en memoria para la metadata de inquilinos (tier, db_target)
_tenant_metadata_cache: dict[UUID, dict[str, Any]] = {}


async def get_tenant_metadata(tenant_id: UUID, default_engine: AsyncEngine) -> dict[str, Any]:
    """Obtiene y cachea la metadata de un inquilino desde la base de datos compartida."""
    if tenant_id not in _tenant_metadata_cache:
        # Usamos una conexión directa para evitar interferir con transacciones activas de la app
        async with default_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT tier, db_target FROM tenants WHERE tenant_id = :tenant_id"),
                {"tenant_id": tenant_id},
            )
            row = result.fetchone()
            if row:
                _tenant_metadata_cache[tenant_id] = {
                    "tier": row[0],
                    "db_target": row[1],
                }
            else:
                _tenant_metadata_cache[tenant_id] = {
                    "tier": "starter",
                    "db_target": "shared",
                }
    return _tenant_metadata_cache[tenant_id]


def set_current_tenant(
    tenant_id: UUID | None,
    schema_name: str | None = None,
    tenant_dsn: str | None = None,
) -> None:
    """Establece las variables de contexto para el tenant, esquema y DSN actual."""
    _tenant_id_var.set(tenant_id)
    _schema_name_var.set(schema_name)
    _tenant_dsn_var.set(tenant_dsn)


def get_current_tenant_id() -> UUID | None:
    """Retorna el ID del tenant en el contexto actual."""
    return _tenant_id_var.get()


def get_current_schema_name() -> str | None:
    """Retorna el nombre del esquema en el contexto actual."""
    return _schema_name_var.get()


def get_current_tenant_dsn() -> str | None:
    """Retorna la URL de conexión (DSN) del tenant en el contexto actual."""
    return _tenant_dsn_var.get()


@asynccontextmanager
async def tenant_context(
    tenant_id: UUID,
    schema_name: str | None = None,
    tenant_dsn: str | None = None,
) -> AsyncGenerator[None, None]:
    """Context manager asíncrono para definir el tenant de forma segura durante un bloque de ejecución."""
    resolved_schema = schema_name
    resolved_dsn = tenant_dsn

    # Si no se especificó esquema/DSN, intentar resolverlos dinámicamente usando el default_engine
    if tenant_id and not resolved_schema and not resolved_dsn:
        shared_engine = None
        # Recuperamos el primer motor del registro global (que es el compartido / base de datos por defecto)
        for engine in _engines_registry.values():
            shared_engine = engine
            break

        if shared_engine:
            try:
                metadata = await get_tenant_metadata(tenant_id, shared_engine)
                db_target = metadata.get("db_target", "shared")
                if db_target.startswith("schema:"):
                    resolved_schema = db_target.split(":", 1)[1]
                elif db_target.startswith("db:"):
                    db_name = db_target.split(":", 1)[1]
                    # Construir el DSN específico reemplazando la base de datos en la URL base sin ocultar el password
                    resolved_dsn = shared_engine.url.set(database=db_name).render_as_string(hide_password=False)
            except Exception as e:
                import traceback
                print(f"DEBUG tenant_context error resolving metadata: {e}")
                traceback.print_exc()

    t_token = _tenant_id_var.set(tenant_id)
    s_token = _schema_name_var.set(resolved_schema)
    d_token = _tenant_dsn_var.set(resolved_dsn)
    try:
        yield
    finally:
        _tenant_id_var.reset(t_token)
        _schema_name_var.reset(s_token)
        _tenant_dsn_var.reset(d_token)


def get_engine(database_url: str) -> AsyncEngine:
    """Retorna un motor de base de datos asíncrono, reutilizando pools existentes."""
    if database_url not in _engines_registry:
        # Configuración del pool optimizada para PostgreSQL
        _engines_registry[database_url] = create_async_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            pool_recycle=1800,
        )
    return _engines_registry[database_url]


# Listener de evento para inyectar variables de RLS y search_path en la sesión de base de datos
@event.listens_for(Session, "after_begin")
def set_tenant_context_in_database(session: Session, transaction: Any, connection: Any) -> None:
    """
    Se ejecuta al iniciar cada transacción en PostgreSQL.
    Configura la variable de sesión `app.current_tenant` para aplicar RLS,
    y cambia el `search_path` si el tenant utiliza un esquema dedicado.
    """
    tenant_id = get_current_tenant_id()
    schema_name = get_current_schema_name()
    print(f"DEBUG Event: tenant_id={tenant_id}, schema_name={schema_name}")

    # 1. Configurar tenant en app.current_tenant (RLS)
    if tenant_id is not None:
        connection.execute(
            text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )

    # 2. Configurar search_path para esquemas aislados
    if schema_name is not None:
        clean_schema = "".join(c for c in schema_name if c.isalnum() or c == "_")
        connection.execute(text(f'SET LOCAL search_path TO "{clean_schema}", public'))
        res = connection.execute(text("SHOW search_path")).fetchone()
        print(f"DEBUG Event search_path check: {res[0]}")


class DynamicSessionMaker:
    """Clase factoría que emula async_sessionmaker pero resuelve el binding dinámicamente por request/contexto."""
    def __init__(self, default_engine: AsyncEngine) -> None:
        self.default_engine = default_engine

    def __call__(self, **kwargs: Any) -> AsyncSession:
        dsn = get_current_tenant_dsn()
        if dsn:
            engine = get_engine(dsn)
        else:
            engine = self.default_engine

        return AsyncSession(
            bind=engine,
            expire_on_commit=False,
            **kwargs,
        )


def create_session_factory(database_url: str) -> Any:
    """Crea una factoría de sesiones asíncronas dinámica para el DSN provisto."""
    engine = get_engine(database_url)
    return DynamicSessionMaker(engine)

