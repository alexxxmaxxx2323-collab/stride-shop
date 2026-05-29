"""Уведомления в Telegram через Bot API (Фаза 3.4).

Веб-приложение не использует aiogram — шлём простым HTTP-запросом к
api.telegram.org. Вызывается как фоновая задача после оформления заказа,
поэтому сетевые задержки и сбои не влияют на ответ и на сам заказ.
"""
from __future__ import annotations

import json
import logging
import urllib.request

from app.config import settings

_API = "https://api.telegram.org/bot{token}/sendMessage"


def _money(n: int) -> str:
    return f"{n:,}".replace(",", " ") + " ₽"


def send_message(chat_id: int, text: str) -> None:
    """Отправить сообщение пользователю/админу. Тихо логируем при сбое."""
    if not settings.tg_bot_token:
        return
    payload = json.dumps(
        {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    ).encode()
    req = urllib.request.Request(
        _API.format(token=settings.tg_bot_token),
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:  # noqa: BLE001 — уведомление не должно ронять заказ
        logging.warning("Telegram-уведомление не отправлено (chat %s): %s", chat_id, e)


def order_summary(order) -> str:
    """Текст сводки заказа для покупателя (HTML)."""
    lines = [f"✅ <b>Заказ №{order.id} оформлен</b>", ""]
    for it in order.items:
        lines.append(
            f"• {it.product_name} ({it.color_name}, р. {it.size}) ×{it.quantity} — {_money(it.subtotal)}"
        )
    lines += [
        "",
        f"<b>Итого: {_money(order.total_amount)}</b>",
        f"📦 {order.delivery_address}",
        "",
        "Мы свяжемся с вами для подтверждения. Спасибо за заказ! 🙌",
    ]
    return "\n".join(lines)
