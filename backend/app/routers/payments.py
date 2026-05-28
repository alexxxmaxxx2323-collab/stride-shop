from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Order, User

router = APIRouter(prefix="/payments", tags=["payments"])


class MockPayIn(BaseModel):
    order_id: int


class MockPayOut(BaseModel):
    success: bool
    order_id: int
    payment_status: str


@router.post("/mock", response_model=MockPayOut)
def mock_pay(
    data: MockPayIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MockPayOut:
    """Имитация оплаты — отмечаем заказ оплаченным.
    В реальном проекте здесь интеграция с YooKassa/Stripe + проверка callback.
    """
    order = db.get(Order, data.order_id)
    if order is None or order.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    if order.payment_status != "paid":
        order.payment_status = "paid"
        order.status = "paid"
        db.commit()
    return MockPayOut(success=True, order_id=order.id, payment_status="paid")
