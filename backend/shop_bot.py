"""STRIDE — запуск бота в режиме polling (для локальной разработки).

Хендлеры живут в app/telegram.py (их же использует webhook на проде).
Локально: задать TG_BOT_TOKEN (+ WEBAPP_URL/PUBLIC_URL) в backend/.env и:
    python shop_bot.py
"""
from __future__ import annotations

import asyncio
import logging

from app.telegram import dp, get_bot, set_menu_button

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    bot = get_bot()
    if not bot:
        raise SystemExit("TG_BOT_TOKEN не задан. Пропиши токен в backend/.env")
    # На случай, если ранее был установлен webhook (прод) — снимаем, иначе polling не пойдёт.
    await bot.delete_webhook(drop_pending_updates=True)
    await set_menu_button()
    logging.info("STRIDE bot (polling). mini-app: %s", bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
