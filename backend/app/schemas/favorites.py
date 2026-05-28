from pydantic import BaseModel

from app.schemas.catalog import ProductOut


class FavoriteIn(BaseModel):
    product_id: int


class FavoriteOut(BaseModel):
    product: ProductOut
