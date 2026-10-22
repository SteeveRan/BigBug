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
# Docker insecure registry for harbor.local:80 (adapted from the retired
# infrastructure/harbor/deploy.sh configure_docker_insecure)
# ---------------------------------------------------------------------------
configure_docker_insecure() {
  local daemon_json="/etc/docker/daemon.json"
  local insecure_reg="harbor.local:80"

  info "Проверка Docker insecure registry..."

  if [[ -f "$daemon_json" ]] && grep -q "$insecure_reg" "$daemon_json" 2>/dev/null; then
    info "  ✓ Insecure registry уже настроен в $daemon_json"
    return
  fi

  if [[ $EUID -eq 0 ]]; then
    warn "Запуск от root — sudo не нужен, продолжаем."
  fi

  if [[ -f "$daemon_json" ]] && ! command -v jq &>/dev/null; then
    warn "  jq не найден. Добавьте вручную в $daemon_json:"
    warn "    \"insecure-registries\": [\"$insecure_reg\"]"
    return
  fi

  warn "Настройка Docker daemon для insecure registry (нужен sudo)..."
  if [[ -f "$daemon_json" ]]; then
    # `unique` only works on arrays — normalize a scalar entry first
    sudo jq --arg reg "$insecure_reg" \
      '."insecure-registries" = (((."insecure-registries" // []) | (if type == "array" then . else [.] end)) + [$reg] | unique)' \
      "$daemon_json" | sudo tee "${daemon_json}.tmp" >/dev/null \
      && sudo mv "${daemon_json}.tmp" "$daemon_json"
  else
    echo "{\"insecure-registries\": [\"${insecure_reg}\"]}" | sudo tee "$daemon_json" >/dev/null
  fi

  warn "Перезапуск Docker daemon..."
  sudo systemctl restart docker 2>/dev/null || sudo service docker restart 2>/dev/null || true
  info "Docker insecure registry настроен."
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
  add_hosts_entry
  configure_docker_insecure
  create_kind_cluster
  print_instructions
}

main "$@"
