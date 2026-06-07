#!/usr/bin/env bash
#
# test.sh — Единый скрипт запуска тестов frontend (Vitest).
#
# Использование:
#   ./scripts/test.sh                        # Запуск всех тестов (unit + integrations)
#   ./scripts/test.sh --unit                 # Только unit-тесты
#   ./scripts/test.sh --integrations         # Только integration-тесты
#   ./scripts/test.sh --all                  # Все тесты (unit + integrations)
#   ./scripts/test.sh --coverage             # Все тесты с покрытием кода
#   ./scripts/test.sh -u -c                  # Unit-тесты с покрытием
#   ./scripts/test.sh -f Admin               # Запуск конкретного файла (по части имени)
#   ./scripts/test.sh -t "should render"     # Запуск тестов по паттерну имени
#   ./scripts/test.sh -w                     # Watch mode
#   ./scripts/test.sh --ui                   # Vitest UI
#   ./scripts/test.sh --help                 # Справка
#
# Требования:
#   - Node.js 24+ через nvm
#   - yarn (Berry) установлен
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$(dirname "$SCRIPT_DIR")"

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

cd "$FRONTEND_DIR"

# ─── Аргументы по умолчанию ───────────────────────────────────────────
SUITE="all"           # unit | integrations | e2e | all
COVERAGE=false
WATCH=false
UI=false
REPORT=false
FILE_FILTER=""
TEST_FILTER=""
EXTRA_ARGS=()

# ─── Разбор аргументов ────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --unit|-u)
            SUITE="unit"
            shift
            ;;
        --integrations|-i)
            SUITE="integrations"
            shift
            ;;
        --e2e|-e)
            SUITE="e2e"
            shift
            ;;
        --all|-a)
            SUITE="all"
            shift
            ;;
        --coverage|-c)
            COVERAGE=true
            shift
            ;;
        --watch|-w)
            WATCH=true
            shift
            ;;
        --ui)
            UI=true
            shift
            ;;
        --report|-r)
            REPORT=true
            shift
            ;;
        --file|-f)
            FILE_FILTER="$2"
            shift 2
            ;;
        --test|-t)
            TEST_FILTER="$2"
            shift 2
            ;;
        --help|-h)
            cat << 'EOF'
Usage: ./scripts/test.sh [OPTIONS]

Suites (выбор набора тестов):
  --unit, -u          Только unit-тесты (src/tests/unit/)
  --integrations, -i  Только integration-тесты (src/tests/integrations/)
  --e2e, -e           Только e2e-тесты (src/tests/e2e/) — пока не реализованы
  --all, -a           Все тесты (unit + integrations) — по умолчанию

Coverage:
  --coverage, -c      Генерация отчёта о покрытии кода (требует прогона тестов)
  --report, -r        Показать сводку покрытия из последнего прогона (без запуска)

Watch & UI:
  --watch, -w         Watch mode (перезапуск при изменениях)
  --ui                Vitest UI (интерактивный интерфейс в браузере)

Targeted run (для отладки конкретных падений):
  --file, -f <name>   Запустить файлы, содержащие <name> в пути
                      Пример: -f Admin → запустит все *Admin*.test.*
  --test, -t <pattern> Запустить тесты, имя которых совпадает с <pattern>
                      Пример: -t "should render title"

Прочие:
  --help, -h          Эта справка

Примеры:
  ./scripts/test.sh                           # Все тесты
  ./scripts/test.sh -u                        # Только unit
  ./scripts/test.sh -i -c                     # Integration с покрытием
  ./scripts/test.sh -f DockerImages           # Конкретный файл
  ./scripts/test.sh -f DockerImages -t "Index" # Конкретный тест в файле
  ./scripts/test.sh --ui                      # Vitest UI
EOF
            exit 0
            ;;
        *)
            EXTRA_ARGS+=("$1")
            shift
            ;;
    esac
done

