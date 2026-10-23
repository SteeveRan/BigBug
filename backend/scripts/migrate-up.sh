#!/usr/bin/env bash
#
# migrate-up.sh — Применить все неприменённые миграции Alembic.
#
# Использование:
#   ./scripts/migrate-up.sh
#
# Требования:
#   - Python 3.14+ с виртуальным окружением (.venv)
#   - установлен uv; зависимости ставятся автоматически из uv.lock
#   - PostgreSQL доступен (см. DATABASE_URL в .env)
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

cd "$BACKEND_DIR"

echo "=== Применение миграций (upgrade head) ==="
"${VENV_PYTHON[@]}" -m alembic upgrade head

echo ""
echo "=== Текущая ревизия ==="
"${VENV_PYTHON[@]}" -m alembic current

echo ""
echo "=== Done ==="
