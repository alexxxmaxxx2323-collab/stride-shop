"""SKU-модель: product_variants/variant_images/variant_stocks, favorites,
рефакторинг cart_items и order_items, удаление image_url/sizes/in_stock из products

Revision ID: d4f2a1b8c930
Revises: c133be69e059
Create Date: 2026-05-28 16:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4f2a1b8c930"
down_revision: Union[str, None] = "c133be69e059"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Новые таблицы под SKU-модель.
    op.create_table(
        "product_variants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("color_name", sa.String(length=64), nullable=False),
        sa.Column("color_hex", sa.String(length=9), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_product_variants_product_id", "product_variants", ["product_id"])

    op.create_table(
        "variant_images",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "variant_id",
            sa.Integer(),
            sa.ForeignKey("product_variants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_variant_images_variant_id", "variant_images", ["variant_id"])

    op.create_table(
        "variant_stocks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "variant_id",
            sa.Integer(),
            sa.ForeignKey("product_variants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("variant_id", "size", name="uq_variant_stock_size"),
    )
    op.create_index("ix_variant_stocks_variant_id", "variant_stocks", ["variant_id"])

    # 2. Favorites.
    op.create_table(
        "favorites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "product_id", name="uq_favorite_user_product"),
    )
    op.create_index("ix_favorites_user_id", "favorites", ["user_id"])
    op.create_index("ix_favorites_product_id", "favorites", ["product_id"])

    # 3. Удаляем устаревшие колонки из products.
    # На локальной SQLite-БД проще пересоздать таблицу (batch).
    with op.batch_alter_table("products", schema=None) as batch:
        batch.drop_column("image_url")
        batch.drop_column("sizes")
        batch.drop_column("in_stock")

    # 4. cart_items: product_id -> variant_id. Старые данные удаляем
    # (локальная демо-БД, корзины пересоздаются автоматически).
    op.execute("DELETE FROM cart_items")
    with op.batch_alter_table("cart_items", schema=None) as batch:
        batch.drop_index("ix_cart_items_product_id")
        batch.drop_constraint("uq_cart_item_product_size", type_="unique")
        batch.drop_column("product_id")
        batch.add_column(sa.Column("variant_id", sa.Integer(), nullable=False))
        batch.create_foreign_key(
            "fk_cart_items_variant_id",
            "product_variants",
            ["variant_id"],
            ["id"],
        )
        batch.create_unique_constraint(
            "uq_cart_item_variant_size", ["cart_id", "variant_id", "size"]
        )
        batch.create_index("ix_cart_items_variant_id", ["variant_id"])

    # 5. order_items: добавляем color_name, переименовываем product_id -> variant_id.
    # Старые заказы тоже сносим (пустая демо-БД).
    op.execute("DELETE FROM order_items")
    with op.batch_alter_table("order_items", schema=None) as batch:
        batch.add_column(
            sa.Column("color_name", sa.String(length=64), nullable=False, server_default="")
        )
        batch.drop_column("product_id")
        batch.add_column(sa.Column("variant_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_order_items_variant_id",
            "product_variants",
            ["variant_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("order_items", schema=None) as batch:
        batch.drop_constraint("fk_order_items_variant_id", type_="foreignkey")
        batch.drop_column("variant_id")
        batch.add_column(
            sa.Column(
                "product_id",
                sa.Integer(),
                sa.ForeignKey("products.id"),
                nullable=True,
            )
        )
        batch.drop_column("color_name")

    with op.batch_alter_table("cart_items", schema=None) as batch:
        batch.drop_index("ix_cart_items_variant_id")
        batch.drop_constraint("uq_cart_item_variant_size", type_="unique")
        batch.drop_constraint("fk_cart_items_variant_id", type_="foreignkey")
        batch.drop_column("variant_id")
        batch.add_column(sa.Column("product_id", sa.Integer(), nullable=False))
        batch.create_unique_constraint(
            "uq_cart_item_product_size", ["cart_id", "product_id", "size"]
        )

    with op.batch_alter_table("products", schema=None) as batch:
        batch.add_column(sa.Column("image_url", sa.String(length=512), nullable=False, server_default=""))
        batch.add_column(sa.Column("sizes", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("in_stock", sa.Boolean(), nullable=False, server_default=sa.true()))

    op.drop_index("ix_favorites_product_id", table_name="favorites")
    op.drop_index("ix_favorites_user_id", table_name="favorites")
    op.drop_table("favorites")

    op.drop_index("ix_variant_stocks_variant_id", table_name="variant_stocks")
    op.drop_table("variant_stocks")

    op.drop_index("ix_variant_images_variant_id", table_name="variant_images")
    op.drop_table("variant_images")

    op.drop_index("ix_product_variants_product_id", table_name="product_variants")
    op.drop_table("product_variants")