# ─── Режим просмотра отчёта (без запуска тестов) ──────────────────────
if [[ "$REPORT" == "true" ]]; then
    REPORT_DIR="$FRONTEND_DIR/coverage"
    if [[ -f "$REPORT_DIR/index.html" ]]; then
        echo "=== Coverage Report ==="
        echo "Открываю HTML-отчёт: $REPORT_DIR/index.html"
        echo ""
        cat "$REPORT_DIR/coverage-summary.json" 2>/dev/null | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    total = data.get('total', {})
    lines = total.get('lines', {})
    stmts = total.get('statements', {})
    branches = total.get('branches', {})
    funcs = total.get('functions', {})
    print('═══════════════════════════════════════')
    print('         Coverage Summary')
    print('═══════════════════════════════════════')
    for name, m in [('Statements', stmts), ('Branches', branches), ('Functions', funcs), ('Lines', lines)]:
        pct = m.get('pct', 0)
        covered = m.get('covered', 0)
        total_n = m.get('total', 0)
        bar = '█' * int(pct / 5) + '░' * (20 - int(pct / 5))
        print(f'  {name:<12} {bar} {pct:5.1f}% ({covered}/{total_n})')
    print('═══════════════════════════════════════')
except Exception:
    print('(не удалось прочитать coverage-summary.json)')
" || true
        echo ""
        echo "Для просмотра в браузере: open $REPORT_DIR/index.html"
    else
        echo "❌ HTML-отчёт не найден. Сначала запустите тесты с --coverage."
        exit 1
    fi
    exit 0
fi

# ─── Проверка e2e (пока не реализованы) ───────────────────────────────
if [[ "$SUITE" == "e2e" ]]; then
    echo "=== E2E тесты ==="
    echo "ℹ E2E-тесты (Cypress) ещё не настроены. Используйте --unit или --integrations."
    exit 0
fi

# ─── Формирование команды vitest ──────────────────────────────────────
CMD=("yarn" "vitest" "run")

# Watch mode — убираем "run"
if [[ "$WATCH" == "true" ]]; then
    CMD=("yarn" "vitest")
fi

# UI mode
if [[ "$UI" == "true" ]]; then
    CMD=("yarn" "vitest" "--ui")
fi

# Coverage
if [[ "$COVERAGE" == "true" ]]; then
    CMD+=("--coverage")
fi

# Фильтр по suite: задаём конкретную директорию
case "$SUITE" in
    unit)
        CMD+=("src/tests/unit")
        ;;
    integrations)
        CMD+=("src/tests/integrations")
        ;;
    all)
        # Без фильтра — vitest сам найдёт всё по include/exclude в конфиге
        ;;
esac

# Фильтр по имени файла
if [[ -n "$FILE_FILTER" ]]; then
    # Ищем файлы, содержащие подстроку в пути
    MATCHING=$(find src/tests -type f -name "*${FILE_FILTER}*" 2>/dev/null | head -20)
    if [[ -z "$MATCHING" ]]; then
        echo "❌ Файлы по фильтру '$FILE_FILTER' не найдены в src/tests/"
        exit 1
    fi
    # Добавляем найденные файлы как аргументы
    while IFS= read -r f; do
        CMD+=("$f")
    done <<< "$MATCHING"
fi

# Фильтр по имени теста
if [[ -n "$TEST_FILTER" ]]; then
    CMD+=("-t" "$TEST_FILTER")
fi

# Дополнительные аргументы
if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
    CMD+=("${EXTRA_ARGS[@]}")
fi

# ─── Вывод и запуск ───────────────────────────────────────────────────
echo "=== Frontend Tests ==="
echo "Suite:       $SUITE"
echo "Coverage:    $COVERAGE"
echo "Watch:       $WATCH"
[[ -n "$FILE_FILTER" ]] && echo "File filter: $FILE_FILTER"
[[ -n "$TEST_FILTER" ]] && echo "Test filter: $TEST_FILTER"
echo "Command:     ${CMD[*]}"
echo ""

"${CMD[@]}"
