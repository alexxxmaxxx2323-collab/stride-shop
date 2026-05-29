from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(
        Text, default="", server_default="", nullable=False
    )


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True, nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    price_old: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # Состав / характеристики (блок «Состав» в карточке)
    upper: Mapped[str] = mapped_column(String(128), default="", server_default="", nullable=False)
    lining: Mapped[str] = mapped_column(String(128), default="", server_default="", nullable=False)
    sole: Mapped[str] = mapped_column(String(128), default="", server_default="", nullable=False)
    season: Mapped[str] = mapped_column(String(64), default="", server_default="", nullable=False)
    country: Mapped[str] = mapped_column(String(64), default="", server_default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    brand: Mapped["Brand"] = relationship(lazy="joined")
    category: Mapped["Category"] = relationship(lazy="joined")
    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductVariant.sort_order",
        lazy="selectin",
    )
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="Review.created_at.desc()",
        lazy="selectin",
    )

    @property
    def review_count(self) -> int:
        return len(self.reviews)

    @property
    def discount_pct(self) -> int | None:
        if self.price_old and self.price_old > self.price:
            return round((1 - self.price / self.price_old) * 100)
        return None

    @property
    def primary_image(self) -> str:
        """Первая картинка первого варианта — для карточки в каталоге."""
        for variant in self.variants:
            if variant.images:
                return variant.images[0].url
        return "/static/products/_placeholder.png"

    @property
    def all_sizes(self) -> list[int]:
        """Объединение размеров всех вариантов где есть остаток."""
        sizes: set[int] = set()
        for variant in self.variants:
            for stock in variant.stocks:
                if stock.quantity > 0:
                    sizes.add(stock.size)
        return sorted(sizes)

    @property
    def in_stock(self) -> bool:
        return any(s.quantity > 0 for v in self.variants for s in v.stocks)


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    color_name: Mapped[str] = mapped_column(String(64), nullable=False)
    color_hex: Mapped[str] = mapped_column(String(9), nullable=False)  # #RRGGBB или #RRGGBBAA
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    product: Mapped["Product"] = relationship(back_populates="variants")
    images: Mapped[list["VariantImage"]] = relationship(
        back_populates="variant",
        cascade="all, delete-orphan",
        order_by="VariantImage.sort_order",
        lazy="selectin",
    )
    stocks: Mapped[list["VariantStock"]] = relationship(
        back_populates="variant",
        cascade="all, delete-orphan",
        order_by="VariantStock.size",
        lazy="selectin",
    )

    @property
    def available_sizes(self) -> list[int]:
        return sorted(s.size for s in self.stocks if s.quantity > 0)


class VariantImage(Base):
    __tablename__ = "variant_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    variant_id: Mapped[int] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    variant: Mapped["ProductVariant"] = relationship(back_populates="images")


class VariantStock(Base):
    __tablename__ = "variant_stocks"
    __table_args__ = (
        UniqueConstraint("variant_id", "size", name="uq_variant_stock_size"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    variant_id: Mapped[int] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    variant: Mapped["ProductVariant"] = relationship(back_populates="stocks")


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    author: Mapped[str] = mapped_column(String(64), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..5
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    product: Mapped["Product"] = relationship(back_populates="reviews")
