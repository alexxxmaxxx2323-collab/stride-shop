"""Самотест виджета поддержки: meta, ответы бота по темам, статус заказа, handoff.

Запуск (сервер поднят):  SHOP_BASE=http://127.0.0.1:8077 python -m tests.smoke_support
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


def ask(msg, token=None):
    code, b = request("POST", "/support/ask", {"message": msg}, token=token)
    assert code == 200, f"ask '{msg}': {code} {b}"
    return b


def main() -> int:
    # meta
    code, m = request("GET", "/support/meta")
    assert code == 200 and "hours" in m, m
    print(f"ok: meta (tg={bool(m['telegram_url'])}, wa={bool(m['whatsapp_url'])})")

    # распознавание тем
    assert "Доставляем" in ask("сколько идёт доставка?")["reply"], "тема доставки"
    assert "размер" in ask("какой размер выбрать")["reply"].lower(), "тема размеров"
    assert "Возврат" in ask("хочу вернуть кроссовки")["reply"], "тема возврата"
    assert "оплат" in ask("как оплатить картой")["reply"].lower(), "тема оплаты"
    fb = ask("абвгде блаблабла")
    assert "менеджер" in fb["reply"].lower() and fb["suggestions"], "фолбэк + чипы"
    print("ok: бот распознаёт темы (доставка/размеры/возврат/оплата) и фолбэк")

    # статус заказа: гость vs залогиненный
    guest = ask("где мой заказ")
    assert "войдите" in guest["reply"].lower() or "вход" in guest["reply"].lower(), guest
    stamp = int(time.time())
    code, reg = request("POST", "/auth/register",
                        {"email": f"sup_{stamp}@test.com", "password": "hunter22pass", "first_name": "Sup"})
    tok = reg["access_token"]
    # без заказов
    no_orders = ask("статус заказа", token=tok)
    assert "не вижу" in no_orders["reply"].lower() or "оформите" in no_orders["reply"].lower(), no_orders
    # создаём заказ → статус виден
    prods = request("GET", "/products?page_size=100", token=tok)[1]
    vid = {p["slug"]: p for p in prods["items"]}["nike-air-force-1"]["variants"][0]["id"]
    request("POST", "/cart/items", {"variant_id": vid, "size": 42, "quantity": 1}, token=tok)
    oid = request("POST", "/orders", {"delivery_name": "Sup", "delivery_phone": "89161234567",
                                      "delivery_type": "pickup", "delivery_address": "Москва, Арбат, 10",
                                      "pickup_code": "MSK001"}, token=tok)[1]["order"]["id"]
    with_order = ask("где мой заказ", token=tok)
    assert f"№{oid}" in with_order["reply"], with_order
    print(f"ok: статус заказа — гость зовётся войти, у залогиненного виден заказ №{oid}")

    # handoff (без admin_tg_id вернёт ok=false, с настроенным — true; проверяем что 200 и есть detail)
    code, h = request("POST", "/support/handoff",
                     {"messages": [{"role": "user", "text": "нужен менеджер"}]}, token=tok)
    assert code == 200 and "detail" in h, h
    print(f"ok: handoff отвечает (ok={h['ok']})")

    print("\nALL SUPPORT CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
