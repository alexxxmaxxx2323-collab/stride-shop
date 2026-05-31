from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Notification(Base):
    """In-app уведомление покупателя (лента в личном кабинете).

    Создаётся параллельно с отправкой в Telegram/e-mail — на каждое событие
    заказа (смена статуса исполнения, успешная оплата). Непрочитанные считаются
    для «красного кружка» с числом в шапке/навигации.
    """

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    body: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    # Краткая строка о составе заказа: «Nike Air Force 1 · Белый, р.42 · 11 988 ₽ · арт. …»
    detail: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # Фото главного товара заказа (для миниатюры в ленте ЛК).
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Slug главного товара — для ссылки на его карточку из уведомления.
    product_slug: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Привязка к заказу (если уведомление про заказ) — для перехода в «Мои заказы».
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
