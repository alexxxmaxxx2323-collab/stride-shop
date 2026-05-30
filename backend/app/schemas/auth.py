from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def normalize_phone(v: str) -> str:
    """Привести телефон к виду +79XXXXXXXXX (11 цифр, мобильный РФ)."""
    digits = "".join(c for c in v if c.isdigit())
    if len(digits) == 11 and digits[0] in ("7", "8") and digits[1] == "9":
        return "+7" + digits[1:]
    raise ValueError("Введите телефон в формате +7 9XX XXX-XX-XX")


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str | None = None
    last_name: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class CheckoutRegisterIn(BaseModel):
    """Авторегистрация на чекауте (Lamoda-стиль): имя/фамилия/телефон/почта."""

    first_name: str = Field(min_length=1, max_length=64)
    last_name: str = Field(min_length=1, max_length=64)
    phone: str
    email: EmailStr
    marketing_consent: bool = True  # галочка стоит по умолчанию

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return normalize_phone(v)


class TgWebAppIn(BaseModel):
    init_data: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str | None
    phone: str | None
    tg_id: int | None
    tg_username: str | None
    first_name: str | None
    last_name: str | None
    is_admin: bool
    is_guest: bool
    email_verified: bool
    marketing_consent: bool
    created_at: datetime
