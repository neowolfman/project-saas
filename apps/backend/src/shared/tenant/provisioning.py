import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from alembic.config import Config
from alembic import command


async def provision_vip_db(db_name: str) -> None:
    """Crea la base de datos física para el inquilino VIP si no existe y concede privilegios."""
    # Intentar obtener la URL administrativa (superuser 'app')
    admin_url = os.getenv("DATABASE_URL")
    if not admin_url:
        # Fallback en caso de que no esté definida (ej. ejecución fuera de dev-runner)
        admin_url = "postgresql+asyncpg://app:change_me_strong_pg_password@postgres:5432/postgres"

    # Forzar driver asyncpg si es necesario
    if admin_url.startswith("postgresql://"):
        admin_url = admin_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif admin_url.startswith("postgresql+psycopg://"):
        admin_url = admin_url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)

    # Conectarse a la base de datos 'postgres' por defecto para poder crear/eliminar bases de datos
    # Reemplazar la base de datos en la URL base de forma robusta
    from sqlalchemy.engine.url import make_url
    url_obj = make_url(admin_url)
    admin_base_url = url_obj.set(database="postgres").render_as_string(hide_password=False)

    engine = create_async_engine(admin_base_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        # Verificar si la base de datos ya existe
        result = await conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'"))
        if not result.fetchone():
            await conn.execute(text(f"CREATE DATABASE {db_name}"))

    await engine.dispose()

    # Conectarse a la nueva base de datos para configurar permisos
    new_db_url = url_obj.set(database=db_name).render_as_string(hide_password=False)
    engine_new = create_async_engine(new_db_url)
    async with engine_new.begin() as conn_new:
        # Otorgar privilegios de conexión y acceso a la base de datos para el rol restringido 'app_api'
        await conn_new.execute(text(f"GRANT CONNECT ON DATABASE {db_name} TO app_api"))
        await conn_new.execute(text("GRANT ALL PRIVILEGES ON SCHEMA public TO app_api"))
        await conn_new.execute(text("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO app_api"))
        await conn_new.execute(text("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO app_api"))

    await engine_new.dispose()


def run_alembic_upgrade(dsn: str, schema_name: str | None = None) -> None:
    """Ejecuta programáticamente las migraciones de Alembic en un DSN y esquema específico."""
    # Convertir DSN asíncrono a síncrono para Alembic/psycopg
    sync_dsn = dsn
    if sync_dsn.startswith("postgresql+asyncpg://"):
        sync_dsn = sync_dsn.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)

    cfg = Config("/app/apps/backend/migrations/alembic.ini")
    cfg.set_main_option("script_location", "/app/apps/backend/migrations")
    cfg.set_main_option("sqlalchemy.url", sync_dsn)
    cfg.set_main_option("is_programmatic", "true")
    if schema_name:
        cfg.set_main_option("version_table_schema", schema_name)

    command.upgrade(cfg, "head")
