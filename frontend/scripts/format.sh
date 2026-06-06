#!/usr/bin/env bash
#
# format.sh — Форматирование кода frontend (prettier).
#
# Использование:
#   ./scripts/format.sh
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

echo "=== Running prettier ==="
yarn run format 2>/dev/null && echo "✓ Prettier formatting completed" || {
    echo "ПРЕДУПРЕЖДЕНИЕ: prettier не найден. Установите: yarn add -D prettier"
}

echo ""
echo "=== Done ==="
