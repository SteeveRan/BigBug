#!/usr/bin/env bash
#
# teardown.sh — Удалить kind кластер bigbug-dev и записи из /etc/hosts
#
# Использование:
#   ./teardown.sh          — удалить кластер, сохранить /etc/hosts
#   ./teardown.sh --all    — удалить кластер и записи из /etc/hosts
#
set -euo pipefail

readonly CLUSTER_NAME="bigbug-dev"
readonly HOSTS=(
  "keycloak.local"
  "harbor.local"
  "app.local"
  "api.local"
  "gitlab.local"
)

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ---------------------------------------------------------------------------
# Удаление kind кластера
# ---------------------------------------------------------------------------
delete_cluster() {
  if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    info "Удаление kind кластера '$CLUSTER_NAME'..."
    kind delete cluster --name="$CLUSTER_NAME"
    info "Кластер '$CLUSTER_NAME' удалён."
  else
    warn "Кластер '$CLUSTER_NAME' не найден, пропускаем."
  fi
}

# ---------------------------------------------------------------------------
# Очистка /etc/hosts
# ---------------------------------------------------------------------------
cleanup_hosts() {
  local host
  for host in "${HOSTS[@]}"; do
    if grep -q "$host" /etc/hosts 2>/dev/null; then
      warn "Удаление записи $host из /etc/hosts (может потребоваться sudo)..."
      sudo sed -i "/${host}/d" /etc/hosts
      info "Запись $host удалена из /etc/hosts."
    else
      info "Запись $host не найдена в /etc/hosts."
    fi
  done
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
  local clean_all=false

  if [[ "${1:-}" == "--all" ]]; then
    clean_all=true
  fi

  echo ""
  info "=== Удаление kind кластера $CLUSTER_NAME ==="
  echo ""

  delete_cluster

  if $clean_all; then
    cleanup_hosts
  else
    warn "Записи в /etc/hosts сохранены. Используйте '--all' для полной очистки."
  fi

  echo ""
  info "Готово."
}

main "$@"
