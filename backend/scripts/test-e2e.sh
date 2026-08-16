#!/usr/bin/env bash
#
# test-e2e.sh — Запуск e2e-тестов backend против живого dev-стенда.
#
# Использование:
#   ./scripts/test-e2e.sh
#   ./scripts/test-e2e.sh -v        # подробный вывод
#   ./scripts/test-e2e.sh -k "test_api"  # фильтр по имени теста
#
# Требования:
#   - запущенный dev-стек: docker compose up -d (backend на localhost:8000)
#   - Python 3.14+ с виртуальным окружением (backend/.venv)
#   - все зависимости из pyproject.toml установлены (включая jsonschema)
#
# Настройка через переменные окружения:
#   BIGBUG_E2E_BASE_URL   — базовый URL backend (по умолчанию http://localhost:8000)
#   E2E_ADMIN_USERNAME    — логин администратора (по умолчанию admin)
#   E2E_ADMIN_PASSWORD    — пароль администратора (по умолчанию admin)
#
# Отчёт о покрытии эндпоинтов (backend/reports/endpoint-coverage.{json,md})
# генерируется автоматически в teardown сессии тестов.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="${BACKEND_DIR}/.venv/bin/python"

BASE_URL="${BIGBUG_E2E_BASE_URL:-http://localhost:8000}"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "ОШИБКА: виртуальное окружение не найдено ($VENV_PYTHON)"
    echo "Создайте: python3 -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'"
    exit 1
fi

cd "$BACKEND_DIR"

echo "=== Проверка доступности backend ($BASE_URL) ==="
if ! "$VENV_PYTHON" -c "
import sys, httpx
try:
    httpx.get('${BASE_URL}/api/health', timeout=5.0).raise_for_status()
except Exception as exc:
    print(f'Backend недоступен: {exc}', file=sys.stderr)
    print('Запустите dev-стек: docker compose up -d', file=sys.stderr)
    sys.exit(1)
"; then
    exit 1
fi
echo "Backend доступен."

echo ""
echo "=== Running e2e tests (tests/e2e/) ==="
# Без pytest-cov: покрытие кода измеряется отдельно скриптом test-e2e-coverage.sh.
"$VENV_PYTHON" -m pytest tests/e2e/ -v "$@"

echo ""
echo "=== Done ==="
