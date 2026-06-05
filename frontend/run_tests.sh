#!/usr/bin/env bash
set -e

# Load nvm
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

cd "$(dirname "$0")"

echo "=== Frontend Tests ==="
echo "Node: $(node --version)"
echo "Yarn: $(yarn --version)"
echo ""

# Run tests
if [ "$1" == "--watch" ]; then
    shift
    yarn test "$@"
elif [ "$1" == "--ui" ]; then
    yarn test:ui
elif [ "$1" == "--coverage" ]; then
    shift
    yarn test:coverage "$@"
elif [ $# -gt 0 ]; then
    yarn test --run "$@"
else
    yarn test --run
fi
