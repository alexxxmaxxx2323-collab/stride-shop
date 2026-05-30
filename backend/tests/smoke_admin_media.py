"""Самотест медиа-ручек админки: цвета (варианты), загрузка фото, остатки.

Запускать при поднятом сервере на 127.0.0.1:8765 (как и smoke_admin.py).
Тест идемпотентен: в начале сносит тестовый товар по slug, в конце убирает за собой.
"""
from __future__ import annotations

import io
import json
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image  # noqa: E402  (после sys.path)

BASE = "http://127.0.0.1:8765"
SLUG = "qa-media-sneaker"


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


def upload(path: str, field: str, filename: str, content: bytes, token: str):
    """multipart/form-data загрузка одного файла."""
    boundary = "----qaBoundary" + uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Authorization": f"Bearer {token}",
    }
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method="POST")
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
    assert code == 200, f"login failed: {code} {body}"
    return body["access_token"]


def set_admin(email: str, value: bool) -> None:
    from app.db import SessionLocal
    from app.models import User
    from sqlalchemy import select

    with SessionLocal() as db:
        u = db.scalar(select(User).where(User.email == email))
        u.is_admin = value
        db.commit()


def make_png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (200, 30, 60)).save(buf, format="PNG")
    return buf.getvalue()


def cleanup_existing(token: str) -> None:
    """Снести тестовый товар по slug, если остался от прошлого прогона."""
    code, body = request("GET", f"/products/slug/{SLUG}")
    if code == 200:
        request("DELETE", f"/admin/products/{body['id']}", token=token)


def main() -> int:
    token = login("alice@test.com", "hunter22pass")
    set_admin("alice@test.com", True)
    cleanup_existing(token)

    # 1) создаём товар
    code, prod = request(
        "POST", "/admin/products",
        {"brand_id": 1, "category_id": 1, "name": "QA Media Sneaker", "slug": SLUG, "price": 6000},
        token=token,
    )
    assert code == 201, f"create product: {code} {prod}"
    pid = prod["id"]
    print(f"product created: id={pid}")

    # 2) добавляем цвет (вариант)
    code, variant = request(
        "POST", f"/admin/products/{pid}/variants",
        {"color_name": "QA White", "color_hex": "#ffffff"}, token=token,
    )
    assert code == 201, f"create variant: {code} {variant}"
    vid = variant["id"]
    print(f"variant created: id={vid} color={variant['color_name']}")

    # 2b) битый hex → 422
    code, _ = request("POST", f"/admin/products/{pid}/variants",
                      {"color_name": "Bad", "color_hex": "white"}, token=token)
    assert code == 422, f"expected 422 for bad hex, got {code}"
    print(f"bad color_hex rejected: {code}")

    # 3) загружаем фото
    code, images = upload(f"/admin/variants/{vid}/images", "files", "shot.png", make_png_bytes(), token)
    assert code == 201, f"upload image: {code} {images}"
    assert len(images) == 1 and images[0]["url"].startswith(f"/static/products/{SLUG}/")
    img_url = images[0]["url"]
    print(f"image uploaded: {img_url}")

    # 3b) не-картинка → 400
    code, _ = upload(f"/admin/variants/{vid}/images", "files", "fake.png", b"not an image", token)
    assert code == 400, f"expected 400 for non-image, got {code}"
    print(f"non-image rejected: {code}")

    # 4) выставляем остатки
    code, _ = request("PUT", f"/admin/variants/{vid}/stock",
                      {"items": [{"size": 42, "quantity": 5}, {"size": 43, "quantity": 0}]}, token=token)
    assert code == 200, f"set stock: {code}"
    print("stock set: size42=5, size43=0")

    # 4b) состав материалов через PATCH
    code, _ = request("PATCH", f"/admin/products/{pid}",
                      {"upper": "Кожа", "lining": "Текстиль", "sole": "Резина",
                       "season": "Лето", "country": "Вьетнам"}, token=token)
    assert code == 200, f"patch composition: {code}"
    print("composition set")

    # 4c) отзыв
    code, review = request("POST", f"/admin/products/{pid}/reviews",
                           {"author": "QA Бот", "rating": 5, "text": "Топ кроссы"}, token=token)
    assert code == 201 and "id" in review, f"create review: {code} {review}"
    rid = review["id"]
    print(f"review created: id={rid}")

    # 4d) битый рейтинг отзыва → 422
    code, _ = request("POST", f"/admin/products/{pid}/reviews",
                      {"author": "X", "rating": 9, "text": "y"}, token=token)
    assert code == 422, f"expected 422 for bad rating, got {code}"
    print(f"bad review rating rejected: {code}")

    # 5) проверяем публичную карточку
    code, detail = request("GET", f"/products/{pid}")
    assert code == 200
    assert detail["in_stock"] is True, "должен быть in_stock=true (размер 42 > 0)"
    assert 42 in detail["all_sizes"] and 43 not in detail["all_sizes"], detail["all_sizes"]
    assert detail["primary_image"] == img_url, detail["primary_image"]
    assert len(detail["variants"][0]["images"]) == 1
    assert detail["upper"] == "Кожа" and detail["country"] == "Вьетнам", "состав не сохранился"
    assert detail["review_count"] == 1 and detail["reviews"][0]["author"] == "QA Бот", detail["reviews"]
    print(f"public card ok: in_stock={detail['in_stock']} sizes={detail['all_sizes']} upper={detail['upper']} reviews={detail['review_count']}")

    # 5b) удаляем отзыв
    code, _ = request("DELETE", f"/admin/reviews/{rid}", token=token)
    assert code == 204, f"delete review: {code}"
    print(f"review deleted: {code}")

    # 6) удаляем фото
    img_id = images[0]["id"]
    code, _ = request("DELETE", f"/admin/images/{img_id}", token=token)
    assert code == 204, f"delete image: {code}"
    print(f"image deleted: {code}")

    # 7) удаляем цвет
    code, _ = request("DELETE", f"/admin/variants/{vid}", token=token)
    assert code == 204, f"delete variant: {code}"
    print(f"variant deleted: {code}")

    # 8) удаляем товар
    code, _ = request("DELETE", f"/admin/products/{pid}", token=token)
    assert code == 204, f"delete product: {code}"
    print(f"product deleted: {code}")

    print("\nALL MEDIA CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
