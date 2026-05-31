"""Виджет поддержки: бот-ассистент + передача диалога оператору в Telegram.

- GET  /support/meta     — каналы связи (Telegram/WhatsApp) и часы работы для виджета;
- POST /support/ask      — вопрос боту, ответ + быстрые подсказки (для «Где мой заказ?»
                           при наличии токена подставляем реальный статус);
- POST /support/handoff  — переслать диалог менеджеру в Telegram.

Авторизация в /ask и /handoff необязательная: виджет доступен и гостю.
"""
from __future__ import annotations

import jwt
from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import bearer_scheme
from app.config import settings
from app.db import get_db
from app.models import Order, User
from app.notifications import send_message
from app.services import order_status, support_bot

router = APIRouter(prefix="/support", tags=["support"])


def get_optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """Пользователь, если токен валиден; иначе None (виджет работает и для гостя)."""
    if creds is None:
        return None
    try:
        payload = jwt.decode(
            creds.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        return db.get(User, int(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


# ─────────────────────────── Схемы ───────────────────────────
class AskIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class AskOut(BaseModel):
    reply: str
    suggestions: list[str]


class ChatMessage(BaseModel):
    role: str  # "user" | "bot"
    text: str = Field(max_length=1000)


class HandoffIn(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list, max_length=50)
    contact: str | None = Field(default=None, max_length=120)  # как связаться (необяз.)


class HandoffOut(BaseModel):
    ok: bool
    detail: str


class SupportMeta(BaseModel):
    telegram_url: str | None
    whatsapp_url: str | None
    hours: str


# ─────────────────────────── Эндпоинты ───────────────────────────
@router.get("/meta", response_model=SupportMeta)
def meta() -> SupportMeta:
    tg = f"https://t.me/{settings.support_telegram}" if settings.support_telegram else None
    wa = f"https://wa.me/{settings.support_whatsapp}" if settings.support_whatsapp else None
    return SupportMeta(telegram_url=tg, whatsapp_url=wa, hours=settings.support_hours)


def _order_status_reply(user: User | None, db: Session) -> tuple[str, list[str]]:
    """Ответ на «Где мой заказ?» — с реальным статусом, если пользователь вошёл."""
    if user is None:
        return (
            "Чтобы показать статус, войдите в аккаунт — в личном кабинете видна вся "
            "история заказов и этапов доставки. Либо назовите номер заказа менеджеру.",
            ["Позвать менеджера", "Доставка"],
        )
    order = db.scalar(
        select(Order).where(Order.user_id == user.id).order_by(Order.id.desc())
    )
    if order is None:
        return (
            "Пока не вижу у вас оформленных заказов. Как оформите — статус появится "
            "здесь и в личном кабинете 🙌",
            ["Доставка", "Размеры", "Оплата"],
        )
    st = order_status.label(order.status)
    pay = order_status.PAYMENT_LABELS.get(order.payment_status, order.payment_status)
    return (
        f"Ваш последний заказ №{order.id}:\n"
        f"• Статус: {st}\n• Оплата: {pay}\n"
        "Подробности и все этапы — в разделе «Заказы» личного кабинета.",
        ["Доставка", "Возврат", "Позвать менеджера"],
    )


@router.post("/ask", response_model=AskOut)
def ask(
    data: AskIn,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> AskOut:
    intent = support_bot.detect_intent(data.message)
    if intent == "order_status":
        reply, chips = _order_status_reply(user, db)
    else:
        reply, chips = support_bot.static_answer(intent)
    return AskOut(reply=reply, suggestions=chips)


@router.post("/handoff", response_model=HandoffOut)
def handoff(
    data: HandoffIn,
    user: User | None = Depends(get_optional_user),
) -> HandoffOut:
    """Переслать переписку менеджеру в Telegram (settings.admin_tg_id)."""
    if not settings.admin_tg_id or not settings.tg_bot_token:
        return HandoffOut(
            ok=False,
            detail="Менеджер сейчас недоступен — напишите нам в Telegram или WhatsApp.",
        )
    who = "Гость"
    if user is not None:
        who = user.email or (user.first_name or f"user #{user.id}")
    lines = [f"🆘 <b>Запрос в поддержку</b>\nОт: {who}"]
    if data.contact:
        lines.append(f"Контакт: {data.contact}")
    lines.append("")
    for m in data.messages[-20:]:
        tag = "🧑" if m.role == "user" else "🤖"
        lines.append(f"{tag} {m.text}")
    send_message(settings.admin_tg_id, "\n".join(lines))
    return HandoffOut(ok=True, detail="Передали менеджеру — ответим в ближайшее время 🙌")
