"""Прогон ВСЕХ сценариев писем — отправляет реальное письмо на каждый шаблон/событие.

Запуск (из папки backend, .env с SMTP заполнен):
    .venv\\Scripts\\python.exe _test_all_emails.py [куда@слать]

Без аргумента шлёт на SMTP_USER. Проверяет два шаблона:
  1) подтверждение e-mail (регистрация / чекаут / повтор в ЛК — функция одна);
  2) статус заказа (оформлен, оплата получена, + все смены статуса исполнения).
Каждое письмо помечено в теме сценарием — удобно сверять в почте.
"""
import sys
import time

from app.config import settings
from app.services import order_status
from app.services.email import send_verification_email, send_order_status_email

to = sys.argv[1] if len(sys.argv) > 1 else settings.smtp_user

if not settings.smtp_host:
    print("SMTP не настроен — заполни .env."); raise SystemExit(1)

print(f"Шлю все сценарии на {to} через {settings.smtp_host}:{settings.smtp_port}\n"
      f"site_url для ссылок = {settings.site_url}\n")

# Демо-данные заказа для блока «детали товара» и ссылки «Открыть товар».
ORDER_ID = 1042
DETAIL = "Nike Air Max 90 · Чёрный, р. 42 · 12 990 ₽ · арт. STR-101-42"
CARD_URL = f"{settings.site_url}/static/shop.html?product=nike-air-max-90"
NAME = "Александр"

sent = 0

def _mark(scenario: str) -> None:
    global sent
    sent += 1
    print(f"  [{sent:>2}] {scenario}")
    time.sleep(0.4)  # не частим по SMTP

# 1) Подтверждение e-mail (один шаблон на регистрацию/чекаут/повтор-в-ЛК).
print("ШАБЛОН 1 — подтверждение e-mail:")
_mark("Подтверждение e-mail (register / checkout-register / resend в ЛК)")
send_verification_email(to, token="demo-verify-token-xyz", first_name=NAME)

# 2) Статус заказа — событийные письма.
print("\nШАБЛОН 2 — статусы заказа:")
events = [
    ("Заказ оформлен", "Мы получили ваш заказ. Как только начнём собирать — сообщим."),
    ("Оплата получена", "Спасибо! Оплата прошла, мы приступаем к сборке заказа."),
]
# + каждая смена статуса исполнения, у которой есть пояснение покупателю.
for status_key, note in order_status.STATUS_CUSTOMER_NOTE.items():
    events.append((order_status.label(status_key), note))

for title, note in events:
    _mark(f"{title} — «{note}»")
    send_order_status_email(
        to, ORDER_ID, title, first_name=NAME, note=note,
        detail=DETAIL, card_url=CARD_URL,
    )

print(f"\nГотово: отправлено {sent} писем. Проверь почту (и «Спам»).")
