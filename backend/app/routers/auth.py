import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
    verify_tg_init_data,
)
from app.db import get_db
from app.models import User
from app.schemas.auth import LoginIn, RegisterIn, TgWebAppIn, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(data: RegisterIn, db: Session = Depends(get_db)) -> TokenOut:
    if db.scalar(select(User).where(User.email == data.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenOut(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    user = db.scalar(select(User).where(User.email == data.email))
    if (
        user is None
        or user.password_hash is None
        or not verify_password(data.password, user.password_hash)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    return TokenOut(access_token=create_access_token(user.id))


@router.post("/tg-webapp", response_model=TokenOut)
def tg_webapp(data: TgWebAppIn, db: Session = Depends(get_db)) -> TokenOut:
    parsed = verify_tg_init_data(data.init_data)
    user_field = parsed.get("user")
    if not user_field:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "user field missing in initData")
    tg_user = json.loads(user_field)
    tg_id = int(tg_user["id"])

    user = db.scalar(select(User).where(User.tg_id == tg_id))
    if user is None:
        user = User(
            tg_id=tg_id,
            tg_username=tg_user.get("username"),
            first_name=tg_user.get("first_name"),
            last_name=tg_user.get("last_name"),
        )
        db.add(user)
    else:
        if tg_user.get("username"):
            user.tg_username = tg_user["username"]
        if tg_user.get("first_name"):
            user.first_name = tg_user["first_name"]
        if tg_user.get("last_name"):
            user.last_name = tg_user["last_name"]
    db.commit()
    db.refresh(user)
    return TokenOut(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return user  # type: ignore[return-value]
