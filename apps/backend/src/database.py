from apps.backend.src.config import settings
from db_clients.session import create_session_factory

# Factoría de sesión asíncrona global utilizando el DSN del rol app_api
api_session_factory = create_session_factory(settings.db_url)
