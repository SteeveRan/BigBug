#!/usr/bin/env bash
#
# init-harbor.sh — Инициализация проектов Harbor через REST API v2.0
#
# Создаёт три проекта, необходимых для работы BigBug:
#   - gold-images  — gold images (эталонные образы)
#   - app-images   — application images (собранные приложения)
#   - mirrors      — зеркалируемые образы из внешних реестров
#
# Требования:
#   - Harbor запущен и доступен (через deploy.sh)
#   - curl, jq
#
# Использование:
#   ./init-harbor.sh                        # Создать проекты
#   ./init-harbor.sh --dry-run              # Проверить, не создавая
#   ./init-harbor.sh --delete               # Удалить проекты
#
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly HARBOR_HOST="${HARBOR_HOST:-harbor.local}"
readonly HARBOR_HTTPS_PORT="${HARBOR_HTTPS_PORT:-30443}"
readonly HARBOR_URL="https://${HARBOR_HOST}:${HARBOR_HTTPS_PORT}"
readonly API_BASE="${HARBOR_URL}/api/v2.0"

# Учётные данные (dev-среда)
readonly HARBOR_USER="${HARBOR_USER:-admin}"
readonly HARBOR_PASS="${HARBOR_PASS:-Harbor12345}"

# Проекты для создания
readonly PROJECTS=(
  "gold-images"
  "app-images"
  "mirrors"
)

# Цветной вывод
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
success() { echo -e "${GREEN}[ ✓ ]${NC} $*"; }
fail()    { echo -e "${RED}[ ✗ ]${NC} $*"; }

readonly CURL_OPTS=(-s -k -u "${HARBOR_USER}:${HARBOR_PASS}" -H "Content-Type: application/json")

# ---------------------------------------------------------------------------
# Проверка доступности Harbor
# ---------------------------------------------------------------------------
check_harbor_health() {
  info "Проверка доступности Harbor API..."

  local response
  if response=$(curl "${CURL_OPTS[@]}" -o /dev/null -w "%{http_code}" "${API_BASE}/health" 2>/dev/null); then
    if [[ "$response" == "200" ]]; then
      success "Harbor API доступен: ${HARBOR_URL}"
      return 0
    else
      error "Harbor API вернул HTTP ${response}"
      return 1
    fi
  else
    error "Не удалось подключиться к Harbor API по адресу ${HARBOR_URL}"
    error "Убедитесь, что Harbor запущен: ${SCRIPT_DIR}/deploy.sh"
    return 1
  fi
}

# ---------------------------------------------------------------------------
# Проверить существование проекта
# Возвращает: 0 если существует, 1 если нет
# ---------------------------------------------------------------------------
project_exists() {
  local project_name="$1"
  local http_code

  http_code=$(curl "${CURL_OPTS[@]}" -o /dev/null -w "%{http_code}" \
    "${API_BASE}/projects/${project_name}" 2>/dev/null)

  [[ "$http_code" == "200" ]]
}

# ---------------------------------------------------------------------------
# Получить project_id по имени
# ---------------------------------------------------------------------------
get_project_id() {
  local project_name="$1"

  curl "${CURL_OPTS[@]}" "${API_BASE}/projects/${project_name}" 2>/dev/null \
    | jq -r '.project_id // 0'
}

# ---------------------------------------------------------------------------
# Создать проект
# ---------------------------------------------------------------------------
create_project() {
  local project_name="$1"
  local is_public="${2:-false}"

  if project_exists "$project_name"; then
    local pid
    pid=$(get_project_id "$project_name")
    success "Проект '${project_name}' уже существует (project_id=${pid})."
    return 0
  fi

  local http_code
  local response

  info "Создание проекта '${project_name}'..."

  response=$(curl "${CURL_OPTS[@]}" -w "\n%{http_code}" \
    -d "{
      \"project_name\": \"${project_name}\",
      \"public\": ${is_public},
      \"metadata\": {
        \"auto_scan\": \"false\",
        \"enable_content_trust\": \"false\",
        \"prevent_vul\": \"false\",
        \"reuse_sys_cve_allowlist\": \"true\",
        \"severity\": \"none\"
      },
      \"storage_limit\": -1
    }" \
    "${API_BASE}/projects" 2>/dev/null)

  http_code=$(echo "$response" | tail -1)
  local body
  body=$(echo "$response" | sed '$d')

  if [[ "$http_code" == "201" ]]; then
    success "Проект '${project_name}' создан (HTTP ${http_code})."
    return 0
  elif [[ "$http_code" == "409" ]]; then
    warn "Проект '${project_name}' уже существует (HTTP 409 Conflict)."
    return 0
  else
    error "Не удалось создать проект '${project_name}' (HTTP ${http_code})."
    if [[ -n "$body" ]]; then
      error "Ответ API: $(echo "$body" | jq -c '.errors // .message // "неизвестная ошибка"' 2>/dev/null || echo "$body")"
    fi
    return 1
  fi
}

