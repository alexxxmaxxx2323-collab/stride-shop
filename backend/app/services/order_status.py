"""Жизненный цикл заказа: статусы исполнения и переходы между ними.

Архитектура — две независимые оси (как в Ozon/WB/Lamoda):
  - payment_status — состояние ОПЛАТЫ (awaiting | paid | cod | refunded);
  - status         — состояние ИСПОЛНЕНИЯ заказа (этот модуль).

`status` управляется через машину состояний: из каждого статуса разрешён
только определённый набор следующих. На этапе «Передан в доставку» ветка
зависит от способа получения (курьер → «В пути», ПВЗ → «Готов к выдаче»).
"""
from __future__ import annotations

# Метки статусов исполнения для покупателя (RU). Набор — синтез реальных
# российских магазинов (WB: «Собран», «Отгружен», «В пути»; Ozon; Lamoda).
STATUS_LABELS: dict[str, str] = {
    "pending": "В обработке",
    "assembling": "Собирается",
    "shipped": "Передан в доставку",
    "in_transit": "В пути",
    "ready_for_pickup": "Готов к выдаче",
    "delivered": "Доставлен",
    "delivery_failed": "Ошибка доставки",
    "cancelled": "Отменён",
    "returned": "Возврат",
}

# Метки статуса оплаты (вторая ось).
PAYMENT_LABELS: dict[str, str] = {
    "awaiting": "Ожидает оплаты",
    "paid": "Оплачен",
    "cod": "Оплата при получении",
    "refunded": "Возврат оформлен",
}

# Базовый граф переходов (до уточнения по способу доставки).
_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["assembling", "cancelled"],
    "assembling": ["shipped", "cancelled"],
    "shipped": ["in_transit", "ready_for_pickup", "cancelled"],
    "in_transit": ["delivered", "delivery_failed"],
    "ready_for_pickup": ["delivered", "delivery_failed"],
    "delivery_failed": ["in_transit", "ready_for_pickup", "returned", "cancelled"],
    "delivered": ["returned"],
    "cancelled": [],
    "returned": [],
}

# Покупатель может отменить заказ сам только пока он не передан в доставку.
CUSTOMER_CANCELLABLE: set[str] = {"pending", "assembling"}

# При входе в эти статусы откатываем бонусы заказа (возврат списанных баллов,
# снятие начисленного кэшбэка) и помечаем оплату возвращённой.
REVERSAL_STATUSES: set[str] = {"cancelled", "returned"}

INITIAL_STATUS = "pending"


def _delivery_leg_filter(nxt: list[str], delivery_type: str) -> list[str]:
    """На «доставочной развилке» оставляем ветку под способ получения."""
    if delivery_type == "pickup":
        return [s for s in nxt if s != "in_transit"]
    return [s for s in nxt if s != "ready_for_pickup"]


def allowed_transitions(status: str, delivery_type: str = "courier") -> list[str]:
    """Список статусов, в которые можно перейти из текущего."""
    nxt = list(_TRANSITIONS.get(status, []))
    if status in ("shipped", "delivery_failed"):
        nxt = _delivery_leg_filter(nxt, delivery_type)
    return nxt


def can_transition(status: str, new_status: str, delivery_type: str = "courier") -> bool:
    return new_status in allowed_transitions(status, delivery_type)


def label(status: str) -> str:
    return STATUS_LABELS.get(status, status)
