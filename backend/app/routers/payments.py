from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import BonusTransaction, Order, User
from app.services.bonus import cashback_for_order, credit_bonus
from app.services.order_notify import notify_payment_received

router = APIRouter(prefix="/payments", tags=["payments"])


def _credit_cashback_once(db: Session, order: Order) -> None:
    """Начислить кэшбэк за оплаченный заказ — ровно один раз.
    Кэшбэк положен только после фактической онлайн-оплаты (payment_status=paid)."""
    if order.payment_status != "paid":
        return
    already = db.scalar(
        select(func.count(BonusTransaction.id)).where(
            BonusTransaction.order_id == order.id,
            BonusTransaction.amount > 0,
            BonusTransaction.reason.like("Кэшбэк%"),
        )
    )
    if already:
        return
    points = cashback_for_order(order.total_amount)
    if points > 0:
        credit_bonus(db, order.user_id, points, f"Кэшбэк за заказ №{order.id}", order_id=order.id)
        db.commit()


class MockPayIn(BaseModel):
    order_id: int
    method: str = "card"  # sbp | card | cod (при получении)


class MockPayOut(BaseModel):
    success: bool
    order_id: int
    payment_status: str
    payment_method: str


@router.post("/mock", response_model=MockPayOut)
def mock_pay(
    data: MockPayIn,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MockPayOut:
    """Имитация оплаты — отмечаем заказ оплаченным.
    В реальном проекте здесь интеграция с YooKassa/Stripe + проверка callback.
    """
    order = db.get(Order, data.order_id)
    if order is None or order.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")

    method = data.method if data.method in ("sbp", "card", "cod") else "card"
    order.payment_method = method
    # Оплата и исполнение — независимые оси: здесь меняем только статус ОПЛАТЫ.
    # Статус исполнения (status) остаётся «В обработке» и ведётся отдельно
    # через машину состояний (склад/доставка), см. app/services/order_status.py.
    order.payment_status = "cod" if method == "cod" else "paid"
    db.commit()

    # Кэшбэк — только после успешной онлайн-оплаты (не для «при получении»).
    _credit_cashback_once(db, order)

    # Уведомление об успешной онлайн-оплате (для «при получении» оплаты ещё нет).
    if order.payment_status == "paid":
        notify_payment_received(background_tasks, db, order)

    return MockPayOut(
        success=True, order_id=order.id,
        payment_status=order.payment_status, payment_method=method,
    )
