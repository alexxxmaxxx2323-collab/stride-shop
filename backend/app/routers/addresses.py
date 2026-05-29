"""Подсказки адресов через OpenStreetMap Nominatim.

Сам вызов геокодера живёт в app/services/geocode.py — этот роутер только
отдаёт подсказки для автодополнения в форме оформления заказа.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.services.geocode import GeocodeUnavailable, search

router = APIRouter(prefix="/addresses", tags=["addresses"])


class AddressSuggestion(BaseModel):
    value: str


@router.get("/suggest", response_model=list[AddressSuggestion])
def suggest(q: str = Query(..., min_length=3, max_length=200)) -> list[AddressSuggestion]:
    try:
        data = search(q, limit=8)
    except GeocodeUnavailable as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Nominatim unreachable: {e}")
    return [AddressSuggestion(value=item["display_name"]) for item in data]
