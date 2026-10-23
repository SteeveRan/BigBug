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
#   - Python 3.14+ (окружением управляет uv: .venv создаётся автоматически)
#   - установлен uv; зависимости ставятся автоматически из uv.lock
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

echo "=== Running unit tests (tests/unit/) ==="
ENVIRONMENT=test "${VENV_PYTHON[@]}" -m pytest tests/unit/ -v "$@"

echo ""
echo "=== Done ==="
