---
status: accepted
date: 2026-10-23
decision-makers: SteeveRan
consulted: SteeveRan
informed: SteeveRan
---

# Adopt gitleaks secret scanning: pre-commit (staged-only) + blocking CI + full-history scan, allowlist вместо inline-маркеров, ротация обязательна — история git не переписывается

## Context and Problem Statement

Как предотвратить попадание живых credentials (provider tokens, GitLab PAT, Harbor credentials — см. [ADR-0010](0010-fernet-secrets-encryption.md)) в git-репозиторий BigBug и что делать, когда утечка всё же случилась?

Сейчас сканирования секретов нет: закоммиченный и запушенный credential не вызывает ни предупреждения, ни ошибки. При этом репозиторий полон фейковых токенов в документации и тестовых фикстурах (`glpat-xyz`, seeded e2e-учётки) — «вечно красный» сканер с дефолтными правилами будет игнорироваться.

Требуется зафиксировать: инструмент сканирования, точки принуждения (enforcement points), стратегию борьбы с false positives и политику реакции на утечку (ротация vs переписывание истории).

## Decision Drivers

* Репозиторий хранит и обрабатывает живые credentials; утечка = компрометация внешней системы (GitLab, Harbor, GitHub)
* Pre-commit hook обходится `--no-verify` — единственная необходимая точка принуждения — CI
* Полный pre-commit-скан на каждый коммит слишком медленный — хук обязан быть staged-only
* Документация и фикстуры намеренно содержат фейковые токены — нужна allowlist-стратегия, иначе сканер «вечно красный» и его игнорируют
* Несколько агентов работают в git worktree одного репозитория (см. AGENTS.md) — переписывание истории ломает всех участников сразу
* Per ADR-0019: весь tooling — через корневой Makefile (единая точка входа)

## Considered Options

* Инструмент: gitleaks (официальный, активно поддерживается) vs trufflehog vs самописный grep-хук
* Точки принуждения: pre-commit + CI + on-demand full-history (три точки) vs только CI vs только pre-commit
* False positives: path-based allowlist + stopwords в `.gitleaks.toml` vs inline-маркеры `gitleaks:allow` в исходниках
* Реакция на утечку: ротация/отзыв credential обязательна, история не переписывается vs переписывание истории (filter-repo) как стандартная реакция

## Decision Outcome

Chosen option — **gitleaks** с тремя точками принуждения, allowlist-конфигом и политикой «ротация обязательна, история не переписывается».

### 1. Инструмент — gitleaks

Официальный сканер секретов с поддерживаемым GitHub Action (`gitleaks/gitleaks-action`) и pre-commit-хуком. Конфиг — репозиторный `.gitleaks.toml`, расширяющий дефолтные правила (не заменяющий их).

### 2. Точки принуждения — три, разной силы

| Точка | Режим | Роль |
|---|---|---|
| pre-commit hook (`.pre-commit-config.yaml`, official gitleaks hook) | staged-only | Быстрая локальная обратная связь до коммита; обходится `--no-verify` |
| GitHub Actions (`gitleaks.yml`: push, pull_request, weekly cron, workflow_dispatch) | blocking | Единственная необходимая точка: не обходится; mirror в GitLab — read-only/backup, отдельной проверки не получает |
| `make secrets-scan` (`gitleaks detect --full-history`) | on-demand + weekly | Baseline-скан при внедрении, расследование подозрений, полный охват истории |

Weekly cron в CI и `make secrets-scan` сканируют **полную историю** — ловят утечки, попавшие до внедрения хуков или обходящие pre-commit.

### 3. False positives — path-based allowlist + stopwords, inline-маркеры запрещены

В `.gitleaks.toml` — extend дефолтных правил с allowlist по путям (`.env.example`, `docs/`, тестовые фикстуры) и `stopwords` для известных фейковых паттернов (например, `glpat-xyz`). **Inline-маркеры `gitleaks:allow` в исходниках не использовать**: они захламляют код и применяются по привычке вместо разбора, почему сработало правило.

### 4. Реакция на утечку — ротация обязательна, история НЕ переписывается

При подтверждённой утечке credential **обязательно** ротируется/отзывается во внешней системе (процедура — [docs/development/security.md](../../development/security.md)). Git-история по умолчанию **не переписывается**: rewrite (`git filter-repo` и т.п.) ломает все worktree-агентов и collaborators, а сам по себе не отзывает уже скомпрометированный секрет — секрет остаётся в клонах, форках и кэше CI. Переписывание истории — last resort, отдельное скоординированное действие, а не стандартная реакция.

