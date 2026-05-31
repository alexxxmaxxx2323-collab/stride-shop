"""Самотест жизненного цикла заказа: статусы, переходы, отмена, откат бонусов.

Проверяет:
  - оплата меняет только payment_status, исполнение (status) ведётся отдельно;
  - happy-path курьера: pending->assembling->shipped->in_transit->delivered;
  - ветка ПВЗ: shipped->ready_for_pickup (а не in_transit);
  - недопустимый переход отклоняется (409);
  - отмена клиентом до отгрузки + возврат списанных баллов;
  - отмена запрещена после передачи в доставку (409);
  - админская отмена/возврат откатывает бонусы и помечает оплату refunded.

Запуск (сервер поднят):  SHOP_BASE=http://127.0.0.1:8077 python -m tests.smoke_order_lifecycle
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
    code, b = request("POST", "/auth/register", {"email": email, "password": "hunter22pass", "first_name": "ЖЦ"})
    assert code == 201, f"register: {code} {b}"
    return b["access_token"]


def variant_id(token):
    code, lst = request("GET", "/products?page_size=100", token=token)
    return {p["slug"]: p for p in lst["items"]}["nike-air-force-1"]["variants"][0]["id"]


def make_order(token, delivery_type="pickup", use_points=0):
    code, cart = request("POST", "/cart/items", {"variant_id": variant_id(token), "size": 42, "quantity": 1}, token=token)
    assert code == 201, f"cart: {code} {cart}"
    body = {
        "delivery_name": "Клиент ЖЦ",
        "delivery_phone": "89161234567",
        "delivery_type": delivery_type,
        "use_points": use_points,
    }
    if delivery_type == "pickup":
        body["delivery_address"] = "Москва, Арбат, 10"
        body["pickup_code"] = "MSK001"
    else:
        body["delivery_address"] = "Москва, улица Тверская, 1"
    code, created = request("POST", "/orders", body, token=token)
    assert code == 201, f"order: {code} {created}"
    return created["order"]["id"], created["order"]["total_amount"]


def pay(token, oid, method="card"):
    code, b = request("POST", "/payments/mock", {"order_id": oid, "method": method}, token=token)
    assert code == 200, f"pay: {code} {b}"
    return b


def admin_set(admin, oid, st):
    return request("PATCH", f"/admin/orders/{oid}/status", {"status": st}, token=admin)


def balance(token):
    code, b = request("GET", "/me/bonuses", token=token)
    return b["balance"]


def main() -> int:
    stamp = int(time.time())
    admin = login("alice@test.com")
    cust = register(f"lc_{stamp}@test.com")

    # A) Оплата меняет только payment_status, исполнение остаётся "pending"
    oid, _ = make_order(cust, "pickup")
    p = pay(cust, oid)
    assert p["payment_status"] == "paid", p
    code, o = request("GET", f"/orders/{oid}", token=cust)
    assert o["status"] == "pending" and o["payment_status"] == "paid", o
    print("ok: оплата не трогает статус исполнения (pending + paid)")

    # B) Недопустимый переход pending -> delivered
    code, b = admin_set(admin, oid, "delivered")
    assert code == 409, f"должно быть 409: {code} {b}"
    # А допустимый pending -> assembling -> ready_for_pickup (ПВЗ-ветка)
    assert admin_set(admin, oid, "assembling")[0] == 200
    code, o = admin_set(admin, oid, "shipped")
    assert code == 200
    nexts = {s["code"] for s in o["allowed_next"]}
    assert "ready_for_pickup" in nexts and "in_transit" not in nexts, f"ПВЗ-ветка: {nexts}"
    assert admin_set(admin, oid, "ready_for_pickup")[0] == 200
    assert admin_set(admin, oid, "delivered")[0] == 200
    print("ok: переходы ПВЗ (assembling->shipped->ready_for_pickup->delivered), невалидный отклонён")

    # C) Курьерская ветка: shipped -> in_transit -> delivered
    oid2, _ = make_order(cust, "courier")
    assert admin_set(admin, oid2, "assembling")[0] == 200
    code, o = admin_set(admin, oid2, "shipped")
    nexts = {s["code"] for s in o["allowed_next"]}
    assert "in_transit" in nexts and "ready_for_pickup" not in nexts, f"курьер-ветка: {nexts}"
    assert admin_set(admin, oid2, "in_transit")[0] == 200
    assert admin_set(admin, oid2, "delivered")[0] == 200
    print("ok: курьерская ветка (shipped->in_transit->delivered)")

    # D) Отмена клиентом до отгрузки + возврат списанных баллов
    pay(cust, oid2) if False else None  # oid2 уже delivered, не трогаем
    bal_before = balance(cust)            # есть кэшбэк за оплаченный oid (pickup)
    assert bal_before > 0, "после оплаченного заказа должен быть кэшбэк"
    oid3, total3 = make_order(cust, "pickup", use_points=100)  # спишем 100 баллов
    assert balance(cust) == bal_before - 100, "100 баллов должны зарезервироваться"
    code, o = request("POST", f"/orders/{oid3}/cancel", token=cust)
    assert code == 200 and o["status"] == "cancelled", o
    assert balance(cust) == bal_before, "после отмены 100 баллов должны вернуться"
    print(f"ok: отмена клиентом возвращает баллы (баланс восстановлен до {bal_before})")

    # E) Отмена запрещена после передачи в доставку
    oid4, _ = make_order(cust, "courier")
    assert admin_set(admin, oid4, "assembling")[0] == 200
    assert admin_set(admin, oid4, "shipped")[0] == 200
    code, b = request("POST", f"/orders/{oid4}/cancel", token=cust)
    assert code == 409, f"отмена после отгрузки должна быть 409: {code} {b}"
    print("ok: отмена после передачи в доставку запрещена (409)")

    # F) Админская отмена оплаченного заказа: откат кэшбэка + payment refunded
    oid5, total5 = make_order(cust, "pickup")
    pay(cust, oid5)
    bal_paid = balance(cust)
    code, o = admin_set(admin, oid5, "cancelled")  # pending -> cancelled
    assert code == 200 and o["status"] == "cancelled" and o["payment_status"] == "refunded", o
    cashback5 = total5 * 5 // 100
    assert balance(cust) == bal_paid - cashback5, "кэшбэк оплаченного заказа должен сняться при отмене"
    print("ok: админ-отмена оплаченного — кэшбэк снят, оплата refunded")

    print("\nALL ORDER-LIFECYCLE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
