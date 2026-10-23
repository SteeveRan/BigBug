#!/usr/bin/env bash
#
# bootstrap.sh — Создать kind кластер bigbug-dev + записи /etc/hosts
#
# In-cluster сущности (haproxy-ingress, операторы) ставятся OpenTofu:
# infrastructure/terraform/base (ADR-0029). Этот скрипт — только императивный
# минимум: кластер + hosts.
#
# Зависимости: kind, kubectl, docker (tofu/helm нужны для tofu-слоя, не здесь)
# Использование: ./bootstrap.sh
#
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly CLUSTER_NAME="bigbug-dev"
readonly HOSTS=(
  "keycloak.local"
  "harbor.local"
  "app.local"
  "api.local"
  "gitlab.local"
)

# Цветной вывод
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ---------------------------------------------------------------------------
# Серты (ADR-0030 §3): до кластера — порядок certs → bootstrap обязателен
# ---------------------------------------------------------------------------
check_certs() {
  local certs_dir="${XDG_STATE_HOME:-$HOME/.local/state}/bigbug/certs"
  for host in "${HOSTS[@]}"; do
    if [[ ! -f "${certs_dir}/${host}/tls.crt" || ! -f "${certs_dir}/${host}/tls.key" ]]; then
      error "Серты не найдены: ${certs_dir}/${host}/"
      error "Запустите сначала: ${SCRIPT_DIR}/certs.sh"
      exit 1
    fi
  done
  info "Серты на месте (${#HOSTS[@]} хостов, ${certs_dir})."
}

# ---------------------------------------------------------------------------
# Проверка зависимостей
# ---------------------------------------------------------------------------
check_dependencies() {
  info "Проверка зависимостей..."

  local deps=("kind" "kubectl" "docker")
  local missing=()

  for dep in "${deps[@]}"; do
    if command -v "$dep" &>/dev/null; then
      info "  ✓ $dep"
    else
      error "  ✗ $dep не найден"
      missing+=("$dep")
    fi
  done

  if [[ ${#missing[@]} -gt 0 ]]; then
    error "Отсутствуют зависимости: ${missing[*]}"
    error "Установите их и повторите попытку."
    exit 1
  fi
}

# ---------------------------------------------------------------------------
# /etc/hosts: idempotent add of ingress hostnames
# ---------------------------------------------------------------------------
add_hosts_entry() {
  local host
  for host in "${HOSTS[@]}"; do
    if grep -q "$host" /etc/hosts 2>/dev/null; then
      info "Запись /etc/hosts для $host уже существует."
    else
      warn "Добавление записи в /etc/hosts (может потребоваться sudo)..."
      echo "127.0.0.1 $host" | sudo tee -a /etc/hosts >/dev/null
      info "Добавлено: 127.0.0.1 $host"
    fi
  done
}

# ---------------------------------------------------------------------------
# Создание kind кластера (idempotent)
# ---------------------------------------------------------------------------
create_kind_cluster() {
  if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    warn "Кластер '$CLUSTER_NAME' уже существует, пропускаем создание."
    return
  fi

  info "Создание kind кластера '$CLUSTER_NAME'..."
  kind create cluster --config="${SCRIPT_DIR}/kind-config.yaml" --name="$CLUSTER_NAME"

  # Проверка подключения
  kubectl cluster-info --context "kind-${CLUSTER_NAME}"
}

# ---------------------------------------------------------------------------
# Вывод инструкций
# ---------------------------------------------------------------------------
print_instructions() {
  echo ""
  echo "============================================"
  echo -e "${GREEN}  Кластер '$CLUSTER_NAME' готов!${NC}"
  echo "============================================"
  echo ""
  echo "Дальше — in-cluster сущности через OpenTofu (ADR-0029):"
  echo "  cd infrastructure/terraform/base && tofu init && tofu apply"
  echo ""
  echo "Проверка ingress (после base-apply):"
  echo "  curl -H 'Host: app.local' http://localhost/"
  echo ""
  echo "Удаление:"
  echo "  ${SCRIPT_DIR}/teardown.sh"
  echo "============================================"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
  echo ""
  info "=== Bootstrap kind кластера $CLUSTER_NAME ==="
  echo ""

  # extraMounts в kind-config.yaml заданы относительно корня репозитория
  cd "${SCRIPT_DIR}/../.."

  check_dependencies
  check_certs
  add_hosts_entry
  create_kind_cluster
  print_instructions
}

main "$@"
