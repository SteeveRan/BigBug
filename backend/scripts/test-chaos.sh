#!/usr/bin/env bash
#
# test-chaos.sh — Chaos-тесты sync_engine (ADR-0039 guardrail 2, merge gate).
#
# Использование:
#   ./scripts/test-chaos.sh           # весь chaos-suite
#   ./scripts/test-chaos.sh -k crash  # фильтр по имени теста
#
# Требования: как у test-unit.sh (uv, Python 3.14+) — стенд не нужен.
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

echo "=== Running chaos tests (tests/chaos/) ==="
ENVIRONMENT=test "${VENV_PYTHON[@]}" -m pytest tests/chaos/ -v "$@"

echo ""
echo "=== Done ==="
