#!/usr/bin/env bash
#
# certs.sh — Генерация self-signed сертификатов для dev-стенда (ADR-0030).
#
# Создаёт certs/<host>/{tls.crt,tls.key} в общем state-каталоге
# ~/.local/state/bigbug/certs — там же, где лежат tofu-стейты. Каталог вне
# репозитория НЕ переживает удаление ворктрия (bind-mount'ы kind-ноды
# умирали вместе с ворктрием бутстрапа), поэтому серты живут рядом со
# стейтами — общими для всех ворктриев машины. Идемпотентен: существующие
# серты не трогает — доверие хоста переживает infra-clean/infra-init.
# Ротация — только вручную: --reset.
#
# Использование:
#   ./certs.sh           # создать отсутствующие серты
#   ./certs.sh --reset   # удалить все серты и сгенерировать заново
#
set -euo pipefail

readonly CERTS_DIR="$HOME/.local/state/bigbug/certs"
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

if [[ "${1:-}" == "--reset" ]]; then
  warn "Удаление существующих сертов: ${CERTS_DIR}"
  rm -rf "${CERTS_DIR}"
  warn "Доверие хоста (trust-host.sh) нужно повторить."
fi

if ! command -v openssl &>/dev/null; then
  error "openssl не найден — установите и повторите."
  exit 1
fi

generated=0
for host in "${HOSTS[@]}"; do
  dir="${CERTS_DIR}/${host}"
  if [[ -f "${dir}/tls.crt" && -f "${dir}/tls.key" ]]; then
    info "Серт ${host} уже существует — пропускаем."
    continue
  fi
  mkdir -p "${dir}"
  openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
    -keyout "${dir}/tls.key" -out "${dir}/tls.crt" \
    -subj "/CN=${host}" \
    -addext "subjectAltName=DNS:${host}" &>/dev/null
  info "Сгенерирован серт: ${dir}/{tls.crt,tls.key}"
  generated=$((generated + 1))
done

if (( generated > 0 )); then
  echo ""
  warn "Сгенерированы новые серты. Чтобы браузер/curl/docker/e2e им доверяли:"
  warn "  запустите infrastructure/kind/trust-host.sh (добавит их в system trust store, нужен sudo)"
fi
