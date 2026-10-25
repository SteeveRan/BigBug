#!/usr/bin/env bash
#
# migrate-check.sh — Накатить все миграции на чистую копию БД (multi-agent
# pre-merge check: ловит конфликтующие головы alembic до мержа в main).
#
# Использование:
#   ./scripts/migrate-check.sh              # БД bigbug_migrate_check
#   ./scripts/migrate-check.sh my_check_db  # своё имя БД
#
# Требования:
#   - kind-стенд с CNPG-подом (make infra-init — владелец инфры)
#   - .venv backend с зависимостями
#   - DATABASE_URL в окружении (port-forward к CNPG — вручную/из .env) — хост/юзер
#     не используются, имя БД подменяется на check-БД, поэтому к общим данным
#     ветки скрипт не прикасается
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON=(uv run --project "$BACKEND_DIR" python)
DB_NAME="${1:-bigbug_migrate_check}"

if ! command -v uv >/dev/null 2>&1; then
    echo "ОШИБКА: uv не установлен"
    echo "Установите: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# CNPG-под (ns bigbug, cluster bigbug-dev) — psql внутрь, как в make dev-db-psql
KUBE_CONTEXT="${KUBE_CONTEXT:-kind-bigbug-dev}"
DB_NAMESPACE="${DB_NAMESPACE:-bigbug}"
CNPG_CLUSTER="${CNPG_CLUSTER:-bigbug-dev}"

PGPOD="$(kubectl --context "$KUBE_CONTEXT" -n "$DB_NAMESPACE" \
    get pod -l "cnpg.io/cluster=${CNPG_CLUSTER}" -o jsonpath='{.items[0].metadata.name}')"
if [ -z "$PGPOD" ]; then
    echo "ОШИБКА: CNPG-под не найден (kind-стенд не поднят: make infra-init)."
    exit 1
fi

PGPW="$(kubectl --context "$KUBE_CONTEXT" -n "$DB_NAMESPACE" \
    get secret "${CNPG_CLUSTER}-app" -o jsonpath='{.data.password}' | base64 -d)"

cnpg_psql() {
    kubectl --context "$KUBE_CONTEXT" -n "$DB_NAMESPACE" exec "$PGPOD" -c postgres -- \
        env PGPASSWORD="$PGPW" psql -h localhost -U bigbug -d bigbug -c "$1"
}

echo "=== Recreate check-БД: ${DB_NAME} ==="
cnpg_psql "DROP DATABASE IF EXISTS ${DB_NAME}"
cnpg_psql "CREATE DATABASE ${DB_NAME}"

cd "$BACKEND_DIR"

# Прогоняем alembic с БД чека: подменяем имя БД в DATABASE_URL (хост — CNPG,
# юзер — bigbug),
CHECK_URL="$("${VENV_PYTHON[@]}" -c "
import sys
sys.path.insert(0, '.')
from app.config import settings
url = str(settings.database_url)
head, sep, _tail = url.rpartition('/')
print(head + sep + '${DB_NAME}')
")"
echo "=== Alembic upgrade head → ${DB_NAME} ==="
DATABASE_URL="$CHECK_URL" "${VENV_PYTHON[@]}" -m alembic upgrade head

echo "=== Текущая ревизия ==="
DATABASE_URL="$CHECK_URL" "${VENV_PYTHON[@]}" -m alembic current

echo ""
echo "=== OK: все миграции ветки накатываются на чистую БД (${DB_NAME}) ==="
echo "Удалить: make dev-db-drop DB=${DB_NAME}"
