"""Интеграция с ЮKassa — приём онлайн-оплаты (тестовый магазин / песочница).

При пустых ``yookassa_shop_id``/``yookassa_secret_key`` интеграция выключена
(``is_enabled() == False``) и фронт работает в режиме mock-заглушки.

Платёж создаётся со встроенным виджетом (``confirmation.type = embedded``) —
покупатель платит, не уходя со страницы оплаты. Достоверный статус платежа мы
никогда не берём из ответа фронта: подтверждаем либо серверной сверкой
(``fetch_payment`` → запрос в API ЮKassa), либо webhook'ом ``payment.succeeded``
(который тоже перезапрашивает платёж). Обе ветки идемпотентны.
"""
import logging
import uuid

from app.config import settings

log = logging.getLogger("app.yookassa")

# ЮKassa → наши короткие коды способа оплаты (для order.payment_method).
_METHOD_MAP = {"sbp": "sbp", "bank_card": "card"}


def is_enabled() -> bool:
    """Настроена ли ЮKassa. Если нет — оплата идёт через mock-заглушку."""
    return bool(settings.yookassa_shop_id and settings.yookassa_secret_key)


def _configure() -> None:
    # Configuration в SDK — глобальное состояние модуля; задаём перед каждым
    # вызовом (дёшево) — креды могут поменяться без перезапуска процесса.
    from yookassa import Configuration

    Configuration.account_id = settings.yookassa_shop_id
    Configuration.secret_key = settings.yookassa_secret_key


def create_embedded_payment(
    *, order_id: int, amount: int, description: str, return_url: str
) -> tuple[str, str]:
    """Создаёт платёж со встроенным виджетом.

    Возвращает ``(payment_id, confirmation_token)``. Способ оплаты (карта/СБП/
    кошельки) выбирает сам виджет — мы его не ограничиваем.
    """
    from yookassa import Payment

    _configure()
    payment = Payment.create(
        {
            "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
            "capture": True,  # одностадийная оплата: списываем сразу
            "confirmation": {"type": "embedded", "return_url": return_url},
            "description": description,
            "metadata": {"order_id": order_id},
        },
        str(uuid.uuid4()),  # ключ идемпотентности — защита от дублей при ретраях
    )
    return payment.id, payment.confirmation.confirmation_token


def fetch_payment(payment_id: str) -> dict:
    """Достоверный статус платежа из API ЮKassa.

    ``status``: ``pending`` | ``waiting_for_capture`` | ``succeeded`` | ``canceled``.
    ``method``: наш короткий код (``sbp``/``card``) или исходный тип ЮKassa.
    """
    from yookassa import Payment

    _configure()
    p = Payment.find_one(payment_id)
    raw_method = getattr(p.payment_method, "type", None) if p.payment_method else None
    return {
        "status": p.status,
        "paid": bool(p.paid),
        "method": _METHOD_MAP.get(raw_method, "card"),
    }
