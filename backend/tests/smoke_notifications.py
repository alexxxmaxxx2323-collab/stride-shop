"""Самотест ленты уведомлений ЛК: создание при событиях, счётчик, прочтение.

Проверяет:
  - оплата + смена статуса админом порождают in-app уведомления покупателю;
  - GET /me/notifications отдаёт ленту (новые сверху), есть привязка к заказу;
  - unread-count считает непрочитанные;
  - read-all обнуляет счётчик и помечает всё прочитанным;
  - уведомления одного пользователя не видны другому.

Запуск (сервер поднят):  SHOP_BASE=http://127.0.0.1:8077 python -m tests.smoke_notifications
Нужен админ alice@test.com / hunter22pass (is_admin).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

BASE = os.environ.get("SHOP_BASE", "http://127.0.0.1:8765")


def request(method, path, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        r = urllib.request.urlopen(req)
        raw = r.read()
        return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


def login(email, password="hunter22pass"):
    code, b = request("POST", "/auth/login", {"email": email, "password": password})
    assert code == 200, f"login {email}: {code} {b}"
    return b["access_token"]


def register(email):
    code, b = request("POST", "/auth/register", {"email": email, "password": "hunter22pass", "first_name": "Notif"})
    assert code == 201, f"register: {code} {b}"
    return b["access_token"]


def variant_id(token):
    code, lst = request("GET", "/products?page_size=100", token=token)
    return {p["slug"]: p for p in lst["items"]}["nike-air-force-1"]["variants"][0]["id"]


def make_order(token):
    code, cart = request("POST", "/cart/items", {"variant_id": variant_id(token), "size": 42, "quantity": 1}, token=token)
    assert code == 201, f"cart: {code} {cart}"
    body = {
        "delivery_name": "Клиент Notif", "delivery_phone": "89161234567",
        "delivery_type": "pickup", "delivery_address": "Москва, Арбат, 10", "pickup_code": "MSK001",
    }
    code, created = request("POST", "/orders", body, token=token)
    assert code == 201, f"order: {code} {created}"
    return created["order"]["id"]


def unread(token):
    code, b = request("GET", "/me/notifications/unread-count", token=token)
    assert code == 200, f"unread: {code} {b}"
    return b["count"]


def main() -> int:
    stamp = int(time.time())
    admin = login("alice@test.com")
    cust = register(f"nt_{stamp}@test.com")

    # Новый покупатель — лента пуста.
    assert unread(cust) == 0, "у нового пользователя не должно быть уведомлений"
    code, lst = request("GET", "/me/notifications", token=cust)
    assert code == 200 and lst == [], f"лента должна быть пустой: {lst}"

    # A) Оформление создаёт уведомление «Заказ оформлен», оплата — «Оплата получена»
    oid = make_order(cust)
    assert unread(cust) == 1, "после оформления должно быть уведомление «Заказ оформлен»"
    request("POST", "/payments/mock", {"order_id": oid, "method": "card"}, token=cust)
    assert unread(cust) == 2, "оформление + оплата = 2"

    # B) Смены статуса админом → по уведомлению на каждый переход
    assert request("PATCH", f"/admin/orders/{oid}/status", {"status": "assembling"}, token=admin)[0] == 200
    assert request("PATCH", f"/admin/orders/{oid}/status", {"status": "shipped"}, token=admin)[0] == 200
    assert request("PATCH", f"/admin/orders/{oid}/status", {"status": "ready_for_pickup"}, token=admin)[0] == 200
    assert unread(cust) == 5, f"оформление + оплата + 3 статуса = 5, получено {unread(cust)}"

    # C) Лента: новые сверху, привязка к заказу, детали товара (для бота и ЛК)
    code, lst = request("GET", "/me/notifications", token=cust)
    assert len(lst) == 5, f"в ленте должно быть 5 записей: {len(lst)}"
    assert lst[0]["title"] == "Готов к выдаче", f"самое свежее сверху: {lst[0]}"
    assert lst[-1]["title"] == "Заказ оформлен", f"оформление — самое старое: {lst[-1]}"
    assert all(n["order_id"] == oid for n in lst), "все привязаны к заказу"
    assert not lst[0]["is_read"], "новое — непрочитанное"
    # детали заказа: краткая строка, фото и slug для ссылки на карточку
    top = lst[0]
    assert top["product_slug"] == "nike-air-force-1", f"slug для ссылки: {top}"
    assert top["detail"] and "р. 42" in top["detail"], f"детали с размером: {top}"
    assert top["image_url"], f"фото товара: {top}"
    print("ok: события заказа создают ленту (оформление + оплата + 3 статуса = 5, с деталями)")

    # D) read-all обнуляет счётчик
    code, b = request("POST", "/me/notifications/read-all", token=cust)
    assert code == 200 and b["count"] == 0, b
    assert unread(cust) == 0, "после read-all непрочитанных нет"
    code, lst = request("GET", "/me/notifications", token=cust)
    assert all(n["is_read"] for n in lst), "все помечены прочитанными"
    print("ok: read-all обнуляет счётчик и помечает всё прочитанным")

    # E) Изоляция: другой пользователь не видит чужих уведомлений
    other = register(f"nt2_{stamp}@test.com")
    assert unread(other) == 0, "чужие уведомления не должны быть видны"
    code, lst = request("GET", "/me/notifications", token=other)
    assert lst == [], "лента другого пользователя пуста"
    print("ok: уведомления изолированы по пользователю")

    print("\nALL NOTIFICATION CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
