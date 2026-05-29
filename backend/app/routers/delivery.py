"""Доставка: список городов и пунктов выдачи (ПВЗ) для карты на оформлении."""
from fastapi import APIRouter, Query

from app.services.cdek import CITIES, CdekUnavailable, get_pickup_points

router = APIRouter(prefix="/delivery", tags=["delivery"])


@router.get("/cities")
def list_cities() -> list[str]:
    return CITIES


@router.get("/points")
def pickup_points(city: str = Query(..., description="Название города")) -> list[dict]:
    """Реальные ПВЗ города (из CDEK). При недоступности CDEK — пустой список."""
    try:
        return get_pickup_points(city)
    except CdekUnavailable:
        return []
