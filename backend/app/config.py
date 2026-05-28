from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    database_url: str = "sqlite:///./shop.db"

    jwt_secret: str = "dev-only-change-me-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_ttl_minutes: int = 60 * 24 * 7  # 7 дней

    tg_bot_token: str | None = None


settings = Settings()
