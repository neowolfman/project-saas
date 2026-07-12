import os
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from apps.backend.src.shared.tenant.provisioning import run_alembic_upgrade


async def migrate_all_tenants() -> None:
    """Ejecuta las migraciones de Alembic en todos los esquemas y bases de datos aisladas de los tenants."""
    print("Iniciando migración multi-tenant...")

    # Obtener el DSN base / admin
    admin_url = os.getenv("DATABASE_URL")
    if not admin_url:
        admin_url = "postgresql+asyncpg://app:change_me_strong_pg_password@postgres:5432/saas"

    # Forzar asyncpg
    if admin_url.startswith("postgresql://"):
        admin_url = admin_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif admin_url.startswith("postgresql+psycopg://"):
        admin_url = admin_url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)

    # 1. Consultar todos los tenants registrados
    engine = create_async_engine(admin_url)
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT tenant_id, name, db_target FROM tenants"))
        tenants = result.fetchall()
    await engine.dispose()

    if not tenants:
        print("No se encontraron inquilinos (tenants) registrados.")
        return

    from sqlalchemy.engine.url import make_url
    url_obj = make_url(admin_url)

    for tenant_id, name, db_target in tenants:
        print(f"Procesando tenant '{name}' ({tenant_id}) - db_target: '{db_target}'")

        if db_target == "shared":
            # El esquema compartido se migra directamente ejecutando alembic normal sobre la DB saas
            print(f"-> Tenant '{name}' usa el esquema compartido. Saltando (ya migrado).")
            continue

        elif db_target.startswith("schema:"):
            schema_name = db_target.split(":", 1)[1]
            print(f"-> Migrando esquema '{schema_name}' en la base de datos compartida...")
            try:
                run_alembic_upgrade(admin_url, schema_name=schema_name)
                print(f"-> Migración del esquema '{schema_name}' completada con éxito.")
            except Exception as e:
                print(f"ERROR migrando el esquema '{schema_name}' para el tenant '{name}': {e}")

        elif db_target.startswith("db:"):
            db_name = db_target.split(":", 1)[1]
            print(f"-> Migrando base de datos física '{db_name}'...")
            try:
                # Construir el DSN administrativo para la base de datos física del tenant sin ocultar el password
                tenant_admin_dsn = url_obj.set(database=db_name).render_as_string(hide_password=False)
                run_alembic_upgrade(tenant_admin_dsn)
                print(f"-> Migración de la base de datos física '{db_name}' completada con éxito.")
            except Exception as e:
                print(f"ERROR migrando la base de datos física '{db_name}' para el tenant '{name}': {e}")

    print("Migración de inquilinos completada.")


if __name__ == "__main__":
    asyncio.run(migrate_all_tenants())
