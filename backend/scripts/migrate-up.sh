#!/usr/bin/env bash
#
# migrate-up.sh — Применить все неприменённые миграции Alembic.
#
# Использование:
#   ./scripts/migrate-up.sh
#
# Требования:
#   - Python 3.14+ с виртуальным окружением (.venv)
#   - все зависимости из pyproject.toml установлены
#   - PostgreSQL доступен (см. DATABASE_URL в .env)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="${BACKEND_DIR}/.venv/bin/python"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "ОШИБКА: виртуальное окружение не найдено ($VENV_PYTHON)"
    echo "Создайте: python3 -m venv .venv && source .venv/bin/activate && pip install -e ."
    exit 1
fi

cd "$BACKEND_DIR"

echo "=== Применение миграций (upgrade head) ==="
"$VENV_PYTHON" -m alembic upgrade head

echo ""
echo "=== Текущая ревизия ==="
"$VENV_PYTHON" -m alembic current

echo ""
echo "=== Done ==="
