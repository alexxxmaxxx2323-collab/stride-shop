"""Скачивает мульти-ракурсные студийные фото товаров с CDN StockX (белый фон).

StockX хранит 360°-съёмку каждой модели по предсказуемому пути:
    https://images.stockx.com/360/<Folder>/Images/<Folder>/Lv2/imgNN.jpg
где NN = 01..36 — кадры полного оборота на чистом белом фоне.
Мы берём из них несколько ключевых ракурсов (сбоку / 3-4 / спереди / с другой
стороны / пятка) и кладём в static/products/<slug>/ как 01.jpg..05.jpg.

После успешной загрузки папки удаляем устаревший одиночный файл
static/products/<slug>.<ext> (его перекрывает папка, см. seed.collect_images).

Запуск:  python _download_photos.py
Идемпотентен: перезаписывает папку заново при каждом запуске.
"""
from __future__ import annotations

import time
import urllib.request
from pathlib import Path

PRODUCTS_DIR = Path(__file__).resolve().parent / "static" / "products"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Кадры 360°-оборота (из 36): сбоку, 3/4-спереди, спереди, с другой стороны, пятка.
FRAMES = [1, 5, 9, 18, 27]

# Наш slug товара -> папка модели в 360-CDN StockX (цвет подобран под наш вариант).
SLUG_MAP: dict[str, str] = {
    "nike-air-force-1":       "Nike-Air-Force-1-07-White",
    "nike-air-max-90":        "Nike-Air-Max-90-Triple-White",
    "nike-pegasus-38":        "Nike-Air-Zoom-Pegasus-38-Black-White",
    "adidas-stan-smith":      "adidas-Stan-Smith-White-Green-OG",
    "adidas-gazelle":         "adidas-Gazelle-Scarlet-Cloud-White",
    "adidas-samba-og":        "adidas-Samba-Black-White-Gum",
    "nb-574":                 "New-Balance-574-Grey",
    "nb-990v6":               "New-Balance-990v6-Grey",
    "puma-rs-x":              "Puma-RS-X-Toys-White",
    "reebok-classic-leather": "Reebok-Classic-Leather-White",
    "reebok-club-c-85":       "Reebok-Club-C-85-White-Green",
    "vans-old-skool":         "Vans-Old-Skool-Black-White",
    "vans-authentic":         "Vans-Authentic-Black-White",
    "vans-sk8-hi":            "Vans-Sk8-Hi-Black-White",
    "converse-chuck-taylor":  "Converse-Chuck-Taylor-All-Star-Hi-Black",
    "converse-chuck-70":      "Converse-Chuck-Taylor-All-Star-70s-Hi-Parchment",
}

# Товары без 360 на StockX — оставляем как есть (1 чистое фото) и здесь не трогаем:
# asics-gel-lyte-iii, puma-suede-classic, timberland-6-inch, clarks-wallabee,
# dr-martens-1460, dr-martens-jadon, dr-martens-1461, palladium-pampa-hi.

# Папки, где раньше лежали любительские доп.фото с Wikipedia — оставить только 01.jpg.
STRIP_EXTRAS = ["dr-martens-1460"]


def frame_url(folder: str, n: int) -> str:
    return f"https://images.stockx.com/360/{folder}/Images/{folder}/Lv2/img{n:02d}.jpg"


def fetch(url: str) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read()
    except Exception as e:  # noqa: BLE001
        print(f"    FAIL {url} ({e})")
        return None


def clear_images(folder: Path) -> None:
    for p in folder.iterdir():
        if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            p.unlink()


def download_set(slug: str, folder_name: str) -> bool:
    folder = PRODUCTS_DIR / slug
    # 1. Сначала качаем всё во временную память — папку трогаем только при полном успехе.
    blobs: list[bytes] = []
    for n in FRAMES:
        data = fetch(frame_url(folder_name, n))
        if data is None or len(data) < 2000:  # 404 отдаёт крошечную заглушку
            print(f"  [{slug}] кадр img{n:02d} не получен — пропускаю товар целиком")
            return False
        blobs.append(data)
        time.sleep(0.15)

    # 2. Все кадры есть — перезаписываем папку.
    folder.mkdir(parents=True, exist_ok=True)
    clear_images(folder)
    for i, data in enumerate(blobs, start=1):
        (folder / f"{i:02d}.jpg").write_bytes(data)
    print(f"  [{slug}] OK — {len(blobs)} фото <- {folder_name}")

    # 3. Удаляем устаревший одиночный файл (его перекрывает папка).
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        single = PRODUCTS_DIR / f"{slug}{ext}"
        if single.is_file():
            single.unlink()
            print(f"  [{slug}] удалён лишний одиночный файл {single.name}")
    return True


def strip_extras(slug: str) -> None:
    """Оставить в папке только 01.* (убрать старые любительские доп.фото)."""
    folder = PRODUCTS_DIR / slug
    if not folder.is_dir():
        return
    removed = 0
    for p in sorted(folder.iterdir()):
        if p.is_file() and not p.stem.startswith("01"):
            p.unlink()
            removed += 1
    if removed:
        print(f"  [{slug}] убрано лишних фото: {removed} (оставлено только 01)")


def main() -> None:
    if not PRODUCTS_DIR.exists():
        raise RuntimeError(f"Нет {PRODUCTS_DIR}")

    print("=== StockX 360 ракурсы ===")
    ok, fail = 0, 0
    for slug, folder_name in SLUG_MAP.items():
        if download_set(slug, folder_name):
            ok += 1
        else:
            fail += 1

    print("\n=== Чистка устаревших доп.фото ===")
    for slug in STRIP_EXTRAS:
        strip_extras(slug)

    print(f"\nГотово: успешно {ok}, неудачно {fail}, всего в карте {len(SLUG_MAP)}.")


if __name__ == "__main__":
    main()
