"""Самотест личного кабинета: сводка, кэшбэк за заказ, рефералка, адреса,
смена пароля, размер/SMS-согласие.

Запуск (сервер должен быть поднят):
    SHOP_BASE=http://127.0.0.1:8077 python -m tests.smoke_account
По умолчанию бьёт в http://127.0.0.1:8765 (как остальные smoke-тесты).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

BASE = os.environ.get("SHOP_BASE", "http://127.0.0.1:8765")


def request(method: str, path: str, body=None, token: str | None = None):
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


def register(email: str, password: str = "hunter22pass", ref: str | None = None):
    body = {"email": email, "password": password, "first_name": "Тест"}
    if ref:
        body["ref"] = ref
    code, b = request("POST", "/auth/register", body)
    assert code == 201, f"register failed: {code} {b}"
    return b["access_token"]


def make_order(token: str) -> int:
    """Положить товар в корзину и оформить pickup-заказ. Вернуть сумму заказа."""
    code, lst = request("GET", "/products?page_size=100", token=token)
    assert code == 200
    by_slug = {p["slug"]: p for p in lst["items"]}
    variant_id = by_slug["nike-air-force-1"]["variants"][0]["id"]
    code, cart = request(
        "POST", "/cart/items", {"variant_id": variant_id, "size": 42, "quantity": 1}, token=token
    )
    assert code == 201, f"add to cart: {code} {cart}"
    code, created = request(
        "POST",
        "/orders",
        {
            "delivery_name": "Тест Тестов",
            "delivery_phone": "89161234567",
            "delivery_address": "Москва, ул. Тверская, д. 1",
            "delivery_type": "pickup",
            "pickup_code": "MSK001",
        },
        token=token,
    )
    assert code == 201, f"order failed: {code} {created}"
    return created["order"]["id"], created["order"]["total_amount"]


def main() -> int:
    stamp = int(time.time())

    # 1) Сводка по существующему пользователю-новичку
    alice_email = f"acc_alice_{stamp}@test.com"
    alice = register(alice_email)
    code, summ = request("GET", "/me/summary", token=alice)
    assert code == 200 and summ["orders_count"] == 0 and summ["bonus_balance"] == 0, summ
    print(f"summary ok: orders={summ['orders_count']} balance={summ['bonus_balance']}")

    # 2) Кэшбэк начисляется ТОЛЬКО после оплаты, не при создании заказа
    oid, total = make_order(alice)
    code, bon = request("GET", "/me/bonuses", token=alice)
    assert code == 200 and bon["balance"] == 0, f"до оплаты баллов быть не должно: {bon['balance']}"
    code, pay = request("POST", "/payments/mock", {"order_id": oid, "method": "card"}, token=alice)
    assert code == 200 and pay["payment_status"] == "paid", pay
    code, bon = request("GET", "/me/bonuses", token=alice)
    expected = total * bon["cashback_pct"] // 100
    assert bon["balance"] == expected, f"cashback: balance={bon['balance']} expected={expected}"
    assert any("Кэшбэк" in t["reason"] for t in bon["transactions"]), bon["transactions"]
    print(f"cashback ok: оплачен заказ {total} -> +{bon['balance']} баллов ({bon['cashback_pct']}%)")

    # 3) Рефералка: друг регистрируется по коду alice → бонусы обоим
    code, ref = request("GET", "/me/referral", token=alice)
    assert code == 200 and len(ref["code"]) == 6, ref
    alice_code = ref["code"]
    friend = register(f"acc_friend_{stamp}@test.com", ref=alice_code)
    code, fsum = request("GET", "/me/summary", token=friend)
    assert code == 200 and fsum["bonus_balance"] == ref["referred_bonus"], fsum
    code, ref2 = request("GET", "/me/referral", token=alice)
    assert ref2["invited_count"] == 1 and ref2["earned"] == ref["referrer_bonus"], ref2
    print(
        f"referral ok: friend +{fsum['bonus_balance']}, alice invited={ref2['invited_count']} "
        f"earned={ref2['earned']}"
    )

    # 4) Адресная книга: первый адрес = дефолтный, второй с is_default перебивает
    code, a1 = request(
        "POST",
        "/me/addresses",
        {"recipient": "Иван", "phone": "89161112233", "full_address": "Москва, Арбат, 1"},
        token=alice,
    )
    assert code == 201 and a1["is_default"] is True, a1
    code, a2 = request(
        "POST",
        "/me/addresses",
        {"recipient": "Пётр", "phone": "89162223344", "full_address": "СПб, Невский, 2", "is_default": True},
        token=alice,
    )
    assert code == 201 and a2["is_default"] is True, a2
    code, lst = request("GET", "/me/addresses", token=alice)
    assert code == 200 and len(lst) == 2
    defaults = [a for a in lst if a["is_default"]]
    assert len(defaults) == 1 and defaults[0]["id"] == a2["id"], lst
    # удаляем дефолтный → дефолт переезжает на оставшийся
    code, _ = request("DELETE", f"/me/addresses/{a2['id']}", token=alice)
    assert code == 204
    code, lst = request("GET", "/me/addresses", token=alice)
    assert len(lst) == 1 and lst[0]["is_default"] is True, lst
    print("addresses ok: default-логика и переезд дефолта при удалении")

    # 5) Размер + SMS-согласие через PATCH /auth/me
    code, me = request("PATCH", "/auth/me", {"preferred_size": 43, "sms_consent": True}, token=alice)
    assert code == 200 and me["preferred_size"] == 43 and me["sms_consent"] is True, me
    code_bad, _ = request("PATCH", "/auth/me", {"preferred_size": 99}, token=alice)
    assert code_bad == 422, f"размер вне диапазона должен дать 422, got {code_bad}"
    print("profile ok: preferred_size=43, sms_consent=true, плохой размер отклонён")

    # 6) Смена пароля
    code, _ = request(
        "POST",
        "/auth/change-password",
        {"current_password": "hunter22pass", "new_password": "newpass12345"},
        token=alice,
    )
    assert code == 204, code
    code, _ = request("POST", "/auth/login", {"email": alice_email, "password": "newpass12345"})
    assert code == 200, "login with new password failed"
    code, b = request(
        "POST",
        "/auth/change-password",
        {"current_password": "wrongone", "new_password": "x" * 10},
        token=alice,
    )
    assert code == 401, f"wrong current password should be 401, got {code}"
    print("password ok: смена + вход новым + отказ при неверном текущем")

    print("\nALL ACCOUNT CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
