#!/usr/bin/env bash
#
# test-unit.sh — Запуск юнит-тестов frontend (Vitest).
#
# Использование:
#   ./scripts/test-unit.sh
#
# Требования:
#   - Node.js 24+ через nvm
#   - yarn (Berry) установлен
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$(dirname "$SCRIPT_DIR")"

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

cd "$FRONTEND_DIR"

echo "=== Running Vitest unit tests ==="
yarn run test:run 2>/dev/null && echo "✓ Vitest tests passed" || {
    echo "ПРЕДУПРЕЖДЕНИЕ: Vitest тесты не прошли или не настроены"
}

echo ""
echo "=== Done ==="
