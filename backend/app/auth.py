"""Хэш паролей, JWT и проверка подписи Telegram WebApp initData."""
from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(user_id: int) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_ttl_minutes)
    payload = {"sub": str(user_id), "exp": expires}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token required")
    try:
        payload = jwt.decode(
            creds.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


def verify_tg_init_data(init_data: str, max_age_seconds: int = 86400) -> dict:
    """Проверка подписи initData из Telegram WebApp по алгоритму из доков TG."""
    if not settings.tg_bot_token:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "TG_BOT_TOKEN is not configured"
        )

    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing hash in initData")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(
        b"WebAppData", settings.tg_bot_token.encode(), hashlib.sha256
    ).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid initData signature")

    auth_date = int(parsed.get("auth_date", 0))
    if auth_date and datetime.now(timezone.utc).timestamp() - auth_date > max_age_seconds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "initData expired")

    return parsed
