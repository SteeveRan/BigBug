#!/usr/bin/env bash
#
# test-e2e.sh — Запуск e2e-тестов backend.
#
# Использование:
#   ./scripts/test-e2e.sh
#
# Требования:
#   - Python 3.14+ с виртуальным окружением (корневой .venv проекта)
#   - все зависимости из pyproject.toml установлены
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

echo "=== Running e2e tests (pytest -m e2e) ==="
"$VENV_PYTHON" -m pytest tests/ -v -m e2e "$@"

echo ""
echo "=== Done ==="
