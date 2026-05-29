"""Карточка товара: описание бренда, состав товара (верх/подкладка/подошва/сезон/
страна) и таблица отзывов reviews.

Revision ID: a1b2c3d4e5f6
Revises: d4f2a1b8c930
Create Date: 2026-05-29 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "d4f2a1b8c930"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Описание бренда (блок «О бренде»).
    with op.batch_alter_table("brands") as batch:
        batch.add_column(
            sa.Column("description", sa.Text(), nullable=False, server_default="")
        )

    # 2. Состав / характеристики товара (блок «Состав»).
    with op.batch_alter_table("products") as batch:
        batch.add_column(sa.Column("upper", sa.String(length=128), nullable=False, server_default=""))
        batch.add_column(sa.Column("lining", sa.String(length=128), nullable=False, server_default=""))
        batch.add_column(sa.Column("sole", sa.String(length=128), nullable=False, server_default=""))
        batch.add_column(sa.Column("season", sa.String(length=64), nullable=False, server_default=""))
        batch.add_column(sa.Column("country", sa.String(length=64), nullable=False, server_default=""))

    # 3. Отзывы (блок «Отзывы»).
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("author", sa.String(length=64), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_reviews_product_id", "reviews", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_reviews_product_id", table_name="reviews")
    op.drop_table("reviews")

    with op.batch_alter_table("products") as batch:
        for col in ("country", "season", "sole", "lining", "upper"):
            batch.drop_column(col)

    with op.batch_alter_table("brands") as batch:
        batch.drop_column("description")
