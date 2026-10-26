#!/usr/bin/env bash
# design-tokens gate (ADR-0040: код — канон, Penpot — зеркало).
#
# Правило (docs/design/design.md, «Canonical tokens»): визуальные константы
# живут ТОЛЬКО в frontend/src/theme.ts (AntD ThemeConfig) и
# frontend/src/colors.css (--bigbug-*). Компоненты и страницы ссылаются на
# токены (theme.useToken() / var(--bigbug-*)), а не пишут литералы.
#
# Ловится механически в frontend/src/{components,pages}:
#   - raw hex-цвета: #RRGGBB и #RRGGBBAA (3/4-значный шортхенд не проверяется —
#     пишите полный формат; проверять его нельзя из-за ложных срабатываний
#     на ссылках вида «issue #123»);
#   - raw rgb()/rgba()/hsl()/hsla();
#   - px-литералы в строках ('40px 0') — там, где размер не из токенов,
#     оформляется через inline-маркер-исключение с причиной.
#
# Исключения: строка, содержащая маркер `design-tokens:allow`, пропускается
# (комментарий с причиной, ревьюится в PR):
#   style={{ flex: '1 1 300px' /* design-tokens:allow: layout */ }}
#
# Вне скоупа: theme.ts / colors.css (канон), числовые style-значения React
# (fontSize: 12 и т.п. — отдельная политика, не гейт), src/tests.
#
# Usage:
#   ./scripts/check-design-tokens.sh          # весь скоуп (CI, make-цель)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCOPE="$ROOT/frontend/src/components $ROOT/frontend/src/pages"

violations="$(grep -rInE \
  -e '#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?\b' \
  -e '\brgba?\(' \
  -e '\bhsla?\(' \
  -e '[0-9]+px\b' \
  --include='*.ts' --include='*.tsx' --include='*.css' \
  $SCOPE 2>/dev/null \
  | grep -v 'design-tokens:allow' || true)"

if [ -n "$violations" ]; then
  echo "design-tokens violation: raw цвет/px-литерал вне канона (ADR-0040, docs/design/design.md)." >&2
  echo "" >&2
  echo "$violations" | sed 's/^/  - /' >&2
  echo "" >&2
  echo "Канон: frontend/src/theme.ts (AntD ThemeConfig) + frontend/src/colors.css (--bigbug-*)." >&2
  echo "В компонентах ссылайтесь на токен: theme.useToken() -> token.color*, var(--bigbug-*)." >&2
  echo "Новая константа — сначала в канон (отдельным PR), потом использование." >&2
  echo "Оправданное исключение — inline-маркер с причиной: /* design-tokens:allow: <reason> */" >&2
  exit 1
fi

echo "design-tokens: OK ($(find $SCOPE -name '*.ts' -o -name '*.tsx' -o -name '*.css' | wc -l) файлов, 0 нарушений)"
