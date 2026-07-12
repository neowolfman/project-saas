"""Alembic environment.

Migraciones con SQL en crudo (op.execute) sobre el motor sincrónico psycopg3.
La URL se toma de DATABASE_URL (inyectada por docker-compose / CI); si no está
presente, se usa el valor por defecto de alembic.ini.

Soporta multi-tenancy híbrido: la misma migración puede aplicarse al esquema
compartido (Starter/Growth) o iterarse por schema/BBDD dedicadas mediante el
runner tenant-aware (ver SAD archivo 02, §7).
"""
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# La URL de BBDD es configurable por entorno (docker-compose / CI), excepto si se define programáticamente.
is_programmatic = config.get_main_option("is_programmatic") == "true"
db_url = os.getenv("DATABASE_URL")
if db_url and not is_programmatic:
    config.set_main_option("sqlalchemy.url", db_url)

# Las migraciones son SQL en crudo (sin SQLAlchemy ORM models autogenerados).
target_metadata = None


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    schema_name = config.get_main_option("version_table_schema")
    context.configure(
        url=url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema=schema_name,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    print(f"DEBUG ALembic URL: {config.get_main_option('sqlalchemy.url')}")
    print(f"DEBUG Alembic Schema: {config.get_main_option('version_table_schema')}")
    print(f"DEBUG Alembic Programmatic: {config.get_main_option('is_programmatic')}")
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    schema_name = config.get_main_option("version_table_schema")

    with connectable.connect() as connection:
        if schema_name:
            from sqlalchemy import text
            # Forzar el search_path para esta ejecución de migración, incluyendo public para resolver extensiones
            connection.execute(text(f'SET search_path TO "{schema_name}", public'))
        
        from sqlalchemy import text
        db_info = connection.execute(text("SELECT current_database(), current_schema(), current_user, current_setting('search_path')")).fetchone()
        print(f"DEBUG Alembic Connection Info: Database={db_info[0]}, Schema={db_info[1]}, User={db_info[2]}, SearchPath={db_info[3]}")
        
        context.configure(connection=connection, version_table_schema=schema_name)
        with context.begin_transaction():
            context.run_migrations()
        connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
