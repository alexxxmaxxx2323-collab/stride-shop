"""Схемы личного кабинета: адресная книга, бонусы, рефералка, сводка, офферы."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.auth import normalize_phone
from app.schemas.catalog import ProductOut


# ---------- Адресная книга ----------
class AddressIn(BaseModel):
    recipient: str = Field(min_length=2, max_length=128)
    phone: str
    full_address: str = Field(min_length=5, max_length=512)
    is_default: bool = False

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return normalize_phone(v)


class AddressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recipient: str
    phone: str
    full_address: str
    is_default: bool
    created_at: datetime


# ---------- Бонусы ----------
class BonusTxOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    amount: int
    reason: str
    order_id: int | None
    created_at: datetime


class BonusesOut(BaseModel):
    balance: int
    cashback_pct: int
    transactions: list[BonusTxOut]


# ---------- Реферальная программа ----------
class ReferralOut(BaseModel):
    code: str
    link: str
    invited_count: int
    earned: int
    referrer_bonus: int
    referred_bonus: int


# ---------- Сводка (дашборд) ----------
class SummaryOut(BaseModel):
    first_name: str | None
    email: str | None
    email_verified: bool
    member_since: datetime
    orders_count: int
    total_spent: int
    bonus_balance: int
    preferred_size: int | None


# ---------- Персональные предложения ----------
class OffersOut(BaseModel):
    reason: str
    products: list[ProductOut]
