"""STRIDE — Telegram-бот магазина (Фаза 3).

Отдельный бот (старый демо-bot.py в корне не трогаем). Делает:
  • /start — приветствие + кнопка «🛍 Открыть магазин» (мини-аппа);
  • ставит постоянную кнопку-меню рядом с полем ввода, открывающую магазин;
  • /help — короткая справка.

Заказы оформляются прямо в мини-аппе через общий API, поэтому бот ничего
не обрабатывает руками — он только «дверь» в магазин. Уведомления о заказах
шлёт бэкенд (см. app/notifications.py, Фаза 3.4).

Запуск (из папки backend):
  1) в .env задать TG_BOT_TOKEN и WEBAPP_URL (https-ссылка на мини-аппу);
  2) python shop_bot.py
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)

from app.config import settings

logging.basicConfig(level=logging.INFO)
dp = Dispatcher()


def shop_keyboard() -> InlineKeyboardMarkup:
    """Inline-кнопка под сообщением, открывающая мини-аппу."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="🛍 Открыть магазин",
                web_app=WebAppInfo(url=settings.webapp_url),
            )
        ]]
    )


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


async def main() -> None:
    if not settings.tg_bot_token:
        raise SystemExit(
            "TG_BOT_TOKEN не задан. Создай бота у @BotFather и пропиши токен в backend/.env"
        )

    bot = Bot(settings.tg_bot_token, default=DefaultBotProperties(parse_mode="HTML"))

    # Постоянная кнопка-меню (слева от поля ввода) открывает мини-аппу.
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Магазин", web_app=WebAppInfo(url=settings.webapp_url)
            )
        )
    except Exception as e:  # noqa: BLE001 — невалидный URL до настройки туннеля не должен ронять бота
        logging.warning("Не удалось установить кнопку-меню: %s", e)

    logging.info("STRIDE bot запущен. WEBAPP_URL=%s", settings.webapp_url)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
