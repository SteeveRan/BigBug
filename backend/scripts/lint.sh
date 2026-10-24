#!/usr/bin/env bash
#
# lint.sh — Проверка кода backend (ruff check + ruff format --check).
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
if ! "${VENV_PYTHON[@]}" -m ruff check app/ tests/; then
    echo ""
    echo "ОШИБКА: ruff check нашёл замечания."
    echo "Для автоматического исправления: ./scripts/format.sh"
    exit 1
fi
echo "No issues found."

echo ""
echo "=== Running ruff format --check ==="
if ! "${VENV_PYTHON[@]}" -m ruff format --check app/ tests/; then
    echo ""
    echo "ОШИБКА: форматирование разошлось с ruff format."
    echo "Для исправления: ./scripts/format.sh (или make format-backend)"
    exit 1
fi

echo ""
echo "=== Done ==="
