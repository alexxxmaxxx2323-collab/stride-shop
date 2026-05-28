from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    brand_id: int
    category_id: int
    name: str = Field(min_length=1, max_length=128)
    slug: str = Field(min_length=1, max_length=128, pattern=r"^[a-z0-9-]+$")
    description: str = ""
    price: int = Field(ge=0)
    price_old: int | None = Field(default=None, ge=0)
    rating: float = Field(default=0.0, ge=0, le=5)


class ProductUpdate(BaseModel):
    brand_id: int | None = None
    category_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=128)
    slug: str | None = Field(default=None, min_length=1, max_length=128, pattern=r"^[a-z0-9-]+$")
    description: str | None = None
    price: int | None = Field(default=None, ge=0)
    price_old: int | None = Field(default=None, ge=0)
    rating: float | None = Field(default=None, ge=0, le=5)
