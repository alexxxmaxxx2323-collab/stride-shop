from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Cart, Order, OrderItem, User
from app.schemas.order import OrderCreate, OrderCreatedOut, OrderOut

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderCreatedOut, status_code=status.HTTP_201_CREATED)
def create_order(
    data: OrderCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrderCreatedOut:
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
        subtotal = ci.product.price * ci.quantity
        total += subtotal
        order.items.append(
            OrderItem(
                product_id=ci.product_id,
                product_name=ci.product.name,
                product_image=ci.product.image_url,
                size=ci.size,
                quantity=ci.quantity,
                unit_price=ci.product.price,
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
