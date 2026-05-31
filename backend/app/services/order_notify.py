"""Уведомления покупателя о событиях заказа (смена статуса исполнения, оплата).

Это ТРАНЗАКЦИОННЫЕ уведомления (про заказ, который покупатель сам оформил), а не
маркетинг — поэтому шлём всегда, когда есть канал связи, не глядя на marketing_consent.

Каналы параллельны:
  - in-app — строка в ленте уведомлений ЛК (пишем в БД синхронно, чтобы «красный
    кружок» обновился сразу же);
  - Telegram и e-mail — фоном (сеть не задерживает ответ роутера).
Текст и адреса собираем здесь, пока ORM-сессия жива (в фоне объект может отвязаться).
"""
from __future__ import annotations

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Notification, Order, ProductVariant, User
from app.notifications import money, order_event_text, send_message
from app.services import order_status
from app.services.email import send_order_status_email


def _order_brief(db: Session, order: Order) -> tuple[str | None, str | None, str | None]:
    """Из заказа собираем (краткая строка, фото главного товара, slug для ссылки).

    Краткая строка: для одного товара — модель/цвет/размер/сумма/артикул;
    для нескольких — «<первый> и ещё N тов. · <сумма>».
    """
    items = list(order.items)
    if not items:
        return None, None, None
    first = items[0]
    slug = None
    if first.variant_id:
        variant = db.get(ProductVariant, first.variant_id)
        if variant is not None:
            slug = variant.product.slug
    total = money(order.total_amount)
    if len(items) == 1:
        detail = f"{first.product_name} · {first.color_name}, р. {first.size} · {total}"
        if first.variant_id:
            detail += f" · арт. STR-{first.variant_id}-{first.size}"
    else:
        detail = f"{first.product_name} и ещё {len(items) - 1} тов. · {total}"
    return detail, first.product_image, slug


def _notify_customer(
    bg: BackgroundTasks, db: Session, order: Order, title: str, note: str = ""
) -> None:
    """Разослать покупателю одно событие заказа по всем каналам сразу."""
    user = db.get(User, order.user_id)
    if user is None:
        return
    detail, image_url, slug = _order_brief(db, order)
    card_url = f"{settings.site_url}/static/shop.html?product={slug}" if slug else None
    # in-app: сохраняем уведомление в ленту ЛК (синхронно — видно сразу).
    db.add(
        Notification(
            user_id=user.id, title=title, body=note, detail=detail,
            image_url=image_url, product_slug=slug, order_id=order.id,
        )
    )
    db.commit()
    if user.tg_id:
        bg.add_task(
            send_message, user.tg_id,
            order_event_text(order.id, title, note, detail, card_url),
        )
    if user.email:
        bg.add_task(
            send_order_status_email, user.email, order.id, title,
            first_name=user.first_name, note=note, detail=detail, card_url=card_url,
        )


def notify_order_placed(bg: BackgroundTasks, db: Session, order: Order) -> None:
    """Покупатель оформил заказ — подтверждение во все каналы (и в ленту ЛК)."""
    _notify_customer(
        bg, db, order,
        "Заказ оформлен",
        "Мы получили ваш заказ. Как только начнём собирать — сообщим.",
    )


def notify_status_change(bg: BackgroundTasks, db: Session, order: Order) -> None:
    """Сообщить покупателю о новом статусе исполнения заказа."""
    _notify_customer(
        bg, db, order,
        order_status.label(order.status),
        order_status.STATUS_CUSTOMER_NOTE.get(order.status, ""),
    )


def notify_payment_received(bg: BackgroundTasks, db: Session, order: Order) -> None:
    """Сообщить покупателю, что онлайн-оплата заказа получена."""
    _notify_customer(
        bg, db, order,
        "Оплата получена",
        "Спасибо! Оплата прошла, мы приступаем к сборке заказа.",
    )
