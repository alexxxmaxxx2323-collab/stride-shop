from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Favorite, Product, User
from app.schemas.catalog import ProductOut
from app.schemas.favorites import FavoriteIn

router = APIRouter(prefix="/favorites", tags=["favorites"])


@router.get("", response_model=list[ProductOut])
def list_favorites(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Product]:
    """Возвращает список избранных товаров пользователя (последние сверху)."""
    rows = db.execute(
        select(Product)
        .join(Favorite, Favorite.product_id == Product.id)
        .where(Favorite.user_id == user.id)
        .order_by(Favorite.created_at.desc())
    ).scalars().all()
    return list(rows)


@router.get("/ids", response_model=list[int])
def list_favorite_ids(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[int]:
    """Только id — для быстрой подсветки сердечек в каталоге."""
    rows = db.scalars(
        select(Favorite.product_id).where(Favorite.user_id == user.id)
    ).all()
    return list(rows)


@router.post("", response_model=list[int], status_code=status.HTTP_201_CREATED)
def add_favorite(
    data: FavoriteIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[int]:
    product = db.get(Product, data.product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")

    existing = db.scalar(
        select(Favorite).where(
            Favorite.user_id == user.id, Favorite.product_id == data.product_id
        )
    )
    if existing is None:
        db.add(Favorite(user_id=user.id, product_id=data.product_id))
        db.commit()

    return list(
        db.scalars(select(Favorite.product_id).where(Favorite.user_id == user.id)).all()
    )


@router.delete("/{product_id}", response_model=list[int])
def remove_favorite(
    product_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[int]:
    fav = db.scalar(
        select(Favorite).where(
            Favorite.user_id == user.id, Favorite.product_id == product_id
        )
    )
    if fav is not None:
        db.delete(fav)
        db.commit()
    return list(
        db.scalars(select(Favorite.product_id).where(Favorite.user_id == user.id)).all()
    )
