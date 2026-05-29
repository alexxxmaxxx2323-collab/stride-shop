"""Интеграция с CDEK API — список реальных пунктов выдачи (ПВЗ) для карты.

Используется тестовая среда CDEK (api.edu.cdek.ru) с публичными тест-ключами —
данные реальные (адреса/координаты ПВЗ), но это «песочница», без боевых заказов.

Поток: имя города -> код города (/location/cities) -> точки (/deliverypoints).
Токен и результаты кэшируем в памяти, чтобы не дёргать CDEK на каждый запрос.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

from app.config import settings

# Города для выпадающего списка (резолвятся в код через CDEK при первом запросе).
CITIES = [
    "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург",
    "Казань", "Нижний Новгород", "Краснодар", "Ростов-на-Дону",
]

_token: dict = {"value": None, "exp": 0}
_city_codes: dict[str, int] = {}     # имя города -> код CDEK
_points_cache: dict[int, tuple[float, list]] = {}  # код города -> (время, точки)
_POINTS_TTL = 3600  # сек


class CdekUnavailable(Exception):
    """CDEK недоступен/ошибка — вызывающий решает, как деградировать."""


def _request(method: str, path: str, *, params=None, data=None, token=None) -> dict | list:
    url = settings.cdek_api_url.rstrip("/") + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Accept": "application/json"}
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:  # noqa: BLE001
        raise CdekUnavailable(str(e)) from e


def _get_token() -> str:
    if _token["value"] and _token["exp"] > time.time():
        return _token["value"]
    res = _request("POST", "/oauth/token", data={
        "grant_type": "client_credentials",
        "client_id": settings.cdek_account,
        "client_secret": settings.cdek_secret,
    })
    tok = res.get("access_token")
    if not tok:
        raise CdekUnavailable("no access_token")
    _token["value"] = tok
    _token["exp"] = time.time() + int(res.get("expires_in", 3600)) - 60
    return tok


def _city_code(name: str) -> int | None:
    if name in _city_codes:
        return _city_codes[name]
    token = _get_token()
    res = _request("GET", "/location/cities",
                   params={"city": name, "country_codes": "RU", "size": 1}, token=token)
    if isinstance(res, list) and res:
        code = int(res[0]["code"])
        _city_codes[name] = code
        return code
    return None


def get_pickup_points(city: str) -> list[dict]:
    """Список ПВЗ города в «тонком» виде для карты/списка."""
    code = _city_code(city)
    if code is None:
        return []
    cached = _points_cache.get(code)
    if cached and time.time() - cached[0] < _POINTS_TTL:
        return cached[1]

    token = _get_token()
    raw = _request("GET", "/deliverypoints",
                   params={"city_code": code, "type": "PVZ", "size": 200}, token=token)
    points = []
    for p in raw if isinstance(raw, list) else []:
        loc = p.get("location") or {}
        lat, lon = loc.get("latitude"), loc.get("longitude")
        if lat is None or lon is None:
            continue
        points.append({
            "code": p.get("code"),
            "name": p.get("name") or "Пункт выдачи CDEK",
            "address": loc.get("address_full") or loc.get("address") or "",
            "lat": lat,
            "lon": lon,
            "work_time": p.get("work_time") or "",
        })
    _points_cache[code] = (time.time(), points)
    return points
