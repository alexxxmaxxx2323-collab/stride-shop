from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Brand, Category, Product, User
from app.schemas.admin import ProductCreate, ProductUpdate
from app.schemas.catalog import ProductOut

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user


def _check_fks(db: Session, brand_id: int | None, category_id: int | None) -> None:
    if brand_id is not None and db.get(Brand, brand_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Brand {brand_id} not found")
    if category_id is not None and db.get(Category, category_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Category {category_id} not found")


@router.post(
    "/products",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_product(data: ProductCreate, db: Session = Depends(get_db)) -> Product:
    if db.scalar(select(Product).where(Product.slug == data.slug)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Slug already taken")
    _check_fks(db, data.brand_id, data.category_id)

    product = Product(**data.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.patch(
    "/products/{product_id}",
    response_model=ProductOut,
    dependencies=[Depends(require_admin)],
)
def update_product(product_id: int, data: ProductUpdate, db: Session = Depends(get_db)) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")

    fields = data.model_dump(exclude_unset=True)
    if "slug" in fields and fields["slug"] != product.slug:
        if db.scalar(select(Product).where(Product.slug == fields["slug"])):
            raise HTTPException(status.HTTP_409_CONFLICT, "Slug already taken")
    _check_fks(db, fields.get("brand_id"), fields.get("category_id"))

    for k, v in fields.items():
        setattr(product, k, v)

    db.commit()
    db.refresh(product)
    return product


@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
def delete_product(product_id: int, db: Session = Depends(get_db)) -> None:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    db.delete(product)
    db.commit()
