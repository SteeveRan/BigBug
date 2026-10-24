#!/usr/bin/env bash
#
# untrust-host.sh — Убрать CA dev-стенда из system trust store.
#
# Обратная операция к trust-host.sh (симметрия teardown, ADR-0030 §4):
# один CA-серт покрывает все хосты.
#
# Использование: ./untrust-host.sh
#
set -euo pipefail

readonly TRUST_TARGET="/usr/local/share/ca-certificates/bigbug-dev-ca.crt"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }

if [[ -f "${TRUST_TARGET}" ]]; then
  sudo rm -f "${TRUST_TARGET}"
  info "Удалён: ${TRUST_TARGET}"
  sudo update-ca-certificates --fresh
else
  warn "CA bigbug в trust store нет."
fi
