from apps.backend.src.database import api_session_factory
from apps.backend.src.middleware.tenant import TenantContextMiddleware
from apps.backend.src.routers import auth
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

app = FastAPI(
    title="SaaS PM+FinOps Backend API",
    description="API Core para la plataforma de Gestión de Proyectos y Finanzas Multi-Tenant",
    version="1.0.0",
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

# Registrar Routers
app.include_router(auth.router)


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
