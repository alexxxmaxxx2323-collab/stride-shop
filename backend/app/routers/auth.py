import json
import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
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
from app.schemas.auth import (
    ChangePasswordIn,
    CheckoutRegisterIn,
    LoginIn,
    ProfileUpdateIn,
    RegisterIn,
    TgWebAppIn,
    TokenOut,
    UserOut,
)
from app.services.bonus import apply_referral
from app.services.email import send_verification_email

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(
    data: RegisterIn, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
) -> TokenOut:
    if db.scalar(select(User).where(User.email == data.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    token = secrets.token_urlsafe(32)
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        email_verify_token=token,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    # Реферальный бонус, если пришёл по чьей-то ссылке (?ref=CODE).
    apply_referral(db, user, data.ref)
    db.commit()
    background_tasks.add_task(send_verification_email, user.email, token, user.first_name)
    return TokenOut(access_token=create_access_token(user.id))


@router.post("/guest", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def guest(db: Session = Depends(get_db)) -> TokenOut:
    """Анонимная гостевая сессия: токен для корзины/избранного без регистрации."""
    user = User(is_guest=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenOut(access_token=create_access_token(user.id))


@router.post("/checkout-register", response_model=TokenOut)
def checkout_register(
    data: CheckoutRegisterIn,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TokenOut:
    """Авторегистрация на чекауте: достраиваем текущего гостя до полноценного
    аккаунта (корзина и избранное при этом сохраняются — это тот же user)."""
    # Если e-mail уже принадлежит другому аккаунту — не «угоняем» его, просим войти.
    existing = db.scalar(select(User).where(User.email == data.email))
    if existing is not None and existing.id != user.id:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Этот e-mail уже зарегистрирован — войдите в аккаунт",
        )

    user.first_name = data.first_name
    user.last_name = data.last_name
    user.phone = data.phone
    user.marketing_consent = data.marketing_consent
    user.is_guest = False

    # Письмо-подтверждение шлём только при первом назначении/смене e-mail.
    send_confirmation = user.email != data.email or not user.email_verified
    if user.email != data.email:
        user.email = data.email
        user.email_verified = False
    if send_confirmation:
        token = secrets.token_urlsafe(32)
        user.email_verify_token = token

    apply_referral(db, user, data.ref)
    db.commit()
    db.refresh(user)

    if send_confirmation and user.email_verify_token:
        background_tasks.add_task(
            send_verification_email, user.email, user.email_verify_token, user.first_name
        )
    return TokenOut(access_token=create_access_token(user.id))


@router.get("/verify-email", response_class=HTMLResponse)
def verify_email(token: str, db: Session = Depends(get_db)) -> HTMLResponse:
    """Переход по ссылке из письма — помечаем e-mail подтверждённым."""
    user = db.scalar(select(User).where(User.email_verify_token == token))
    if user is None:
        body = "<h2>Ссылка недействительна или уже использована.</h2>"
    else:
        user.email_verified = True
        user.email_verify_token = None
        db.commit()
        body = "<h2>E-mail подтверждён ✓</h2><p>Спасибо! Можете вернуться в магазин.</p>"
    html = (
        '<div style="font-family:Arial,sans-serif;text-align:center;margin-top:80px;color:#111">'
        f"{body}"
        '<p style="margin-top:24px"><a href="/static/shop.html" '
        'style="color:#f5163f">← В магазин</a></p></div>'
    )
    return HTMLResponse(html)


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
    try:
        tg_user = json.loads(user_field)
        tg_id = int(tg_user["id"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Malformed user field in initData")

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


@router.post("/resend-verification", response_model=UserOut)
def resend_verification(
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Повторно выслать письмо подтверждения e-mail (кнопка в личном кабинете)."""
    if not user.email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "К аккаунту не привязан e-mail")
    if user.email_verified:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "E-mail уже подтверждён")
    token = secrets.token_urlsafe(32)
    user.email_verify_token = token
    db.commit()
    db.refresh(user)
    background_tasks.add_task(send_verification_email, user.email, token, user.first_name)
    return user


@router.patch("/me", response_model=UserOut)
def update_me(
    data: ProfileUpdateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Редактирование профиля в личном кабинете: имя/фамилия/телефон/согласие.
    Меняем только присланные поля (partial update); e-mail здесь не трогаем —
    его смена требует повторного подтверждения и идёт отдельным флоу."""
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    data: ChangePasswordIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Смена пароля из личного кабинета: проверяем текущий, ставим новый."""
    if user.password_hash is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "У аккаунта нет пароля — вход через Telegram или гостевой режим",
        )
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Текущий пароль неверный")
    user.password_hash = hash_password(data.new_password)
    db.commit()


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return user  # type: ignore[return-value]
