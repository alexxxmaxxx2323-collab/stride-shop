"""
STRIDE — Telegram-бот магазина.

Что делает:
  • по /start показывает кнопку «Открыть магазин» (WebApp);
  • когда пользователь оформляет заказ в мини-приложении,
    бот получает данные и присылает аккуратную сводку заказа.

Запуск:
  1) задать переменные окружения BOT_TOKEN и WEBAPP_URL (см. README.md);
  2) python bot.py
"""

import asyncio
import json
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

# Токен бота от @BotFather и HTTPS-ссылка на webapp/index.html.
# Лучше задавать через переменные окружения, а не хранить в коде.
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВСТАВЬ_ТОКЕН_СЮДА")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://example.com")

dp = Dispatcher()


@dp.message(CommandStart())
async def on_start(message: Message) -> None:
    """Приветствие + кнопка, открывающая мини-приложение."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(
                text="🛍 Открыть магазин",
                web_app=WebAppInfo(url=WEBAPP_URL),
            )
        ]],
        resize_keyboard=True,
    )
    await message.answer(
        "Добро пожаловать в STRIDE 👟\n"
        "Нажмите кнопку ниже, чтобы открыть каталог кроссовок:",
        reply_markup=keyboard,
    )


@dp.message(F.web_app_data)
async def on_order(message: Message) -> None:
    """Приём заказа из мини-приложения (метод Telegram.WebApp.sendData)."""
    order = json.loads(message.web_app_data.data)

    lines = ["🧾 <b>Новый заказ</b>", ""]
    for item in order["items"]:
        lines.append(f"• {item['name']} × {item['qty']} — {item['sum']:,} ₽".replace(",", " "))
    lines.append("")
    lines.append(f"<b>Итого: {order['total']:,} ₽</b>".replace(",", " "))

    customer = order["customer"]
    lines.append(f"\n👤 {customer['name']}\n📞 {customer['phone']}")

    await message.answer("\n".join(lines), parse_mode="HTML")


async def main() -> None:
    bot = Bot(BOT_TOKEN)
    print("Бот запущен. Откройте его в Telegram и отправьте /start")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
