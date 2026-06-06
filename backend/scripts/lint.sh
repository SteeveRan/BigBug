#!/usr/bin/env bash
#
# lint.sh — Проверка кода backend (ruff check).
#
# Использование:
#   ./scripts/lint.sh
#
# Требования:
#   - Python 3.14+ с виртуальным окружением (backend/.venv)
#   - установлен ruff: pip install ruff
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="${BACKEND_DIR}/.venv/bin/python"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "ОШИБКА: виртуальное окружение не найдено ($VENV_PYTHON)"
    echo "Создайте: python3 -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'"
    exit 1
fi

cd "$BACKEND_DIR"

echo "=== Running ruff check ==="
if "$VENV_PYTHON" -m ruff check app/ tests/ 2>&1; then
    echo "No issues found."
else
    echo ""
    echo "ПРЕДУПРЕЖДЕНИЕ: ruff check нашёл ошибки (код $?)."
    echo "Для автоматического исправления: ./scripts/format.sh"
    echo "Для детального просмотра: $VENV_PYTHON -m ruff check app/ tests/"
fi

echo ""
echo "=== Done ==="
