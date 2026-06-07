#!/usr/bin/env bash
#
# test-unit.sh — Запуск юнит-тестов backend.
#
# Использование:
#   ./scripts/test-unit.sh           # все юнит-тесты
#   ./scripts/test-unit.sh -v        # подробный вывод
#   ./scripts/test-unit.sh -x        # остановка после первой ошибки
#   ./scripts/test-unit.sh -k "test_login"  # фильтр по имени теста
#
# Требования:
#   - Python 3.14+ с виртуальным окружением (корневой .venv проекта)
#   - все зависимости из pyproject.toml установлены
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

echo "=== Running unit tests (tests/unit/) ==="
"$VENV_PYTHON" -m pytest tests/unit/ -v "$@"

echo ""
echo "=== Done ==="
