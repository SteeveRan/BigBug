#!/usr/bin/env bash
#
# certs.sh — Генерация сертификатов dev-стенда: единый локальный CA, все
# серты сервисов подписаны им (ADR-0030 §2, редакция 2026-10-24 #62).
#
# Структура state-каталога ~/.local/state/bigbug/certs:
#   ca.crt / ca.key          — локальный CA (один на стенд)
#   <host>/tls.crt / tls.key — серты хостов, подписанные CA
#
# Каталог вне репозитория НЕ переживает удаление ворктрия, поэтому серты
# живут рядом со стейтами — общими для всех ворктриев машины.
# Идемпотентен: существующие CA/серты не трогает. Ротация — вручную: --reset.
#
# Использование:
#   ./certs.sh           # создать отсутствующие CA/серты
#   ./certs.sh --reset   # удалить всё и сгенерировать заново
#
set -euo pipefail

readonly CERTS_DIR="$HOME/.local/state/bigbug/certs"
readonly HOSTS=(
  "keycloak.local"
  "harbor.local"
  "app.local"
  "api.local"
  "gitlab.local"
  "penpot.local"
)

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

if [[ "${1:-}" == "--reset" ]]; then
  warn "Удаление существующих сертов и CA: ${CERTS_DIR}"
  rm -rf "${CERTS_DIR}"
  warn "Доверие хоста (trust-host.sh) нужно повторить."
fi

if ! command -v openssl &>/dev/null; then
  error "openssl не найден — установите и повторите."
  exit 1
fi

# ── Единый CA ────────────────────────────────────────────────
if [[ -f "${CERTS_DIR}/ca.crt" && -f "${CERTS_DIR}/ca.key" ]]; then
  info "CA уже существует — пропускаем."
else
  mkdir -p "${CERTS_DIR}"
  openssl req -x509 -newkey rsa:4096 -nodes -days 3650 \
    -keyout "${CERTS_DIR}/ca.key" -out "${CERTS_DIR}/ca.crt" \
    -subj "/CN=BigBug Dev CA" \
    -addext "basicConstraints=critical,CA:TRUE" \
    -addext "keyUsage=critical,keyCertSign,cRLSign" &>/dev/null
  info "Сгенерирован CA: ${CERTS_DIR}/ca.{crt,key}"
fi

# ── Серты хостов, подписанные CA ─────────────────────────────
generated=0
for host in "${HOSTS[@]}"; do
  dir="${CERTS_DIR}/${host}"
  if [[ -f "${dir}/tls.crt" && -f "${dir}/tls.key" ]]; then
    info "Серт ${host} уже существует — пропускаем."
    continue
  fi
  mkdir -p "${dir}"
  # key + CSR + подпись CA-шным ключом (одна команда x509 -req)
  openssl req -newkey rsa:2048 -nodes \
    -keyout "${dir}/tls.key" -out "${dir}/tls.csr" \
    -subj "/CN=${host}" &>/dev/null
  openssl x509 -req -in "${dir}/tls.csr" \
    -CA "${CERTS_DIR}/ca.crt" -CAkey "${CERTS_DIR}/ca.key" -CAcreateserial \
    -days 825 -sha256 \
    -extfile <(printf "subjectAltName=DNS:%s\nbasicConstraints=CA:FALSE\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth" "${host}") \
    -out "${dir}/tls.crt" &>/dev/null
  rm -f "${dir}/tls.csr"
  info "Серт ${host} подписан CA: ${dir}/{tls.crt,tls.key}"
  generated=$((generated + 1))
done

# Проверка: все серты реально подписаны этим CA
for host in "${HOSTS[@]}"; do
  if ! openssl verify -CAfile "${CERTS_DIR}/ca.crt" "${CERTS_DIR}/${host}/tls.crt" &>/dev/null; then
    error "Серт ${host} НЕ подписан CA — ротируйте: ./certs.sh --reset"
    exit 1
  fi
done

if (( generated > 0 )); then
  echo ""
  info "В trust store добавляется один CA (${CERTS_DIR}/ca.crt) — он покрывает все хосты."
fi
