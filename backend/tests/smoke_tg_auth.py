"""Самотест: формируем валидный initData как делает Telegram и дёргаем /auth/tg-webapp."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse
import urllib.request

BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "123456:test-token")
BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8765")


def build_init_data(tg_id: int, username: str, first_name: str) -> str:
    user_payload = json.dumps(
        {"id": tg_id, "first_name": first_name, "username": username, "language_code": "ru"}
    )
    fields = {
        "user": user_payload,
        "auth_date": str(int(time.time())),
        "query_id": "AAH_test",
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    received_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    fields["hash"] = received_hash
    return urllib.parse.urlencode(fields)


def post_json(path: str, body: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def main() -> int:
    init_data = build_init_data(tg_id=987654321, username="alice_tg", first_name="Alice")
    code, body = post_json("/auth/tg-webapp", {"init_data": init_data})
    print(f"tg-webapp: {code} {body}")
    assert code == 200, "tg-webapp must succeed with valid signature"
    token = body["access_token"]

    req = urllib.request.Request(
        BASE_URL + "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    me = json.loads(urllib.request.urlopen(req).read())
    print(f"/me      : {me}")
    assert me["tg_id"] == 987654321

    # повторный логин — должен вернуть того же юзера
    code2, body2 = post_json("/auth/tg-webapp", {"init_data": init_data})
    req2 = urllib.request.Request(
        BASE_URL + "/auth/me", headers={"Authorization": f"Bearer {body2['access_token']}"}
    )
    me2 = json.loads(urllib.request.urlopen(req2).read())
    assert me2["id"] == me["id"], "second login must return the same user"
    print("OK: повторный вход вернул того же юзера")

    # битый hash
    bad = init_data.replace(init_data[-3:], "000")
    code3, _ = post_json("/auth/tg-webapp", {"init_data": bad})
    assert code3 == 401, "broken hash must be rejected"
    print(f"bad hash : {code3} (rejected, как и ожидалось)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
