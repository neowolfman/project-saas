import asyncio
import pytest
from db_clients.session import _engines_registry


@pytest.fixture(scope="session")
def event_loop():
    """Crea un event loop de asyncio único para toda la sesión de pruebas."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def cleanup_database_engines():
    """Cierra y desecha de forma limpia todos los motores de base de datos de SQLAlchemy al finalizar."""
    yield
    for engine in list(_engines_registry.values()):
        await engine.dispose()
    _engines_registry.clear()
