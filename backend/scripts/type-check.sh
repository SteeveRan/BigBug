#!/usr/bin/env bash
#
# type-check.sh — Проверка типов backend (mypy).
#
# Использование:
#   ./scripts/type-check.sh
#
# Требования:
#   - Python 3.14+ с виртуальным окружением (backend/.venv)
#   - установлен mypy: pip install -e '.[dev]'
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="${BACKEND_DIR}/.venv/bin/python"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "ОШИБКА: виртуальное окружение не найдено ($VENV_PYTHON)" >&2
    echo "Создайте: python3 -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'" >&2
    exit 1
fi

cd "$BACKEND_DIR"

echo "=== Running mypy ==="
"$VENV_PYTHON" -m mypy app/

echo ""
echo "=== Done ==="
