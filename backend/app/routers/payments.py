import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.db import get_db
from app.models import BonusTransaction, Order, User
from app.services import yookassa_pay
from app.services.bonus import cashback_for_order, credit_bonus
from app.services.order_notify import notify_payment_received

log = logging.getLogger("app.payments")

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


def _settle_paid(
    db: Session, background_tasks: BackgroundTasks, order: Order, method: str
) -> None:
    """Отметить заказ оплаченным онлайн — идемпотентно.

    Безопасно вызывать несколько раз (повторная сверка + webhook): если заказ
    уже paid, ничего не делаем — кэшбэк и уведомление не дублируются.
    Оплата и исполнение — независимые оси: меняем только статус ОПЛАТЫ,
    статус исполнения ведётся отдельно (app/services/order_status.py).
    """
    if order.payment_status == "paid":
        return
    order.payment_method = method
    order.payment_status = "paid"
    db.commit()
    _credit_cashback_once(db, order)
    notify_payment_received(background_tasks, db, order)


def _load_own_order(db: Session, order_id: int, user: User) -> Order:
    order = db.get(Order, order_id)
    if order is None or order.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    return order


# ────────────────────────── config ──────────────────────────


class PayConfigOut(BaseModel):
    yookassa_enabled: bool
    test_mode: bool


@router.get("/config", response_model=PayConfigOut)
def pay_config() -> PayConfigOut:
    """Фронт спрашивает, чем оплачивать: реальным виджетом ЮKassa или mock'ом."""
    return PayConfigOut(yookassa_enabled=yookassa_pay.is_enabled(), test_mode=True)


# ────────────────────────── ЮKassa ──────────────────────────


class YkCreateIn(BaseModel):
    order_id: int


class YkCreateOut(BaseModel):
    confirmation_token: str


@router.post("/yookassa/create", response_model=YkCreateOut)
def yookassa_create(
    data: YkCreateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> YkCreateOut:
    """Создать платёж в ЮKassa и вернуть confirmation_token для встроенного виджета."""
    if not yookassa_pay.is_enabled():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "ЮKassa не настроена")
    order = _load_own_order(db, data.order_id, user)
    if order.payment_status in ("paid", "cod"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Заказ уже оплачен")

    # yk=1 — маркер возврата из виджета: на нём фронт сверяет статус оплаты.
    return_url = f"{settings.site_url}/static/payment.html?order={order.id}&yk=1"
    try:
        payment_id, token = yookassa_pay.create_embedded_payment(
            order_id=order.id,
            amount=order.total_amount,
            description=f"Заказ №{order.id} в STRIDE",
            return_url=return_url,
        )
    except Exception as e:  # noqa: BLE001 — не отдаём наружу детали платёжки
        log.exception("yookassa create failed for order %s: %s", order.id, e)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Не удалось создать платёж")

    order.yookassa_payment_id = payment_id
    db.commit()
    return YkCreateOut(confirmation_token=token)


class YkCheckOut(BaseModel):
    payment_status: str


@router.post("/yookassa/check", response_model=YkCheckOut)
def yookassa_check(
    data: YkCreateIn,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> YkCheckOut:
    """Серверная сверка статуса платежа (вызывается фронтом на возврате из виджета).

    Достоверный статус берём из API ЮKassa — это работает и локально без
    публичного webhook'а. Если платёж succeeded — отмечаем заказ оплаченным.
    """
    order = _load_own_order(db, data.order_id, user)
    if order.payment_status == "paid":
        return YkCheckOut(payment_status="paid")
    if not order.yookassa_payment_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Платёж не создавался")

    try:
        info = yookassa_pay.fetch_payment(order.yookassa_payment_id)
    except Exception as e:  # noqa: BLE001
        log.exception("yookassa check failed for order %s: %s", order.id, e)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Не удалось проверить платёж")

    if info["status"] == "succeeded":
        _settle_paid(db, background_tasks, order, info["method"])
    return YkCheckOut(payment_status=order.payment_status)


@router.post("/yookassa/webhook")
async def yookassa_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    """Webhook ЮKassa (для прода). На payment.succeeded перезапрашиваем платёж
    у ЮKassa (не доверяем телу запроса) и отмечаем заказ оплаченным.

    Всегда отвечаем 200 — иначе ЮKassa будет ретраить. Своих заказов по
    payment_id не нашли / событие не то — просто игнорируем.
    """
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return {"ok": True}

    if body.get("event") != "payment.succeeded":
        return {"ok": True}
    payment_id = (body.get("object") or {}).get("id")
    if not payment_id:
        return {"ok": True}

    order = db.scalar(select(Order).where(Order.yookassa_payment_id == payment_id))
    if order is None:
        return {"ok": True}
    try:
        info = yookassa_pay.fetch_payment(payment_id)
        if info["status"] == "succeeded":
            _settle_paid(db, background_tasks, order, info["method"])
    except Exception as e:  # noqa: BLE001
        log.exception("yookassa webhook verify failed (order %s): %s", order.id, e)
    return {"ok": True}


# ────────────────────────── mock (фоллбэк + оплата при получении) ──────────────────────────


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

    Используется для оплаты «при получении» (cod) всегда, а для card/sbp —
    только когда ЮKassa не настроена (демо-режим без реального платежа).
    """
    order = _load_own_order(db, data.order_id, user)

    method = data.method if data.method in ("sbp", "card", "cod") else "card"
    if method == "cod":
        # Оплата при получении: онлайн-платежа нет, кэшбэк не начисляется.
        order.payment_method = "cod"
        order.payment_status = "cod"
        db.commit()
    else:
        _settle_paid(db, background_tasks, order, method)

    return MockPayOut(
        success=True, order_id=order.id,
        payment_status=order.payment_status, payment_method=order.payment_method or method,
    )
