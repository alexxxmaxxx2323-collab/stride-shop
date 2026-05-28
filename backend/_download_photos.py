"""Скачивает дополнительные фото для нескольких флагманских товаров с Wikipedia.

Для каждого slug:
- Создаёт папку static/products/<slug>/
- Перемещает оригинальный одиночный файл в <slug>/01.jpg
- Скачивает 2-3 дополнительные из Wikipedia как 02..04.jpg

Запуск: python _download_photos.py
Идемпотентен — пропустит уже существующие папки.
"""
from __future__ import annotations

import shutil
import urllib.request
from pathlib import Path

PRODUCTS_DIR = Path(__file__).resolve().parent / "static" / "products"
USER_AGENT = "stride-shop-demo/0.1 (educational portfolio project)"

# slug -> список URL для скачивания дополнительных фото.
# Размер 800px у Wikipedia thumbnail — нормально для каталога.
EXTRA_PHOTOS: dict[str, list[str]] = {
    "nike-air-force-1": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7e/Nike_air_Force_1_white_on_white.jpg/800px-Nike_air_Force_1_white_on_white.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9d/Dessus_et_dessous_de_l%27AF1.jpg/800px-Dessus_et_dessous_de_l%27AF1.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/d/df/Nike_AF1.JPG/800px-Nike_AF1.JPG",
    ],
    "adidas-stan-smith": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/0/03/Stan_Smith_white_and_green.png/800px-Stan_Smith_white_and_green.png",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6a/Adidas_Stan_Smith_%28made_in_France%29.jpg/800px-Adidas_Stan_Smith_%28made_in_France%29.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0b/Adidas_Stan_Smith%2C_details.jpg/800px-Adidas_Stan_Smith%2C_details.jpg",
    ],
    "dr-martens-1460": [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/8/89/Dr_martens_boots.jpg/800px-Dr_martens_boots.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/3/39/Dr_Martens%2C_black%2C_old.jpg/800px-Dr_Martens%2C_black%2C_old.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/thumb/3/32/DM_stitching.jpg/800px-DM_stitching.jpg",
    ],
}


def _candidate_urls(url: str) -> list[str]:
    """Wikipedia ограничивает размеры thumbnails. Перебираем варианты:
    исходный размер из URL → разрешённые 640/480/1024 → оригинал без /thumb/."""
    out = [url]
    if "/thumb/" in url:
        # Подменяем размер
        for size in ("1024", "640", "480", "330", "250"):
            if f"/{size}px-" in url:
                continue
            # заменяем последний /SIZEpx-...
            import re
            replaced = re.sub(r"/(\d+)px-", f"/{size}px-", url)
            if replaced != url:
                out.append(replaced)
        # оригинал
        original = url.replace("/thumb/", "/").rsplit("/", 1)[0]
        out.append(original)
    return out


def download(url: str, dest: Path) -> bool:
    for candidate in _candidate_urls(url):
        req = urllib.request.Request(candidate, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                dest.write_bytes(r.read())
            return True
        except Exception:
            continue
    print(f"  FAIL {url} (все варианты)")
    return False


def setup_slug(slug: str, urls: list[str]) -> None:
    folder = PRODUCTS_DIR / slug
    if folder.exists():
        print(f"[skip] {slug} — folder already exists")
        return

    # 1. Найти исходный файл (slug.jpg или slug.png)
    src = None
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        candidate = PRODUCTS_DIR / f"{slug}{ext}"
        if candidate.exists():
            src = candidate
            break
    if src is None:
        print(f"[skip] {slug} — нет исходного файла")
        return

    # 2. Создать папку и положить исходный как 01.<ext>
    folder.mkdir(parents=True)
    dest_01 = folder / f"01{src.suffix}"
    shutil.copy2(src, dest_01)
    print(f"[{slug}] 01 <- {src.name}")

    # 3. Скачать дополнительные
    for i, url in enumerate(urls, start=2):
        ext = ".jpg"
        for e in (".jpg", ".jpeg", ".png", ".webp"):
            if url.lower().endswith(e):
                ext = e
                break
        dest = folder / f"{i:02d}{ext}"
        if download(url, dest):
            print(f"[{slug}] {i:02d} <- {url.split('/')[-1][:60]}")


def main() -> None:
    if not PRODUCTS_DIR.exists():
        raise RuntimeError(f"Нет {PRODUCTS_DIR}")
    for slug, urls in EXTRA_PHOTOS.items():
        setup_slug(slug, urls)


if __name__ == "__main__":
    main()
