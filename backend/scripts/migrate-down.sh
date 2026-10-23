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
#   - установлен uv; зависимости ставятся автоматически из uv.lock
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON=(uv run --project "$BACKEND_DIR" python)

if ! command -v uv >/dev/null 2>&1; then
    echo "ОШИБКА: uv не установлен"
    echo "Установите: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

STEPS="${1:--1}"

cd "$BACKEND_DIR"

echo "=== Откат миграций (downgrade ${STEPS}) ==="
"${VENV_PYTHON[@]}" -m alembic downgrade "${STEPS}"

echo ""
echo "=== Текущая ревизия ==="
"${VENV_PYTHON[@]}" -m alembic current

echo ""
echo "=== Done ==="
