import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

_VOWELS = set("аеёиоуыэюяaeiouy")
# Разрешённые в адресе символы: буквы, цифры, пробел и обычная адресная пунктуация.
_ADDRESS_ALLOWED = re.compile(r"^[А-Яа-яЁёA-Za-z0-9\s.,\-/№#()\"'’]+$")
_LETTER_TOKEN = re.compile(r"[А-Яа-яЁёA-Za-z]+")


def _looks_like_gibberish(v: str) -> bool:
    """Грубая эвристика «это не слова, а набор букв» — без обращения в сеть.

    Ловит кракозябры вида «фывфыв», «qwerty», «ййййй» до того, как мы
    дёрнем геокодер. Реальные слова почти всегда содержат гласные и не
    состоят из десятка одинаковых букв подряд.
    """
    if re.search(r"(.)\1{4,}", v):  # 5+ одинаковых символов подряд
        return True
    tokens = _LETTER_TOKEN.findall(v)
    if not tokens:
        return True  # вообще нет буквенных слов — только цифры/символы
    for tok in tokens:
        if len(tok) >= 4 and not (set(tok.lower()) & _VOWELS):
            return True  # длинное «слово» без единой гласной
    return False


class OrderCreate(BaseModel):
    delivery_name: str = Field(min_length=2, max_length=128)
    delivery_phone: str
    delivery_address: str = Field(min_length=5, max_length=512)
    delivery_type: str = "courier"          # courier | pickup
    pickup_code: str | None = None          # код ПВЗ CDEK при delivery_type=pickup
    use_points: int = Field(default=0, ge=0)  # списать столько бонусных баллов (1 балл = 1 ₽)

    @field_validator("delivery_type")
    @classmethod
    def check_type(cls, v: str) -> str:
        if v not in ("courier", "pickup"):
            raise ValueError("delivery_type должен быть courier или pickup")
        return v

    @field_validator("delivery_phone")
    @classmethod
    def normalize_phone(cls, v: str) -> str:
        digits = "".join(c for c in v if c.isdigit())
        # 11 цифр, начинаются с 7 или 8, мобильный код = 9XX
        if len(digits) == 11 and digits[0] in ("7", "8") and digits[1] == "9":
            return "+7" + digits[1:]
        raise ValueError("Введите телефон в формате +7 9XX XXX-XX-XX")

    @field_validator("delivery_address")
    @classmethod
    def validate_address(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Адрес слишком короткий — укажите город, улицу и дом")
        if not _ADDRESS_ALLOWED.match(v):
            raise ValueError("В адресе есть недопустимые символы")
        if "," not in v:
            raise ValueError("Адрес через запятые: Москва, ул. Тверская, д. 1")
        if not any(c.isdigit() for c in v):
            raise ValueError("В адресе должен быть номер дома")
        if _looks_like_gibberish(v):
            raise ValueError("Похоже на случайный набор символов — введите настоящий адрес")
        return v


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    variant_id: int | None
    product_name: str
    product_image: str
    color_name: str
    size: int
    quantity: int
    unit_price: int
    subtotal: int


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    payment_status: str
    total_amount: int
    delivery_name: str
    delivery_phone: str
    delivery_address: str
    delivery_type: str
    pickup_code: str | None
    payment_method: str | None
    created_at: datetime
    items: list[OrderItemOut]


class OrderCreatedOut(BaseModel):
    """Ответ на POST /orders — заказ + URL страницы оплаты."""

    order: OrderOut
    payment_url: str
