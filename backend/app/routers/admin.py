import io
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import (
    Brand,
    Category,
    Order,
    Product,
    ProductVariant,
    Review,
    User,
    VariantImage,
    VariantStock,
)
from app.schemas.admin import (
    AdminOrderOut,
    OrderStatusUpdate,
    ProductCreate,
    ProductUpdate,
    ReviewCreate,
    StatusOption,
    StockUpdate,
    VariantCreate,
)
from app.schemas.catalog import ProductOut, ReviewOut, VariantImageOut, VariantOut
from app.schemas.order import OrderOut
from app.services import order_status
from app.services.bonus import reverse_order_bonuses
from app.services.order_notify import notify_status_change

router = APIRouter(prefix="/admin", tags=["admin"])

# backend/static — туда же монтируется StaticFiles в app/main.py.
STATIC_DIR = Path(__file__).resolve().parents[2] / "static"
ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_BYTES = 15 * 1024 * 1024  # 15 МБ на файл (фото с телефона бывают крупными)


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user


def _check_fks(db: Session, brand_id: int | None, category_id: int | None) -> None:
    if brand_id is not None and db.get(Brand, brand_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Brand {brand_id} not found")
    if category_id is not None and db.get(Category, category_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Category {category_id} not found")


@router.post(
    "/products",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_product(data: ProductCreate, db: Session = Depends(get_db)) -> Product:
    """Создаёт «голый» товар без вариантов.
    Варианты, фото и остатки добавляются seed-скриптом или отдельным API
    (вне scope текущей админки)."""
    if db.scalar(select(Product).where(Product.slug == data.slug)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Slug already taken")
    _check_fks(db, data.brand_id, data.category_id)

    product = Product(**data.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.patch(
    "/products/{product_id}",
    response_model=ProductOut,
    dependencies=[Depends(require_admin)],
)
def update_product(product_id: int, data: ProductUpdate, db: Session = Depends(get_db)) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")

    fields = data.model_dump(exclude_unset=True)
    if "slug" in fields and fields["slug"] != product.slug:
        if db.scalar(select(Product).where(Product.slug == fields["slug"])):
            raise HTTPException(status.HTTP_409_CONFLICT, "Slug already taken")
    _check_fks(db, fields.get("brand_id"), fields.get("category_id"))

    for k, v in fields.items():
        setattr(product, k, v)

    # price/price_old могли прийти по отдельности — сверяем итог.
    if product.price_old is not None and product.price_old <= product.price:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "price_old должна быть больше price (это старая цена до скидки)",
        )

    db.commit()
    db.refresh(product)
    return product


@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
def delete_product(product_id: int, db: Session = Depends(get_db)) -> None:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    db.delete(product)
    try:
        db.commit()
    except IntegrityError:
        # Вариант товара уже фигурирует в заказах или чьей-то корзине —
        # внешний ключ не даёт удалить, чтобы не порушить историю.
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Нельзя удалить: товар есть в заказах или корзинах",
        )


# ─────────────────────────── Варианты (цвета) ───────────────────────────


def _get_variant(db: Session, variant_id: int) -> ProductVariant:
    variant = db.get(ProductVariant, variant_id)
    if variant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Variant not found")
    return variant


@router.post(
    "/products/{product_id}/variants",
    response_model=VariantOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_variant(product_id: int, data: VariantCreate, db: Session = Depends(get_db)) -> ProductVariant:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    next_order = max((v.sort_order for v in product.variants), default=-1) + 1
    variant = ProductVariant(
        product_id=product_id,
        color_name=data.color_name,
        color_hex=data.color_hex,
        sort_order=next_order,
    )
    db.add(variant)
    db.commit()
    db.refresh(variant)
    return variant


@router.delete(
    "/variants/{variant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
def delete_variant(variant_id: int, db: Session = Depends(get_db)) -> None:
    variant = _get_variant(db, variant_id)
    # Запоминаем url'ы фото, чтобы подчистить файлы после успешного удаления строк.
    image_urls = [img.url for img in variant.images]
    db.delete(variant)
    try:
        db.commit()
    except IntegrityError:
        # Цвет уже в заказах/корзине — FK не даёт удалить (как и у товара).
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Нельзя удалить цвет: он есть в заказах или корзинах",
        )
    for url in image_urls:
        _delete_image_file(db, url)


# ─────────────────────────── Фото вариантов ───────────────────────────


def _delete_image_file(db: Session, url: str) -> None:
    """Удаляет файл с диска, только если на него не ссылается другая VariantImage."""
    still_used = db.scalar(select(VariantImage).where(VariantImage.url == url))
    if still_used is not None:
        return
    if not url.startswith("/static/"):
        return
    path = STATIC_DIR / Path(url[len("/static/"):])
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass  # файл занят/недоступен — не валим запрос из-за уборки


@router.post(
    "/variants/{variant_id}/images",
    response_model=list[VariantImageOut],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
async def upload_variant_images(
    variant_id: int,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> list[VariantImage]:
    variant = _get_variant(db, variant_id)
    slug = variant.product.slug
    folder = STATIC_DIR / "products" / slug
    folder.mkdir(parents=True, exist_ok=True)

    next_order = max((img.sort_order for img in variant.images), default=-1) + 1
    created: list[VariantImage] = []

    for upload in files:
        ext = Path(upload.filename or "").suffix.lower()
        if ext not in ALLOWED_IMAGE_EXTS:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Недопустимый формат «{ext or '?'}». Можно: jpg, png, webp",
            )
        content = await upload.read()
        if len(content) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Файл «{upload.filename}» больше 6 МБ",
            )
        # Проверяем, что это действительно картинка (а не переименованный файл).
        try:
            Image.open(io.BytesIO(content)).verify()
        except (UnidentifiedImageError, OSError):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Файл «{upload.filename}» не является изображением",
            )

        fname = f"{uuid.uuid4().hex}{ext}"
        (folder / fname).write_bytes(content)

        image = VariantImage(
            variant_id=variant_id,
            url=f"/static/products/{slug}/{fname}",
            sort_order=next_order,
        )
        next_order += 1
        db.add(image)
        created.append(image)

    db.commit()
    for image in created:
        db.refresh(image)
    return created


@router.delete(
    "/images/{image_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
def delete_image(image_id: int, db: Session = Depends(get_db)) -> None:
    image = db.get(VariantImage, image_id)
    if image is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Image not found")
    url = image.url
    db.delete(image)
    db.commit()
    _delete_image_file(db, url)


# ─────────────────────────── Остатки по размерам ───────────────────────────


@router.put(
    "/variants/{variant_id}/stock",
    response_model=VariantOut,
    dependencies=[Depends(require_admin)],
)
def set_variant_stock(variant_id: int, data: StockUpdate, db: Session = Depends(get_db)) -> ProductVariant:
    variant = _get_variant(db, variant_id)
    # Replace-стратегия: сносим все остатки варианта и кладём переданные.
    # Дедуп по размеру (последнее значение побеждает) — на случай дублей во вводе.
    by_size: dict[int, int] = {item.size: item.quantity for item in data.items}
    for stock in list(variant.stocks):
        db.delete(stock)
    db.flush()
    for size, quantity in by_size.items():
        db.add(VariantStock(variant_id=variant_id, size=size, quantity=quantity))
    db.commit()
    db.refresh(variant)
    return variant


# ─────────────────────────── Отзывы ───────────────────────────


@router.post(
    "/products/{product_id}/reviews",
    response_model=ReviewOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
)
def create_review(product_id: int, data: ReviewCreate, db: Session = Depends(get_db)) -> Review:
    if db.get(Product, product_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    review = Review(
        product_id=product_id,
        author=data.author,
        rating=data.rating,
        text=data.text,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@router.delete(
    "/reviews/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
def delete_review(review_id: int, db: Session = Depends(get_db)) -> None:
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Review not found")
    db.delete(review)
    db.commit()


# ---------- Заказы ----------
def _admin_order_out(order: Order) -> AdminOrderOut:
    """Заказ + человекочитаемые метки + доступные следующие статусы."""
    return AdminOrderOut(
        **OrderOut.model_validate(order).model_dump(),
        status_label=order_status.label(order.status),
        payment_label=order_status.PAYMENT_LABELS.get(
            order.payment_status, order.payment_status
        ),
        allowed_next=[
            StatusOption(code=c, label=order_status.label(c))
            for c in order_status.allowed_transitions(order.status, order.delivery_type)
        ],
    )


@router.get(
    "/orders",
    response_model=list[AdminOrderOut],
    dependencies=[Depends(require_admin)],
)
def admin_list_orders(db: Session = Depends(get_db)) -> list[AdminOrderOut]:
    orders = db.scalars(select(Order).order_by(Order.id.desc())).all()
    return [_admin_order_out(o) for o in orders]


@router.patch(
    "/orders/{order_id}/status",
    response_model=AdminOrderOut,
    dependencies=[Depends(require_admin)],
)
def admin_set_order_status(
    order_id: int,
    data: OrderStatusUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> AdminOrderOut:
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    new = data.status
    if new not in order_status.STATUS_LABELS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Неизвестный статус: {new}")
    if not order_status.can_transition(order.status, new, order.delivery_type):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Недопустимый переход: {order_status.label(order.status)} → "
            f"{order_status.label(new)}",
        )
    # Вход в «Отменён»/«Возврат» — откатываем бонусы и помечаем оплату возвратом.
    if new in order_status.REVERSAL_STATUSES and order.status not in order_status.REVERSAL_STATUSES:
        reverse_order_bonuses(
            db, order.user_id, order.id,
            f"Возврат бонусов: заказ №{order.id} ({order_status.label(new)})",
        )
        if order.payment_status == "paid":
            order.payment_status = "refunded"
    order.status = new
    db.commit()
    db.refresh(order)
    # Покупателю — уведомление о новом статусе (фоном, по TG и/или e-mail).
    notify_status_change(background_tasks, db, order)
    return _admin_order_out(order)
