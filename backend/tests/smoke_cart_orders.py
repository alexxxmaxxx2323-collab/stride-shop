"""Самотест корзины и заказов: цепочка login → add → patch → delete → order."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8765"


def request(method: str, path: str, body=None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        r = urllib.request.urlopen(req)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}


def main() -> int:
    # 1) логинимся существующей учёткой Alice
    code, body = request("POST", "/auth/login", {"email": "alice@test.com", "password": "hunter22pass"})
    assert code == 200, f"login failed: {code} {body}"
    token = body["access_token"]
    print(f"login ok, token={token[:20]}...")

    # 2) пустая корзина
    code, cart = request("GET", "/cart", token=token)
    assert code == 200 and cart["items_count"] == 0
    print(f"empty cart: items={cart['items_count']} total={cart['total']}")

    # 3) положили Air Force 1 (id=1) размер 42
    code, cart = request("POST", "/cart/items", {"product_id": 1, "size": 42, "quantity": 2}, token=token)
    assert code == 201 and cart["items_count"] == 2
    print(f"added AF1 x2: total={cart['total']}, items={cart['items_count']}")

    # 4) положили Stan Smith (id=4) размер 43
    code, cart = request("POST", "/cart/items", {"product_id": 4, "size": 43, "quantity": 1}, token=token)
    assert code == 201 and cart["items_count"] == 3
    print(f"added Stan Smith x1: total={cart['total']}, lines={len(cart['items'])}")

    # 5) тот же товар+размер -> количество увеличивается, новой строки не появляется
    code, cart = request("POST", "/cart/items", {"product_id": 1, "size": 42, "quantity": 1}, token=token)
    assert code == 201 and cart["items_count"] == 4 and len(cart["items"]) == 2
    print(f"add AF1 again: items={cart['items_count']}, lines={len(cart['items'])}")

    # 6) PATCH — поменяли количество Air Force 1 на 1
    af1_id = next(i["id"] for i in cart["items"] if i["product"]["id"] == 1)
    code, cart = request("PATCH", f"/cart/items/{af1_id}", {"quantity": 1}, token=token)
    assert code == 200 and cart["items_count"] == 2
    print(f"patched AF1 -> qty=1: items={cart['items_count']}, total={cart['total']}")

    # 7) валидация размера которого нет
    code, _ = request("POST", "/cart/items", {"product_id": 1, "size": 38, "quantity": 1}, token=token)
    assert code == 400
    print(f"size=38 rejected: {code}")

    # 8) DELETE одной строки
    stan_id = next(i["id"] for i in cart["items"] if i["product"]["id"] == 4)
    code, cart = request("DELETE", f"/cart/items/{stan_id}", token=token)
    assert code == 200 and len(cart["items"]) == 1
    print(f"deleted Stan Smith: lines={len(cart['items'])}")

    # 9) создание заказа из корзины
    code, order = request(
        "POST", "/orders",
        {"delivery_name": "Alice", "delivery_phone": "+79991234567", "delivery_address": "Москва, ул. Пушкина 1"},
        token=token,
    )
    assert code == 201
    print(f"order #{order['id']}: status={order['status']}, total={order['total_amount']}, items={len(order['items'])}")

    # 10) после оформления — корзина пустая
    code, cart = request("GET", "/cart", token=token)
    assert cart["items_count"] == 0
    print(f"cart after order: empty ({cart['items_count']})")

    # 11) пустую корзину нельзя оформить
    code, body = request(
        "POST", "/orders",
        {"delivery_name": "Alice", "delivery_phone": "+79991234567", "delivery_address": "Москва"},
        token=token,
    )
    assert code == 400
    print(f"empty cart order rejected: {code} ({body.get('detail')})")

    # 12) /orders — наш заказ есть в истории
    code, orders = request("GET", "/orders", token=token)
    assert code == 200 and len(orders) >= 1
    print(f"orders history: {len(orders)} order(s)")

    # 13) без токена — везде 401
    code, _ = request("GET", "/cart")
    assert code == 401
    code, _ = request("POST", "/orders", {"delivery_name": "x", "delivery_phone": "x", "delivery_address": "xxxxx"})
    assert code == 401
    print("unauth requests: 401 OK")

    print("\nALL CART + ORDERS CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
