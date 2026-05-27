# STRIDE — Telegram-магазин с мини-приложением (WebApp)

Демо интернет-магазина кроссовок прямо внутри Telegram: каталог → корзина →
оформление заказа. Заказ уходит боту структурированным сообщением.

**Стек:** Python · aiogram · Telegram WebApp · HTML/CSS/JS

```
tg-shop-demo/
├─ webapp/
│  ├─ index.html   ← каталог + корзина + оформление
│  ├─ styles.css   ← стиль
│  └─ app.js       ← товары, логика корзины, отправка заказа
├─ bot.py          ← aiogram: кнопка WebApp + приём заказа
├─ requirements.txt
└─ README.md
```

---

## 1. Скриншоты для портфолио (просто, без Telegram)

Чтобы сделать красивые скрины, бот и интернет-хостинг не нужны — хватит браузера.

1. Открой `webapp/index.html` в Chrome (двойной клик по файлу).
2. Нажми **F12** → кнопка «toggle device toolbar» (Ctrl+Shift+M) — включится вид телефона.
3. Выбери ширину ~**390px** (iPhone) сверху.
4. Делай скрины:
   - **каталог** — главный экран с карточками;
   - **корзина** — добавь 2–3 пары, нажми иконку 🛒;
   - **оформление** — заполни имя/телефон (видно форму и итог).

> Фото товаров грузятся с Unsplash, поэтому при скриншоте нужен интернет.

---

## 2. Запуск «живьём» в Telegram (опционально, для бонус-скрина)

WebApp в Telegram открывается только по **HTTPS-ссылке**, поэтому нужен туннель.

1. Получи токен бота у [@BotFather](https://t.me/BotFather) → `/newbot`.
2. Установи зависимости:
   ```powershell
   pip install -r requirements.txt
   ```
3. Подними локальный сайт из папки webapp:
   ```powershell
   cd webapp
   python -m http.server 8080
   ```
4. В **другом окне** подними HTTPS-туннель (нужен [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)):
   ```powershell
   cloudflared tunnel --url http://localhost:8080
   ```
   Скопируй выданную ссылку вида `https://xxxx.trycloudflare.com`.
5. Запусти бота, подставив токен и ссылку:
   ```powershell
   $env:BOT_TOKEN = "ТОКЕН_ОТ_BOTFATHER"
   $env:WEBAPP_URL = "https://xxxx.trycloudflare.com"
   python bot.py
   ```
6. Открой бота в Telegram → `/start` → «🛍 Открыть магазин» → оформи заказ.
   Бот пришлёт сводку заказа в чат — **это второй сильный скрин**.

---

## Что демонстрирует проект

- Связку **бот ↔ WebApp** и передачу данных в обе стороны
  (`Telegram.WebApp.sendData` → хендлер `web_app_data` в aiogram).
- Каталог, корзину с подсчётом суммы, оформление и приём заказа.
- Аккуратный UI, адаптированный под тему Telegram.
