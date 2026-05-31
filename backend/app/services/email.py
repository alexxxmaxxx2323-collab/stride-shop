"""Отправка писем по SMTP.

Если SMTP не настроен (`smtp_host` пуст) — письмо не уходит по-настоящему,
а печатается в консоль. Это demo-режим: разработка и проверка флоу не требуют
реального почтового сервера. Достаточно вписать SMTP-креды в .env, чтобы письма
начали отправляться.
"""
from __future__ import annotations

import smtplib
import sys
from email.message import EmailMessage

from app.config import settings


def _log(msg: str, *, err: bool = False) -> None:
    """Печать в консоль, устойчивая к не-кодируемым символам (cp1251 на Windows)."""
    stream = sys.stderr if err else sys.stdout
    try:
        print(msg, file=stream, flush=True)
    except UnicodeEncodeError:
        enc = stream.encoding or "utf-8"
        print(msg.encode(enc, "replace").decode(enc), file=stream, flush=True)


def send_email(to: str, subject: str, html: str) -> None:
    """Отправить письмо. Без SMTP-настроек — залогировать в консоль."""
    if not settings.smtp_host:
        _log(
            f"[email:STUB] -> {to}\n  subject: {subject}\n"
            f"  (SMTP не настроен — письмо не отправлено, demo-режим)"
        )
        return

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content("Для просмотра письма откройте его в HTML-совместимом клиенте.")
    msg.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_tls:
                smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        _log(f"[email:SENT] -> {to} · {subject}")
    except Exception as exc:  # сеть/авторизация не должны ронять заказ
        _log(f"[email:ERROR] -> {to} · {subject} · {exc!r}", err=True)


def send_verification_email(to: str, token: str, first_name: str | None = None) -> None:
    """Письмо со ссылкой подтверждения адреса."""
    link = f"{settings.site_url}/auth/verify-email?token={token}"
    hello = f"Здравствуйте, {first_name}!" if first_name else "Здравствуйте!"
    html = f"""\
<div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;color:#111">
  <h2 style="margin:0 0 16px">Stride Shop</h2>
  <p>{hello}</p>
  <p>Спасибо за заказ. Подтвердите адрес электронной почты, чтобы получить доступ
     к личному кабинету и истории заказов.</p>
  <p style="margin:24px 0">
    <a href="{link}" style="background:#111;color:#fff;text-decoration:none;
       padding:12px 24px;border-radius:8px;display:inline-block">Подтвердить e-mail</a>
  </p>
  <p style="color:#888;font-size:13px">Если кнопка не работает, откройте ссылку:<br>{link}</p>
</div>"""
    send_email(to, "Подтвердите ваш e-mail · Stride Shop", html)


def send_order_status_email(
    to: str,
    order_id: int,
    title: str,
    *,
    first_name: str | None = None,
    note: str | None = None,
    detail: str | None = None,
    card_url: str | None = None,
) -> None:
    """Письмо покупателю о смене статуса/оплаты заказа."""
    link = f"{settings.site_url}/static/account.html#notifications"
    hello = f"Здравствуйте, {first_name}!" if first_name else "Здравствуйте!"
    note_html = f'<p style="font-size:15px">{note}</p>' if note else ""
    detail_html = (
        f'<p style="font-size:14px;color:#444;background:#f5f5f7;border-radius:8px;'
        f'padding:12px 14px;margin:14px 0">🛍 {detail}</p>'
        if detail else ""
    )
    card_btn = (
        f'<a href="{card_url}" style="border:1px solid #ddd;color:#111;text-decoration:none;'
        f'padding:12px 24px;border-radius:8px;display:inline-block;margin-left:8px">Открыть товар</a>'
        if card_url else ""
    )
    html = f"""\
<div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;color:#111">
  <h2 style="margin:0 0 16px">Stride Shop</h2>
  <p>{hello}</p>
  <p style="font-size:17px;margin:18px 0 4px">
    Заказ №{order_id}: <b>{title}</b>
  </p>
  {note_html}
  {detail_html}
  <p style="margin:24px 0">
    <a href="{link}" style="background:#111;color:#fff;text-decoration:none;
       padding:12px 24px;border-radius:8px;display:inline-block">Мои заказы</a>{card_btn}
  </p>
  <p style="color:#888;font-size:13px">Если кнопка не работает, откройте ссылку:<br>{link}</p>
</div>"""
    send_email(to, f"Заказ №{order_id}: {title} · Stride Shop", html)
