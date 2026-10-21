---
status: proposed
date: 2026-10-21
decision-makers: SteeveRan
---

# Developer tooling — корневой Makefile как единая точка входа (mypy, knip, vulture, lint/format/typecheck)

## Context and Problem Statement

К моменту написания ADR в репозитории накопился набор скриптов, размазанных по трём каталогам: [`backend/scripts/`](../../../backend/scripts/), [`frontend/scripts/`](../../../frontend/scripts/), [`infrastructure/`](../../../infrastructure/) (`init.sh`, `update-env.sh`, `harbor/deploy.sh`, `harbor/teardown.sh`). У каждого скрипта свои требования к окружению (backend — venv, frontend — nvm + yarn Berry, infra — docker/tofu), и агент или новый разработчик должен знать, какой скрипт где лежит и как его вызывать. Документация (`AGENTS.md`, `docs/development/*`) дублировала простыни bash-команд, которые расходились с реальностью.

Дополнительно не был зафиксирован выбор инструментов code quality: проверка типов backend (mypy — добавить или нет?), поиск мёртвого кода (vulture уже был, чем покрывать frontend?).

Фактические вопросы:

1. **Единая точка входа**: чем оркестрировать все скрипты — Makefile, just, task, npm-скрипты или README со списком команд?
2. **Typecheck backend**: mypy или pyright, и на каком уровне строгости?
3. **Dead-code frontend**: knip или ts-prune?

Решение о стеке (ruff, eslint, prettier, pytest, vitest) уже зафиксировано в [ADR-0001](../backend/0001-choose-backend-stack.md) и [ADR-0002](../frontend/0002-frontend-stack-react-antd-rtk.md); этот ADR не пересматривает его, а фиксирует **слой запуска** поверх. Dev-стенд — [ADR-0022](../infrastructure/0022-dev-stand-on-kind.md) (kind) с историческим compose-слоем [ADR-0012](../archive/infrastructure/0012-docker-compose-split-dev-env.md), IaC-слой — [ADR-0013](../infrastructure/0013-opentofu-iac-keycloak-gitlab-harbor.md); их make-цели — тонкие обёртки, владение логикой остаётся в тех ADR.

## Decision Drivers

- **Минимализм** (драйвер ADR-0001): не добавлять инструменты ради инструментов; make есть везде (Linux/macOS), ничего устанавливать не нужно
- **Тонкая обёртка**: Makefile не дублирует логику скриптов — только вызывает их; вся логика окружения (venv, nvm) остаётся в скриптах
- **Self-documenting**: `make help` по умолчанию, без отдельной документации по целям
- **Агент-дружелюбность**: AI-агентам нужна одна предсказуемая точка входа с единым паттерном имён
- **Зелёный baseline**: новые проверки (mypy, knip) обязаны проходить на текущем коде — не strict, без красного прогонов в CI

## Considered Options

* Корневой Makefile, тонкая обёртка над существующими скриптами, hyphen-стиль имён
* just / task (современные make-аналоги)
* npm/yarn-скрипты в frontend/package.json как центральная точка
* README со списком команд (без раннера)
* mypy (backend typecheck): vs pyright
* knip (frontend dead-code): vs ts-prune

## Decision Outcome

Chosen option: **корневой Makefile — тонкая обёртка, self-documenting через `make help`**; **mypy** для typecheck backend; **knip** для dead-code frontend.

### Makefile (корневой [`Makefile`](../../../Makefile))

Принцип: **Makefile не содержит логики** — каждая цель вызывает существующий скрипт (`./backend/scripts/*.sh`, `./frontend/scripts/*.sh`, `./infrastructure/init.sh`) или одну compose/tofu-команду. Никакой дублированной логики окружения.

Конвенции:

- Имена целей — **hyphen-стиль**: `dev-up`, `test-unit-backend`, `lint-frontend` (не snake_case)
- Паттерн имени: `<группа>-<стек>`; цель без суффикса стека = оба стека (`lint`, `typecheck`, `dead-code`)
- Группы (все цели `.PHONY`, `.DEFAULT_GOAL := help`):

