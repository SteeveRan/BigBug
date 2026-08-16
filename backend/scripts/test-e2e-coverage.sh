#!/usr/bin/env bash
#
# test-e2e-coverage.sh — Замер code coverage e2e-прогона.
#
# Запускает backend в отдельном процессе под ``coverage run``, прогоняет
# e2e-тесты против него, затем снимает профиль coverage и формирует отчёт.
#
# Использование:
#   ./scripts/test-e2e-coverage.sh
#   ./scripts/test-e2e-coverage.sh -v            # pytest подробный вывод
#   ./scripts/test-e2e-coverage.sh -k "test_api" # фильтр по имени теста
#
# Требования:
#   - backend/.venv с установленными dev-зависимостями (coverage, pytest)
#   - PostgreSQL/Redis из dev-стека (docker compose up -d), БД накатана миграциями
#   - переменные окружения из backend/.env (DATABASE_URL, REDIS_URL, ...)
#
# Порты можно переопределить через COVERAGE_PORT (по умолчанию 8011), чтобы
# не конфликтовать с уже запущенным dev-сервером на 8000.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="${BACKEND_DIR}/.venv/bin/python"

COVERAGE_PORT="${COVERAGE_PORT:-8011}"
BASE_URL="http://localhost:${COVERAGE_PORT}"
PID_FILE="$(mktemp)"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "ОШИБКА: виртуальное окружение не найдено ($VENV_PYTHON)"
    echo "Создайте: python3 -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'"
    exit 1
fi

cd "$BACKEND_DIR"

# 1. Загрузить переменные окружения из backend/.env (если есть).
if [ -f ".env" ]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
fi

cleanup() {
    if [ -s "$PID_FILE" ]; then
        kill "$(cat "$PID_FILE")" 2>/dev/null || true
        wait "$(cat "$PID_FILE")" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
    rm -f .coverage.host
}
trap cleanup EXIT

echo "=== Запуск backend под coverage (порт ${COVERAGE_PORT}) ==="
"$VENV_PYTHON" -m coverage run \
    --data-file=.coverage.host \
    -m uvicorn app.main:app \
    --host 127.0.0.1 \
    --port "$COVERAGE_PORT" \
    >/tmp/bigbug-e2e-coverage-uvicorn.log 2>&1 &
echo $! > "$PID_FILE"

# 2. Дождаться готовности сервера.
echo "=== Ожидание готовности backend ==="
for _ in $(seq 1 60); do
    if "$VENV_PYTHON" -c "
import httpx
try:
    httpx.get('${BASE_URL}/api/health', timeout=2.0).raise_for_status()
except Exception:
    raise SystemExit(1)
" 2>/dev/null; then
        break
    fi
    sleep 1
done

if ! "$VENV_PYTHON" -c "
import httpx
httpx.get('${BASE_URL}/api/health', timeout=2.0).raise_for_status()
" 2>/dev/null; then
    echo "ОШИБКА: backend под coverage не поднялся. Лог: /tmp/bigbug-e2e-coverage-uvicorn.log"
    exit 1
fi

# 3. Прогнать e2e-тесты против поднятого сервера.
echo ""
echo "=== Running e2e tests против ${BASE_URL} ==="
BIGBUG_E2E_BASE_URL="$BASE_URL" "$VENV_PYTHON" -m pytest tests/e2e/ -v "$@"

# 4. Остановить сервер и снять покрытие.
kill "$(cat "$PID_FILE")" 2>/dev/null || true
wait "$(cat "$PID_FILE")" 2>/dev/null || true
: > "$PID_FILE"

echo ""
echo "=== Формирование отчёта о покрытии кода ==="
"$VENV_PYTHON" -m coverage report --data-file=.coverage.host
"$VENV_PYTHON" -m coverage html --data-file=.coverage.host -d htmlcov

echo ""
echo "Отчёты:"
echo "  - текст: вывод выше (coverage report)"
echo "  - HTML:  ${BACKEND_DIR}/htmlcov/index.html"
echo "  - эндпоинты: ${BACKEND_DIR}/reports/endpoint-coverage.md"
echo ""
echo "=== Done ==="
