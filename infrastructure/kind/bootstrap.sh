#!/usr/bin/env bash
#
# bootstrap.sh — Создать kind кластер bigbug-dev + haproxy-ingress
#
# Зависимости: kind, kubectl, helm, docker, tofu
# Использование: ./bootstrap.sh
#
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly CLUSTER_NAME="bigbug-dev"
readonly INGRESS_NAMESPACE="haproxy-ingress"
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

  local deps=("kind" "kubectl" "helm" "docker" "tofu")
  local missing=()

  for dep in "${deps[@]}"; do
    if command -v "$dep" &>/dev/null; then
      info "  ✓ $dep ($($dep --version 2>&1 | head -1 || echo '?'))"
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
# Установка haproxy-ingress (haproxytech chart, ingressClass default)
# ---------------------------------------------------------------------------
install_ingress() {
  info "Установка haproxy-ingress в namespace '$INGRESS_NAMESPACE'..."

  kubectl create namespace "$INGRESS_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

  helm repo add haproxytech https://haproxytech.github.io/helm-charts 2>/dev/null || true
  helm repo update

  helm upgrade --install haproxy-ingress haproxytech/kubernetes-ingress \
    --namespace "$INGRESS_NAMESPACE" \
    --set controller.ingressClassResource.default=true \
    --set controller.service.nodePorts.http=30080 \
    --set controller.service.nodePorts.https=30443 \
    --wait \
    --timeout 10m

  info "haproxy-ingress установлен."
}

# ---------------------------------------------------------------------------
# Ожидание готовности подов
# ---------------------------------------------------------------------------
wait_for_ready() {
  info "Ожидание готовности подов haproxy-ingress (таймаут 300с)..."

  kubectl wait --for=condition=ready pod \
    --all \
    --namespace "$INGRESS_NAMESPACE" \
    --timeout=300s 2>/dev/null || {
      warn "Не все поды готовы в течение 300с."
      warn "Текущее состояние подов:"
      kubectl get pods -A
    }

  info "Поды кластера:"
  kubectl get pods -A
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
  echo "Проверка ingress:"
  echo "  curl -H 'Host: app.local' http://localhost/"
  echo ""
  echo "Дальнейшие шаги: установка CNPG, Valkey, keycloakx, Harbor, app (отдельные issues)."
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
  create_kind_cluster
  install_ingress
  wait_for_ready
  print_instructions
}

main "$@"
