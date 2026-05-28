from pydantic import BaseModel, ConfigDict, Field

from app.schemas.catalog import ProductOut


class CartItemIn(BaseModel):
    variant_id: int
    size: int = Field(ge=30, le=50)
    quantity: int = Field(default=1, ge=1, le=20)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1, le=20)


class CartItemVariantOut(BaseModel):
    """Что показываем в строке корзины: товар + выбранный цвет."""

    id: int
    color_name: str
    color_hex: str
    image_url: str


class CartItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product: ProductOut
    variant: CartItemVariantOut
    size: int
    quantity: int
    subtotal: int


class CartOut(BaseModel):
    items: list[CartItemOut]
    total: int
    items_count: int
