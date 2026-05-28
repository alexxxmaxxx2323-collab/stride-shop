from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrderCreate(BaseModel):
    delivery_name: str = Field(min_length=2, max_length=128)
    delivery_phone: str
    delivery_address: str = Field(min_length=5, max_length=512)

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
        if "," not in v:
            raise ValueError("Адрес через запятые: Москва, ул. Тверская, д. 1")
        if not any(c.isdigit() for c in v):
            raise ValueError("В адресе должен быть номер дома")
        return v


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int | None
    product_name: str
    product_image: str
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
    created_at: datetime
    items: list[OrderItemOut]


class OrderCreatedOut(BaseModel):
    """Ответ на POST /orders — заказ + URL страницы оплаты."""

    order: OrderOut
    payment_url: str
