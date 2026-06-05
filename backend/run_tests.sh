#!/usr/bin/env bash
#
# run_tests.sh — Запуск автотестов BigBug backend.
#
# Использование:
#   ./run_tests.sh               # все тесты
#   ./run_tests.sh -v            # подробный вывод
#   ./run_tests.sh -x            # остановка после первой ошибки
#   ./run_tests.sh tests/test_oidc.py  # конкретный файл
#   ./run_tests.sh -k "test_login"     # фильтр по имени теста
#
# Требования:
#   - Python 3.12+ с виртуальным окружением .venv
#   - все зависимости из pyproject.toml установлены

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${SCRIPT_DIR}/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
    echo "ОШИБКА: виртуальное окружение не найдено ($PYTHON)"
    echo "Создайте его: python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'"
    exit 1
fi

cd "$SCRIPT_DIR"

echo "=== Запуск pytest ==="
exec "$PYTHON" -m pytest tests/ "$@" --tb=short
