#!/usr/bin/env bash
#
# lint.sh — Проверка кода backend (ruff check).
#
# Использование:
#   ./scripts/lint.sh
#
# Требования:
#   - Python 3.14+ с виртуальным окружением (корневой .venv проекта)
#   - установлен ruff: pip install ruff
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$(dirname "$BACKEND_DIR")"
VENV_PYTHON="${PROJECT_DIR}/.venv/bin/python"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "ОШИБКА: виртуальное окружение не найдено ($VENV_PYTHON)"
    echo "Создайте: python3 -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'"
    exit 1
fi

cd "$BACKEND_DIR"

echo "=== Running ruff check ==="
"$VENV_PYTHON" -m ruff check app/ tests/ || {
    echo "ПРЕДУПРЕЖДЕНИЕ: ruff не установлен. Установите: pip install ruff"
}

echo ""
echo "=== Done ==="
