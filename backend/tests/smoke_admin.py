"""Самотест админских ручек."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BASE = "http://127.0.0.1:8765"


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
            return e.code, None


def login(email: str, password: str) -> str:
    code, body = request("POST", "/auth/login", {"email": email, "password": password})
    assert code == 200, f"login failed for {email}: {code} {body}"
    return body["access_token"]


def main() -> int:
    token = login("alice@test.com", "hunter22pass")

    # 1) без токена → 401
    code, _ = request("POST", "/admin/products", {"brand_id": 1, "category_id": 1, "name": "x", "slug": "x", "price": 100, "image_url": "/x"})
    assert code == 401
    print(f"no token: {code}")

    # 2) не-админ → 403 (Alice ещё не админ)
    code, body = request(
        "POST", "/admin/products",
        {"brand_id": 1, "category_id": 1, "name": "Test", "slug": "test-slug", "price": 100, "image_url": "/x", "sizes": [42]},
        token=token,
    )
    assert code == 403, f"expected 403 for non-admin, got {code} {body}"
    print(f"non-admin user: {code}")

    # 3) делаем Alice админом и логинимся снова (старый JWT всё ещё валиден — is_admin читаем из БД при каждом запросе)
    from app.db import SessionLocal
    from app.models import User
    from sqlalchemy import select
    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == "alice@test.com"))
        u.is_admin = True
        db.commit()
    print("alice promoted to admin")

    # 4) теперь POST работает
    code, prod = request(
        "POST", "/admin/products",
        {"brand_id": 1, "category_id": 1, "name": "Admin Test Sneaker", "slug": "admin-test-sneaker", "price": 9999, "image_url": "/static/products/nike-air-force-1.jpg", "sizes": [40, 41, 42], "rating": 4.2},
        token=token,
    )
    assert code == 201, f"create failed: {code} {prod}"
    print(f"create: id={prod['id']} name={prod['name']} price={prod['price']}")
    new_id = prod["id"]

    # 5) повторный slug → 409
    code, _ = request(
        "POST", "/admin/products",
        {"brand_id": 1, "category_id": 1, "name": "x", "slug": "admin-test-sneaker", "price": 100, "image_url": "/x"},
        token=token,
    )
    assert code == 409
    print(f"duplicate slug: {code}")

    # 6) несуществующий brand_id → 400
    code, _ = request(
        "POST", "/admin/products",
        {"brand_id": 9999, "category_id": 1, "name": "x", "slug": "x-y-z", "price": 100, "image_url": "/x"},
        token=token,
    )
    assert code == 400
    print(f"bad brand_id: {code}")

    # 7) PATCH: меняем цену
    code, prod = request("PATCH", f"/admin/products/{new_id}", {"price": 7777, "price_old": 9999}, token=token)
    assert code == 200 and prod["price"] == 7777 and prod["price_old"] == 9999
    print(f"patch price: now={prod['price']} old={prod['price_old']} disc={prod['discount_pct']}%")

    # 8) PATCH несуществующего → 404
    code, _ = request("PATCH", "/admin/products/99999", {"price": 1}, token=token)
    assert code == 404
    print(f"patch missing: {code}")

    # 9) товар появился в публичном каталоге
    code, body = request("GET", f"/products/{new_id}")
    assert code == 200 and body["name"] == "Admin Test Sneaker"
    print(f"visible in public catalog: name={body['name']}")

    # 10) DELETE
    code, _ = request("DELETE", f"/admin/products/{new_id}", token=token)
    assert code == 204
    print(f"delete: {code}")

    # 11) после delete — 404
    code, _ = request("GET", f"/products/{new_id}")
    assert code == 404
    print(f"after delete: {code}")

    print("\nALL ADMIN CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