### Consequences

* Good, потому что утечка в push блокируется в CI независимо от локальных хуков
* Good, потому что staged-only хук не замедляет каждый коммит полным сканом
* Good, потому что allowlist в одном конфиг-файле видим и ревьюится, в отличие от маркеров, размазанных по коду
* Good, потому что обязательная ротация устраняет сам риск: переписывание истории без ротации ничего не защищает
* Bad, потому что allowlist по путям скрывает реальные секреты, добавленные в allowlisted-пути (mitigation: allowlist минимальный, ревью изменений `.gitleaks.toml` обязателен)
* Bad, потому что без переписывания истории секрет остаётся в git до переписывания/удаления репозитория (принятый риск: компрометация нейтрализована ротацией)
* Bad, потому что weekly full-history scan растёт по времени с историей репозитория
* Neutral, потому что pre-commit framework — новая dev-зависимость репозитория (стандартная, versioned, Renovate-совместимая)
* Non-goals: автоматическая ротация или alerting-интеграции (реакция — человеческая, по security.md); сканирование секретов в runtime-логах приложения; секрет-сканирование в GitLab CI mirror

### Confirmation

* Хук: `pre-commit run gitleaks --all-files` → exit 0 на чистом дереве; коммит файла с фейковым секретом (`glpat-` + 20 символов) вне allowlist → блокируется с finding'ом
* CI: push с фейковым секретом → красный check; `make secrets-scan` → exit 0 на текущей истории
* Конфиг: существующие `docs/` и фикстуры с `glpat-xyz` не дают findings
* Политика: шаги реакции в `docs/development/security.md` соответствуют «ротация обязательна / история не переписывается» — проверяется при ревью изменений security.md (в ADR-чеклисте ревью)

## Pros and Cons of the Options

### gitleaks — chosen

* Good, потому что официальный pre-commit hook и GitHub Action — не нужно писать обвязку
* Good, потому что `detect --full-history` из коробки покрывает baseline-кейс
* Bad, потому что дефолтные правила шумят на документации с фейковыми токенами (mitigation: allowlist, §3)

### trufflehog

* Good, потому что верифицирует найденные секреты живостью (проверка во внешней системе)
* Bad, потому что верификация = активные запросы к внешним системам с фейковыми/чужими секретами — нежелательное поведение в CI
* Bad, потому что pre-commit-интеграция слабее официальной у gitleaks

### Самописный grep-хук

* Good, потому что нулевая зависимость
* Bad, потому что правила секретов — экспертиза, которую нельзя поддерживать в репозитории приложения (паттерны меняются, false positive tuning бесконечен)

### Только CI (без pre-commit)

* Good, потому что одна точка настройки
* Bad, потому что обратная связь приходит после push, а не до коммита — утечка уже в локальной истории

### Только pre-commit (без CI)

* Bad, потому что `--no-verify` делает политику необязательной; защита должна быть необходмой хотя бы в одной точке

### Inline-маркеры `gitleaks:allow`

* Good, потому что подавление точечное, у места срабатывания
* Bad, потому что захламляет код и применяется по привычке; в allowlisted-пути маркер не нужен, вне его — повод перепроверить, а не глушить

### Переписывание истории как стандартная реакция

* Good, потому что удаляет секрет из истории репозитория
* Bad, потому что ломает все git worktree (несколько агентов работают параллельно — AGENTS.md) и всех collaborators
* Bad, потому что не отзывает секрет: клоны/форки/CI-кэш сохраняют историю — безопасность даёт только ротация
* Bad, потому что force-push сбрасывает open PR'ы и локальные ветки

## More Information

* Реакция на утечку (пошагово), работа с allowlist: [docs/development/security.md](../../development/security.md)
* Tooling-issues: #72 (pre-commit + `.gitleaks.toml`), #73 (blocking GitHub Actions workflow), #74 (`make secrets-scan`)
* Связанные ADR: ADR-0010 (Fernet-шифрование stored credentials — защита в БД; ADR-0032 — защита git-истории), ADR-0019 (Makefile — единая точка входа, `make secrets-scan`), ADR-0024 (secrets в k8s), ADR-0028 (транспортная безопасность)
* Нумерация: issue #75 планировал номер 0031, но он занят ADR-0031 (`backend/0031-uv-package-manager.md`); по конвенции сквозной нумерации реестра этот ADR получил 0032.
* Триггеры пересмотра: миграция enforcement в GitLab (если mirror перестанет быть read-only); появление требований регуляторики к удалению секретов из истории (пересмотреть no-rewrite политику).
