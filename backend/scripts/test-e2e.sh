#!/usr/bin/env bash
#
# test-e2e.sh — Запуск e2e-тестов backend против живого dev-стенда (kind).
#
# Использование:
#   make test-e2e-backend                          # канонический запуск (через make)
#   ./scripts/test-e2e.sh -v                       # напрямую (env уже задан make)
#   ./scripts/test-e2e.sh -k "test_api"            # фильтр по имени теста
#
# Требования:
#   - запущенный dev-стенд: make infra-init (kind) + helm upgrade bigbug
#   - окружение (SSL_CERT_FILE/DATABASE_URL) задаёт make: backend/scripts/e2e-env.sh
#   - Python 3.14+ с виртуальным окружением (backend/.venv)
#   - установлен uv; зависимости ставятся автоматически из uv.lock
#
# Учетные записи (ADR-0024 §3): прогон начинается с идемпотентного seed
# (scripts/seed-e2e.sh) — креды e2e: константы в scripts/seed_e2e.py /
# tests/e2e/conftest.py, никаких E2E_ADMIN_USERNAME/E2E_ADMIN_PASSWORD.
#
# Настройка через переменные окружения:
#   BIGBUG_E2E_BASE_URL   — базовый URL backend (по умолчанию https://api.local)
#
# Отчёт о покрытии эндпоинтов (backend/reports/endpoint-coverage.{json,md})
# генерируется автоматически в teardown сессии тестов.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON=(uv run --project "$BACKEND_DIR" python)

BASE_URL="${BIGBUG_E2E_BASE_URL:-https://api.local}"

if ! command -v uv >/dev/null 2>&1; then
    echo "ОШИБКА: uv не установлен"
    echo "Установите: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

cd "$BACKEND_DIR"

echo "=== Seeding e2e accounts ==="
"$SCRIPT_DIR/seed-e2e.sh"

echo ""
echo "=== Проверка доступности backend ($BASE_URL) ==="
if ! "${VENV_PYTHON[@]}" -c "
import sys, httpx
try:
    httpx.get('${BASE_URL}/api/health', timeout=5.0).raise_for_status()
except Exception as exc:
    print(f'Backend недоступен: {exc}', file=sys.stderr)
    print('Поднимите dev-стенд: make infra-init (+ helm upgrade bigbug).', file=sys.stderr)
    print('TLS-ошибка? Сгенерируйте серты: infrastructure/kind/certs.sh (ADR-0030 §3).', file=sys.stderr)
    sys.exit(1)"; then
    exit 1
fi
echo "Backend доступен."

echo ""
echo "=== Running e2e tests (tests/e2e/) ==="
# Без pytest-cov: покрытие кода измеряется отдельно скриптом test-e2e-coverage.sh.
"${VENV_PYTHON[@]}" -m pytest tests/e2e/ -v "$@"

echo ""
echo "=== Done ==="
