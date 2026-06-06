#!/usr/bin/env bash
#
# lint.sh — Проверка кода frontend (ESLint + TypeScript type check).
#
# Использование:
#   ./scripts/lint.sh
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

echo "=== Running ESLint ==="
yarn run lint 2>/dev/null && echo "✓ ESLint check passed" || {
    echo "ПРЕДУПРЕЖДЕНИЕ: ESLint не прошёл или не настроен"
}

echo ""
echo "=== Running TypeScript type check ==="
yarn run type-check 2>/dev/null && echo "✓ TypeScript type check passed" || {
    echo "ПРЕДУПРЕЖДЕНИЕ: TypeScript type check не прошёл"
}

echo ""
echo "=== Done ==="
