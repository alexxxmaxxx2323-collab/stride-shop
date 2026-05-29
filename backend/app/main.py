from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

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

app = FastAPI(title="Stride Shop API", version="0.2.0")
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


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "env": settings.app_env}
