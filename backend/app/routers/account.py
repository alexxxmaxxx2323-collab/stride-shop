"""Личный кабинет: сводка, бонусы, рефералка, персональные предложения, адреса."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.db import get_db
from app.models import (
    Address,
    BonusTransaction,
    Favorite,
    Notification,
    Order,
    OrderItem,
    Product,
    ProductVariant,
    User,
)
from app.schemas.account import (
    AddressIn,
    AddressOut,
    BonusesOut,
    NotificationOut,
    OffersOut,
    ReferralOut,
    SummaryOut,
    UnreadCountOut,
)
from app.schemas.catalog import ProductOut
from app.services.bonus import (
    CASHBACK_PCT,
    REFERRED_BONUS,
    REFERRER_BONUS,
    bonus_balance,
    ensure_referral_code,
)
from app.services.geocode import GeocodeUnavailable, address_exists

router = APIRouter(prefix="/me", tags=["account"])


def _verify_real_address(addr: str) -> None:
    """Проверяем существование адреса через геокодер (как на чекауте).
    Если геокодер недоступен — не блокируем (строгая эвристика уже отсекла мусор)."""
    try:
        if not address_exists(addr):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Не удалось найти такой адрес — проверьте город, улицу и дом",
            )
    except GeocodeUnavailable:
        pass


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
    """Персональная подборка по прозрачному скорингу.

    Сигнал вкуса собираем из избранного и истории покупок (бренды + категории),
    затем оцениваем каждый товар в наличии:
      +3  бренд из ваших интересов
      +2  категория из ваших интересов
      +2  товар со скидкой
      +rating·0.5  выше рейтинг — выше в выдаче
    Уже знакомые товары (в избранном/купленные) из выдачи исключаем.
    Без сигнала (новый пользователь) подборка вырождается в «популярное со скидкой».
    """
    favorited = db.scalars(
        select(Product).join(Favorite, Favorite.product_id == Product.id)
        .where(Favorite.user_id == user.id)
    ).all()
    bought = db.scalars(
        select(Product)
        .join(ProductVariant, ProductVariant.product_id == Product.id)
        .join(OrderItem, OrderItem.variant_id == ProductVariant.id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.user_id == user.id)
    ).all()

    signal = list(favorited) + list(bought)
    brand_ids = {p.brand_id for p in signal}
    cat_ids = {p.category_id for p in signal}
    seen = {p.id for p in signal}  # уже знакомые — не рекомендуем повторно

    scored: list[tuple[float, Product]] = []
    for p in db.scalars(select(Product)).all():
        if p.id in seen or not p.in_stock:
            continue
        score = 0.0
        if p.brand_id in brand_ids:
            score += 3
        if p.category_id in cat_ids:
            score += 2
        if p.discount_pct:
            score += 2
        score += (p.rating or 0) * 0.5
        scored.append((score, p))

    scored.sort(key=lambda t: (t[0], t[1].rating or 0), reverse=True)
    chosen = [p for _, p in scored[:8]]

    reason = (
        "На основе ваших интересов и покупок"
        if brand_ids
        else "Популярное со скидкой — присмотритесь"
    )
    return OffersOut(
        reason=reason,
        products=[ProductOut.model_validate(p) for p in chosen],
    )


# ---------- Уведомления (лента ЛК) ----------
@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Notification]:
    """Последние уведомления покупателя (новые сверху)."""
    return list(
        db.scalars(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.id.desc())
            .limit(50)
        ).all()
    )


@router.get("/notifications/unread-count", response_model=UnreadCountOut)
def unread_count(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> UnreadCountOut:
    """Сколько непрочитанных — для «красного кружка» с числом."""
    n = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == user.id, Notification.is_read.is_(False)
        )
    ) or 0
    return UnreadCountOut(count=int(n))


@router.post("/notifications/read-all", response_model=UnreadCountOut)
def mark_all_read(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> UnreadCountOut:
    """Пометить все уведомления прочитанными (вызывается при открытии раздела)."""
    for n in db.scalars(
        select(Notification).where(
            Notification.user_id == user.id, Notification.is_read.is_(False)
        )
    ).all():
        n.is_read = True
    db.commit()
    return UnreadCountOut(count=0)


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
    _verify_real_address(data.full_address)
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
    if data.full_address != addr.full_address:
        _verify_real_address(data.full_address)
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
