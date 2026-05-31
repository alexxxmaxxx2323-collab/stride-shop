from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def normalize_phone(v: str) -> str:
    """Привести телефон к виду +79XXXXXXXXX (11 цифр, мобильный РФ)."""
    digits = "".join(c for c in v if c.isdigit())
    if len(digits) == 11 and digits[0] in ("7", "8") and digits[1] == "9":
        return "+7" + digits[1:]
    raise ValueError("Введите телефон в формате +7 9XX XXX-XX-XX")


def validate_size(v: int | None) -> int | None:
    """Размер обуви РФ — в разумных пределах (или None = не задан)."""
    if v is None:
        return None
    if not 30 <= v <= 50:
        raise ValueError("Размер должен быть в диапазоне 30–50")
    return v


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str | None = None
    last_name: str | None = None
    ref: str | None = None  # реферальный код пригласившего (?ref=CODE)


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
    ref: str | None = None  # реферальный код пригласившего

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return normalize_phone(v)


class ProfileUpdateIn(BaseModel):
    """Редактирование профиля в личном кабинете. Любое поле опционально:
    применяем только присланные (partial update через exclude_unset)."""

    first_name: str | None = Field(default=None, max_length=64)
    last_name: str | None = Field(default=None, max_length=64)
    phone: str | None = None
    marketing_consent: bool | None = None
    sms_consent: bool | None = None
    preferred_size: int | None = None

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        if v is None or v.strip() == "":
            return None
        return normalize_phone(v)

    @field_validator("preferred_size")
    @classmethod
    def _size(cls, v: int | None) -> int | None:
        return validate_size(v)


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


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
    sms_consent: bool
    preferred_size: int | None
    referral_code: str | None
    created_at: datetime
