#!/usr/bin/env bash
#
# e2e-env.sh — Окружение для e2e-прогонов. СОРСИРУЕТСЯ make-целями (Makefile),
#              не запускается напрямую.
#
# Экспортирует:
#   SSL_CERT_FILE — бандл сертов стенда из state-каталога (ADR-0030 §4; httpx
#                   использует certifi-bundle, а не system trust store, поэтому
#                   одного trust-host.sh для httpx недостаточно)
#
# E2E-учётки создаются/удаляются тестами через публичный API (issue #134) —
# прямой доступ к БД/Redis из e2e-инфраструктуры не нужен.
#
set -euo pipefail

# TLS: ПОЛНЫЙ бандл — системные корни (github/gitlab.com и пр. публичные хосты)
# + CA стенда (ADR-0030 §4; все серты хостов подписаны единым CA — certs.sh).
# Один только стендовый бандл подменяет store целиком и ломает внешние вызовы.
BIGBUG_CERTS_DIR="${BIGBUG_CERTS_DIR:-$HOME/.local/state/bigbug/certs}"
if [ -f "${BIGBUG_CERTS_DIR}/ca.crt" ]; then
    _HOST_BUNDLE="$(mktemp /tmp/bigbug-host-bundle.XXXXXX.pem)"
    cat /etc/ssl/certs/ca-certificates.crt "${BIGBUG_CERTS_DIR}/ca.crt" > "$_HOST_BUNDLE"
    export SSL_CERT_FILE="${SSL_CERT_FILE:-$_HOST_BUNDLE}"
fi
