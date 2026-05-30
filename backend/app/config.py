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
    # CDEK API (пункты выдачи). По умолчанию — тестовая среда с публичными тест-ключами.
    cdek_api_url: str = "https://api.edu.cdek.ru/v2"
    cdek_account: str = "wqGwiQx0gg8mLtiEKsUinjVSICCjtTEP"
    cdek_secret: str = "RmAmgvSgSl1yirlz9QupbzOJVqhCxcP5"
    # HTTPS-ссылка на мини-аппу (кнопка «Открыть магазин» в боте + регистрация в BotFather).
    # Локально задаётся в .env адресом туннеля, напр. https://abc.trycloudflare.com/static/tg/index.html
    webapp_url: str = "https://example.com/static/tg/index.html"
    # Куда слать уведомление админу о новом заказе (tg_id). Пусто — не слать.
    admin_tg_id: int | None = None
    # Боевой домен (для webhook бота и URL мини-аппы). На Render берётся
    # автоматически из RENDER_EXTERNAL_URL; локально можно задать PUBLIC_URL.
    public_url: str = ""
    render_external_url: str = ""
    tg_webhook_secret: str = "stride-hook"

    # SMTP для писем (подтверждение e-mail). Если smtp_host пуст — письма
    # не отправляются по-настоящему, а логируются в консоль (demo-режим).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "Stride Shop <no-reply@stride.shop>"
    smtp_tls: bool = True

    # ЮKassa (тестовый магазин). Пусто — оплата работает в режиме заглушки.
    yookassa_shop_id: str = ""
    yookassa_secret_key: str = ""

    @property
    def base_url(self) -> str:
        return (self.public_url or self.render_external_url or "").rstrip("/")

    @property
    def site_url(self) -> str:
        """Базовый URL сайта для ссылок в письмах. Локально — адрес uvicorn."""
        return self.base_url or f"http://{self.app_host}:{self.app_port}"

    @property
    def mini_app_url(self) -> str:
        """URL мини-аппы: явный webapp_url, иначе — собранный с боевого домена."""
        if self.webapp_url and "example.com" not in self.webapp_url:
            return self.webapp_url
        if self.base_url:
            return self.base_url + "/static/tg/index.html"
        return self.webapp_url


settings = Settings()
