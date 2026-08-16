#!/usr/bin/env bash
#
# export-openapi.sh — Экспорт OpenAPI-схемы в backend/openapi.json.
#
# Использование:
#   ./scripts/export-openapi.sh
#
# Требования:
#   - Python 3.14+ с виртуальным окружением (.venv)
#   - все зависимости из pyproject.toml установлены
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="${BACKEND_DIR}/.venv/bin/python"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "ОШИБКА: виртуальное окружение не найдено ($VENV_PYTHON)"
    echo "Создайте: python3 -m venv .venv && source .venv/bin/activate && pip install -e ."
    exit 1
fi

cd "$BACKEND_DIR"

echo "=== Экспорт OpenAPI-схемы ==="
"$VENV_PYTHON" -m scripts.export_openapi

echo ""
echo "=== Done ==="
