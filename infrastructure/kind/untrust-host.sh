#!/usr/bin/env bash
#
# untrust-host.sh — Убрать серты dev-стенда из system trust store.
#
# Обратная операция к trust-host.sh (симметрия teardown, ADR-0030 §4).
#
# Использование: ./untrust-host.sh
#
set -euo pipefail

readonly TRUST_DIR="/usr/local/share/ca-certificates"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }

removed=0
for crt in "${TRUST_DIR}"/bigbug-*.crt; do
  [[ -f "${crt}" ]] || { warn "Сертов bigbug-* в trust store нет."; exit 0; }
  sudo rm -f "${crt}"
  info "Удалён: ${crt}"
  removed=$((removed + 1))
done

if (( removed > 0 )); then
  sudo update-ca-certificates --fresh
fi
