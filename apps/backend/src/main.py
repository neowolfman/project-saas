import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from apps.backend.src.config import settings
from apps.backend.src.database import api_session_factory
from apps.backend.src.middleware.tenant import TenantContextMiddleware
from apps.backend.src.routers import auth, financial_contracts, projects, tasks, time_logs, webhooks
from apps.backend.src.shared.outbox.relay import run_outbox_relay
from apps.backend.src.shared.observability import configure_logging, W3CTracingMiddleware, setup_metrics
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from faststream.rabbit import RabbitBroker
from sqlalchemy import text

# Inicializar logging estructurado JSON al arrancar el módulo
configure_logging(level=settings.LOG_LEVEL)
logger = logging.getLogger("saas.backend")

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

# Configuración de CORS — única fuente de verdad para orígenes permitidos.
# Traefik NO aplica cors-default en el router del backend para evitar headers duplicados.
ALLOWED_ORIGINS = [
    "http://localhost:3000",  # app (dashboard)
    "http://localhost:3001",  # landing
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Tenant-ID", "X-Request-ID"],
)

# Registrar el middleware de trazado W3C (debe ir primero para capturar toda la request)
app.add_middleware(W3CTracingMiddleware)

# Registrar el middleware de aislamiento por Tenant (RLS)
app.add_middleware(TenantContextMiddleware)

# Montar el endpoint /metrics para Prometheus
setup_metrics(app)

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
    except Exception:
        logger.exception("Error consultando proyectos en ruta de test RLS")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# Registrar Routers
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(time_logs.router)
app.include_router(financial_contracts.router)
app.include_router(webhooks.router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Chequeo de salud del servicio backend y la base de datos.

    Retorna HTTP 503 si la base de datos no responde, para que Docker/Traefik
    marquen el contenedor como unhealthy y retiran el tráfico.
    """
    try:
        async with api_session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Healthcheck: la base de datos no responde")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database disconnected",
        )
    return {"status": "healthy", "database": "connected"}
