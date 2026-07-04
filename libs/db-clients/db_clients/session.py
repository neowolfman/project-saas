import contextvars
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any
from uuid import UUID
from sqlalchemy import event, text
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine

# Variables de contexto asíncronas para el Tenant ID y el esquema actual
_tenant_id_var: contextvars.ContextVar[UUID | None] = contextvars.ContextVar("tenant_id", default=None)
_schema_name_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("schema_name", default=None)

# Registro global para reutilizar motores de base de datos (connection pools)
_engines_registry: dict[str, AsyncEngine] = {}


def set_current_tenant(tenant_id: UUID | None, schema_name: str | None = None) -> None:
    """Establece las variables de contexto para el tenant y esquema actual."""
    _tenant_id_var.set(tenant_id)
    _schema_name_var.set(schema_name)


def get_current_tenant_id() -> UUID | None:
    """Retorna el ID del tenant en el contexto actual."""
    return _tenant_id_var.get()


def get_current_schema_name() -> str | None:
    """Retorna el nombre del esquema en el contexto actual."""
    return _schema_name_var.get()


@asynccontextmanager
async def tenant_context(tenant_id: UUID, schema_name: str | None = None) -> AsyncGenerator[None, None]:
    """Context manager asíncrono para definir el tenant de forma segura durante un bloque de ejecución."""
    t_token = _tenant_id_var.set(tenant_id)
    s_token = _schema_name_var.set(schema_name)
    try:
        yield
    finally:
        _tenant_id_var.reset(t_token)
        _schema_name_var.reset(s_token)


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


def create_session_factory(database_url: str) -> async_sessionmaker[AsyncSession]:
    """Crea una factoría de sesiones asíncronas para el DSN provisto."""
    engine = get_engine(database_url)
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
