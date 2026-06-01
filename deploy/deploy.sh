#!/usr/bin/env bash
# Обновление прод-версии на VPS: подтянуть код, поставить зависимости, перезапустить.
# Запуск на сервере:  cd /opt/stride-shop && ./deploy/deploy.sh
set -euo pipefail

cd "$(dirname "$0")/.."          # корень репозитория (/opt/stride-shop)
echo "==> git pull"
git pull --ff-only

echo "==> зависимости"
cd backend
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install -q -r requirements.txt

echo "==> миграции БД"
.venv/bin/alembic upgrade head || echo "alembic: пропущено (нет миграций/первый старт)"

echo "==> перезапуск сервиса"
sudo systemctl restart stride
sleep 2
curl -sf http://127.0.0.1:8077/healthz && echo "  <- healthz OK" || echo "  !! healthz не ответил, смотри: journalctl -u stride -e"
echo "==> готово"
