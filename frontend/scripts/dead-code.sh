#!/usr/bin/env bash
#
# dead-code.sh — Поиск мёртвого кода frontend (knip).
#
# Использование:
#   ./scripts/dead-code.sh
#
# Требования:
#   - Node.js 24+ через nvm
#   - yarn (Berry) установлен
#   - knip (devDependency)
#
# Паритет с backend/scripts/vulture.sh: knip запускается с --no-exit-code,
# поэтому скрипт не ломает CI/локальный запуск, а только показывает находки.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$(dirname "$SCRIPT_DIR")"

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

cd "$FRONTEND_DIR"

echo "=== Running knip (dead code analysis) ==="
yarn run dead-code

echo ""
echo "=== Done ==="
