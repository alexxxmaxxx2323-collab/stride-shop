"""Проверка реальной отправки письма по SMTP.

Запуск (из папки backend, с заполненным .env):
    .venv\\Scripts\\python.exe _send_test_email.py you@example.com

Без аргумента шлёт на адрес из SMTP_USER (самому себе).
Печатает [email:SENT] при успехе или [email:ERROR] с причиной.
"""
import sys

from app.config import settings
from app.services.email import send_email

to = sys.argv[1] if len(sys.argv) > 1 else settings.smtp_user

if not settings.smtp_host:
    print("SMTP не настроен (SMTP_HOST пуст) — письмо ушло бы в demo-лог. Заполни .env.")
    raise SystemExit(1)

print(f"Отправляю тестовое письмо на {to} через {settings.smtp_host}:{settings.smtp_port} "
      f"(ssl={settings.smtp_ssl}, tls={settings.smtp_tls})…")

send_email(
    to,
    "Тест отправки · Stride Shop",
    "<div style='font-family:Arial,sans-serif'>"
    "<h2>Stride Shop</h2><p>Если ты видишь это письмо — SMTP настроен и письма уходят. 🎉</p></div>",
)
