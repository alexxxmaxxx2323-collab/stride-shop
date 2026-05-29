from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Cart, Order, OrderItem, User
from app.schemas.order import OrderCreate, OrderCreatedOut, OrderOut
from app.services.geocode import GeocodeUnavailable, address_exists

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderCreatedOut, status_code=status.HTTP_201_CREATED)
def create_order(
    data: OrderCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrderCreatedOut:
    # Реальность адреса проверяем у геокодера. Эвристика в схеме уже
    # отсекла явный мусор; здесь убеждаемся, что такой адрес существует.
    # Если геокодер недоступен — не блокируем заказ (эвристики достаточно).
    try:
        if not address_exists(data.delivery_address):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Не удалось найти такой адрес — проверьте город, улицу и дом",
            )
    except GeocodeUnavailable:
        pass

    cart = db.scalar(select(Cart).where(Cart.user_id == user.id))
    if cart is None or not cart.items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cart is empty")

    order = Order(
        user_id=user.id,
        status="pending",
        payment_status="awaiting",
        total_amount=0,
        delivery_name=data.delivery_name,
        delivery_phone=data.delivery_phone,
        delivery_address=data.delivery_address,
    )

    total = 0
    for ci in cart.items:
        variant = ci.variant
        product = variant.product
        snapshot_image = variant.images[0].url if variant.images else product.primary_image
        unit_price = product.price
        subtotal = unit_price * ci.quantity
        total += subtotal
        order.items.append(
            OrderItem(
                variant_id=variant.id,
                product_name=product.name,
                product_image=snapshot_image,
                color_name=variant.color_name,
                size=ci.size,
                quantity=ci.quantity,
                unit_price=unit_price,
                subtotal=subtotal,
            )
        )
    order.total_amount = total

    db.add(order)
    cart.items.clear()
    db.commit()
    db.refresh(order)

    return OrderCreatedOut(
        order=OrderOut.model_validate(order),
        payment_url=f"/static/payment.html?order={order.id}",
    )


@router.get("", response_model=list[OrderOut])
def list_orders(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Order]:
    return list(
        db.scalars(
            select(Order).where(Order.user_id == user.id).order_by(Order.id.desc())
        ).all()
    )


@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Order:
    order = db.get(Order, order_id)
    if order is None or order.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    return order
