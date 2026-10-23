#!/usr/bin/env bash
#
# e2e-env.sh — Окружение для e2e-прогонов. СОРСИРУЕТСЯ make-целями (Makefile),
#              не запускается напрямую.
#
# Экспортирует:
#   SSL_CERT_FILE — бандл сертов стенда из state-каталога (ADR-0030 §4; httpx
#                   использует certifi-bundle, а не system trust store, поэтому
#                   одного trust-host.sh для httpx недостаточно)
#   DATABASE_URL  — если не задан: из секрета bigbug-db-credentials (tofu,
#                   ADR-0024) с переписью host:port на временный kubectl
#                   port-forward к svc <cluster>-rw (CNPG недоступен с хоста)
#   REDIS_URL     — аналогично через port-forward к bigbug-cache
#
# port-forward'ы прибираются trap'ом EXIT вызывающего шелла.
#
# Переменные: KUBE_CONTEXT (kind-bigbug-dev), DB_NAMESPACE (bigbug),
#             PORT_FWD_PORT (15432), REDIS_PORT_FWD_PORT (16379).
#
set -euo pipefail

# TLS: ПОЛНЫЙ бандл — системные корни (github/gitlab.com и пр. публичные хосты)
# + серты стенда (ADR-0030 §4). Один только стендовый бандл подменяет store
# целиком и ломает внешние вызовы — как SSL_CERT_FILE в поде до фикса.
BIGBUG_CERTS_DIR="${BIGBUG_CERTS_DIR:-$HOME/.local/state/bigbug/certs}"
if [ -d "$BIGBUG_CERTS_DIR" ] && ls "$BIGBUG_CERTS_DIR"/*/tls.crt >/dev/null 2>&1; then
    _HOST_BUNDLE="$(mktemp /tmp/bigbug-host-bundle.XXXXXX.pem)"
    cat /etc/ssl/certs/ca-certificates.crt "$BIGBUG_CERTS_DIR"/*/tls.crt > "$_HOST_BUNDLE"
    export SSL_CERT_FILE="${SSL_CERT_FILE:-$_HOST_BUNDLE}"
fi

if [ -z "${DATABASE_URL:-}" ]; then
    if ! command -v kubectl >/dev/null 2>&1; then
        echo "ОШИБКА: kubectl не найден, а DATABASE_URL не задан" >&2
        return 1 2>/dev/null || exit 1
    fi
    KUBE_CONTEXT="${KUBE_CONTEXT:-kind-bigbug-dev}"
    DB_NAMESPACE="${DB_NAMESPACE:-bigbug}"
    PORT_FWD_PORT="${PORT_FWD_PORT:-15432}"
    REDIS_PORT_FWD_PORT="${REDIS_PORT_FWD_PORT:-16379}"

    RAW_URL="$(kubectl --context "$KUBE_CONTEXT" -n "$DB_NAMESPACE" \
        get secret bigbug-db-credentials -o jsonpath='{.data.DATABASE_URL}' | base64 -d)"
    if [ -z "$RAW_URL" ]; then
        echo "ОШИБКА: секрет bigbug-db-credentials не найден в ns $DB_NAMESPACE" >&2
        echo "Поднимите стенд: make infra-init" >&2
        return 1 2>/dev/null || exit 1
    fi

    CLUSTER_HOST="$(sed -E 's/.*@([^:/]+):.*/\1/' <<<"$RAW_URL")"
    CLUSTER_PORT="$(sed -E 's/.*:([0-9]+)\/.*/\1/' <<<"$RAW_URL")"
    export DATABASE_URL="$(sed -E "s|@$CLUSTER_HOST:$CLUSTER_PORT|@127.0.0.1:$PORT_FWD_PORT|" <<<"$RAW_URL")"
    export REDIS_URL="${REDIS_URL:-redis://127.0.0.1:${REDIS_PORT_FWD_PORT}/0}"

    PF_PIDS=()
    cleanup_port_forwards() {
        for pid in "${PF_PIDS[@]:-}"; do
            kill "$pid" 2>/dev/null || true
        done
    }
    trap cleanup_port_forwards EXIT

    kubectl --context "$KUBE_CONTEXT" -n "$DB_NAMESPACE" \
        port-forward "svc/${CLUSTER_HOST}" "$PORT_FWD_PORT:$CLUSTER_PORT" >/dev/null 2>&1 &
    PF_PIDS+=("$!")
    kubectl --context "$KUBE_CONTEXT" -n "$DB_NAMESPACE" \
        port-forward svc/bigbug-cache "$REDIS_PORT_FWD_PORT:6379" >/dev/null 2>&1 &
    PF_PIDS+=("$!")

    # ждём готовности port-forward к БД (TCP-ping через asyncpg)
    for _ in $(seq 1 15); do
        if (export DATABASE_URL; uv run --project "$(dirname "${BASH_SOURCE[0]}")/.." python - <<'PY' 2>/dev/null
import asyncio, os
from urllib.parse import urlparse, unquote
u = urlparse(os.environ["DATABASE_URL"])
async def ping():
    conn = await asyncpg.connect(
        host=u.hostname, port=u.port, user=unquote(u.username),
        password=unquote(u.password), database=u.path.lstrip("/"),
    )
    await conn.close()
asyncio.run(ping())
PY
) ; then
            break
        fi
        sleep 1
    done
fi
