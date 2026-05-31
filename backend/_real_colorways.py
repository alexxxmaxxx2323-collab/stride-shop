"""Заменяет фейковые цвет-варианты на РЕАЛЬНЫЕ расцветки с настоящими фото.

Что делает:
1. Качает подтверждённые StockX-360 расцветки в static/products/<slug>/c<idx>/01..05.jpg
   (по 5 ракурсов на каждую расцветку, чистый белый студийный фон).
2. В БД для этих моделей удаляет ВСЕ текущие варианты (включая ранее добавленные
   фейковые) и создаёт реальные — у каждого свой цвет И свои фото, поэтому при
   выборе цвета меняется и картинка.
3. Для остальных моделей (ботинки/asics/suede/neon, без 360) убирает фейковые
   дубли-варианты, возвращая исходный единственный реальный цвет.

Перед удалением вариантов обнуляем ссылки в order_items (снапшот заказа хранит
имя/фото/цвет отдельно — заказы не ломаются) и чистим cart_items на эти варианты.

Запуск:  .venv\Scripts\python.exe _real_colorways.py
Идемпотентен: повторный прогон пере-скачивает фото и пересобирает варианты.
"""
from __future__ import annotations

import time
import urllib.request
from pathlib import Path

from sqlalchemy import bindparam, text

from app.db import SessionLocal
from app.models import Product, ProductVariant, VariantImage, VariantStock

PRODUCTS_DIR = Path(__file__).resolve().parent / "static" / "products"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
FRAMES = [1, 5, 9, 18, 27]
SIZES = range(39, 46)

PALETTE_HEX = {
    "#111114", "#f1f1ef", "#9aa0a6", "#1f2a44", "#c0392b", "#2e7d4f",
    "#d8c3a5", "#6db3f2", "#6d1f2b", "#c2a878", "#6b6b3a", "#e0a0bd",
}
SKIP_PRODUCT_IDS = {25}  # пользовательский тестовый товар

# slug -> [(имя цвета, hex, StockX-папка)] — только ПОДТВЕРЖДЁННЫЕ зондом папки
CONFIRMED: dict[str, list[tuple[str, str, str]]] = {
    "nike-air-force-1": [("Белый", "#f1f1ef", "Nike-Air-Force-1-07-White"),
                         ("Чёрный", "#15161a", "Nike-Air-Force-1-07-Black")],
    "nike-air-max-90": [("Белый", "#f1f1ef", "Nike-Air-Max-90-Triple-White"),
                        ("Инфракрасный", "#c0392b", "Nike-Air-Max-90-Infrared-2020")],
    "nike-pegasus-38": [("Чёрно-белый", "#15161a", "Nike-Air-Zoom-Pegasus-38-Black-White"),
                        ("Серый", "#9aa0a6", "Nike-Air-Zoom-Pegasus-38-Wolf-Grey")],
    "adidas-stan-smith": [("Бело-зелёный", "#2e7d4f", "adidas-Stan-Smith-White-Green-OG"),
                          ("Чёрный", "#15161a", "adidas-Stan-Smith-Core-Black")],
    "adidas-gazelle": [("Алый", "#c0392b", "adidas-Gazelle-Scarlet-Cloud-White")],
    "adidas-samba-og": [("Чёрный", "#15161a", "adidas-Samba-Black-White-Gum"),
                        ("Белый", "#f1f1ef", "adidas-Samba-OG-Cloud-White-Core-Black")],
    "nb-574": [("Серый", "#9aa0a6", "New-Balance-574-Grey"),
               ("Тёмно-синий", "#1f2a44", "New-Balance-574-Navy")],
    "nb-990v6": [("Серый", "#9aa0a6", "New-Balance-990v6-Grey")],
    "puma-rs-x": [("Белый", "#f1f1ef", "Puma-RS-X-Toys-White")],
    "reebok-classic-leather": [("Белый", "#f1f1ef", "Reebok-Classic-Leather-White"),
                               ("Чёрный", "#15161a", "Reebok-Classic-Leather-Black")],
    "reebok-club-c-85": [("Бело-зелёный", "#2e7d4f", "Reebok-Club-C-85-White-Green"),
                         ("Бело-синий", "#1f2a44", "Reebok-Club-C-85-White-Navy")],
    "vans-old-skool": [("Чёрно-белый", "#15161a", "Vans-Old-Skool-Black-White")],
    "vans-authentic": [("Чёрно-белый", "#15161a", "Vans-Authentic-Black-White"),
                       ("Красный", "#c0392b", "Vans-Authentic-Red")],
    "vans-sk8-hi": [("Чёрно-белый", "#15161a", "Vans-Sk8-Hi-Black-White")],
    "converse-chuck-taylor": [("Чёрный", "#15161a", "Converse-Chuck-Taylor-All-Star-Hi-Black")],
    "converse-chuck-70": [("Кремовый", "#d8c3a5", "Converse-Chuck-Taylor-All-Star-70s-Hi-Parchment"),
                          ("Чёрный", "#15161a", "Converse-Chuck-Taylor-All-Star-70s-Hi-Black")],
}


