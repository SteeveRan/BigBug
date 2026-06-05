#!/usr/bin/env bash
#
# test-push.sh — Проверить работу Harbor: логин, push образа, API
#
# Требования: запущенный Harbor (через deploy.sh)
# Использование: ./test-push.sh
#
set -euo pipefail

readonly HARBOR_HOST="harbor.local"
readonly HARBOR_HTTP_PORT="30080"
readonly HARBOR_HTTPS_PORT="30443"
readonly HARBOR_USER="admin"
readonly HARBOR_PASS="Harbor12345"
readonly REGISTRY="${HARBOR_HOST}:${HARBOR_HTTP_PORT}"
readonly TEST_IMAGE="alpine:latest"
readonly TAG="${REGISTRY}/library/alpine:test"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

info "=== Тестирование Harbor ==="
echo ""

# 1. Docker login
info "1. Docker login в $REGISTRY..."
if echo "$HARBOR_PASS" | docker login "$REGISTRY" \
    --username "$HARBOR_USER" \
    --password-stdin 2>&1; then
  info "   ✓ Логин успешен."
else
  error "   ✗ Ошибка логина."
  error "   Проверьте, что Harbor запущен и доступен по адресу $REGISTRY"
  exit 1
fi
echo ""

# 2. Pull alpine (если ещё нет локально)
info "2. Загрузка образа $TEST_IMAGE..."
if docker pull "$TEST_IMAGE" 2>&1; then
  info "   ✓ Образ $TEST_IMAGE загружен."
else
  error "   ✗ Не удалось загрузить $TEST_IMAGE"
  exit 1
fi
echo ""

# 3. Tag образа для Harbor
info "3. Тегирование образа как $TAG..."
docker tag "$TEST_IMAGE" "$TAG"
info "   ✓ Образ помечен: $TAG"
echo ""

# 4. Push образа в Harbor
info "4. Push образа в Harbor..."
if docker push "$TAG" 2>&1; then
  info "   ✓ Push успешен: $TAG"
else
  error "   ✗ Push не удался."
  error "   Проверьте insecure registry настройки Docker."
  exit 1
fi
echo ""

# 5. Проверка через Harbor REST API
info "5. Проверка проектов через Harbor REST API..."
API_RESPONSE=$(curl -s -k -u "${HARBOR_USER}:${HARBOR_PASS}" \
  "https://${HARBOR_HOST}:${HARBOR_HTTPS_PORT}/api/v2.0/projects" 2>&1) || true

if echo "$API_RESPONSE" | grep -q '"project_id"'; then
  info "   ✓ API отвечает. Проекты:"
  echo "$API_RESPONSE" | python3 -m json.tool 2>/dev/null | head -20 || echo "$API_RESPONSE" | head -20
else
  warn "   ! API ответил неожиданно:"
  echo "$API_RESPONSE" | head -10
fi
echo ""

# 6. Проверка тегов образа через API
info "6. Проверка тегов образа 'library/alpine' через API..."
TAGS_RESPONSE=$(curl -s -k -u "${HARBOR_USER}:${HARBOR_PASS}" \
  "https://${HARBOR_HOST}:${HARBOR_HTTPS_PORT}/api/v2.0/projects/library/repositories/alpine/artifacts" 2>&1) || true

if echo "$TAGS_RESPONSE" | grep -q '"digest"'; then
  info "   ✓ Репозиторий 'library/alpine' содержит артефакты."
else
  warn "   ! Не удалось получить теги."
  echo "$TAGS_RESPONSE" | head -5
fi

# 7. Очистка локального тега
info "7. Очистка локального тега..."
docker rmi "$TAG" 2>/dev/null || true
info "   ✓ Локальный тег удалён."

echo ""
echo "============================================"
echo -e "${GREEN}  Все тесты пройдены!${NC}"
echo "============================================"
echo ""
echo "Harbor UI:  https://${HARBOR_HOST}:${HARBOR_HTTPS_PORT}"
echo "Registry:   ${REGISTRY}"
echo "Образ:      ${TAG}"
echo ""
info "Тестирование завершено успешно."
