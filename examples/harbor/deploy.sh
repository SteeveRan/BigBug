#!/usr/bin/env bash
#
# deploy.sh — Развернуть Harbor в kind кластере
#
# Зависимости: kind, kubectl, helm, docker
# Использование: ./deploy.sh
#
set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly CLUSTER_NAME="harbor"
readonly NAMESPACE="harbor"
readonly HARBOR_HOST="harbor.local"
readonly HARBOR_HTTP_PORT="30080"
readonly HARBOR_HTTPS_PORT="30443"

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

  local deps=("kind" "kubectl" "helm" "docker")
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
# Добавление записи в /etc/hosts
# ---------------------------------------------------------------------------
add_hosts_entry() {
  if grep -q "$HARBOR_HOST" /etc/hosts 2>/dev/null; then
    info "Запись /etc/hosts для $HARBOR_HOST уже существует."
  else
    warn "Добавление записи в /etc/hosts (может потребоваться sudo)..."
    echo "127.0.0.1 ${HARBOR_HOST}" | sudo tee -a /etc/hosts >/dev/null
    info "Добавлено: 127.0.0.1 ${HARBOR_HOST}"
  fi
}

# ---------------------------------------------------------------------------
# Настройка Docker daemon для insecure registry
# ---------------------------------------------------------------------------
configure_docker_insecure() {
  local daemon_json="/etc/docker/daemon.json"
  local insecure_reg="harbor.local:${HARBOR_HTTP_PORT}"

  info "Проверка Docker insecure registry..."

  # Проверяем, нужно ли добавить insecure registry
  if [[ -f "$daemon_json" ]]; then
    if grep -q "$insecure_reg" "$daemon_json" 2>/dev/null; then
      info "  ✓ Insecure registry уже настроен в $daemon_json"
      return
    fi
  fi

  warn "Настройка Docker daemon для insecure registry..."

  if [[ -f "$daemon_json" ]]; then
    # Файл существует — добавляем insecure-registries
    warn "  Обновление существующего $daemon_json (нужен sudo)"
    # Используем jq если доступен, иначе предупреждаем
    if command -v jq &>/dev/null; then
      sudo jq --arg reg "$insecure_reg" \
        '."insecure-registries" = (."insecure-registries" // []) + [$reg] | unique' \
        "$daemon_json" | sudo tee "${daemon_json}.tmp" >/dev/null \
        && sudo mv "${daemon_json}.tmp" "$daemon_json"
    else
      warn "  jq не найден. Добавьте вручную в $daemon_json:"
      warn "    \"insecure-registries\": [\"$insecure_reg\"]"
    fi
  else
    # Файла нет — создаём
    warn "  Создание $daemon_json (нужен sudo)"
    cat <<EOF | sudo tee "$daemon_json" >/dev/null
{
  "insecure-registries": ["${insecure_reg}"]
}
EOF
  fi

  warn "Перезапуск Docker daemon..."
  sudo systemctl restart docker 2>/dev/null || sudo service docker restart 2>/dev/null || true
  info "Docker insecure registry настроен."
}

# ---------------------------------------------------------------------------
# Создание kind кластера
# ---------------------------------------------------------------------------
create_kind_cluster() {
  info "Создание kind кластера '$CLUSTER_NAME'..."

  if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    warn "Кластер '$CLUSTER_NAME' уже существует."
    read -p "Удалить и пересоздать? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      kind delete cluster --name="$CLUSTER_NAME"
    else
      info "Используем существующий кластер."
      return
    fi
  fi

  kind create cluster --config="${SCRIPT_DIR}/kind-config.yaml" --name="$CLUSTER_NAME"
  info "Kind кластер '$CLUSTER_NAME' создан."

  # Проверка подключения
  kubectl cluster-info --context "kind-${CLUSTER_NAME}"
}

# ---------------------------------------------------------------------------
# Установка Harbor через Helm
# ---------------------------------------------------------------------------
install_harbor() {
  info "Установка Harbor в namespace '$NAMESPACE'..."

  # Создаём namespace
  kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

  # Добавляем Helm repo
  info "Добавление Helm репозитория harbor..."
  helm repo add harbor https://helm.goharbor.io 2>/dev/null || true
  helm repo update

  # Установка Harbor
  info "Установка Harbor (это может занять несколько минут)..."
  helm upgrade --install harbor harbor/harbor \
    --namespace "$NAMESPACE" \
    --values "${SCRIPT_DIR}/harbor-values.yaml" \
    --wait \
    --timeout 10m

  info "Harbor установлен."
}

# ---------------------------------------------------------------------------
# Ожидание готовности подов
# ---------------------------------------------------------------------------
wait_for_ready() {
  info "Ожидание готовности подов Harbor (таймаут 300с)..."

  # Ждём все поды в namespace harbor
  kubectl wait --for=condition=ready pod \
    --all \
    --namespace "$NAMESPACE" \
    --timeout=300s 2>/dev/null || {
      warn "Не все поды готовы в течение 300с."
      warn "Текущее состояние подов:"
      kubectl get pods -n "$NAMESPACE"
    }

  info "Поды Harbor:"
  kubectl get pods -n "$NAMESPACE" -o wide
}

# ---------------------------------------------------------------------------
# Вывод инструкций
# ---------------------------------------------------------------------------
print_instructions() {
  echo ""
  echo "============================================"
  echo -e "${GREEN}  Harbor развёрнут успешно!${NC}"
  echo "============================================"
  echo ""
  echo "Harbor UI:       https://${HARBOR_HOST}:${HARBOR_HTTPS_PORT}"
  echo "Registry (HTTP): ${HARBOR_HOST}:${HARBOR_HTTP_PORT}"
  echo ""
  echo "Credentials:"
  echo "  Username: admin"
  echo "  Password: Harbor12345"
  echo ""
  echo "Docker login:"
  echo "  docker login ${HARBOR_HOST}:${HARBOR_HTTP_PORT} -u admin -p Harbor12345"
  echo ""
  echo "Helm repo add:"
  echo "  helm repo add harbor-local https://${HARBOR_HOST}:${HARBOR_HTTPS_PORT}/chartrepo/library \\"
  echo "    --username=admin --password=Harbor12345"
  echo ""
  echo "Тестирование:"
  echo "  ${SCRIPT_DIR}/test-push.sh"
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
  info "=== Развёртывание Harbor в kind ==="
  echo ""

  check_dependencies
  add_hosts_entry
  configure_docker_insecure
  create_kind_cluster
  install_harbor
  wait_for_ready
  print_instructions
}

main "$@"
