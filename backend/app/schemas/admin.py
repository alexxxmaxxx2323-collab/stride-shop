from pydantic import BaseModel, Field, model_validator

from app.schemas.order import OrderOut


class ProductCreate(BaseModel):
    brand_id: int
    category_id: int
    name: str = Field(min_length=1, max_length=128)
    slug: str = Field(min_length=1, max_length=128, pattern=r"^[a-z0-9-]+$")
    description: str = ""
    price: int = Field(ge=0)
    price_old: int | None = Field(default=None, ge=0)
    rating: float = Field(default=0.0, ge=0, le=5)
    # Состав / характеристики (блок «Состав» в карточке товара)
    upper: str = Field(default="", max_length=128)
    lining: str = Field(default="", max_length=128)
    sole: str = Field(default="", max_length=128)
    season: str = Field(default="", max_length=64)
    country: str = Field(default="", max_length=64)

    @model_validator(mode="after")
    def check_price_old(self):
        if self.price_old is not None and self.price_old <= self.price:
            raise ValueError("price_old должна быть больше price (это старая цена до скидки)")
        return self


class ProductUpdate(BaseModel):
    brand_id: int | None = None
    category_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=128)
    slug: str | None = Field(default=None, min_length=1, max_length=128, pattern=r"^[a-z0-9-]+$")
    description: str | None = None
    price: int | None = Field(default=None, ge=0)
    price_old: int | None = Field(default=None, ge=0)
    rating: float | None = Field(default=None, ge=0, le=5)
    upper: str | None = Field(default=None, max_length=128)
    lining: str | None = Field(default=None, max_length=128)
    sole: str | None = Field(default=None, max_length=128)
    season: str | None = Field(default=None, max_length=64)
    country: str | None = Field(default=None, max_length=64)


class ReviewCreate(BaseModel):
    author: str = Field(min_length=1, max_length=64)
    rating: int = Field(ge=1, le=5)
    text: str = Field(min_length=1)


class VariantCreate(BaseModel):
    color_name: str = Field(min_length=1, max_length=64)
    # #RRGGBB или #RRGGBBAA — как в модели ProductVariant.color_hex
    color_hex: str = Field(pattern=r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")


class StockItem(BaseModel):
    size: int = Field(ge=30, le=50)
    quantity: int = Field(ge=0)


class StockUpdate(BaseModel):
    items: list[StockItem]


# ---------- Заказы в админке ----------
class StatusOption(BaseModel):
    code: str
    label: str


class OrderStatusUpdate(BaseModel):
    status: str


class AdminOrderOut(OrderOut):
    """Заказ для админки: данные заказа + человекочитаемые метки и доступные
    следующие статусы (для кнопок смены статуса)."""

    status_label: str
    payment_label: str
    allowed_next: list[StatusOption]
