from pydantic import BaseModel, ConfigDict


class BrandOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str


class VariantImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    url: str
    sort_order: int


class VariantStockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    size: int
    quantity: int


class VariantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    color_name: str
    color_hex: str
    images: list[VariantImageOut]
    stocks: list[VariantStockOut]
    available_sizes: list[int]


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    description: str
    price: int
    price_old: int | None
    discount_pct: int | None
    primary_image: str
    rating: float
    all_sizes: list[int]
    in_stock: bool
    brand: BrandOut
    category: CategoryOut
    variants: list[VariantOut]


class ProductListOut(BaseModel):
    items: list[ProductOut]
    total: int
    page: int
    page_size: int
    pages: int
