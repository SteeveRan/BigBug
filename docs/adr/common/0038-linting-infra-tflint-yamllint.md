---
status: accepted
date: 2026-10-24
decision-makers: SteeveRan
consulted: SteeveRan
informed: SteeveRan
---

# Linting tooling: tflint + yamllint для инфра-среза, make-цели lint-infra и CI lint-workflow

## Context and Problem Statement

Как выстроить линтинг для всех срезов репозитория BigBug? Сейчас линтинг покрывает только backend (`ruff`, [ADR-0019](0019-makefile-tooling-single-entrypoint.md)) и frontend (`eslint`). Инфра-код не проверяется ничем:

* OpenTofu-описания ([ADR-0029](infrastructure/0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md)): `infrastructure/terraform/{base,infra-apps,apps}` — форматирование, синтаксис, неиспользуемые declarations и валидность провайдерских конфигов не проверяются автоматически;
* Helm values-YAML (`infrastructure/terraform/*/values/*.yaml`, `infrastructure/terraform/infra-apps/modules/*/values/*.yaml`) — стиль и синтаксис не проверяются.

Кроме того, в CI (GitHub Actions) нет ни одной lint-джобы: регрессии стиля/валидности любого среза ловятся только на ревью или в рантайме.

Вопросы для решения: какие инструменты выбрать для OpenTofu и для YAML, как они интегрируются в единый Makefile-вход и в CI, и нужно ли расширять `make format`.

## Decision Drivers

* Per [ADR-0019](0019-makefile-tooling-single-entrypoint.md): весь tooling — через корневой Makefile, тонкие цели-обёртки, self-documenting help
* CI-политика ([ADR-0018](0018-e2e-testing-strategy.md) — прецедент): тесты/e2e в CI пока не выносим, но lint-джобы — необходимый минимум, иначе линтинг локальный и необязательный
* Инфра-код линтуется без живого стенда и без credentials — иначе его не прогнать в CI на github-hosted раннере
* Helm chart `charts/bigbug` появится с issue #59 ([ADR-0023](infrastructure/0023-bigbug-helm-chart.md)) — решения по chart-линтингу (`helm lint`/`helm template`) отложены туда, сейчас Helm присутствует только как values-YAML
* Multi-agent worktree discipline: линтинг не должен требовать общий dev-стенд или state

## Considered Options

* OpenTofu: голый `tofu fmt -check` + `tofu validate` vs добавить tflint (bundled ruleset, без плагинов и deep-check) vs trivy config (security-сканирование IaC)
* YAML: yamllint (extends default, отключены `line-length` и `document-start`) vs prettier YAML vs без линтера
* CI: один workflow `lint.yml` с параллельными джобами по срезам vs джобы в существующих workflow vs без CI

## Decision Outcome

Chosen option: **tflint (bundled ruleset) + yamllint, цель `lint-infra` в Makefile, workflow `.github/workflows/lint.yml` с четырьмя параллельными джобами** (backend, frontend, terraform, helm-yaml).

### 1. OpenTofu — tflint поверх fmt/validate

`tofu fmt -check` + `tofu validate` остаются основой (форматирование и провайдерская валидность), но не ловят неиспользуемые declarations, устаревший синтаксис и т.п. tflint с bundled ruleset (preset `recommended`, без плагинов и `deep_check`) закрывает эту дыру без внешних зависимостей: модули локальные, deep-check требует скачанных провайдеров — не годится для быстрого локального и CI-прогона.

### 2. YAML — yamllint с ослабленным default

yamllint проверяет и синтаксис, и стиль Helm values. Голый prettier — только форматирование, без семантических проверок. `line-length` и `document-start` отключены: существующие values-файлы не влезают в жёсткую колонку, а заголовки `---` — шум без пользы; strict-default завалил бы весь инфра-срез и линтер стали бы игнорировать.

### 3. CI — первый lint-workflow

Триггеры: `push` в `main` + все `pull_request`. Четыре параллельные джобы переиспользуют существующие скрипты стеков и make-логику инфры. Пины: tofu `1.13.2` (совпадает с локальной), tflint `>= 0.65`, yamllint `>= 1.38`. Без кэширования (провайдеры качаются с registry — допустимо; оптимизация позже). `tofu init -backend=false` — state не нужен для validate.

### 4. Makefile

`lint-terraform` (fmt-check → tflint → validate × 3 слоя: `base`, `infra-apps`, `apps`) + `lint-helm` (yamllint по `infrastructure/**/*.yaml`) → агрегатор `lint-infra`, включённый в `make lint`. `make format` на инфру **не** расширяется (tofu fmt в fix-режиме не добавлялся — не просили).

### Consequences

* Good, потому что весь срез проверяется одной командой `make lint` — локально и в CI, до ревью
* Good, потому что tflint/yamllint без плагинов и credentials — быстрый прогон без стенда
* Bad, потому что tflint без deep-check не валидирует провайдерские схемы ресурсов (покрывается только `tofu validate` на уровне root'ов)
* Bad, потому что yaml покрывает только `*.yaml` под `infrastructure/` — сломанные GitLab component-шаблоны (`*.yml`) не линтуются (один уже синтаксически бит)
* Neutral, потому что CI без кэша: ~минута на закачку провайдеров за прогон

### Confirmation

* `make lint-infra` — зелёный на актуальном main (tflint/yamllint/fmt/validate без замечаний)
* `.github/workflows/lint.yml` валиден (`actionlint` — 0 ошибок), 4 джобы с пинами tofu 1.13.2 / tflint >= 0.65 / yamllint >= 1.38
* Регрессия стиля values-YAML или неиспользуемая `variable` в модуле ловятся прогоном `make lint-infra` (правила `terraform_unused_declarations`, `terraform_required_providers` активны через preset `recommended`)

## Pros and Cons of the Options

### Голый `tofu fmt` + `tofu validate`

* Good, потому что ноль новых инструментов
* Bad, потому что не ловит неиспользуемые declarations, устаревший синтаксис, missing provider constraints

### tflint (выбрано)

* Good, потому что статический анализ без credentials и сети; правила расширяемы плагинами позже
* Bad, потому что bundled ruleset не видит провайдерские схемы без deep-check

### trivy config

* Good, потому что security-сканирование IaC в придачу
* Bad, потому что другой класс задач (security, не lint) — отдельный follow-up

### yamllint (выбрано)

* Good, потому что синтаксис + стиль, конфиг на 5 строк
* Bad, потому что не понимает Helm-специфики (`helm lint` придёт с issue #59)

## More Information

* Issue: #78; chart-линтинг — issue #59 ([ADR-0023](infrastructure/0023-bigbug-helm-chart.md))
* Единый Makefile-вход — [ADR-0019](0019-makefile-tooling-single-entrypoint.md); слои tofu — [ADR-0029](infrastructure/0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md)
* Follow-up'ы (не в этом решении): tflint-плагины и deep-check, trivy config, actions/cache, линтинг `infrastructure/gitlab-components/**/*.yml` (там уже есть файл с невалидным синтаксисом — починить при включении в скоуп)
