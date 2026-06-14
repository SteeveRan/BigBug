#!/usr/bin/env bash
#
# type-check.sh — Проверка типов TypeScript (tsc --noEmit).
#
# Использование:
#   ./scripts/type-check.sh
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

echo "=== Running TypeScript type check ==="
yarn run type-check 2>/dev/null && echo "✓ TypeScript type check passed" || {
    echo "ОШИБКА: TypeScript type check не прошёл"
    exit 1
}

echo ""
echo "=== Done ==="
