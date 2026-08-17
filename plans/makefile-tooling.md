# Makefile — единая точка входа для запуска всего

Статус: спроектировано, передаётся в Code mode.
Связанные todo: см. актуальный список (7 пунктов).

## Решения (подтверждены пользователем)

1. **Дефис-стиль** имён: `dev-up`, `test-unit-backend`, `lint-frontend`.
2. **mypy добавляем** в backend (новый скрипт + конфиг, зелёный прогон на текущем коде).
3. **knip добавляем** во frontend (devDependency + конфиг + yarn-скрипт).
4. **infra-clean** дергает отдельные подкоманды чистки каждого сервиса:
   - compose (keycloak+gitlab+postgres): `down -v` (с вольюмами);
   - harbor (kind): `teardown.sh --all`;
   - tofu: удаляем всё, что создают `tofu init/plan/apply` и `init.sh` в `infrastructure/terraform/` (`.terraform/`, `.terraform.lock.hcl`, `terraform.tfstate*`, `*.tfplan`, `crash.log`, `terraform.tfvars`). `infrastructure/.env` НЕ трогаем (нужен самому `infra-clean-compose`, содержит секреты пользователя).
5. Makefile — тонкая обёртка над существующими скриптами (никакой дублированной логики). `make help` — self-documenting (`##` комментарии, секции через `##@`).

## Карта целей Makefile (корень репозитория)

Переменные: `COMPOSE_APP = docker compose`, `COMPOSE_INFRA = docker compose -f infrastructure/docker-compose.yml --env-file infrastructure/.env`, `TF_DIR = infrastructure/terraform`, `.DEFAULT_GOAL := help`, `SHELL := /usr/bin/env bash`, все цели `.PHONY`.

### Группа 1 — dev (дев-сборка приложения, `docker-compose.yml`)

| Цель | Рецепт | Комментарий |
|---|---|---|
| `dev-build` | `$(COMPOSE_APP) build` | |
| `dev-up` | `$(COMPOSE_APP) up -d` | entrypoint сам ждёт БД и мигрирует |
| `dev-init` | `$(COMPOSE_APP) run --rm backend app:init` | повторный прогон миграций (entrypoint поддерживает `app:init`: wait DB → alembic → exit) |
| `dev-down` | `$(COMPOSE_APP) down` | |
| `dev-clean` | `$(COMPOSE_APP) down -v --remove-orphans` | чистка ПОСЛЕ остановки, с вольюмами (postgres/redis) |

### Группа 2 — infra (зависимости: keycloak, gitlab, harbor)

| Цель | Рецепт |
|---|---|
| `infra-up` | `$(COMPOSE_INFRA) up -d` |
| `infra-init` | `./infrastructure/init.sh` (compose → harbor → tofu → update-env) |
| `infra-down` | `$(COMPOSE_INFRA) down` |
| `infra-clean` | aggregate: `infra-clean-compose infra-clean-harbor infra-clean-tofu` |
| `infra-clean-compose` | `$(COMPOSE_INFRA) down -v --remove-orphans` |
| `infra-clean-harbor` | `bash infrastructure/harbor/teardown.sh --all` (sudo для /etc/hosts) |
| `infra-clean-tofu` | `rm -rf` по списку из решения №4 |

### Группа 3 — test (матрица стек × тип)

Backend: только `unit` и `e2e` (интеграционной папки нет). Frontend: `unit`, `integrations`, `e2e` (заглушка).

| Цель | Рецепт |
|---|---|
| `test-unit-backend` | `./backend/scripts/test-unit.sh` |
| `test-e2e-backend` | `./backend/scripts/test-e2e.sh` (нужен запущенный dev-стек) |
| `test-all-backend` | `test-unit-backend test-e2e-backend` |
| `test-unit-frontend` | `./frontend/scripts/test.sh --unit` |
| `test-integrations-frontend` | `./frontend/scripts/test.sh --integrations` |
| `test-e2e-frontend` | `./frontend/scripts/test.sh --e2e` |
| `test-all-frontend` | `./frontend/scripts/test.sh --all` |
| `test-unit` | оба стека |
| `test-integrations` | `test-integrations-frontend` |
| `test-e2e` | оба стека |
| `test-all` | `test-all-backend test-all-frontend` |

