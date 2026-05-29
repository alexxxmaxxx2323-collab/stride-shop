"""Telegram-бот STRIDE — общий модуль для polling (локально) и webhook (прод).

Хендлеры и Dispatcher живут здесь; shop_bot.py запускает их в режиме polling,
а FastAPI (app.main) принимает апдейты по webhook и кормит их в этот же dp.
"""
from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    Update,
    WebAppInfo,
)

from app.config import settings

log = logging.getLogger("tgbot")
dp = Dispatcher()
_bot: Bot | None = None


def get_bot() -> Bot | None:
    """Singleton Bot. None, если токен не задан."""
    global _bot
    if _bot is None and settings.tg_bot_token:
        _bot = Bot(settings.tg_bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    return _bot


def shop_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🛍 Открыть магазин", web_app=WebAppInfo(url=settings.mini_app_url))
    ]])


@dp.message(CommandStart())
async def on_start(message: Message) -> None:
    name = message.from_user.first_name or "друг"
    await message.answer(
        f"Привет, {name}! 👟\n\n"
        "Это <b>STRIDE</b> — магазин кроссовок, кед и ботинок.\n"
        "Жми кнопку ниже, выбирай пару и оформляй заказ прямо здесь, в Telegram.",
        reply_markup=shop_keyboard(),
    )


@dp.message(Command("help"))
async def on_help(message: Message) -> None:
    await message.answer(
        "🛍 <b>Открыть магазин</b> — кнопка под /start или меню слева от поля ввода.\n"
        "Внутри: каталог, корзина и оформление заказа.\n"
        "После заказа я пришлю подтверждение сюда, в чат.",
        reply_markup=shop_keyboard(),
    )


async def set_menu_button() -> None:
    """Постоянная кнопка-меню рядом с полем ввода (нужен https-URL мини-аппы)."""
    bot = get_bot()
    if not bot:
        return
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Магазин", web_app=WebAppInfo(url=settings.mini_app_url))
        )
    except Exception as e:  # noqa: BLE001
        log.warning("Не удалось установить кнопку-меню: %s", e)


async def setup_webhook() -> None:
    """Регистрируем webhook на боевом домене (вызывается при старте FastAPI)."""
    bot = get_bot()
    if not bot or not settings.base_url:
        return
    await set_menu_button()
    url = f"{settings.base_url}/tg/webhook/{settings.tg_webhook_secret}"
    await bot.set_webhook(url, secret_token=settings.tg_webhook_secret, drop_pending_updates=True)
    log.info("Webhook установлен: %s", url)


async def feed_update(data: dict) -> None:
    bot = get_bot()
    if not bot:
        return
    await dp.feed_update(bot, Update.model_validate(data))


async def shutdown() -> None:
    bot = get_bot()
    if bot:
        try:
            await bot.session.close()
        except Exception:  # noqa: BLE001
            pass
