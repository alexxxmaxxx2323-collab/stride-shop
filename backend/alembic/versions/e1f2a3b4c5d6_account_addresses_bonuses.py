"""Личный кабинет: адресная книга, бонусный леджер, поля профиля (размер, SMS, рефералка).

Revision ID: e1f2a3b4c5d6
Revises: d1e2f3a4b5c6
Create Date: 2026-05-31 20:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Новые поля пользователя
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("sms_consent", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("preferred_size", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("referral_code", sa.String(length=16), nullable=True))
        batch.add_column(sa.Column("referred_by", sa.Integer(), nullable=True))
        batch.create_index("ix_users_referral_code", ["referral_code"], unique=True)

    # 2) Адресная книга
    op.create_table(
        "addresses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recipient", sa.String(length=128), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("full_address", sa.String(length=512), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_addresses_user_id", "addresses", ["user_id"])

    # 3) Леджер бонусов
    op.create_table(
        "bonus_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=128), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_bonus_transactions_user_id", "bonus_transactions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_bonus_transactions_user_id", table_name="bonus_transactions")
    op.drop_table("bonus_transactions")
    op.drop_index("ix_addresses_user_id", table_name="addresses")
    op.drop_table("addresses")
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_referral_code")
        batch.drop_column("referred_by")
        batch.drop_column("referral_code")
        batch.drop_column("preferred_size")
        batch.drop_column("sms_consent")
