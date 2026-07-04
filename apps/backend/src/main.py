import asyncio
from contextlib import asynccontextmanager, suppress

from apps.backend.src.config import settings
from apps.backend.src.database import api_session_factory
from apps.backend.src.middleware.tenant import TenantContextMiddleware
from apps.backend.src.routers import auth, financial_contracts, projects, tasks, time_logs, webhooks
from apps.backend.src.shared.outbox.relay import run_outbox_relay
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from faststream.rabbit import RabbitBroker
from sqlalchemy import text

broker = RabbitBroker(settings.rabbitmq_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Conectar al broker de RabbitMQ
    await broker.connect()
    # Iniciar la tarea de background de Outbox Relay
    relay_task = asyncio.create_task(run_outbox_relay(api_session_factory, broker))
    yield
    # Apagar la tarea de background y cerrar la conexión del broker
    relay_task.cancel()
    with suppress(asyncio.CancelledError):
        await relay_task
    await broker.close()


app = FastAPI(
    title="SaaS PM+FinOps Backend API",
    description="API Core para la plataforma de Gestión de Proyectos y Finanzas Multi-Tenant",
    version="1.0.0",
    lifespan=lifespan,
)

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar el middleware de aislamiento por Tenant (RLS)
app.add_middleware(TenantContextMiddleware)

# Registrar ruta de test de RLS antes del router de proyectos para evitar conflictos de ruteo
@app.get("/projects/test")
async def test_rls_projects() -> list[dict[str, str]]:
    """Ruta de prueba protegida por RLS.

    Solo retornará los proyectos del tenant activo en la sesión (contexto RLS).
    """
    try:
        async with api_session_factory() as session:
            result = await session.execute(text("SELECT project_id, name, status FROM projects"))
            rows = result.fetchall()
            return [
                {"project_id": str(row[0]), "name": row[1], "status": row[2]}
                for row in rows
            ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error consultando proyectos: {e}",
        ) from e


# Registrar Routers
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(time_logs.router)
app.include_router(financial_contracts.router)
app.include_router(webhooks.router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Chequeo básico de salud del servicio backend y la base de datos."""
    try:
        async with api_session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "detail": str(e)}
    else:
        return {"status": "healthy", "database": "connected"}
