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
if ! yarn run lint; then
    echo "ОШИБКА: ESLint не прошёл"
    exit 1
fi
echo "✓ ESLint check passed"

echo ""
echo "=== Running TypeScript type check ==="
if ! yarn run type-check; then
    echo "ОШИБКА: TypeScript type check не прошёл"
    exit 1
fi
echo "✓ TypeScript type check passed"

echo ""
echo "=== Done ==="
