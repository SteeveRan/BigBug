#!/usr/bin/env bash
#
# trust-host.sh — Добавить CA dev-стенда в system trust store (ADR-0030 §4).
#
# Один CA покрывает все хосты (серты подписаны им — certs.sh). После него
# браузер, curl, docker daemon, httpx e2e и tofu доверяют https://*.local
# без -k. Повторный запуск безопасен (idempotent).
#
# shortcut: Debian/Ubuntu only (update-ca-certificates), при появлении macOS/Fedora — добавить ветки
#
# Использование: ./trust-host.sh
#
set -euo pipefail

# Sudo resets $HOME to /root; resolve certs from the invoking user's home
if [ -n "${SUDO_USER:-}" ]; then
    CERTS_DIR="$(getent passwd "${SUDO_USER}" | cut -d: -f6)/.local/state/bigbug/certs"
else
    CERTS_DIR="${HOME}/.local/state/bigbug/certs"
fi
readonly CERTS_DIR
readonly CA_CERT="${CERTS_DIR}/ca.crt"
readonly TRUST_TARGET="/usr/local/share/ca-certificates/bigbug-dev-ca.crt"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

if [[ ! -f "${CA_CERT}" ]]; then
  error "CA не найден: ${CA_CERT} — сначала запустите certs.sh."
  exit 1
fi

if [[ $EUID -ne 0 ]] && ! sudo -v 2>/dev/null; then
  error "Нужен sudo для записи в system trust store."
  exit 1
fi

if [[ -f "${TRUST_TARGET}" ]] && cmp -s "${CA_CERT}" "${TRUST_TARGET}"; then
  info "CA уже в trust store — пропускаем."
else
  # Regenerated CA replaced the old one: remove first so
  # update-ca-certificates rebuilds the hash symlinks (plain overwrite
  # leaves stale hashes pointing at the old cert).
  sudo rm -f "${TRUST_TARGET}"
  sudo cp "${CA_CERT}" "${TRUST_TARGET}"
  info "Скопирован: ${TRUST_TARGET}"
fi

sudo update-ca-certificates --fresh

info "Готово. Docker daemon: перезапустите (systemctl restart docker), чтобы он подхватил доверие."
