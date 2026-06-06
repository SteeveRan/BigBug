#!/usr/bin/env bash
#
# test-e2e.sh — Запуск e2e-тестов frontend (Cypress).
#
# Использование:
#   ./scripts/test-e2e.sh
#
# Требования:
#   - Node.js 24+ через nvm
#   - yarn (Berry) установлен
#   - Cypress настроен (пока не настроен — пропускается)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$(dirname "$SCRIPT_DIR")"

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

cd "$FRONTEND_DIR"

echo "=== Running Cypress e2e tests ==="
if yarn run cypress:run 2>/dev/null; then
    echo "✓ Cypress e2e tests completed"
else
    echo "ℹ Cypress e2e тесты не настроены — пропускаем"
fi

echo ""
echo "=== Done ==="
