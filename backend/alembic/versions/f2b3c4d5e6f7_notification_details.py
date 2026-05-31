"""Детали заказа в уведомлении: краткая строка, фото товара, slug для ссылки.

Revision ID: f2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-05-31 23:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2b3c4d5e6f7"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("notifications") as batch:
        batch.add_column(sa.Column("detail", sa.String(length=256), nullable=True))
        batch.add_column(sa.Column("image_url", sa.String(length=512), nullable=True))
        batch.add_column(sa.Column("product_slug", sa.String(length=128), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("notifications") as batch:
        batch.drop_column("product_slug")
        batch.drop_column("image_url")
        batch.drop_column("detail")