# ---------------------------------------------------------------------------
# Удалить проект
# ---------------------------------------------------------------------------
delete_project() {
  local project_name="$1"

  if ! project_exists "$project_name"; then
    info "Проект '${project_name}' не существует, пропускаем."
    return 0
  fi

  warn "Удаление проекта '${project_name}'..."

  local http_code
  http_code=$(curl "${CURL_OPTS[@]}" -X DELETE \
    -o /dev/null -w "%{http_code}" \
    "${API_BASE}/projects/${project_name}" 2>/dev/null)

  if [[ "$http_code" == "200" ]]; then
    success "Проект '${project_name}' удалён (HTTP ${http_code})."
  else
    error "Не удалось удалить проект '${project_name}' (HTTP ${http_code})."
    return 1
  fi
}

# ---------------------------------------------------------------------------
# Вывести список проектов
# ---------------------------------------------------------------------------
list_projects() {
  info "Текущие проекты в Harbor:"
  echo ""

  local projects
  projects=$(curl "${CURL_OPTS[@]}" "${API_BASE}/projects" 2>/dev/null \
    | jq -r '.[] | "  \(.name)  (project_id=\(.project_id), public=\(.metadata.public), repos=\(.repo_count))"' 2>/dev/null) || true

  if [[ -z "$projects" ]]; then
    echo "  (нет проектов или ошибка API)"
  else
    echo "$projects"
  fi

  echo ""
}

# ---------------------------------------------------------------------------
# Dry-run: только проверка
# ---------------------------------------------------------------------------
dry_run() {
  info "=== DRY RUN: проверка проектов без создания ==="
  echo ""

  for project in "${PROJECTS[@]}"; do
    if project_exists "$project"; then
      local pid
      pid=$(get_project_id "$project")
      success "Проект '${project}' СУЩЕСТВУЕТ (project_id=${pid})."
    else
      echo -e "${CYAN}[  ? ]${NC} Проект '${project}' ОТСУТСТВУЕТ (будет создан)."
    fi
  done

  echo ""
  list_projects
}

# ---------------------------------------------------------------------------
# Usage
# ---------------------------------------------------------------------------
usage() {
  cat <<EOF
Использование: $(basename "$0") [ОПЦИИ]

Инициализация проектов Harbor для BigBug.

Опции:
  --dry-run     Проверить существование проектов без создания
  --delete      Удалить все проекты BigBug (gold-images, app-images, mirrors)
  -h, --help    Показать эту справку

Проекты:
  gold-images   — Gold images (эталонные образы)
  app-images    — Application images (собранные приложения)
  mirrors       — Зеркалируемые образы из внешних реестров

Переменные окружения:
  HARBOR_HOST         — Хост Harbor (по умолчанию: harbor.local)
  HARBOR_HTTPS_PORT   — HTTPS порт Harbor API (по умолчанию: 30443)
  HARBOR_USER         — Пользователь Harbor (по умолчанию: admin)
  HARBOR_PASS         — Пароль Harbor (по умолчанию: Harbor12345)

Примеры:
  ./init-harbor.sh              # Создать проекты
  ./init-harbor.sh --dry-run    # Проверить без создания
  ./init-harbor.sh --delete     # Удалить все проекты
EOF
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
  local mode="create"

  case "${1:-}" in
    --dry-run) mode="dry-run" ;;
    --delete)  mode="delete" ;;
    -h|--help) usage; exit 0 ;;
    "")        mode="create" ;;
    *)         error "Неизвестная опция: $1"; usage; exit 1 ;;
  esac

  echo ""
  echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
  echo -e "${CYAN}║   Инициализация проектов Harbor             ║${NC}"
  echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
  echo ""

  # Проверка зависимостей
  local deps=("curl" "jq")
  local missing=()
  for dep in "${deps[@]}"; do
    if ! command -v "$dep" &>/dev/null; then
      error "Отсутствует зависимость: ${dep}"
      missing+=("$dep")
    fi
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    error "Установите отсутствующие зависимости: ${missing[*]}"
    exit 1
  fi

  # Проверка доступности Harbor
  if ! check_harbor_health; then
    exit 1
  fi

  echo ""

  case "$mode" in
    "dry-run")
      dry_run
      ;;

    "delete")
      warn "=== УДАЛЕНИЕ проектов BigBug ==="
      echo ""
      local errors=0
      for project in "${PROJECTS[@]}"; do
        delete_project "$project" || ((errors++))
      done
      echo ""
      if [[ $errors -gt 0 ]]; then
        error "Удаление завершено с ${errors} ошибкой(ами)."
      else
        success "Все проекты удалены."
      fi
      echo ""
      list_projects
      ;;

    "create")
      info "Создание проектов..."
      echo ""
      local errors=0

      # gold-images — приватный (gold images чувствительны)
      create_project "gold-images" false  || ((errors++))

      # app-images — публичный (удобно для CI/CD pull)
      create_project "app-images" true    || ((errors++))

      # mirrors — публичный (зеркала должны быть доступны)
      create_project "mirrors" true       || ((errors++))

      echo ""
      if [[ $errors -gt 0 ]]; then
        error "Инициализация завершена с ${errors} ошибкой(ами)."
        exit 1
      else
        success "Все проекты инициализированы."
      fi

      echo ""
      list_projects
      ;;
  esac

  echo "============================================"
  echo -e "${GREEN}  Инициализация завершена.${NC}"
  echo "============================================"
}

main "$@"
