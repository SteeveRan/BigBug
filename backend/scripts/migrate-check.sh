#!/usr/bin/env bash
#
# migrate-check.sh — Накатить все миграции на чистую копию БД (multi-agent
# pre-merge check: ловит конфликтующие головы alembic до мержа в main).
#
# Использование:
#   ./scripts/migrate-check.sh              # БД bigbug_migrate_check
#   ./scripts/migrate-check.sh my_check_db  # своё имя БД
#
# Требования:
#   - запущенный контейнер postgres-backend (make dev-up — владелец инфры)
#   - .venv backend с зависимостями
#   - backend/.env содержит DATABASE_URL (хост/юзер) — имя БД подменяется
#     на check-БД, поэтому к общим данным ветки скрипт не прикасается
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="${BACKEND_DIR}/.venv/bin/python"
DB_NAME="${1:-bigbug_migrate_check}"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "ОШИБКА: виртуальное окружение не найдено ($VENV_PYTHON)"
    exit 1
fi

COMPOSE_APP="docker compose"
if [ -z "$($COMPOSE_APP ps -q postgres-backend 2>/dev/null)" ]; then
    echo "ОШИБКА: контейнер postgres-backend не запущен (make dev-up)."
    exit 1
fi

PG_USER="${POSTGRES_USER:-bigbug}"
echo "=== Recreate check-БД: ${DB_NAME} ==="
$COMPOSE_APP exec postgres-backend psql -U "$PG_USER" -c "DROP DATABASE IF EXISTS ${DB_NAME}"
$COMPOSE_APP exec postgres-backend psql -U "$PG_USER" -c "CREATE DATABASE ${DB_NAME}"

cd "$BACKEND_DIR"

# Прогоняем alembic с БД чека: подменяем имя БД в DATABASE_URL из окружения,
# остальное (хост/пользователь) берётся из backend/.env как обычно.
CHECK_URL="$("$VENV_PYTHON" -c "
import sys
sys.path.insert(0, '.')
from app.config import settings
url = str(settings.database_url)
head, sep, _tail = url.rpartition('/')
print(head + sep + '${DB_NAME}')
")"
echo "=== Alembic upgrade head → ${DB_NAME} ==="
DATABASE_URL="$CHECK_URL" "$VENV_PYTHON" -m alembic upgrade head

echo "=== Текущая ревизия ==="
DATABASE_URL="$CHECK_URL" "$VENV_PYTHON" -m alembic current

echo ""
echo "=== OK: все миграции ветки накатываются на чистую БД (${DB_NAME}) ==="
echo "Удалить: make dev-db-drop DB=${DB_NAME}"
