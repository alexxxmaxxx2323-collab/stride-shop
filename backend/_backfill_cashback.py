"""Разовый бэкфилл кэшбэка за заказы, оформленные до появления бонусной программы.

Идемпотентно: начисляет 5%-кэшбэк только тем заказам, у которых ещё нет
бонусной транзакции. Повторный запуск ничего не дублирует.

Запуск:  python _backfill_cashback.py
"""
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import BonusTransaction, Order
from app.services.bonus import cashback_for_order, credit_bonus


def main() -> None:
    db = SessionLocal()
    try:
        orders = db.scalars(select(Order).order_by(Order.id)).all()
        credited = 0
        for o in orders:
            already = db.scalar(
                select(func.count(BonusTransaction.id)).where(
                    BonusTransaction.order_id == o.id
                )
            )
            if already:
                continue
            points = cashback_for_order(o.total_amount)
            if points > 0:
                credit_bonus(
                    db, o.user_id, points, f"Кэшбэк за заказ №{o.id}", order_id=o.id
                )
                credited += 1
        db.commit()
        print(f"Заказов обработано: {len(orders)}, начислено кэшбэка: {credited}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
