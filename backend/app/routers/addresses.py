"""Подсказки адресов через OpenStreetMap Nominatim (бесплатно, без ключа).

Документация: https://nominatim.org/release-docs/develop/api/Search/
Ограничения: не больше 1 запроса в секунду, нужно слать User-Agent.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

router = APIRouter(prefix="/addresses", tags=["addresses"])

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "stride-shop-demo/0.1 (educational portfolio project)"


class AddressSuggestion(BaseModel):
    value: str


@router.get("/suggest", response_model=list[AddressSuggestion])
def suggest(q: str = Query(..., min_length=3, max_length=200)) -> list[AddressSuggestion]:
    params = {
        "q": q,
        "format": "json",
        "addressdetails": "1",
        "limit": "8",
        "accept-language": "ru",
        "countrycodes": "ru",  # только Россия
    }
    url = f"{NOMINATIM_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Nominatim HTTP {e.code}")
    except urllib.error.URLError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Nominatim unreachable: {e.reason}")

    return [AddressSuggestion(value=item["display_name"]) for item in data]
