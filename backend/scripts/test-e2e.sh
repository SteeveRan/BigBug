#!/usr/bin/env bash
#
# test-e2e.sh — Запуск e2e-тестов backend.
#
# Использование:
#   ./scripts/test-e2e.sh
#   ./scripts/test-e2e.sh -v        # подробный вывод
#   ./scripts/test-e2e.sh -k "test_api"  # фильтр по имени теста
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

echo "=== Running e2e tests (tests/e2e/) ==="
"$VENV_PYTHON" -m pytest tests/e2e/ -v "$@"

echo ""
echo "=== Done ==="
