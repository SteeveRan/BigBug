#!/usr/bin/env bash
#
# export-openapi.sh — Экспорт OpenAPI-схемы в backend/openapi.json.
#
# Использование:
#   ./scripts/export-openapi.sh
#
# Требования:
#   - Python 3.14+ с виртуальным окружением (.venv)
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

echo "=== Экспорт OpenAPI-схемы ==="
"${VENV_PYTHON[@]}" -m scripts.export_openapi

echo ""
echo "=== Done ==="
