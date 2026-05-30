"""Самотест авторегистрации на чекауте (Lamoda-флоу).

Цепочка: guest-сессия → корзина → checkout-register (достройка того же юзера)
→ корзина сохранилась → заказ → коллизия e-mail (409) → подтверждение почты.

Зависит от seed: products содержит nike-air-force-1 (первый variant, размер 42).
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8765"
DB_PATH = Path(__file__).resolve().parent.parent / "shop.db"


def request(method: str, path: str, body=None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        r = urllib.request.urlopen(req)
        raw = r.read()
        try:
            return r.status, json.loads(raw)
        except Exception:
            return r.status, raw.decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


def main() -> int:
    email = f"guest{int(time.time())}@test.com"

    # 1) гостевая сессия
    code, body = request("POST", "/auth/guest")
    assert code == 201, f"guest failed: {code} {body}"
    gtoken = body["access_token"]
    code, me = request("GET", "/auth/me", token=gtoken)
    assert code == 200 and me["is_guest"] is True and me["email"] is None
    print(f"guest session ok: id={me['id']}, is_guest={me['is_guest']}")

    # 2) кладём товар в корзину под гостевым токеном
    code, lst = request("GET", "/products?page_size=100")
    assert code == 200
    by_slug = {p["slug"]: p for p in lst["items"]}
    af1_id = by_slug["nike-air-force-1"]["variants"][0]["id"]
    code, cart = request("POST", "/cart/items", {"variant_id": af1_id, "size": 42, "quantity": 1}, token=gtoken)
    assert code == 201 and cart["items_count"] == 1, f"add to guest cart: {code} {cart}"
    print(f"guest cart: items={cart['items_count']}, total={cart['total']}")

    # 3) авторегистрация на чекауте — тем же токеном (достройка гостя)
    code, body = request(
        "POST", "/auth/checkout-register",
        {"first_name": "Иван", "last_name": "Петров", "phone": "8 (999) 123-45-67", "email": email},
        token=gtoken,
    )
    assert code == 200, f"checkout-register: {code} {body}"
    token = body["access_token"]
    code, me = request("GET", "/auth/me", token=token)
    assert me["is_guest"] is False, "после регистрации is_guest должен стать False"
    assert me["email"] == email and me["email_verified"] is False
    assert me["phone"] == "+79991234567", f"phone normalize: {me['phone']}"
    assert me["marketing_consent"] is True, "галочка маркетинга по умолчанию True"
    print(f"checkout-register ok: email={me['email']}, phone={me['phone']}, guest={me['is_guest']}")

    # 4) КЛЮЧЕВОЕ: корзина сохранилась (это тот же user, не новый)
    code, cart = request("GET", "/cart", token=token)
    assert code == 200 and cart["items_count"] == 1, f"корзина потерялась: {cart}"
    print(f"cart preserved after register: items={cart['items_count']}")

    # 5) заказ оформляется
    code, order = request(
        "POST", "/orders",
        {"delivery_name": "Иван Петров", "delivery_phone": "+79991234567",
         "delivery_address": "Москва, ул. Тверская, д. 7"},
        token=token,
    )
    assert code == 201, f"order: {code} {order}"
    print(f"order #{order['order']['id']} created, total={order['order']['total_amount']}")

    # 6) коллизия: другой гость пытается занять тот же e-mail → 409
    code, body2 = request("POST", "/auth/guest")
    g2 = body2["access_token"]
    code, body = request(
        "POST", "/auth/checkout-register",
        {"first_name": "Пётр", "last_name": "Сидоров", "phone": "+79995556677", "email": email},
        token=g2,
    )
    assert code == 409, f"e-mail collision должен быть 409, получили {code} {body}"
    print(f"email collision rejected: {code} ({body.get('detail')})")

    # 7) подтверждение e-mail по токену из БД
    con = sqlite3.connect(DB_PATH)
    row = con.execute("SELECT email_verify_token FROM users WHERE email=?", (email,)).fetchone()
    con.close()
    assert row and row[0], "verify-token не записан в БД"
    code, html = request("GET", f"/auth/verify-email?token={row[0]}")
    assert code == 200 and "подтверждён" in html, f"verify-email: {code}"
    code, me = request("GET", "/auth/me", token=token)
    assert me["email_verified"] is True, "после перехода по ссылке email_verified должен стать True"
    print("email verified via link: email_verified=True")

    # 8) битый verify-токен — мягкая страница, не падение
    code, html = request("GET", "/auth/verify-email?token=bogus-token-xxx")
    assert code == 200 and "недействительна" in html
    print("bogus verify-token handled gracefully")

    print("\nALL CHECKOUT-AUTH CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
