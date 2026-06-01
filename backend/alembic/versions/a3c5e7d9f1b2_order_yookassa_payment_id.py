"""add yookassa_payment_id to orders

Revision ID: a3c5e7d9f1b2
Revises: f2b3c4d5e6f7
Create Date: 2026-06-01 09:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3c5e7d9f1b2'
down_revision: Union[str, None] = 'f2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('yookassa_payment_id', sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_column('yookassa_payment_id')
