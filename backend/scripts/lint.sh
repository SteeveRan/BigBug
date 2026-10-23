#!/usr/bin/env bash
#
# lint.sh — Проверка кода backend (ruff check).
#
# Использование:
#   ./scripts/lint.sh
#
# Требования:
#   - Python 3.14+ с виртуальным окружением (backend/.venv)
#   - установлен ruff: uv sync
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

echo "=== Running ruff check ==="
if "${VENV_PYTHON[@]}" -m ruff check app/ tests/ 2>&1; then
    echo "No issues found."
else
    echo ""
    echo "ПРЕДУПРЕЖДЕНИЕ: ruff check нашёл ошибки (код $?)."
    echo "Для автоматического исправления: ./scripts/format.sh"
    echo "Для детального просмотра: uv run --project backend python -m ruff check app/ tests/"
fi

echo ""
echo "=== Done ==="
