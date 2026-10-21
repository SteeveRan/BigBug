---
status: proposed
date: 2026-10-22
decision-makers: SteeveRan
---

# Тестировать e2e-уровень: backend — pytest-suite против живого dev-стенда, frontend — Cypress как запланированное направление (сейчас пусто); удалить `plans/development/testing.md`

## Context and Problem Statement

Семейство тестовых ADR закрывается последним, пятым документом: ADR-0014 (backend unit), [ADR-0015](../frontend/0015-frontend-unit-testing-vitest.md) (frontend unit), [ADR-0016](../backend/0016-backend-integration-testing.md) (backend integration) и [ADR-0017](../frontend/0017-frontend-integration-testing.md) (frontend integration) уже зафиксированы. Остался сводный e2e-домен, которым `plans/development/testing.md` владеет целиком: roadmap ADR (`.agents/plans/adr-roadmap.md`, принцип «один домен — один ADR») отводит ADR-0018 роль последнего потребителя этого файла — после его выхода документ удаляется, операциональный runbook (pytest-шпаргалка, рецепты `TEST_ARGS`) переезжает в `AGENTS.md`, решения — сюда.

Фактическое состояние (проверено по коду, 2026-10-22):

- **Backend e2e существует и велик**: `backend/tests/e2e/` — 25 тестовых файлов, ~156 тестов против живого dev-стенда (`make dev-up`, ADR-0012). ADR-0016 уже объявил этот suite **интеграционным уровнем backend** — механика (транспорт, аутентификация, изоляция данных) зафиксирована там. Но за пределами ADR-0016 остались: CI-политика запуска, отчёт покрытия эндпоинтов как gate и место хранения runbook.
- **Frontend e2e не существует**: каталог `frontend/src/tests/e2e/` отсутствует, Cypress не входит в `frontend/package.json`. Заготовки под него уже разбросаны по кодовой базе: make-цели `test-e2e-frontend` и `test-e2e`, ветка `--e2e` в `frontend/scripts/test.sh` (с сообщением «Cypress ещё не настроены»), пометки «Cypress — planned» в `AGENTS.md`. То есть намерение зафиксировано операционально, но нигде не документировано как решение.

Фактические вопросы:

1. **Backend e2e**: подтвердить pytest-suite против dev-стенда как e2e-стратегию и зафиксировать CI-политику (e2e не выполняется в голом CI) и отчёт покрытия эндпоинтов?
2. **Frontend e2e**: записать Cypress как запланированное направление (proposed, без установки зависимости) или выбрать альтернативу сейчас?
3. **Документация**: удалить `plans/development/testing.md`, перенеся runbook в `AGENTS.md`, и убрать висячие ссылки?

## Decision Drivers

- Граница уровней уже задана ADR-0014 и ADR-0016: unit и integration закрывают in-process и API→PostgreSQL сценарии; e2e-домен отличается **политикой** (два стека, зависимость от dev-стенда, полнота покрытия API), а не новой механикой backend-тестов
- Backend e2e-прогон требует запущенного dev-стенда (`make dev-up`) — ADR-0016 записал это как «Bad» без решения; именно ADR-0018 фиксирует политику: e2e — уровень живого стенда, не голого CI
- Полнота e2e-покрытия API измерима и уже измеряется: teardown-отчёт `backend/reports/endpoint-coverage.{json,md}` с мягким порогом 90% (`MIN_COVERAGE_PERCENT` в `openapi_utils.py`)
- Frontend: ограничения jsdom (нет layout, нет реальных событий браузера) записаны как «Bad» в ADR-0015/0017 и закрываются только настоящим браузерным e2e; но реальной потребности в нём пока нет — suite пуст, заготовки — placeholder'ы
- Минимализм (драйвер ADR-0001): не добавлять зависимость Cypress в `package.json` до появления первого сценария
- Runbook (pytest-шпаргалка, рецепты `TEST_ARGS`) — операциональное знание для агентов и CI, место ему в `AGENTS.md`; ADR — только решения

## Considered Options

* Backend: pytest-suite против dev-стенда (как в ADR-0016); frontend: Cypress — запланированное направление без установки — chosen
* Frontend: Playwright вместо Cypress (установить сейчас)
* Frontend: не фиксировать e2e-направление вовсе (убрать заготовки `--e2e` из Makefile и скриптов)
* Backend e2e как обязательный CI-gate (гонять e2e в CI с поднятием dev-стенда)

## Decision Outcome

