#!/usr/bin/env bash
#
# format.sh — Форматирование кода backend (ruff format + ruff check --fix).
#
# Использование:
#   ./scripts/format.sh
#
# Требования:
#   - Python 3.14+ с виртуальным окружением (backend/.venv)
#   - установлен ruff: pip install ruff
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

echo "=== Formatting with ruff format ==="
if "$VENV_PYTHON" -m ruff format app/ tests/ 2>&1; then
    echo "Formatting complete."
else
    echo "ПРЕДУПРЕЖДЕНИЕ: ruff format завершился с ошибкой (код $?)."
    echo "Убедитесь, что ruff установлен: pip install ruff"
fi

echo ""
echo "=== Fixing with ruff check --fix ==="
if "$VENV_PYTHON" -m ruff check --fix app/ tests/ 2>&1; then
    echo "No issues found."
else
    echo "ПРЕДУПРЕЖДЕНИЕ: ruff check нашёл ошибки, которые не удалось исправить автоматически."
    echo "Запустите 'ruff check app/ tests/' для просмотра."
fi

echo ""
echo "=== Done ==="
