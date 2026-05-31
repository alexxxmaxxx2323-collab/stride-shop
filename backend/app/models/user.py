from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)
    tg_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True, nullable=True)
    tg_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Анонимная гостевая сессия: корзина/избранное живут до авторегистрации на чекауте.
    is_guest: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Подтверждение e-mail по ссылке из письма.
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verify_token: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    # Согласие на маркетинговые уведомления (галочка на чекауте, по умолчанию включена).
    marketing_consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Согласие на SMS-уведомления (тумблер в настройках ЛК).
    sms_consent: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    # «Мой размер» обуви — для быстрой покупки и фильтра «есть в моём размере».
    preferred_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Реферальная программа: личный код (генерится при первом обращении) + кто пригласил.
    referral_code: Mapped[str | None] = mapped_column(
        String(16), unique=True, index=True, nullable=True
    )
    referred_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
