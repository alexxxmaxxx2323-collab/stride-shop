# Деплой Stride Shop на VPS + домен .ru

Пошаговая инструкция: развернуть магазин на своём сервере под доменом с HTTPS.
Один процесс обслуживает сайт + API + Telegram-бот (webhook). База — SQLite на диске.

Файлы рядом: `stride.service` (systemd), `nginx.conf`, `.env.production.example`, `deploy.sh`.

---

## Кто что делает

Деплой отложен (сначала ЮKassa и мобильная версия). Когда вернёмся —
**бóльшую часть установки агент делает сам по SSH** с машины владельца
(локально есть ssh/scp/git/gh): пакеты, заливка кода, venv+pip, генерация
секретов и запись `backend/.env`, systemd, nginx, выпуск HTTPS через certbot,
проверки (healthz/webhook/письма), пуш на GitHub.

**Только владелец:** (1) оплата+регистрация .ru-домена (паспорт); (2) оплата+
создание VPS; (3) выдача SSH-доступа (вставить публичный ключ при создании
сервера); (4) DNS A-записи в панели регистратора; (5) кнопка мини-аппы в BotFather.

---

## 0. Что купить (блокирует деплой)

- **Домен .ru** — reg.ru / timeweb.com. Нужен паспорт (требование .ru). ~200–900 ₽/год.
- **VPS** — рекомендую **Timeweb Cloud** (RU, принимает карты РФ) или Selectel.
  Минимальная конфигурация хватает с запасом: **1 vCPU / 1–2 ГБ RAM / 20 ГБ SSD**, ОС **Ubuntu 24.04**. ~200–400 ₽/мес.
  При создании добавь свой **SSH-ключ** (или задай root-пароль).

После покупки на руках: **IP сервера** и доступ по SSH.

---

## 1. DNS: направить домен на сервер

В панели регистратора домена создай записи **A**:

| Тип | Имя | Значение |
|-----|-----|----------|
| A   | `@`   | IP твоего VPS |
| A   | `www` | IP твоего VPS |

Применяется до ~30–60 мин. Проверка: `ping stride-shop.ru` должен отвечать с IP сервера.

---

## 2. Первичная настройка сервера

```bash
ssh root@IP_СЕРВЕРА

# пакеты
apt update && apt upgrade -y
apt install -y python3-venv python3-pip git nginx certbot python3-certbot-nginx ufw

# фаервол: пускаем SSH и веб
ufw allow OpenSSH && ufw allow 'Nginx Full' && ufw --force enable

# отдельный пользователь для сервиса (без прав root)
adduser --system --group --home /opt/stride-shop stride
```

---

## 3. Код и зависимости

```bash
# код в /opt/stride-shop (замени URL на свой репозиторий)
git clone https://github.com/ТВОЙ_АККАУНТ/tg-shop-demo.git /opt/stride-shop
cd /opt/stride-shop/backend

python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r requirements.txt
```

> Если репозиторий приватный — заведи на сервере SSH-ключ (`ssh-keygen`) и добавь его в GitHub (Deploy keys), клонируй по `git@github.com:...`.

---

## 4. Конфиг .env (прод)

```bash
cp /opt/stride-shop/deploy/.env.production.example /opt/stride-shop/backend/.env
nano /opt/stride-shop/backend/.env
```

Обязательно заполни:
- `PUBLIC_URL=https://stride-shop.ru` — иначе письма уйдут с `http://127.0.0.1`;
- `JWT_SECRET` — `openssl rand -hex 32`;
- `TG_WEBHOOK_SECRET` — `openssl rand -hex 16`;
- `TG_BOT_TOKEN`, `ADMIN_TG_ID`;
- блок `SMTP_*` (пароль приложения Яндекса).

Права на файл с секретами:
```bash
chown stride:stride /opt/stride-shop/backend/.env && chmod 600 /opt/stride-shop/backend/.env
chown -R stride:stride /opt/stride-shop      # чтобы сервис мог писать shop.db
```

---

## 5. systemd-сервис (автозапуск + рестарт)

```bash
cp /opt/stride-shop/deploy/stride.service /etc/systemd/system/stride.service
systemctl daemon-reload
systemctl enable --now stride
systemctl status stride            # active (running)?
curl -s http://127.0.0.1:8077/healthz   # {"status":"ok",...}
```

При первом старте БД создаётся и сидируется каталогом автоматически (`bootstrap_db`).

---

## 6. nginx + HTTPS

```bash
# подставь свой домен в конфиге
sed -i 's/stride-shop.ru/ТВОЙ_ДОМЕН/g' /opt/stride-shop/deploy/nginx.conf
cp /opt/stride-shop/deploy/nginx.conf /etc/nginx/sites-available/stride
ln -s /etc/nginx/sites-available/stride /etc/nginx/sites-enabled/stride
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# бесплатный сертификат Let's Encrypt (сам допишет 443 и редирект с http)
certbot --nginx -d ТВОЙ_ДОМЕН -d www.ТВОЙ_ДОМЕН
```

Открой `https://ТВОЙ_ДОМЕН` — должна загрузиться витрина.

---

## 7. Telegram-бот и мини-аппа

- **Webhook** поднимается сам при старте сервиса (есть `TG_BOT_TOKEN` + `PUBLIC_URL`).
  Проверка: `curl "https://api.telegram.org/bot<ТОКЕН>/getWebhookInfo"` → url на твой домен.
- **Мини-аппа в BotFather:** `/setmenubutton` (или Bot Settings → Menu Button) →
  URL = `https://ТВОЙ_ДОМЕН/static/tg/index.html`.

---

## 8. Проверка боевого флоу

1. `https://ТВОЙ_ДОМЕН` — каталог, корзина, оформление.
2. Зарегистрируйся → проверь, что письмо-подтверждение пришло, **ссылка в нём ведёт на https-домен** и подтверждает почту.
3. Оформи заказ → письма о статусах приходят.
4. Открой бота в Telegram → кнопка «Магазин» открывает мини-аппу.

---

## Обновление версии (после правок)

Локально запушил в репозиторий → на сервере:
```bash
cd /opt/stride-shop && ./deploy/deploy.sh
```
(подтянет код, поставит зависимости, прогонит миграции, перезапустит сервис, дёрнет healthz)

---

## Заметки

- **Бэкап БД:** `cp /opt/stride-shop/backend/shop.db ~/shop-$(date +%F).db` (можно по cron).
- **Письма в спам:** для боевой доходимости добавь в DNS домена **SPF/DKIM/DMARC**
  (см. провайдера почты). К работе ссылок отношения не имеет — только к папке доставки.
- **ЮKassa:** на портфолио держим тестовый режим; ключи — в `.env` (`YOOKASSA_*`).
