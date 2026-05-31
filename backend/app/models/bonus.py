from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class BonusTransaction(Base):
    """Леджер бонусных баллов. Баланс = сумма всех amount по пользователю.

    Начисление (amount > 0): кэшбэк за заказ, реферальные бонусы.
    Списание (amount < 0): оплата баллами (на будущее).
    Так история «как копятся/тратятся» строится из реальных операций,
    а не из захардкоженного числа.
    """

    __tablename__ = "bonus_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # + начисление, − списание
    reason: Mapped[str] = mapped_column(String(128), nullable=False)
    # Привязка к заказу, если начисление — кэшбэк (для дедупликации/показа).
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
