"""Сквозная проверка ссылки подтверждения e-mail из письма.

Создаёт двух тех-пользователей с настоящими токенами:
  - PROOF — токен печатается, им проверяем эндпоинт server-side (curl);
  - EMAIL — реальное письмо уходит на указанный ящик, ссылку кликает человек.
После клика смотрим в БД, что email_verified стал True (см. _verify_link_check.py).

Запуск (из backend, сервер на 8077 поднят, .env с SMTP):
    .venv\\Scripts\\python.exe _verify_link_test.py [куда@слать]
"""
import secrets
import sys

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import User
from app.services.email import send_verification_email

to = sys.argv[1] if len(sys.argv) > 1 else settings.smtp_user


def make_user(db, email: str) -> str:
    """Создать (или пересоздать) тех-юзера с новым токеном. Вернуть токен."""
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        db.delete(existing)
        db.commit()
    token = secrets.token_urlsafe(32)
    db.add(User(email=email, first_name="Александр",
               email_verify_token=token, email_verified=False))
    db.commit()
    return token


with SessionLocal() as db:
    proof_token = make_user(db, "linktest-proof@stride.local")
    email_token = make_user(db, "linktest-email@stride.local")

base = settings.site_url
print("== PROOF (для server-side curl) ==")
print(f"PROOF_URL={base}/auth/verify-email?token={proof_token}")
print("\n== EMAIL (уйдёт человеку на почту) ==")
print(f"EMAIL_URL={base}/auth/verify-email?token={email_token}")

send_verification_email(to, token=email_token, first_name="Александр")
print(f"\nПисьмо с настоящей ссылкой отправлено на {to}.")
