#!/usr/bin/env bash
#
# secrets-scan.sh — Полное сканирование git-истории на утечки секретов (gitleaks).
#
# Использование:
#   ./scripts/secrets-scan.sh        # обычно через: make secrets-scan
#
# Сканирует всю git-историю репозитория (не только рабочее дерево).
# Конфиг — репозиторный .gitleaks.toml; пока его нет — дефольные правила gitleaks.
# Находки выводятся с --redact: значения секретов маскируются.
# Exit 0 — находок нет; non-zero — есть находки или gitleaks недоступен.
#
# Требования:
#   - gitleaks в PATH (свежий release: brew install gitleaks или бинарник с
#     https://github.com/gitleaks/gitleaks/releases; пакет из distro-apt устарел)
#   - подробности: docs/development/setup.md
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if ! command -v gitleaks >/dev/null 2>&1; then
    echo "ОШИБКА: gitleaks не установлен." >&2
    echo "Установите свежий release: https://github.com/gitleaks/gitleaks/releases" >&2
    echo "(brew install gitleaks или бинарник в PATH; пакет из apt дистрибутива устарел)." >&2
    echo "Подробности: docs/development/setup.md" >&2
    exit 1
fi

CONFIG_FLAG=()
if [ -f .gitleaks.toml ]; then
    CONFIG_FLAG=(--config .gitleaks.toml)
else
    echo "Внимание: .gitleaks.toml не найден — используются дефолтные правила gitleaks."
fi

echo "=== gitleaks: full-history scan ==="
# gitleaks 8.x: полная история = --log-opts="--all" (флаг --full-history не существует)
gitleaks detect --log-opts="--all" --redact -v "${CONFIG_FLAG[@]}"
