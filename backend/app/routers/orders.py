from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.db import get_db
from app.models import Cart, Order, OrderItem, User
from app.notifications import order_summary, send_message
from app.routers.cart import get_stock_qty
from app.schemas.order import OrderCreate, OrderCreatedOut, OrderOut
from app.services.bonus import bonus_balance, cashback_for_order, credit_bonus
from app.services.geocode import GeocodeUnavailable, address_exists

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderCreatedOut, status_code=status.HTTP_201_CREATED)
def create_order(
    data: OrderCreate,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrderCreatedOut:
    # Реальность адреса проверяем у геокодера. Эвристика в схеме уже
    # отсекла явный мусор; здесь убеждаемся, что такой адрес существует.
    # Если геокодер недоступен — не блокируем заказ (эвристики достаточно).
    # Для самовывоза адрес — это выбранный ПВЗ (он заведомо реальный), геокодер не нужен.
    if data.delivery_type == "courier":
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

    # Финальная проверка остатка: между добавлением в корзину и оформлением
    # склад мог измениться (или корзина пролежала долго).
    for ci in cart.items:
        available = get_stock_qty(db, ci.variant_id, ci.size)
        if ci.quantity > available:
            name = ci.variant.product.name
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"«{name}» размер {ci.size}: на складе только {available} шт.",
            )

    order = Order(
        user_id=user.id,
        status="pending",
        payment_status="awaiting",
        total_amount=0,
        delivery_name=data.delivery_name,
        delivery_phone=data.delivery_phone,
        delivery_address=data.delivery_address,
        delivery_type=data.delivery_type,
        pickup_code=data.pickup_code if data.delivery_type == "pickup" else None,
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
    # Оплата баллами: списываем не больше, чем есть на балансе и чем сумма заказа.
    spend = 0
    if data.use_points > 0:
        spend = max(0, min(data.use_points, bonus_balance(db, user.id), total))
    order.total_amount = total - spend

    db.add(order)
    cart.items.clear()
    db.commit()
    db.refresh(order)

    # Списание баллов и кэшбэк — обе операции в бонусный леджер.
    if spend > 0:
        credit_bonus(db, user.id, -spend, f"Оплата баллами заказа №{order.id}", order_id=order.id)
    # Кэшбэк начисляем с фактически оплаченной суммы (после списания баллов).
    cashback = cashback_for_order(order.total_amount)
    if cashback > 0:
        credit_bonus(db, user.id, cashback, f"Кэшбэк за заказ №{order.id}", order_id=order.id)
    if spend > 0 or cashback > 0:
        db.commit()

    # Уведомления шлём фоном: ответ не ждёт сети, а сбой Telegram не ломает заказ.
    # Текст собираем сейчас, пока сессия жива (в фоне ORM-объект может отвязаться).
    summary = order_summary(order)
    if user.tg_id:
        background_tasks.add_task(send_message, user.tg_id, summary)
    if settings.admin_tg_id:
        admin_text = (
            f"🆕 <b>Новый заказ №{order.id}</b>\n"
            f"{order.delivery_name} · {order.delivery_phone}\n\n" + summary
        )
        background_tasks.add_task(send_message, settings.admin_tg_id, admin_text)

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
