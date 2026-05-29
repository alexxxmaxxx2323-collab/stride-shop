"""Заказ: способ получения (курьер/ПВЗ), код ПВЗ и способ оплаты.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-29 14:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("orders") as batch:
        batch.add_column(sa.Column("delivery_type", sa.String(length=16), nullable=False, server_default="courier"))
        batch.add_column(sa.Column("pickup_code", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("payment_method", sa.String(length=16), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch:
        batch.drop_column("payment_method")
        batch.drop_column("pickup_code")
        batch.drop_column("delivery_type")
