from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Cart, CartItem, ProductVariant, User, VariantStock
from app.schemas.cart import (
    CartItemIn,
    CartItemOut,
    CartItemUpdate,
    CartItemVariantOut,
    CartOut,
)
from app.schemas.catalog import ProductOut

router = APIRouter(prefix="/cart", tags=["cart"])


MAX_QTY = 20


def get_stock_qty(db: Session, variant_id: int, size: int) -> int:
    """Остаток конкретного варианта в конкретном размере (0 если нет строки)."""
    stock = db.scalar(
        select(VariantStock).where(
            VariantStock.variant_id == variant_id, VariantStock.size == size
        )
    )
    return stock.quantity if stock else 0


def _get_or_create_cart(db: Session, user: User) -> Cart:
    cart = db.scalar(select(Cart).where(Cart.user_id == user.id))
    if cart is None:
        cart = Cart(user_id=user.id)
        db.add(cart)
        db.flush()
    return cart


def _serialize_item(item: CartItem) -> CartItemOut:
    variant = item.variant
    product = variant.product
    primary_url = variant.images[0].url if variant.images else product.primary_image
    subtotal = product.price * item.quantity
    return CartItemOut(
        id=item.id,
        product=ProductOut.model_validate(product),
        variant=CartItemVariantOut(
            id=variant.id,
            color_name=variant.color_name,
            color_hex=variant.color_hex,
            image_url=primary_url,
        ),
        size=item.size,
        quantity=item.quantity,
        subtotal=subtotal,
    )


def _serialize_cart(cart: Cart) -> CartOut:
    items_out: list[CartItemOut] = []
    total = 0
    count = 0
    for it in cart.items:
        out = _serialize_item(it)
        total += out.subtotal
        count += it.quantity
        items_out.append(out)
    return CartOut(items=items_out, total=total, items_count=count)


@router.get("", response_model=CartOut)
def get_cart(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> CartOut:
    cart = _get_or_create_cart(db, user)
    db.commit()
    return _serialize_cart(cart)


@router.post("/items", response_model=CartOut, status_code=status.HTTP_201_CREATED)
def add_item(
    data: CartItemIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CartOut:
    variant = db.get(ProductVariant, data.variant_id)
    if variant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Variant not found")

    available = get_stock_qty(db, variant.id, data.size)
    if available <= 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Selected size is not available for this color",
        )

    cart = _get_or_create_cart(db, user)
    existing = db.scalar(
        select(CartItem).where(
            CartItem.cart_id == cart.id,
            CartItem.variant_id == variant.id,
            CartItem.size == data.size,
        )
    )
    current = existing.quantity if existing else 0
    desired = current + data.quantity
    if desired > available:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Недостаточно на складе: доступно {available} шт.",
        )
    if desired > MAX_QTY:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Максимум {MAX_QTY} шт. одного товара в заказе",
        )

    if existing is None:
        cart.items.append(CartItem(variant_id=variant.id, size=data.size, quantity=data.quantity))
    else:
        existing.quantity = desired

    db.commit()
    db.refresh(cart)
    return _serialize_cart(cart)


@router.patch("/items/{item_id}", response_model=CartOut)
def update_item(
    item_id: int,
    data: CartItemUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CartOut:
    cart = _get_or_create_cart(db, user)
    item = next((i for i in cart.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cart item not found")
    available = get_stock_qty(db, item.variant_id, item.size)
    if data.quantity > available:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Недостаточно на складе: доступно {available} шт.",
        )
    item.quantity = data.quantity
    db.commit()
    db.refresh(cart)
    return _serialize_cart(cart)


@router.delete("/items/{item_id}", response_model=CartOut)
def delete_item(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CartOut:
    cart = _get_or_create_cart(db, user)
    item = next((i for i in cart.items if i.id == item_id), None)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cart item not found")
    cart.items.remove(item)
    db.commit()
    db.refresh(cart)
    return _serialize_cart(cart)


@router.delete("", response_model=CartOut)
def clear_cart(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CartOut:
    cart = _get_or_create_cart(db, user)
    cart.items.clear()
    db.commit()
    db.refresh(cart)
    return _serialize_cart(cart)
