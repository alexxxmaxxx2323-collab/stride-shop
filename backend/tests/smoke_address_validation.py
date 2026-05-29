"""Самотест валидации адреса — на уровне схемы, без сети.

Проверяем эвристику OrderCreate.delivery_address: реальные адреса проходят,
кракозябры и явный мусор отсекаются ещё до обращения к геокодеру.
"""
from __future__ import annotations

import sys

from pydantic import ValidationError

from app.schemas.order import OrderCreate

PHONE = "+79991234567"

GOOD = [
    "Москва, ул. Тверская, д. 7",
    "Санкт-Петербург, Невский проспект, 28",
    "Казань, ул. Баумана, д. 3, кв. 12",
    "Екатеринбург, проспект Ленина, 50",
]

# Что гарантированно ловит эвристика (без сети). Кракозябры с гласными
# («фыва, фыва, 1») здесь НЕ проверяем — их по дизайну отсекает геокодер
# при создании заказа, см. smoke-проверку с запущенным сервером.
BAD = [
    ("ййййййй, д. 1", "повтор одного символа"),
    ("Москва, ул. Пшщщщ, д. 1", "слово без единой гласной"),
    ("Москва Тверская 7", "нет запятых"),
    ("Москва, Тверская", "нет номера дома"),
    ("дом, 1", "слишком короткий"),
    ("Москва, ул. Тверская!!!@@@ 7", "недопустимые символы"),
    ("123, 456, 789", "нет ни одного слова"),
]


def _make(addr: str) -> None:
    OrderCreate(delivery_name="Alice", delivery_phone=PHONE, delivery_address=addr)


def main() -> int:
    for addr in GOOD:
        try:
            _make(addr)
            print(f"OK  принят: {addr}")
        except ValidationError as e:
            print(f"FAIL реальный адрес отклонён: {addr}\n     {e}")
            return 1

    for addr, why in BAD:
        try:
            _make(addr)
            print(f"FAIL мусор прошёл ({why}): {addr}")
            return 1
        except ValidationError:
            print(f"OK  отклонён ({why}): {addr}")

    print("\nALL ADDRESS VALIDATION CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
