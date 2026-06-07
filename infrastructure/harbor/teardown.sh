#!/usr/bin/env bash
#
# teardown.sh — Удалить Harbor и kind кластер
#
# Использование:
#   ./teardown.sh          — удалить кластер, сохранить /etc/hosts
#   ./teardown.sh --all    — удалить кластер и запись из /etc/hosts
#
set -euo pipefail

readonly CLUSTER_NAME="harbor"
readonly HARBOR_HOST="harbor.local"

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
  if grep -q "$HARBOR_HOST" /etc/hosts 2>/dev/null; then
    warn "Удаление записи $HARBOR_HOST из /etc/hosts (может потребоваться sudo)..."
    sudo sed -i "/${HARBOR_HOST}/d" /etc/hosts
    info "Запись $HARBOR_HOST удалена из /etc/hosts."
  else
    info "Запись $HARBOR_HOST не найдена в /etc/hosts."
  fi
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
  info "=== Удаление Harbor из kind ==="
  echo ""

  delete_cluster

  if $clean_all; then
    cleanup_hosts
  else
    warn "Запись в /etc/hosts сохранена. Используйте '--all' для полной очистки."
    warn "  Текущая запись: $(grep "$HARBOR_HOST" /etc/hosts 2>/dev/null || echo 'не найдена')"
  fi

  echo ""
  info "Готово."
}

main "$@"
