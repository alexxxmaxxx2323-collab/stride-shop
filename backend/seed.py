"""Заливает справочники (бренды/категории) и 24 товара с вариантами/фото/остатками.

Запуск: python seed.py
Идемпотентен — перед вставкой чистит таблицы каталога, корзин и заказов.
Юзеров (таблица users) и избранное на них не трогает.

Каждый товар получает один или несколько вариантов (цветов). Каждый вариант
имеет 3-4 фото (разные ракурсы) и остатки по 7 размерам (39..45).

Фото лежат в backend/static/products/<slug>/ — папке на каждый товар.
Если папки нет, фолбэк — единственное фото backend/static/products/<slug>.jpg.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import (
    Brand,
    Cart,
    CartItem,
    Category,
    Order,
    OrderItem,
    Product,
    ProductVariant,
    VariantImage,
    VariantStock,
)

SIZES_ALL = [39, 40, 41, 42, 43, 44, 45]

PRODUCTS_DIR = Path(__file__).resolve().parent / "static" / "products"


def collect_images(slug: str) -> list[str]:
    """Ищет фото для товара: сначала в подпапке slug/, потом одиночный файл."""
    folder = PRODUCTS_DIR / slug
    if folder.is_dir():
        urls: list[str] = []
        for p in sorted(folder.iterdir()):
            if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                urls.append(f"/static/products/{slug}/{p.name}")
        if urls:
            return urls

    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        single = PRODUCTS_DIR / f"{slug}{ext}"
        if single.is_file():
            return [f"/static/products/{single.name}"]

    return []


BRANDS = [
    ("Nike", "nike"),
    ("adidas", "adidas"),
    ("New Balance", "new-balance"),
    ("Puma", "puma"),
    ("Reebok", "reebok"),
    ("ASICS", "asics"),
    ("Vans", "vans"),
    ("Converse", "converse"),
    ("Timberland", "timberland"),
    ("Dr. Martens", "dr-martens"),
    ("Palladium", "palladium"),
    ("Clarks", "clarks"),
]

CATEGORIES = [
    ("Кроссовки", "krossovki"),
    ("Кеды", "kedy"),
    ("Ботинки", "botinki"),
]


# brand_slug, name, slug, price, price_old, rating, description, category_slug, color_name, color_hex
PRODUCTS = [
    # ===== КРОССОВКИ =====
    ("nike",        "Air Force 1",          "nike-air-force-1",       12990, 14990, 4.9, "Культовая белая классика из натуральной кожи",            "krossovki", "Белый", "#FFFFFF"),
    ("nike",        "Air Max 90",           "nike-air-max-90",        14990, None,  4.8, "Видимая воздушная амортизация и узнаваемый силуэт",       "krossovki", "Бело-серый", "#E0E0E0"),
    ("nike",        "Pegasus 38",           "nike-pegasus-38",        13490, 15990, 4.7, "Лёгкие беговые с отзывчивой пеной React",                 "krossovki", "Чёрный", "#1A1A1A"),
    ("adidas",      "Stan Smith",           "adidas-stan-smith",      9490,  None,  4.7, "Минималистичная белая модель с зелёной пяткой",           "krossovki", "Белый/зелёный", "#FFFFFF"),
    ("adidas",      "Gazelle",              "adidas-gazelle",         10490, 11990, 4.7, "Замшевый верх с 1968 года, узкий силуэт, Т-носок",        "krossovki", "Красный", "#C8102E"),
    ("adidas",      "Samba OG",             "adidas-samba-og",        11490, None,  4.8, "Низкий профиль, замша и кожа, T-носок",                   "krossovki", "Чёрный", "#1A1A1A"),
    ("new-balance", "574",                  "nb-574",                 10990, 12490, 4.7, "Классика 80-х, амортизация ENCAP и замшевые накладки",    "krossovki", "Серый", "#9AA0A6"),
    ("new-balance", "990v6",                "nb-990v6",               22990, None,  4.9, "Made in USA, флагман по комфорту, премиум-материалы",     "krossovki", "Серый", "#9AA0A6"),
    ("puma",        "RS-X",                 "puma-rs-x",              9990,  None,  4.5, "Объёмная подошва, ретро-футуризм в чистом виде",          "krossovki", "Мульти", "#7C7C7C"),
    ("asics",       "Gel-Lyte III",         "asics-gel-lyte-iii",     13490, None,  4.7, "Раздельный язычок и гелевая вставка в пятке",             "krossovki", "Серо-голубой", "#A8B8C8"),
    ("reebok",      "Classic Leather",      "reebok-classic-leather", 7990,  9490,  4.6, "Кожаный верх и мягкая стелька — иконка 80-х",             "krossovki", "Белый", "#FFFFFF"),
    ("reebok",      "Club C 85",            "reebok-club-c-85",       6990,  None,  4.5, "Корт-силуэт, тонкая подошва, нестареющий дизайн",         "krossovki", "Белый", "#FFFFFF"),
    # ===== КЕДЫ =====
    ("vans",        "Old Skool",            "vans-old-skool",         7490,  8490,  4.8, "Замшевый мыс, фирменная боковая полоса Side Stripe",      "kedy",      "Чёрно-белый", "#1A1A1A"),
    ("vans",        "Authentic",            "vans-authentic",         5990,  None,  4.6, "Самая первая модель Vans 1966 года, парусина",            "kedy",      "Чёрный", "#1A1A1A"),
    ("vans",        "Sk8-Hi",               "vans-sk8-hi",            8290,  None,  4.7, "Высокая скейтовая модель с защитой щиколотки",            "kedy",      "Чёрно-белый", "#1A1A1A"),
    ("converse",    "Chuck Taylor All Star","converse-chuck-taylor",  6490,  None,  4.7, "Самые продаваемые кеды в истории, классика 1917",         "kedy",      "Чёрный", "#1A1A1A"),
    ("converse",    "Chuck 70",             "converse-chuck-70",      9490,  10990, 4.8, "Премиум-версия Chuck Taylor: плотный канвас, выше пятка", "kedy",      "Бежевый", "#D4C4A8"),
    ("puma",        "Suede Classic",        "puma-suede-classic",     7990,  None,  4.6, "Замшевый верх и резиновая подошва — модель 1968 года",    "kedy",      "Синий", "#1F4FA8"),
    # ===== БОТИНКИ =====
    ("timberland",  "6-Inch Premium",       "timberland-6-inch",      18990, 21990, 4.8, "Премиум-силуэт из водоотталкивающего нубука, белый",      "botinki",   "Белый", "#F5F5F0"),
    ("clarks",      "Wallabee",             "clarks-wallabee",        13490, None,  4.7, "Мокасин-ботинок из нубука на креп-подошве",               "botinki",   "Коричневый", "#7A4E2D"),
    ("dr-martens",  "1460",                 "dr-martens-1460",        16490, None,  4.9, "Восьмидырочные ботинки с жёлтой прошивкой, 1960",         "botinki",   "Чёрный", "#1A1A1A"),
    ("dr-martens",  "Jadon",                "dr-martens-jadon",       19990, 22490, 4.8, "Платформа 4.5 см, утяжелённая версия 1460",               "botinki",   "Чёрный", "#1A1A1A"),
    ("dr-martens",  "1461",                 "dr-martens-1461",        14990, None,  4.7, "Низкие туфли-дерби на фирменной подошве AirWair",         "botinki",   "Чёрный", "#1A1A1A"),
    ("palladium",   "Pampa Hi",             "palladium-pampa-hi",     11490, None,  4.5, "Высокие парусиновые ботинки с резиновой подошвой",        "botinki",   "Хаки", "#7C6F4D"),
]


def clean_catalog(db) -> None:
    """Чистим всё что зависит от товаров, потом сами товары и справочники.
    Юзеров оставляем — там может быть учётка Alice из тестов авторизации.
    Избранное снесётся каскадом по FK (ondelete=CASCADE на products.id).
    """
    db.execute(delete(OrderItem))
    db.execute(delete(Order))
    db.execute(delete(CartItem))
    db.execute(delete(Cart))
    db.execute(delete(VariantStock))
    db.execute(delete(VariantImage))
    db.execute(delete(ProductVariant))
    db.execute(delete(Product))
    db.execute(delete(Brand))
    db.execute(delete(Category))
    db.flush()


def main() -> None:
    with SessionLocal() as db:
        clean_catalog(db)

        brands = {slug: Brand(name=name, slug=slug) for name, slug in BRANDS}
        db.add_all(brands.values())

        categories = {slug: Category(name=name, slug=slug) for name, slug in CATEGORIES}
        db.add_all(categories.values())
        db.flush()

        missing: list[str] = []
        for row in PRODUCTS:
            (
                brand_slug,
                name,
                slug,
                price,
                price_old,
                rating,
                description,
                cat_slug,
                color_name,
                color_hex,
            ) = row

            image_urls = collect_images(slug)
            if not image_urls:
                missing.append(slug)
                continue

            product = Product(
                name=name,
                slug=slug,
                description=description,
                brand_id=brands[brand_slug].id,
                category_id=categories[cat_slug].id,
                price=price,
                price_old=price_old,
                rating=rating,
            )
            variant = ProductVariant(
                color_name=color_name,
                color_hex=color_hex,
                sort_order=0,
            )
            for i, url in enumerate(image_urls):
                variant.images.append(VariantImage(url=url, sort_order=i))
            for size in SIZES_ALL:
                variant.stocks.append(VariantStock(size=size, quantity=10))
            product.variants.append(variant)
            db.add(product)

        if missing:
            raise RuntimeError(f"Нет фото для slug: {missing}")

        db.commit()

        all_products = db.scalars(select(Product).order_by(Product.id)).all()
        by_cat: dict[str, list[Product]] = {c.name: [] for c in categories.values()}
        for p in all_products:
            by_cat[p.category.name].append(p)

        total_variants = sum(len(p.variants) for p in all_products)
        total_images = sum(len(v.images) for p in all_products for v in p.variants)

        print(
            f"OK: brands={len(brands)}, categories={len(categories)}, "
            f"products={len(all_products)}, variants={total_variants}, images={total_images}"
        )
        for cat_name, items in by_cat.items():
            disc_count = sum(1 for p in items if p.price_old)
            print(f"  [{cat_name}] {len(items)} sht. (so skidkoj: {disc_count})")


if __name__ == "__main__":
    main()
