from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Bot
    bot_token: str

    # PostgreSQL
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_user: str
    postgres_password: str
    postgres_db: str

    # Admin
    admin_telegram_id: int

    # GigaChat
    gigachat_client_id: str = ""
    gigachat_auth_key: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        """Для Alembic — синхронный драйвер."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
