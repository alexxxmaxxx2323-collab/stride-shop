"""Пользователь: телефон, гостевая сессия, подтверждение e-mail, согласие на рассылку.

Revision ID: d1e2f3a4b5c6
Revises: c3d4e5f6a7b8
Create Date: 2026-05-30 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("phone", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("is_guest", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("email_verify_token", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("marketing_consent", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.create_index("ix_users_phone", ["phone"])
        batch.create_index("ix_users_email_verify_token", ["email_verify_token"])


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_email_verify_token")
        batch.drop_index("ix_users_phone")
        batch.drop_column("marketing_consent")
        batch.drop_column("email_verify_token")
        batch.drop_column("email_verified")
        batch.drop_column("is_guest")
        batch.drop_column("phone")