| Группа | Цели | Назначение |
|---|---|---|
| `dev-*` | `build`, `up`, `init`, `down`, `clean` | дев-стек приложения (после [ADR-0022](../infrastructure/0022-dev-stand-on-kind.md) — kind/helm; ранее `docker compose`, [ADR-0012](../archive/infrastructure/0012-docker-compose-split-dev-env.md)) |
| `infra-*` | `up`, `init`, `down`, `clean` (+ `clean-compose`, `clean-harbor`, `clean-tofu`) | зависимости; `infra-init` = `./infrastructure/init.sh` (flow — [ADR-0013](../infrastructure/0013-opentofu-iac-keycloak-gitlab-harbor.md)) |
| `test-*` | `unit`, `e2e`, `integrations`, `all` × стек | тесты; проброс аргументов через `TEST_ARGS` |
| `lint-*` / `format-*` / `typecheck-*` | `backend`, `frontend`, без суффикса | ruff / eslint+prettier / mypy+tsc |
| `coverage-*` | `backend-unit`, `backend-e2e`, `frontend`, `all` | покрытие кода и эндпоинтов |
| `dead-code-*` | `backend`, `frontend`, без суффикса | vulture / knip |

- Self-documenting help: секции `##@ Название`, цели с `## Описание`, awk-парсер `make help` (дефолтная цель)
- `infra-clean` — **агрегация** трёх под-целей чистки (compose `down -v`, harbor `teardown.sh --all`, tofu — `rm` стейт-файлов), а не одна большая команда; каждая под-цель вызываема отдельно

### Typecheck backend — mypy

**mypy** в `backend` ([`backend/scripts/type-check.sh`](../../../backend/scripts/type-check.sh) + `[tool.mypy]` в [`pyproject.toml`](../../../backend/pyproject.toml)), **не pyright**:

- mypy — фактический стандарт для FastAPI/SQLAlchemy-проектов; SQLAlchemy и pydantic поставляют **официальные mypy-плагины** (`sqlalchemy.ext.mypy.plugin`, `pydantic.mypy`), pyright-эквивалентов нет
- консистентно с ADR-0001 (типизированный backend, mypy как оговорённый инструмент)
- Уровень — **pragmatic baseline, не strict**: `ignore_missing_imports = true` (python-gitlab/PyGithub/apscheduler/authlib без type stubs), плагины pydantic+SQLAlchemy, `explicit_package_bases` (editable install). Устаревшие `Column()`-модели требуют отключения части error-codes (`arg-type`, `assignment`, ...) — путь апгрейда: миграция моделей на `Mapped[]`/`mapped_column()` с постепенным включением кодов обратно
- Обязательство: конфигурация держится **зелёной**; новые отключения — только с обоснованием в комментарии

### Dead-code

- Backend — **vulture** (`backend/scripts/vulture.sh`, всегда exit 0 + whitelist [`backend/vulture-whitelist.py`](../../../backend/vulture-whitelist.py) с обоснованием каждого ложного срабатывания)
- Frontend — **knip** (`knip@^6`, devDependency, [`frontend/knip.json`](../../../frontend/knip.json): entry `src/main.tsx` + тесты, project `src/**/*.{ts,tsx}`; yarn-скрипт `dead-code` с `--no-exit-code`), **не ts-prune**: ts-prune заброшен (последний релиз 2022, не поддерживает exports-граф ECD/Vite), knip активен и покрывает не только unused exports, но и неиспользуемые зависимости/файлы
- Паритет поведения: оба инструмента **не ломают** запуск (exit 0) — находки носят информационный характер до ручного разбора

### Consequences

* Good, because один паттерн запуска для агента и человека: `make <группа>-<стек>`, справка — `make help`
* Good, because логика окружения остаётся в скриптах (venv/nvm-акробатика не дублируется в Makefile)
* Good, because mypy-плагины SQLAlchemy/pydantic дают осмысленные проверки типов на ORM-слое, чего pyright из коробки не даёт
* Good, because knip+vulture закрывают dead-code в обоих стеках единым паттерном (`make dead-code`)
* Bad, because pragmatic mypy baseline отключает часть проверок на ORM-атрибутах — до миграции моделей на `Mapped[]` часть реальных ошибок типов в моделях не ловится
* Bad, because make — ещё один синтаксис (табы, `.PHONY`) для тех, кто его не знает; но альтернативы требуют установки
* Neutral, because `dead-code` и `test-e2e-coverage` — информационные цели (exit 0), гейтинг качества решается отдельно, не этим ADR
* Non-goals: CI-интеграция (gitlab-ci), watch-режимы, pre-commit hooks, отказ от прямого вызова скриптов (скрипты вызываемы и напрямую)

### Confirmation

1. Контракт Makefile (структура, группы, отсутствие дублирования логики) проверяется dry-run и help:

