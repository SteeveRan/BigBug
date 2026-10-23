#!/usr/bin/env bash
#
# seed-e2e.sh — Идемпотентный сид e2e-учёток в БД BigBug (ADR-0024 §3).
#
# Создаёт/обновляет e2e-пользователей (e2e-admin/e2e-viewer/e2e-operator,
# пароли — константы в scripts/seed_e2e.py). Вызывается из test-e2e*.sh
# перед прогоном; повторный запуск безопасен.
#
# Окружение (DATABASE_URL и др.) задаёт вызывающий контекст — make-цель
# (test-e2e-seed / test-e2e-backend) сорсирует scripts/e2e-env.sh. При
# запуске напрямую без DATABASE_URL — честная ошибка с подсказкой.
#
# Использование (канонично через make):
#   make test-e2e-seed
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

if [ -z "${DATABASE_URL:-}" ]; then
    echo "ОШИБКА: DATABASE_URL не задан. Запускайте через make: make test-e2e-seed" >&2
    exit 1
fi

cd "$BACKEND_DIR"

echo "=== Seeding e2e accounts (scripts/seed_e2e.py) ==="
"${VENV_PYTHON[@]}" -m scripts.seed_e2e
echo "=== Seed complete ==="