Chosen option: **двухстековая e2e-стратегия** — backend: существующий pytest-suite против живого dev-стенда (механика — ADR-0016, этот ADR фиксирует CI-политику и отчёт покрытия); frontend: Cypress как запланированное направление (proposed, каталог `src/tests/e2e/`, без установки зависимости до первого сценария), because backend-уровень уже работает на ~156 тестах и его политика требует лишь фиксации, а frontend-e2e сегодня — пустая заготовка: выбор Cypress vs Playwright честно делать, когда появится первый браузерный сценарий и живая потребность.

### Зафиксированные правила

**1. Backend e2e** (механика — [ADR-0016](../backend/0016-backend-integration-testing.md), здесь — политика):

- прогон **только** против живого dev-стенда (`make dev-up` → `make test-e2e-backend`); fail-fast на `/api/health` обязателен
- **CI-политика**: e2e-backend не выполняется в голом CI — это осознанное решение, а не упущение; unit (ADR-0014) и frontend unit/integrations (ADR-0015/0017) покрывают голый CI, e2e — уровень живого стенда разработчика. Автоматизация e2e в CI (поднятие стенда в CI-runner'е) — отдельное будущее решение, не часть этого ADR
- **Отчёт покрытия эндпоинтов** — часть teardown e2e-сессии: `backend/reports/endpoint-coverage.{json,md}`, порог `MIN_COVERAGE_PERCENT = 90%`, мягкий gate (warning, не падение); каждый новый API-эндпоинт должен получить e2e-покрытие, попадающее в отчёт
- валидация ответов — по замороженному контракту `backend/openapi.json` (`assert_matches_openapi`); пересборка замороженной спеки — `backend/scripts/export-openapi.sh`
- code-coverage e2e-прогона — отдельный скрипт `backend/scripts/test-e2e-coverage.sh` (backend под `coverage run` на `COVERAGE_PORT=8011`), не смешивается с обычным прогоном

**2. Frontend e2e — proposed direction**:

- целевой инструмент — **Cypress**, каталог `frontend/src/tests/e2e/`, против того же живого dev-стенда (backend API + frontend SPA)
- зависимость **не устанавливается** до появления первого сценария; существующие заготовки (make-цели `test-e2e-frontend`/`test-e2e`, ветка `--e2e` в `frontend/scripts/test.sh`) остаются placeholder'ами
- первый реальный Cypress-сценарий = триггер: установить `cypress` в dev-зависимости, настроить конфиг и закрепить правила отдельным изменением этого же ADR (или новым, если решение изменится)
- до тех пор браузерное покрытие frontend не существует и не подразумевается: unit/integrations на jsdom (ADR-0015/0017) — единственные уровни frontend-тестов

**3. Документация**:

- `plans/development/testing.md` **удаляется**; её решения распределены по ADR-0014/0015/0016/0017/0018, операциональный runbook (pytest-шпаргалка, `TEST_ARGS`-рецепты, запуск e2e) — в [`AGENTS.md`](../../../AGENTS.md) (раздел Testing)
- источник истины по конфигурации — файлы кода (`pyproject.toml`, `vitest.config.ts`, `conftest.py`, скрипты), не документы

### Consequences

* Good, because семейство тестовых ADR замкнуто: у каждого уровня (unit/integration/e2e × backend/frontend) есть ровно один документ-решение
* Good, because CI-политика и порог покрытия эндпоинтов впервые записаны явно — раньше они существовали только в коде и в удаляемом гайде
* Good, because runbook переехал к своей аудитории (агенты и разработчики) в `AGENTS.md`, а решения остались в ADR — без дублей
* Good, because frontend e2e остаётся честной заготовкой: намерение зафиксировано, зависимость и инфраструктура не тянутся в проект впустую
* Bad, because e2e-уровень не выполняется в голом CI: регрессии, ловимые только реальным PostgreSQL + реальным HTTP, обнаруживаются лишь на живом стенде (осознанный риск, унаследованный от ADR-0016)
* Bad, потому что мягкий gate покрытия (90%, warning) не блокирует прогон: падение покрытия ниже порога замечает только внимательный читатель отчёта; перевод в жёсткий gate — при стабилизации
* Bad, because заготовка Cypress без зависимости может «протухнуть»: make-цели `test-e2e-frontend` сообщают «не настроены» неопределённо долго; условие пересмотра — ниже
* Neutral, because выбор Cypress vs Playwright отложен до первого сценария — предложенное направление нечувствительно к этому выбору: каталог, dev-стенд и make-цели останутся теми же
* Non-goals: механика backend e2e-тестов (ADR-0016), unit/integrations-уровни (ADR-0014/0015/0017), CI-пайплайны самого приложения (ADR-0011), автоматизация dev-стенда в CI

### Confirmation

1. **Backend e2e-прогон** (стратегия «только против живого стенда»):

```bash
make dev-up
make test-e2e-backend TEST_ARGS="tests/e2e/test_auth.py -v"
```

Ожидаемый результат: тесты проходят; без dev-стенда — ошибка «E2E backend is not reachable». После прогона существует `backend/reports/endpoint-coverage.md` с покрытием ≥ 90%.

2. **Frontend e2e остаётся заготовкой** — при ревью: в `frontend/package.json` нет `cypress`, каталог `src/tests/e2e/` пуст или отсутствует:

```bash
# ожидание: пусто
grep -n '"cypress' frontend/package.json
```

3. **Документация** — при ревью: `plans/development/testing.md` не существует; `grep -rn "development/testing.md"` по репозиторию не находит живых ссылок (исторические упоминания внутри самих ADR-0014/0015/0016/0017 — описание факта удаления, не ссылки-инструкции); pytest-шпаргалка и рецепты `TEST_ARGS` присутствуют в `AGENTS.md`.

## Pros and Cons of the Options

### Backend: pytest-против-dev-стенда; frontend: Cypress planned — chosen

* Good, because фиксирует работающий статус-кво без единой строки миграции
* Good, because отложенный выбор инструмента frontend-e2e не блокирует ничто: сценарий всё равно появится позже
* Bad, because «planned» без дедлайна: заготовка может оставаться пустой сколь угодно долго
* Bad, because CI не ловит e2e-регрессии (см. Consequences)

### Frontend: Playwright вместо Cypress (установить сейчас)

* Good, because один инструмент на браузерное тестирование с сильным API и trace-отладкой; свободная лицензия
* Bad, because решение принимается без единого сценария — выбор инструмента без потребности
* Bad, потому что существующие заготовки (сообщения в `scripts/test.sh`, пометки в `AGENTS.md`) указывают на Cypress — смена инструмента сейчас = чистый churn

### Frontend: не фиксировать e2e-направление (убрать заготовки)

* Good, because честнее: нет ни инструмента, ни тестов — зачем make-цели?
* Bad, because заготовки (`test-e2e-frontend`, `--e2e`) уже встроены в tooling (ADR-0019) и в пометки `AGENTS.md`; их удаление — обратимый, но бессмысленный churn
* Bad, потому что направление «браузерный e2e закроет ограничения jsdom» (ADR-0015/0017) теряет якорь в документации

### Backend e2e как обязательный CI-gate

* Good, потому что e2e-регрессии ловятся до merge
* Bad, потому что требует полноценного dev-стенда (PostgreSQL, Redis, миграции) в CI-runner'е — новая инфраструктура без запроса от CI-процесса
* Условие пересмотра: при появлении постоянного CI-контура с Docker-раннерами — переоткрыть этот ADR

## More Information

- Родственные ADR (семейство testing): [ADR-0014](../backend/0014-backend-unit-testing-pytest.md) (backend unit), [ADR-0015](../frontend/0015-frontend-unit-testing-vitest.md) (frontend unit), [ADR-0016](../backend/0016-backend-integration-testing.md) (backend integration = e2e-suite), [ADR-0017](../frontend/0017-frontend-integration-testing.md) (frontend integration); [ADR-0019](0019-makefile-tooling-single-entrypoint.md) (make-цели тестирования), [ADR-0012](../archive/infrastructure/0012-docker-compose-split-dev-env.md) (архив; dev-стенд как требование e2e — теперь [ADR-0022](../infrastructure/0022-dev-stand-on-kind.md))
- Фактура: `backend/tests/e2e/` (25 файлов, ~156 тестов), `backend/tests/e2e/conftest.py`, `backend/tests/e2e/openapi_utils.py` (`MIN_COVERAGE_PERCENT = 90`), `backend/scripts/test-e2e.sh`, `backend/scripts/test-e2e-coverage.sh`, `backend/scripts/export-openapi.sh`; frontend-заготовки: Makefile (`test-e2e-frontend`, `test-e2e`), `frontend/scripts/test.sh` (ветка `--e2e`)
- Runbook (запуск, `TEST_ARGS`, pytest-шпаргалка, переменные окружения e2e): [`AGENTS.md`](../../../AGENTS.md), раздел Testing
- Roadmap ADR: `.agents/plans/adr-roadmap.md` — ADR-0018 назначен последним потребителем `plans/development/testing.md` с её удалением
- Условие пересмотра: (а) первый frontend e2e-сценарий — установка и фиксация Cypress (или смена выбора на Playwright); (б) появление CI-контура с Docker — перевод e2e в CI-gate; (в) стабилизация API — жёсткий gate порога 90%; (г) появление кросс-системных e2e-сценариев (браузер + backend + GitLab) — тогда термин «e2e» разводится на уровни новым ADR
- Реестр ADR и конвенции: [docs/adr/README.md](../README.md)