```bash
make help                       # все группы и цели с описаниями
make -n dev-up infra-clean test-all coverage-all   # рецепты resolve без ошибок
```

2. Зелёность новых проверок на текущем коде:

```bash
make typecheck-backend   # mypy: 0 ошибок на backend/app
make dead-code           # vulture + knip завершаются с exit 0
```

3. Fitness-критерии для ревью:
   - Новая make-цель не содержит логики окружения (venv/nvm/экспорт переменных) — только вызов существующего скрипта или одну compose/tofu-команду; если скрипта нет — он создаётся в `backend/scripts/`/`frontend/scripts/` по паттерну соседей
   - Имя новой цели следует паттерну `<группа>-<стек>`; цель «оба стека» — без суффикса; группа описана `##@`-секцией
   - Новое отключение в `[tool.mypy]` (error-code, per-module override) имеет комментарий с обоснованием и путём включения обратно

## Pros and Cons of the Options

### Корневой Makefile — chosen

* Good, because make предустановлен почти везде — ноль новых зависимостей (драйвер минимализма)
* Good, because зрелый паттерн self-documenting help (`##@`/`##` + awk) — цели документируют сами себя
* Good, because цели-агрегаторы (`test-all`, `lint`, `infra-clean`) тривиальны — это просто пререквизиты
* Bad, because синтаксис с табами хрупок (копипаст из docs ломает файл)
* Neutral, because параллелизм (`-j`) для агрегаторов не используется — цели и так быстрые

### just / task

* Good, because современный синтаксис без табов, встроенные аргументы
* Bad, because требует установки отдельного бинарника у каждого разработчика и агента — против драйвера минимализма
* Neutral, because выигрыш в синтаксисе не окупает барьер установки для 6 групп целей

### npm/yarn-скрипты как центральная точка

* Good, because для frontend это и так есть (yarn scripts)
* Bad, because backend и infra не Node: центральная точка в `package.json` требует Node для запуска python/docker-команд — инверсия зависимостей
* Bad, because не решает infra-цели (`infra-init` с kind/tofu)

### README со списком команд (без раннера)

* Good, because ноль кода
* Bad, because команды копипастятся вручную и неизбежно расходятся с документацией — ровно та проблема, от которой уходим
* Bad, because нет целей-агрегаторов: «запусти всё» = длинная строка в README

### mypy vs pyright

* Good (mypy), because официальные плагины SQLAlchemy + pydantic — ключевой фактор для этого стека
* Good (mypy), because упоминается в ADR-0001 как инструмент стека
* Bad (mypy), because медленнее pyright на больших кодовых базах (для 132 файлов backend несущественно)
* Neutral (pyright), because он строже «из коробки», но строгость без ORM-плагинов даёт больше шума, чем пользы на legacy `Column()`-моделях

### knip vs ts-prune

* Good (knip), because активная поддержка (v6, 2024+) против заброшенного ts-prune
* Good (knip), because шире покрытие: unused files, dependencies, exports — одним инструментом
* Bad (knip), because требует конфигурации entry/project (ts-prune работал без конфига) — цена: один `knip.json`

## More Information

- [ADR-0001](../backend/0001-choose-backend-stack.md) — backend-стек (ruff, pytest, mypy как оговорённый инструмент); [ADR-0002](../frontend/0002-frontend-stack-react-antd-rtk.md) — frontend-стек (eslint, prettier, vitest, tsc)
- [ADR-0012](../archive/infrastructure/0012-docker-compose-split-dev-env.md) (архив) — исторический compose-слой (после [ADR-0022](../infrastructure/0022-dev-stand-on-kind.md) владение `dev-*` переходит к kind/helm-схеме); [ADR-0013](../infrastructure/0013-opentofu-iac-keycloak-gitlab-harbor.md) — IaC-слой и `init.sh` (владение `infra-init`)
- Использование агентами: [`AGENTS.md`](../../../AGENTS.md) (разделы «Start Development Environment», «Run Tests», «Code Quality Checks»), детально — [`docs/development/setup.md`](../../development/setup.md); тестовые решения — семейство ADR-0014…0018 (реестр: [`docs/adr/README.md`](../../README.md))
- Источник подтверждённых решений (удалён после фиксации в этом ADR): `plans/makefile-tooling.md`
- Условие пересмотра: переход на CI-гейтинг качества (обязательные mypy strict / knip exit-code в pipeline) — новый ADR
