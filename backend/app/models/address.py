from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Address(Base):
    """Адресная книга личного кабинета: сохранённые адреса доставки."""

    __tablename__ = "addresses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Кому/куда — повторяем поля чекаута, чтобы адрес можно было подставить одним кликом.
    recipient: Mapped[str] = mapped_column(String(128), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    full_address: Mapped[str] = mapped_column(String(512), nullable=False)
    # Адрес по умолчанию подставляется в чекаут первым. На пользователя — максимум один.
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
