from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Brand, Category, Product, ProductVariant, VariantStock
from app.schemas.catalog import (
    BrandOut,
    CategoryOut,
    ProductDetailOut,
    ProductListOut,
    ProductOut,
)

router = APIRouter(tags=["catalog"])

SortKey = Literal["popular", "price_asc", "price_desc", "new"]


@router.get("/brands", response_model=list[BrandOut])
def list_brands(db: Session = Depends(get_db)):
    return db.scalars(select(Brand).order_by(Brand.name)).all()


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.scalars(select(Category).order_by(Category.id)).all()


@router.get("/products", response_model=ProductListOut)
def list_products(
    db: Session = Depends(get_db),
    brand: list[str] | None = Query(None, description="Один или несколько slug бренда"),
    category: str | None = Query(None, description="Slug категории"),
    size: int | None = Query(None, ge=30, le=50),
    price_min: int | None = Query(None, ge=0),
    price_max: int | None = Query(None, ge=0),
    only_discount: bool = Query(False),
    q: str | None = Query(None, description="Поиск по названию"),
    sort: SortKey = "popular",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    stmt = select(Product)

    if brand:
        stmt = stmt.where(Product.brand_id.in_(select(Brand.id).where(Brand.slug.in_(brand))))
    if category:
        stmt = stmt.where(
            Product.category_id.in_(select(Category.id).where(Category.slug == category))
        )
    if price_min is not None:
        stmt = stmt.where(Product.price >= price_min)
    if price_max is not None:
        stmt = stmt.where(Product.price <= price_max)
    if only_discount:
        # Скидка реальна только если старая цена строго больше текущей —
        # так же, как считается бейдж discount_pct на карточке.
        stmt = stmt.where(
            Product.price_old.is_not(None), Product.price_old > Product.price
        )
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q}%"))

    # Фильтр по размеру: товар подходит если хотя бы у одного варианта
    # есть остаток в этом размере (quantity > 0).
    if size is not None:
        stmt = stmt.where(
            Product.id.in_(
                select(ProductVariant.product_id)
                .join(VariantStock, VariantStock.variant_id == ProductVariant.id)
                .where(VariantStock.size == size, VariantStock.quantity > 0)
            )
        )

    if sort == "popular":
        stmt = stmt.order_by(Product.rating.desc(), Product.id)
    elif sort == "price_asc":
        stmt = stmt.order_by(Product.price.asc(), Product.id)
    elif sort == "price_desc":
        stmt = stmt.order_by(Product.price.desc(), Product.id)
    elif sort == "new":
        stmt = stmt.order_by(Product.created_at.desc(), Product.id.desc())

    all_items = db.scalars(stmt).all()
    total = len(all_items)
    pages = (total + page_size - 1) // page_size if total else 0
    start = (page - 1) * page_size
    items = all_items[start : start + page_size]

    return ProductListOut(
        items=[ProductOut.model_validate(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/products/{product_id}", response_model=ProductDetailOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.get("/products/slug/{slug}", response_model=ProductDetailOut)
def get_product_by_slug(slug: str, db: Session = Depends(get_db)):
    product = db.scalar(select(Product).where(Product.slug == slug))
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
