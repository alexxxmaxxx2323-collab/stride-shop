"""Сверка кэшбэка со статусом оплаты заказа.

Кэшбэк положен ТОЛЬКО за фактически оплаченные заказы (payment_status='paid').
Скрипт идемпотентно приводит леджер в соответствие:
  - убирает кэшбэк у заказов, которые НЕ оплачены (были начислены по ошибке);
  - добавляет кэшбэк оплаченным заказам, у которых его ещё нет.
Операции «Оплата баллами» (списания) не трогаем.

Запуск:  python _backfill_cashback.py
"""
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import BonusTransaction, Order
from app.services.bonus import cashback_for_order, credit_bonus


def main() -> None:
    db = SessionLocal()
    try:
        removed = added = 0
        cashbacks = db.scalars(
            select(BonusTransaction).where(
                BonusTransaction.amount > 0,
                BonusTransaction.reason.like("Кэшбэк%"),
            )
        ).all()
        # 1) снять кэшбэк у неоплаченных заказов
        for tx in cashbacks:
            order = db.get(Order, tx.order_id) if tx.order_id else None
            if order is None or order.payment_status != "paid":
                db.delete(tx)
                removed += 1

        # 2) добавить кэшбэк оплаченным заказам без него
        paid_orders = db.scalars(
            select(Order).where(Order.payment_status == "paid")
        ).all()
        for o in paid_orders:
            has = db.scalar(
                select(func.count(BonusTransaction.id)).where(
                    BonusTransaction.order_id == o.id,
                    BonusTransaction.amount > 0,
                    BonusTransaction.reason.like("Кэшбэк%"),
                )
            )
            if not has:
                pts = cashback_for_order(o.total_amount)
                if pts > 0:
                    credit_bonus(db, o.user_id, pts, f"Кэшбэк за заказ №{o.id}", order_id=o.id)
                    added += 1
        db.commit()
        print(f"Кэшбэк-операций снято (неоплаченные): {removed}, добавлено (оплаченные): {added}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
