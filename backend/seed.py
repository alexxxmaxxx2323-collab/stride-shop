"""Заливает справочники (бренды/категории) и 24 товара в БД.

Запуск: python seed.py
Идемпотентен — перед вставкой чистит таблицы товаров/корзин/заказов и заливает заново.
Юзеров (таблица users) не трогает.

Фото лежат локально в backend/static/products/<slug>.{jpg,png}.
Скачаны из брендовых каталогов и StockX, все на белом фоне, студийные.
URL формата /static/products/<slug>.ext — раздаются FastAPI через StaticFiles.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import Brand, Cart, CartItem, Category, Order, OrderItem, Product

SIZES_ALL = [39, 40, 41, 42, 43, 44, 45]

PRODUCTS_DIR = Path(__file__).resolve().parent / "static" / "products"

# slug → URL картинки (раздаём через StaticFiles из ../static/products/)
IMAGES: dict[str, str] = {
    p.stem: f"/static/products/{p.name}" for p in PRODUCTS_DIR.iterdir() if p.is_file()
}

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

# brand_slug, name, slug, price, price_old, rating, description, category_slug
PRODUCTS = [
    # ===== КРОССОВКИ =====
    ("nike",        "Air Force 1",          "nike-air-force-1",       12990, 14990, 4.9, "Культовая белая классика из натуральной кожи",            "krossovki"),
    ("nike",        "Air Max 90",           "nike-air-max-90",        14990, None,  4.8, "Видимая воздушная амортизация и узнаваемый силуэт",       "krossovki"),
    ("nike",        "Pegasus 38",           "nike-pegasus-38",        13490, 15990, 4.7, "Лёгкие беговые с отзывчивой пеной React",                 "krossovki"),
    ("adidas",      "Stan Smith",           "adidas-stan-smith",      9490,  None,  4.7, "Минималистичная белая модель с зелёной пяткой",           "krossovki"),
    ("adidas",      "Gazelle",              "adidas-gazelle",         10490, 11990, 4.7, "Замшевый верх с 1968 года, узкий силуэт, Т-носок",        "krossovki"),
    ("adidas",      "Samba OG",             "adidas-samba-og",        11490, None,  4.8, "Низкий профиль, замша и кожа, T-носок",                   "krossovki"),
    ("new-balance", "574",                  "nb-574",                 10990, 12490, 4.7, "Классика 80-х, амортизация ENCAP и замшевые накладки",    "krossovki"),
    ("new-balance", "990v6",                "nb-990v6",               22990, None,  4.9, "Made in USA, флагман по комфорту, премиум-материалы",     "krossovki"),
    ("puma",        "RS-X",                 "puma-rs-x",              9990,  None,  4.5, "Объёмная подошва, ретро-футуризм в чистом виде",          "krossovki"),
    ("asics",       "Gel-Lyte III",         "asics-gel-lyte-iii",     13490, None,  4.7, "Раздельный язычок и гелевая вставка в пятке",             "krossovki"),
    ("reebok",      "Classic Leather",      "reebok-classic-leather", 7990,  9490,  4.6, "Кожаный верх и мягкая стелька — иконка 80-х",             "krossovki"),
    ("reebok",      "Club C 85",            "reebok-club-c-85",       6990,  None,  4.5, "Корт-силуэт, тонкая подошва, нестареющий дизайн",         "krossovki"),
    # ===== КЕДЫ =====
    ("vans",        "Old Skool",            "vans-old-skool",         7490,  8490,  4.8, "Замшевый мыс, фирменная боковая полоса Side Stripe",      "kedy"),
    ("vans",        "Authentic",            "vans-authentic",         5990,  None,  4.6, "Самая первая модель Vans 1966 года, парусина",            "kedy"),
    ("vans",        "Sk8-Hi",               "vans-sk8-hi",            8290,  None,  4.7, "Высокая скейтовая модель с защитой щиколотки",            "kedy"),
    ("converse",    "Chuck Taylor All Star","converse-chuck-taylor",  6490,  None,  4.7, "Самые продаваемые кеды в истории, классика 1917",         "kedy"),
    ("converse",    "Chuck 70",             "converse-chuck-70",      9490,  10990, 4.8, "Премиум-версия Chuck Taylor: плотный канвас, выше пятка", "kedy"),
    ("puma",        "Suede Classic",        "puma-suede-classic",     7990,  None,  4.6, "Замшевый верх и резиновая подошва — модель 1968 года",    "kedy"),
    # ===== БОТИНКИ =====
    ("timberland",  "6-Inch Premium",       "timberland-6-inch",      18990, 21990, 4.8, "Премиум-силуэт из водоотталкивающего нубука, белый",      "botinki"),
    ("clarks",      "Wallabee",             "clarks-wallabee",        13490, None,  4.7, "Мокасин-ботинок из нубука на креп-подошве",               "botinki"),
    ("dr-martens",  "1460",                 "dr-martens-1460",        16490, None,  4.9, "Восьмидырочные ботинки с жёлтой прошивкой, 1960",         "botinki"),
    ("dr-martens",  "Jadon",                "dr-martens-jadon",       19990, 22490, 4.8, "Платформа 4.5 см, утяжелённая версия 1460",               "botinki"),
    ("dr-martens",  "1461",                 "dr-martens-1461",        14990, None,  4.7, "Низкие туфли-дерби на фирменной подошве AirWair",         "botinki"),
    ("palladium",   "Pampa Hi",             "palladium-pampa-hi",     11490, None,  4.5, "Высокие парусиновые ботинки с резиновой подошвой",        "botinki"),
]


def clean_catalog(db) -> None:
    """Чистим всё что зависит от товаров, потом сами товары и справочники.
    Юзеров оставляем — там может быть учётка Alice из тестов авторизации.
    """
    db.execute(delete(OrderItem))
    db.execute(delete(Order))
    db.execute(delete(CartItem))
    db.execute(delete(Cart))
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

        missing = [row[2] for row in PRODUCTS if row[2] not in IMAGES]
        if missing:
            raise RuntimeError(f"Нет фото для slug: {missing}")

        for row in PRODUCTS:
            brand_slug, name, slug, price, price_old, rating, description, cat_slug = row
            db.add(
                Product(
                    name=name,
                    slug=slug,
                    description=description,
                    brand_id=brands[brand_slug].id,
                    category_id=categories[cat_slug].id,
                    price=price,
                    price_old=price_old,
                    image_url=IMAGES[slug],
                    rating=rating,
                    sizes=SIZES_ALL,
                    in_stock=True,
                )
            )

        db.commit()

        all_products = db.scalars(select(Product).order_by(Product.id)).all()
        by_cat: dict[str, list[Product]] = {c.name: [] for c in categories.values()}
        for p in all_products:
            by_cat[p.category.name].append(p)

        print(f"OK: brands={len(brands)}, categories={len(categories)}, products={len(all_products)}")
        for cat_name, items in by_cat.items():
            disc_count = sum(1 for p in items if p.price_old)
            print(f"  [{cat_name}] {len(items)} sht. (so skidkoj: {disc_count})")


if __name__ == "__main__":
    main()
