"""Добавляет в каталог реальную модель Nike Air Max 95 «OG Neon» (вольт-вставки).

1. Качает 5 ракурсов 360°-съёмки со StockX CDN в static/products/nike-air-max-95-neon/.
2. Создаёт товар + вариант (цвет Neon) + фото + остатки, если его ещё нет.

Идемпотентен: если товар уже есть — ничего не делает.
Запуск:  .venv/Scripts/python.exe _add_neon.py
"""
from __future__ import annotations

import time
import urllib.request
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Product, ProductVariant, VariantImage, VariantStock

SLUG = "nike-air-max-95-neon"
FOLDER = "Nike-Air-Max-95-OG-Neon-2020"
FRAMES = [1, 5, 9, 18, 27]
SIZES = [39, 40, 41, 42, 43, 44, 45]
PRODUCTS_DIR = Path(__file__).resolve().parent / "static" / "products"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def frame_url(n: int) -> str:
    return f"https://images.stockx.com/360/{FOLDER}/Images/{FOLDER}/Lv2/img{n:02d}.jpg"


def fetch(url: str) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read()
    except Exception as e:  # noqa: BLE001
        print(f"  FAIL {url} ({e})")
        return None


def download_photos() -> list[str]:
    """Скачивает кадры; возвращает список url-путей для VariantImage."""
    blobs = []
    for n in FRAMES:
        data = fetch(frame_url(n))
        if not data or len(data) < 2000:
            raise RuntimeError(f"кадр img{n:02d} не получен — прерываю")
        blobs.append(data)
        time.sleep(0.15)
    folder = PRODUCTS_DIR / SLUG
    folder.mkdir(parents=True, exist_ok=True)
    urls = []
    for i, data in enumerate(blobs, start=1):
        (folder / f"{i:02d}.jpg").write_bytes(data)
        urls.append(f"/static/products/{SLUG}/{i:02d}.jpg")
    print(f"  фото сохранены: {len(urls)} шт.")
    return urls


def main() -> int:
    with SessionLocal() as db:
        if db.scalar(select(Product).where(Product.slug == SLUG)):
            print(f"{SLUG} уже есть в каталоге — пропускаю")
            return 0

        urls = download_photos()

        product = Product(
            name="Air Max 95 «Neon»",
            slug=SLUG,
            description=(
                "Культовая модель 1995 года с узнаваемыми неоновыми вставками и "
                "видимой амортизацией Air. Градиентный верх, агрессивный силуэт — "
                "икона уличного стиля."
            ),
            brand_id=1,       # Nike
            category_id=1,    # Кроссовки
            price=16990,
            price_old=19990,
            rating=4.9,
            upper="Сетка, замша, синтетика",
            lining="Текстиль",
            sole="Резина с амортизацией Nike Air",
            season="Демисезон",
            country="Вьетнам",
        )
        db.add(product)
        db.flush()

        variant = ProductVariant(
            product_id=product.id,
            color_name="Neon",
            color_hex="#d8ff2e",
            sort_order=0,
        )
        db.add(variant)
        db.flush()

        for i, url in enumerate(urls):
            db.add(VariantImage(variant_id=variant.id, url=url, sort_order=i))
        for sz in SIZES:
            db.add(VariantStock(variant_id=variant.id, size=sz, quantity=8))

        db.commit()
        print(f"OK: добавлен товар id={product.id} «{product.name}» ({SLUG})")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
