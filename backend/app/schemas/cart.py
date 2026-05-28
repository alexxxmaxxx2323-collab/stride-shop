from pydantic import BaseModel, ConfigDict, Field

from app.schemas.catalog import ProductOut


class CartItemIn(BaseModel):
    product_id: int
    size: int = Field(ge=30, le=50)
    quantity: int = Field(default=1, ge=1, le=20)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1, le=20)


class CartItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product: ProductOut
    size: int
    quantity: int
    subtotal: int


class CartOut(BaseModel):
    items: list[CartItemOut]
    total: int
    items_count: int
