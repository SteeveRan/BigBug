#!/usr/bin/env bash
#
# migrate-down.sh — Откатить последнюю миграцию Alembic.
#
# Использование:
#   ./scripts/migrate-down.sh          # откат на одну миграцию (-1)
#   ./scripts/migrate-down.sh -2       # откат на две миграции
#
# Требования:
#   - Python 3.14+ с виртуальным окружением (.venv)
#   - все зависимости из pyproject.toml установлены
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

STEPS="${1:--1}"

cd "$BACKEND_DIR"

echo "=== Откат миграций (downgrade ${STEPS}) ==="
"$VENV_PYTHON" -m alembic downgrade "${STEPS}"

echo ""
echo "=== Текущая ревизия ==="
"$VENV_PYTHON" -m alembic current

echo ""
echo "=== Done ==="
