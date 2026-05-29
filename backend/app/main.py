import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import telegram
from app.config import settings
from app.routers import addresses as addresses_router
from app.routers import admin as admin_router
from app.routers import auth as auth_router
from app.routers import cart as cart_router
from app.routers import catalog as catalog_router
from app.routers import delivery as delivery_router
from app.routers import favorites as favorites_router
from app.routers import orders as orders_router
from app.routers import payments as payments_router

log = logging.getLogger("app")


def bootstrap_db() -> None:
    """Готовим БД к работе: создаём таблицы и сидируем каталог, если он пуст.
    Нужно для эфемерного диска на хостинге — каталог должен быть на каждом старте.
    """
    from sqlalchemy import select

    from app import models  # noqa: F401 — регистрируем модели в Base.metadata
    from app.db import Base, SessionLocal, engine
    from app.models import Product

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.scalar(select(Product).limit(1)) is None:
            log.info("Каталог пуст — сидируем…")
            import seed  # backend/seed.py
            seed.main()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        bootstrap_db()
    except Exception as e:  # noqa: BLE001 — не валим сервис, если сид не прошёл
        log.exception("bootstrap_db failed: %s", e)
    if settings.tg_bot_token and settings.base_url:
        try:
            await telegram.setup_webhook()
        except Exception as e:  # noqa: BLE001
            log.warning("setup_webhook failed: %s", e)
    yield
    await telegram.shutdown()


app = FastAPI(title="Stride Shop API", version="0.3.0", lifespan=lifespan)
app.include_router(auth_router.router)
app.include_router(catalog_router.router)
app.include_router(cart_router.router)
app.include_router(orders_router.router)
app.include_router(favorites_router.router)
app.include_router(admin_router.router)
app.include_router(addresses_router.router)
app.include_router(payments_router.router)
app.include_router(delivery_router.router)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/static/shop.html")


@app.post("/tg/webhook/{secret}", include_in_schema=False)
async def tg_webhook(secret: str, request: Request) -> dict:
    """Приём апдейтов Telegram (webhook). Проверяем секрет в пути и в заголовке."""
    if secret != settings.tg_webhook_secret:
        raise HTTPException(status_code=404, detail="Not found")
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != settings.tg_webhook_secret:
        raise HTTPException(status_code=403, detail="Bad secret")
    await telegram.feed_update(await request.json())
    return {"ok": True}


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "env": settings.app_env}
