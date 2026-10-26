#!/usr/bin/env bash
# ADR-order gate (ADR-before-code).
#
# Правило (docs/adr/README.md, «Порядок: запрос → ADR → разработка»):
#   1. PR, который ДОБАВЛЯЕТ новый ADR, не должен содержать изменений
#      реализации — ADR мержится отдельным docs-PR ДО разработки.
#   2. Новый ADR создаётся только со статусом `proposed`;
#      `accepted` выставляет человек отдельным решением.
#
# Нарушение = fail. Ретро-ADR («фактическое», «как сделано») под это правило
# не подпадает: его создание запрещено конвенцией, а не этим гейтом — здесь
# ловится механически: ADR + код в одном PR.
#
# Usage:
#   ./scripts/check-adr-order.sh <base-ref> [<head-ref>]   # CI: base=origin/main
#   ./scripts/check-adr-order.sh origin/main HEAD
set -euo pipefail

BASE="${1:?usage: check-adr-order.sh <base-ref> [<head-ref>]}"
HEAD="${2:-HEAD}"

# Новые ADR-файлы вне архива (файлы-реестр README/ARCHIVE не считаются ADR).
new_adrs="$(git diff --name-only --diff-filter=A "${BASE}...${HEAD}" -- 'docs/adr/*.md' 'docs/adr/*/*.md' \
  | grep -v '/archive/' | grep -vE '/(README|ARCHIVE)\.md$' || true)"

# Изменения реализации (код, инфра, чарты). Документация и конфиги репо не считаются.
code_changes="$(git diff --name-only "${BASE}...${HEAD}" \
  -- backend/ frontend/ charts/ infrastructure/ || true)"

status=0

if [ -n "$new_adrs" ] && [ -n "$code_changes" ]; then
  echo "ADR-order violation: этот PR добавляет новый ADR и одновременно меняет реализацию." >&2
  echo "" >&2
  echo "Новые ADR:" >&2
  echo "$new_adrs" | sed 's/^/  - /' >&2
  echo "Файлы реализации:" >&2
  echo "$code_changes" | sed 's/^/  - /' >&2
  echo "" >&2
  echo "Порядок по конвенции: запрос → ADR (отдельный docs-PR, status: proposed) → merge →" >&2
  echo "только потом реализация. Разделите изменения: ADR — в свой PR." >&2
  status=1
fi

for f in $new_adrs; do
  if ! sed -n '1,15p' "$f" | grep -qE '^status:[[:space:]]*proposed([[:space:]]|$)'; then
    echo "ADR-order violation: новый ADR '$f' должен создаваться со статусом 'proposed'." >&2
    echo "Статус 'accepted' выставляет только человек, отдельным решением." >&2
    status=1
  fi
done

if [ "$status" -eq 0 ]; then
  echo "ADR-order: OK (новых ADR вне реализации: $(echo -n "$new_adrs" | grep -c . || true))"
fi

exit "$status"
