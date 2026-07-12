from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "saas"
    POSTGRES_USER: str = "app_api"
    APP_API_PASSWORD: str = "change_me_strong_app_api_password"

    # DSN alternativo completo que sobrescribe los parámetros individuales
    API_DATABASE_URL: str | None = None

    JWT_SECRET: str = "change_me_to_a_very_secure_random_key_in_production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 horas
    GIT_WEBHOOK_SECRET: str = "change_me_git_webhook_secret_in_production"

    RABBITMQ_HOST: str = "rabbitmq"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASSWORD: str = "change_me_rabbitmq_password"

    @property
    def rabbitmq_url(self) -> str:
        """Retorna la URL de conexión para RabbitMQ."""
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/"

    ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    @property
    def db_url(self) -> str:
        """Retorna el DSN asíncrono para conectarse con asyncpg bajo el rol restringido app_api."""
        if self.API_DATABASE_URL:
            # Si ya tiene el driver asíncrono, lo retorna. Si no, lo adaptamos.
            url = self.API_DATABASE_URL
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql+psycopg://"):
                url = url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
            return url
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.APP_API_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
