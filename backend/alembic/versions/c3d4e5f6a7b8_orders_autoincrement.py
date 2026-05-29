"""orders.id → AUTOINCREMENT (номера заказов не переиспользуются после удаления).

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-29 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Пересоздаём таблицу с AUTOINCREMENT (данные копируются автоматически).
    with op.batch_alter_table("orders", recreate="always", table_kwargs={"sqlite_autoincrement": True}):
        pass


def downgrade() -> None:
    with op.batch_alter_table("orders", recreate="always", table_kwargs={}):
        pass