### Группа 4 — lint / format / typecheck

| Цель | Рецепт |
|---|---|
| `lint-backend` / `lint-frontend` / `lint` | `./backend/scripts/lint.sh` / `./frontend/scripts/lint.sh` / оба |
| `format-backend` / `format-frontend` / `format` | `./backend/scripts/format.sh` / `./frontend/scripts/format.sh` / оба |
| `typecheck-backend` / `typecheck-frontend` / `typecheck` | `./backend/scripts/type-check.sh` (НОВЫЙ) / `./frontend/scripts/type-check.sh` / оба |

### Группа 5 — coverage (код и эндпоинты)

| Цель | Рецепт |
|---|---|
| `coverage-backend-unit` | `./backend/scripts/test-unit.sh --cov=app --cov-report=term-missing` (скрипт прокидывает `"$@"` в pytest — работает без правок) |
| `coverage-backend-e2e` | `./backend/scripts/test-e2e-coverage.sh` (code coverage; отчёт по эндпоинтам `backend/reports/endpoint-coverage.md` генерится в teardown любого e2e-прогона) |
| `coverage-frontend` | `./frontend/scripts/test.sh --coverage` |
| `coverage-all` | три цели выше подряд |

### Группа 6 — dead-code

| Цель | Рецепт |
|---|---|
| `dead-code-backend` | `./backend/scripts/vulture.sh` (всегда exit 0) |
| `dead-code-frontend` | `./frontend/scripts/dead-code.sh` (НОВЫЙ) |
| `dead-code` | оба |

## Новые файлы / правки кода

### 1. `backend/scripts/type-check.sh` (новый)

Копия паттерна `backend/scripts/lint.sh`: venv-проверка → `cd backend` → `"$(VENV)" -m mypy app/`. Заголовок с usage/требованиями как у соседей.

### 2. `backend/pyproject.toml` — секция `[tool.mypy]`

Прагматичный базовый уровень (цель — зелёный прогон текущего кода, не strict):
`python_version = "3.14"`, `ignore_missing_imports = true` (python-gitlab/PyGithub/apscheduler и пр. без type stubs), `warn_unused_ignores`, `warn_redundant_casts`, `check_untyped_defs = true`. Если прогон красный — тонко докручивать (per-module overrides последним средством). Итерации до зелёного `make typecheck-backend`.

### 3. Frontend knip

- `cd frontend && yarn add -D knip`;
- `frontend/package.json`: скрипт `"dead-code": "knip --no-exit-code --production false"` (паритет с vulture: не ломает CI, только предупреждение);
- `frontend/knip.json`: `entry: ["src/main.tsx"]`, `project: ["src/**/*.{ts,tsx}"]`, тесты в entry (`src/tests/**/*.{test,tsx}` и setup), при необходимости `ignore`. Настройка по фактическому прогону;
- `frontend/scripts/dead-code.sh` (новый): паттерн `frontend/scripts/type-check.sh` (nvm → `yarn dead-code`).

### 4. Верификация (кодер обязан прогнать)

```bash
make help
make -n dev-up dev-clean infra-clean test-all coverage-all   # dry-run: рецепты без ошибок
make lint-backend && make typecheck-backend                   # реальные прогоны
make dead-code-backend && make dead-code-frontend             # реальные прогоны
```

## Документация (лаконично, без мусора)

- `AGENTS.md`: секции «Start Development Environment», «Run Tests», «Code Quality Checks» — заменить простыни bash на make-команды + краткая таблица групп. Ничего сверх этого.
- `plans/development/setup.md`: секция «Quick start via Make» (up инфры → init → dev up).
- `plans/development/testing.md`: в «Запуск тестов» добавить make-варианты (backend + frontend + coverage).
- `plans/development/infrastructure.md`: make infra-* команды.
- `infrastructure/README.md`: ссылка на make infra-*.
- `CHANGELOG.md`: `## [Unreleased] → ### Added` — Makefile, mypy, knip.

## Что НЕ делаем (YAGNI)

- Не добавляем `infra-harbor-down` (kind-кластер не «останавливается», только сносится — уже есть в clean).
- Не трогаем существующие скрипты (кроме чтения) — Makefile их вызывает.
- Не заводим CI-интеграцию, watch-режимы и прочее, чего не просили.
