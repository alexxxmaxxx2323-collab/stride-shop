"""Бонусные баллы и реферальная программа.

Баланс — это всегда сумма операций в bonus_transactions (леджер), а не
отдельное число. Так история «как копятся/тратятся» строится из реальных
начислений: кэшбэк за заказы и реферальные бонусы.
"""
from __future__ import annotations

import secrets

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import BonusTransaction, User

# Правила программы (в одном месте, чтобы легко менять).
CASHBACK_PCT = 5          # % от суммы заказа возвращается баллами
REFERRER_BONUS = 500      # баллов пригласившему за каждого друга
REFERRED_BONUS = 300      # баллов новому пользователю за регистрацию по коду

# Без похожих символов (0/O, 1/I) — код диктуют голосом/переписывают вручную.
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_referral_code(db: Session) -> str:
    """Уникальный 6-значный код. Повторяем при коллизии (их почти не бывает)."""
    for _ in range(25):
        code = "".join(secrets.choice(_ALPHABET) for _ in range(6))
        if db.scalar(select(User).where(User.referral_code == code)) is None:
            return code
    raise RuntimeError("Не удалось сгенерировать уникальный реферальный код")


def ensure_referral_code(db: Session, user: User) -> str:
    """Вернуть код пользователя, создав его при первом обращении."""
    if not user.referral_code:
        user.referral_code = generate_referral_code(db)
        db.commit()
    return user.referral_code


def bonus_balance(db: Session, user_id: int) -> int:
    """Текущий баланс баллов = сумма всех операций."""
    return int(
        db.scalar(
            select(func.coalesce(func.sum(BonusTransaction.amount), 0)).where(
                BonusTransaction.user_id == user_id
            )
        )
        or 0
    )


def credit_bonus(
    db: Session, user_id: int, amount: int, reason: str, order_id: int | None = None
) -> BonusTransaction:
    """Добавить операцию в леджер (не коммитит — коммит на стороне вызывающего)."""
    tx = BonusTransaction(user_id=user_id, amount=amount, reason=reason, order_id=order_id)
    db.add(tx)
    return tx


def cashback_for_order(total_amount: int) -> int:
    """Сколько баллов вернётся за заказ на сумму total_amount."""
    return total_amount * CASHBACK_PCT // 100


def apply_referral(db: Session, new_user: User, code: str | None) -> None:
    """Привязать новичка к пригласившему по коду и начислить бонусы обоим.

    Идемпотентно по факту: если referred_by уже стоит — ничего не делаем.
    Не коммитит — это часть транзакции регистрации.
    """
    if not code or new_user.referred_by:
        return
    referrer = db.scalar(select(User).where(User.referral_code == code.strip().upper()))
    if referrer is None or referrer.id == new_user.id:
        return
    new_user.referred_by = referrer.id
    credit_bonus(db, referrer.id, REFERRER_BONUS, "Реферальный бонус за друга")
    credit_bonus(db, new_user.id, REFERRED_BONUS, "Бонус за регистрацию по приглашению")
