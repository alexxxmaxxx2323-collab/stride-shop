"""Геокодирование адресов через OpenStreetMap Nominatim (бесплатно, без ключа).

Документация: https://nominatim.org/release-docs/develop/api/Search/
Ограничения: не больше 1 запроса в секунду, обязателен User-Agent.

Один модуль на два сценария:
- подсказки адресов (/addresses/suggest)
- проверка реальности адреса при оформлении заказа
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "stride-shop-demo/0.1 (educational portfolio project)"


class GeocodeUnavailable(RuntimeError):
    """Геокодер недоступен (сеть/таймаут/ошибка сервиса)."""


def search(q: str, limit: int = 8) -> list[dict]:
    """Спросить Nominatim про адрес. Возвращает список найденных мест.

    Бросает GeocodeUnavailable, если до сервиса не достучались — вызывающий
    код сам решает, как на это реагировать.
    """
    params = {
        "q": q,
        "format": "json",
        "addressdetails": "1",
        "limit": str(limit),
        "accept-language": "ru",
        "countrycodes": "ru",  # только Россия
    }
    url = f"{NOMINATIM_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise GeocodeUnavailable(str(e)) from e


def address_exists(q: str) -> bool:
    """True, если Nominatim нашёл хотя бы один реальный адрес.

    Дом ищем строго: запрашиваем 1 результат и проверяем, что в нём есть
    либо номер дома, либо улица — чтобы «Москва» в одиночку не считалась
    полноценным адресом доставки.
    """
    results = search(q, limit=1)
    if not results:
        return False
    addr = results[0].get("address", {})
    has_house = "house_number" in addr
    has_street = "road" in addr or "pedestrian" in addr
    return has_house or has_street
