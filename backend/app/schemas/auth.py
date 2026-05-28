from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str | None = None
    last_name: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TgWebAppIn(BaseModel):
    init_data: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str | None
    tg_id: int | None
    tg_username: str | None
    first_name: str | None
    last_name: str | None
    is_admin: bool
    created_at: datetime
