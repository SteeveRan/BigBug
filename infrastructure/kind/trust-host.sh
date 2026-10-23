#!/usr/bin/env bash
#
# trust-host.sh — Добавить серты dev-стенда в system trust store (ADR-0030 §4).
#
# Ручной шаг пользователя (sudo — осознанное действие). После него браузер,
# curl, docker daemon, httpx e2e и tofu доверяют https://*.local без -k.
# Повторный запуск безопасен (idempotent).
#
# shortcut: Debian/Ubuntu only (update-ca-certificates), при появлении macOS/Fedora — добавить ветки
#
# Использование: ./trust-host.sh
#
set -euo pipefail

readonly CERTS_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/bigbug/certs"
readonly TRUST_DIR="/usr/local/share/ca-certificates"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

if [[ ! -d "${CERTS_DIR}" ]] || ! ls "${CERTS_DIR}"/*/tls.crt &>/dev/null; then
  error "Серты не найдены в ${CERTS_DIR} — сначала запустите certs.sh."
  exit 1
fi

if [[ $EUID -ne 0 ]] && ! sudo -v 2>/dev/null; then
  error "Нужен sudo для записи в system trust store."
  exit 1
fi

for crt in "${CERTS_DIR}"/*/tls.crt; do
  host="$(basename "$(dirname "${crt}")")"
  target="${TRUST_DIR}/bigbug-${host}.crt"
  if [[ -f "${target}" ]] && cmp -s "${crt}" "${target}"; then
    info "${host} уже в trust store — пропускаем."
    continue
  fi
  sudo cp "${crt}" "${target}"
  info "Скопирован: ${target}"
done

sudo update-ca-certificates

info "Готово. Docker daemon: перезапустите (systemctl restart docker), чтобы он подхватил доверие."