def frame_url(folder: str, n: int) -> str:
    return f"https://images.stockx.com/360/{folder}/Images/{folder}/Lv2/img{n:02d}.jpg"


def fetch(url: str) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read()
            return data if len(data) >= 2000 else None
    except Exception as e:  # noqa: BLE001
        print(f"    FAIL {url} ({e})")
        return None


def download_colorway(slug: str, idx: int, folder: str) -> list[str] | None:
    """Качает кадры расцветки в static/products/<slug>/c<idx>/. Возвращает url'ы."""
    blobs = []
    for n in FRAMES:
        data = fetch(frame_url(folder, n))
        if data is None:
            print(f"  [{slug}] c{idx} кадр img{n:02d} не получен — расцветка пропущена")
            return None
        blobs.append(data)
        time.sleep(0.12)
    sub = PRODUCTS_DIR / slug / f"c{idx}"
    sub.mkdir(parents=True, exist_ok=True)
    urls = []
    for i, data in enumerate(blobs, start=1):
        (sub / f"{i:02d}.jpg").write_bytes(data)
        urls.append(f"/static/products/{slug}/c{idx}/{i:02d}.jpg")
    print(f"  [{slug}] c{idx} OK ({len(urls)} фото) <- {folder}")
    return urls


def main() -> None:
    # --- 1) скачиваем все подтверждённые расцветки ---
    print("=== Скачивание реальных расцветок (StockX 360) ===")
    images: dict[str, list[tuple[str, str, list[str]]]] = {}
    for slug, cws in CONFIRMED.items():
        rows = []
        for idx, (name, hex_, folder) in enumerate(cws, start=1):
            urls = download_colorway(slug, idx, folder)
            if urls:
                rows.append((name, hex_, urls))
        if rows:
            images[slug] = rows

    # --- 2) пересборка вариантов в БД ---
    with SessionLocal() as db:
        products = db.query(Product).all()
        by_slug = {p.slug: p for p in products}

        del_ids: list[int] = []
        # confirmed-модели: сносим все варианты, создадим реальные заново
        for slug in images:
            p = by_slug.get(slug)
            if p:
                del_ids += [v.id for v in p.variants]
        # остальные: убираем только фейковые дубли (palette-hex + фото = фото базового)
        for p in products:
            if p.slug in images or p.id in SKIP_PRODUCT_IDS or not p.variants:
                continue
            base_imgs = sorted(im.url for im in p.variants[0].images)
            for v in p.variants[1:]:
                same_imgs = sorted(im.url for im in v.images) == base_imgs
                if v.color_hex.lower() in PALETTE_HEX and same_imgs:
                    del_ids.append(v.id)

        # снять FK-ссылки перед удалением
        if del_ids:
            db.execute(
                text("UPDATE order_items SET variant_id=NULL WHERE variant_id IN :ids")
                .bindparams(bindparam("ids", expanding=True)), {"ids": del_ids})
            db.execute(
                text("DELETE FROM cart_items WHERE variant_id IN :ids")
                .bindparams(bindparam("ids", expanding=True)), {"ids": del_ids})
            for vid in del_ids:
                v = db.get(ProductVariant, vid)
                if v:
                    db.delete(v)
            db.flush()
            print(f"\nУдалено вариантов: {len(del_ids)}")

        # создаём реальные варианты
        created = 0
        for slug, rows in images.items():
            p = by_slug[slug]
            for idx, (name, hex_, urls) in enumerate(rows):
                v = ProductVariant(product_id=p.id, color_name=name, color_hex=hex_, sort_order=idx)
                for i, url in enumerate(urls):
                    v.images.append(VariantImage(url=url, sort_order=i))
                for s in SIZES:
                    v.stocks.append(VariantStock(size=s, quantity=10))
                db.add(v)
                created += 1
        db.commit()
        print(f"Создано реальных вариантов: {created}")
        print("Модели с реальными расцветками:", len(images))


if __name__ == "__main__":
    main()
