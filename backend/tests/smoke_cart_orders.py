"""Самотест корзины и заказов: цепочка login → add → patch → delete → order.

Зависит от seed: products[1] = Air Force 1 (его первый variant — белый, 7 размеров).
"""
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

    # 2) тянем нужные варианты из каталога
    code, lst = request("GET", "/products?page_size=100")
    assert code == 200
    by_slug = {p["slug"]: p for p in lst["items"]}
    af1_variant = by_slug["nike-air-force-1"]["variants"][0]
    stan_variant = by_slug["adidas-stan-smith"]["variants"][0]
    af1_id = af1_variant["id"]
    stan_id = stan_variant["id"]
    print(f"variants resolved: AF1={af1_id}, StanSmith={stan_id}")

    # 3) пустая корзина
    code, cart = request("GET", "/cart", token=token)
    assert code == 200 and cart["items_count"] == 0
    print(f"empty cart: items={cart['items_count']} total={cart['total']}")

    # 4) положили AF1 (variant) размер 42 x2
    code, cart = request("POST", "/cart/items", {"variant_id": af1_id, "size": 42, "quantity": 2}, token=token)
    assert code == 201 and cart["items_count"] == 2, f"add AF1: {code} {cart}"
    print(f"added AF1 x2: total={cart['total']}, items={cart['items_count']}")

    # 5) положили Stan Smith размер 43
    code, cart = request("POST", "/cart/items", {"variant_id": stan_id, "size": 43, "quantity": 1}, token=token)
    assert code == 201 and cart["items_count"] == 3
    print(f"added Stan Smith x1: total={cart['total']}, lines={len(cart['items'])}")

    # 6) тот же вариант+размер → merge, новая строка не появляется
    code, cart = request("POST", "/cart/items", {"variant_id": af1_id, "size": 42, "quantity": 1}, token=token)
    assert code == 201 and cart["items_count"] == 4 and len(cart["items"]) == 2
    print(f"add AF1 again: items={cart['items_count']}, lines={len(cart['items'])}")

    # 7) PATCH — поменяли количество Air Force 1 на 1
    af1_line_id = next(i["id"] for i in cart["items"] if i["variant"]["id"] == af1_id)
    code, cart = request("PATCH", f"/cart/items/{af1_line_id}", {"quantity": 1}, token=token)
    assert code == 200 and cart["items_count"] == 2
    print(f"patched AF1 -> qty=1: items={cart['items_count']}, total={cart['total']}")

    # 8) валидация размера которого нет в наличии
    code, _ = request("POST", "/cart/items", {"variant_id": af1_id, "size": 38, "quantity": 1}, token=token)
    assert code == 400
    print(f"size=38 rejected: {code}")

    # 9) DELETE одной строки
    stan_line_id = next(i["id"] for i in cart["items"] if i["variant"]["id"] == stan_id)
    code, cart = request("DELETE", f"/cart/items/{stan_line_id}", token=token)
    assert code == 200 and len(cart["items"]) == 1
    print(f"deleted Stan Smith: lines={len(cart['items'])}")

    # 10) создание заказа из корзины
    code, order = request(
        "POST", "/orders",
        {"delivery_name": "Alice", "delivery_phone": "+79991234567", "delivery_address": "Москва, ул. Тверская, д. 7"},
        token=token,
    )
    assert code == 201, f"order create: {code} {order}"
    print(f"order #{order['order']['id']}: status={order['order']['status']}, total={order['order']['total_amount']}, items={len(order['order']['items'])}")
    assert order["order"]["items"][0]["color_name"], "color_name пустой в snapshot"
    print(f"snapshot color: {order['order']['items'][0]['color_name']}")

    # 11) после оформления — корзина пустая
    code, cart = request("GET", "/cart", token=token)
    assert cart["items_count"] == 0
    print(f"cart after order: empty ({cart['items_count']})")

    # 12) пустую корзину нельзя оформить
    code, body = request(
        "POST", "/orders",
        {"delivery_name": "Alice", "delivery_phone": "+79991234567", "delivery_address": "Москва, ул. Тверская, д. 7"},
        token=token,
    )
    assert code == 400
    print(f"empty cart order rejected: {code} ({body.get('detail')})")

    # 13) /orders — наш заказ есть в истории
    code, orders = request("GET", "/orders", token=token)
    assert code == 200 and len(orders) >= 1
    print(f"orders history: {len(orders)} order(s)")

    # 14) без токена — везде 401
    code, _ = request("GET", "/cart")
    assert code == 401
    code, _ = request("POST", "/orders", {"delivery_name": "x", "delivery_phone": "x", "delivery_address": "xxxxx"})
    assert code == 401
    print("unauth requests: 401 OK")

    print("\nALL CART + ORDERS CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
