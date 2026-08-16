#!/usr/bin/env bash
#
# vulture.sh — Поиск мёртвого кода в backend (vulture).
#
# Использование:
#   ./scripts/vulture.sh                  # основной прогон (app/ scripts/ docker/)
#   ./scripts/vulture.sh tests/           # + тесты отдельным прогоном
#   ./scripts/vulture.sh --min-confidence 80
#
# Полный вывод сохраняется в backend/reports/vulture-report.txt.
# Сводка (количество находок + разбивка по confidence) печатается в stdout.
#
# Скрипт ВСЕГДА завершается с кодом 0, даже если vulture нашёл кандидатов
# (vulture возвращает код 3 при наличии находок) — чтобы его можно было
# спокойно запускать в CI/локально. При наличии находок выводится
# предупреждение.
#
# Требования:
#   - Python 3.14+ с виртуальным окружением (backend/.venv)
#   - установлен vulture (dev-зависимость: pip install -e '.[dev]')
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="${BACKEND_DIR}/.venv/bin/python"
WHITELIST="${BACKEND_DIR}/vulture-whitelist.py"
REPORT_DIR="${BACKEND_DIR}/reports"
REPORT_FILE="${REPORT_DIR}/vulture-report.txt"

# Порог по умолчанию можно переопределить через переменную окружения или
# аргументом командной строки (последний переданный --min-confidence побеждает).
MIN_CONFIDENCE="${VULTURE_MIN_CONFIDENCE:-60}"

if [ ! -x "$VENV_PYTHON" ]; then
    echo "ОШИБКА: виртуальное окружение не найдено ($VENV_PYTHON)" >&2
    echo "Создайте: python3 -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'" >&2
    exit 1
fi

if [ ! -f "$WHITELIST" ]; then
    echo "ОШИБКА: whitelist не найден ($WHITELIST)" >&2
    exit 1
fi

cd "$BACKEND_DIR"
mkdir -p "$REPORT_DIR"

# Основные пути + whitelist. Миграции исключаем: upgrade/downgrade вызывает
# alembic, это не «мёртвый» код. Тесты в основной прогон не включаем — они не
# бизнес-код; при необходимости передайте tests/ отдельным аргументом.
BASE_PATHS=(app/ scripts/ docker/ "$WHITELIST")

echo "=== Running vulture (min-confidence ${MIN_CONFIDENCE}) ==="

# vulture возвращает ExitCode.DeadCode (3) при наличии находок — не роняем скрипт.
set +e
"$VENV_PYTHON" -m vulture \
    --min-confidence "$MIN_CONFIDENCE" \
    --ignore-decorators '@router.*,@app.*' \
    --exclude 'alembic/versions*,*versions_backup*' \
    "${BASE_PATHS[@]}" \
    "$@" > "$REPORT_FILE" 2>&1
VULTURE_EXIT=$?
set -e

# Количество находок = строк вида "(NN% confidence)".
total="$(grep -cE '\([0-9]+% confidence\)' "$REPORT_FILE" || true)"

echo ""
if [ "$total" -gt 0 ]; then
    echo "ПРЕДУПРЕЖДЕНИЕ: vulture нашёл ${total} кандидатов в мёртвый код."
    echo ""
    echo "Разбивка по confidence:"
    grep -oE '\([0-9]+% confidence\)' "$REPORT_FILE" | sort | uniq -c | sort -rn
else
    echo "Мёртвый код не найден (при пороге confidence ${MIN_CONFIDENCE})."
fi

echo ""
echo "Полный отчёт сохранён: ${REPORT_FILE}"
echo ""
echo "--- Находки ---"
cat "$REPORT_FILE"
echo "--- Конец отчёта ---"
echo ""
echo "=== Done ==="

exit 0
