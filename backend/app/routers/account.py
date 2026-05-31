"""Личный кабинет: сводка, бонусы, рефералка, персональные предложения, адреса."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.db import get_db
from app.models import Address, BonusTransaction, Favorite, Order, Product, User
from app.schemas.account import (
    AddressIn,
    AddressOut,
    BonusesOut,
    OffersOut,
    ReferralOut,
    SummaryOut,
)
from app.schemas.catalog import ProductOut
from app.services.bonus import (
    CASHBACK_PCT,
    REFERRED_BONUS,
    REFERRER_BONUS,
    bonus_balance,
    ensure_referral_code,
)

router = APIRouter(prefix="/me", tags=["account"])


@router.get("/summary", response_model=SummaryOut)
def summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> SummaryOut:
    """Данные для обзорного экрана ЛК: заказы, потрачено, баланс баллов."""
    orders_count = db.scalar(
        select(func.count(Order.id)).where(Order.user_id == user.id)
    ) or 0
    total_spent = db.scalar(
        select(func.coalesce(func.sum(Order.total_amount), 0)).where(Order.user_id == user.id)
    ) or 0
    return SummaryOut(
        first_name=user.first_name,
        email=user.email,
        email_verified=user.email_verified,
        member_since=user.created_at,
        orders_count=int(orders_count),
        total_spent=int(total_spent),
        bonus_balance=bonus_balance(db, user.id),
        preferred_size=user.preferred_size,
    )


@router.get("/bonuses", response_model=BonusesOut)
def bonuses(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> BonusesOut:
    txs = db.scalars(
        select(BonusTransaction)
        .where(BonusTransaction.user_id == user.id)
        .order_by(BonusTransaction.id.desc())
    ).all()
    return BonusesOut(
        balance=bonus_balance(db, user.id),
        cashback_pct=CASHBACK_PCT,
        transactions=list(txs),  # type: ignore[arg-type]
    )


@router.get("/referral", response_model=ReferralOut)
def referral(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ReferralOut:
    code = ensure_referral_code(db, user)
    invited = db.scalar(
        select(func.count(User.id)).where(User.referred_by == user.id)
    ) or 0
    # Заработано по рефералке = сумма реферальных начислений этому пользователю.
    earned = db.scalar(
        select(func.coalesce(func.sum(BonusTransaction.amount), 0)).where(
            BonusTransaction.user_id == user.id,
            BonusTransaction.reason == "Реферальный бонус за друга",
        )
    ) or 0
    return ReferralOut(
        code=code,
        link=f"{settings.site_url}/static/shop.html?ref={code}",
        invited_count=int(invited),
        earned=int(earned),
        referrer_bonus=REFERRER_BONUS,
        referred_bonus=REFERRED_BONUS,
    )


@router.get("/offers", response_model=OffersOut)
def offers(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> OffersOut:
    """Персональная подборка: товары со скидкой, в приоритете — из брендов,
    которые пользователь добавлял в избранное."""
    on_sale = (
        select(Product)
        .where(Product.price_old.is_not(None), Product.price_old > Product.price)
    )
    fav_brand_ids = db.scalars(
        select(Product.brand_id)
        .join(Favorite, Favorite.product_id == Product.id)
        .where(Favorite.user_id == user.id)
        .distinct()
    ).all()

    chosen: list[Product] = []
    if fav_brand_ids:
        chosen = list(
            db.scalars(on_sale.where(Product.brand_id.in_(fav_brand_ids)).limit(8)).all()
        )
    # Добор до 8 общими скидочными товарами (без дублей).
    if len(chosen) < 8:
        seen = {p.id for p in chosen}
        for p in db.scalars(on_sale.order_by(Product.rating.desc()).limit(12)).all():
            if p.id not in seen:
                chosen.append(p)
                seen.add(p.id)
            if len(chosen) >= 8:
                break

    reason = (
        "На основе ваших избранных брендов"
        if fav_brand_ids
        else "Лучшие предложения со скидкой"
    )
    return OffersOut(
        reason=reason,
        products=[ProductOut.model_validate(p) for p in chosen],
    )


# ---------- Адресная книга ----------
def _unset_defaults(db: Session, user_id: int) -> None:
    for a in db.scalars(
        select(Address).where(Address.user_id == user_id, Address.is_default.is_(True))
    ).all():
        a.is_default = False


@router.get("/addresses", response_model=list[AddressOut])
def list_addresses(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Address]:
    return list(
        db.scalars(
            select(Address)
            .where(Address.user_id == user.id)
            .order_by(Address.is_default.desc(), Address.id.desc())
        ).all()
    )


@router.post("/addresses", response_model=AddressOut, status_code=status.HTTP_201_CREATED)
def create_address(
    data: AddressIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Address:
    # Первый адрес делаем дефолтным автоматически.
    has_any = db.scalar(select(func.count(Address.id)).where(Address.user_id == user.id)) or 0
    make_default = data.is_default or has_any == 0
    if make_default:
        _unset_defaults(db, user.id)
    addr = Address(
        user_id=user.id,
        recipient=data.recipient,
        phone=data.phone,
        full_address=data.full_address,
        is_default=make_default,
    )
    db.add(addr)
    db.commit()
    db.refresh(addr)
    return addr


@router.put("/addresses/{address_id}", response_model=AddressOut)
def update_address(
    address_id: int,
    data: AddressIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Address:
    addr = db.get(Address, address_id)
    if addr is None or addr.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Адрес не найден")
    if data.is_default and not addr.is_default:
        _unset_defaults(db, user.id)
    addr.recipient = data.recipient
    addr.phone = data.phone
    addr.full_address = data.full_address
    addr.is_default = data.is_default
    db.commit()
    db.refresh(addr)
    return addr


@router.delete("/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_address(
    address_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    addr = db.get(Address, address_id)
    if addr is None or addr.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Адрес не найден")
    was_default = addr.is_default
    db.delete(addr)
    db.commit()
    # Если удалили дефолтный — назначим дефолтным самый свежий из оставшихся.
    if was_default:
        nxt = db.scalar(
            select(Address).where(Address.user_id == user.id).order_by(Address.id.desc())
        )
        if nxt is not None:
            nxt.is_default = True
            db.commit()
