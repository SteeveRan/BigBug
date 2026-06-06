#!/usr/bin/env bash
#
# format.sh — Форматирование кода backend (black + ruff fix).
#
# Использование:
#   ./scripts/format.sh
#
# Требования:
#   - Python 3.14+ с виртуальным окружением (корневой .venv проекта)
#   - установлены black и ruff: pip install black ruff
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

echo "=== Formatting with black ==="
"$VENV_PYTHON" -m black app/ tests/ || {
    echo "ПРЕДУПРЕЖДЕНИЕ: black не установлен. Установите: pip install black"
}

echo ""
echo "=== Fixing with ruff ==="
"$VENV_PYTHON" -m ruff check --fix app/ tests/ || {
    echo "ПРЕДУПРЕЖДЕНИЕ: ruff не установлен. Установите: pip install ruff"
}

echo ""
echo "=== Done ==="
