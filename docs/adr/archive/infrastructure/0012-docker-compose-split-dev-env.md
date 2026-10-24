---
status: superseded by [ADR-0022](../../infrastructure/0022-dev-stand-on-kind.md)
date: 2026-10-21
decision-makers: SteeveRan
---

# Dev environment: разделение Docker Compose на infrastructure и application, entrypoint с wait-for-DB и auto-migration

> **SUPERSEDED** [ADR-0022](../../infrastructure/0022-dev-stand-on-kind.md): dev-стенд переезжает в единый kind-кластер (compose остаётся только для GitLab omnibus). Сохранено как исторический контекст: entrypoint-логика `app:start`/`app:init` частично переезжает в helm hook Job ([ADR-0023](../../infrastructure/0023-bigbug-helm-chart.md)). Снос compose-приложения выполнен в #62 (2026-10-24): корневого docker-compose.yml больше нет.

## Context and Problem Statement

Dev-окружение BigBug фактически существует, но решение о его структуре нигде не зафиксировано в ADR. Вопрос: **как организовать docker compose для dev-окружения** — один файл или разделение по частоте перезапуска — и **как гарантировать готовность БД и схему** при старте приложения?

Фактическое состояние (проверено по коду, 2026-10-21):

**1. Два compose-файла** (источники: [`infrastructure/docker-compose.yml`](../../../infrastructure/docker-compose.yml), [`docker-compose.yml`](../../../docker-compose.yml)):

- `infrastructure/docker-compose.yml` — редко перезапускаемые инфраструктурные сервисы: `postgres-keycloak` (:5433), `keycloak` (:8180), `gitlab` (:8080/:8443/:2222), `gitlab-runner`. Запускается с `--env-file infrastructure/.env`, создаёт именованную сеть `bigbug-network`.
- корневой `docker-compose.yml` — часто пересобираемые сервисы приложения: `postgres-backend` (:5432), `redis` (:6379), `backend` (:8000, bind-mount `./backend`, uvicorn `--reload` в development), `frontend` (:5173, bind-mount `./frontend`, `yarn dev`). Подключается к той же сети `bigbug-network` как `external: true`.

**2. Схема портов**: 5173 (frontend) / 8000 (backend) / 8180 (keycloak) / 8080 (gitlab) / 5432 (postgres-backend) / 5433 (postgres-keycloak) / 6379 (redis). GitLab Runner портов не публикует.

**3. Entrypoint** ([`backend/docker/entrypoint.sh`](../../../backend/docker/entrypoint.sh)) — единая точка старта backend-контейнера с тремя режимами:

- `app:start` (команда из compose) — `wait_for_db` (poll `pg_isready`, timeout `DB_WAIT_TIMEOUT=60s`) → `alembic upgrade head` → idempotent seeding (`seed_admin`, `seed_providers`) → `uvicorn` (`--reload` при `ENVIRONMENT=development`)
- `app:init` — то же без запуска uvicorn; используется make-целью `dev-init` (`docker compose run --rm backend app:init`)
- произвольная команда — `exec` как есть (bash, pytest, alembic) без обхода entrypoint

Коды выхода: `0` — успех, `1` — БД недоступна за timeout, `2` — alembic failed.

Связанные планы: [`plans/development/backend.md`](../../../plans/development/backend.md), ADR-0006 (политика миграций Alembic).

## Decision Drivers

- Разный жизненный цикл: GitLab/Keycloak поднимаются часами (GitLab `start_period: 300s`, 4 GB RAM) и пересоздаются раз в месяцы; backend/frontend пересобираются десятки раз в день
- Скорость dev-цикла: рестарт `make dev-up` не должен трогать инфраструктуру и её вольюмы (риск потери данных GitLab при неаккуратном `down -v`)
- Детерминированная готовность БД: compose `depends_on: service_healthy` не покрывает все сценарии запуска (plain `docker run`, CI-джобы), поэтому нужна независимая проверка в entrypoint
- Отсутствие ручных шагов: после `make dev-up` схема применена, admin и провайдеры засеяны — разработчик сразу открывает UI

## Considered Options

* Два compose-файла (infra vs app) + entrypoint с wait-for-DB и auto-migration — фактический стандарт кода
* Один общий compose-файл на все сервисы
* Kubernetes/kind для dev-окружения
* Dev-скрипты без compose (нативный uvicorn/vite + compose только для БД)

## Decision Outcome

Chosen option: **два compose-файла + entrypoint с wait-for-DB и auto-migration** — это работающий стандарт кода, он согласован с ADR-0006 (идемпотентный `alembic upgrade head` безопасно запускать на каждом старте) и требует нуля рефакторинга.

### Зафиксированные правила

**1. Структура compose-файлов**:

| Файл | Сервисы | Запуск | Правило |
|---|---|---|---|
| `infrastructure/docker-compose.yml` | postgres-keycloak, keycloak, gitlab, gitlab-runner | `make infra-up` / `infra-init` | Редко перезапускаемое; внешние данные — в именованных вольюмах (`gitlab_data`, `postgres_keycloak_data`, …) |
| `docker-compose.yml` | postgres-backend, redis, backend, frontend | `make dev-up` | Часто пересобираемое; bind-mount `./backend` и `./frontend` для hot-reload |

- Общая сеть: `bigbug-network`, создаётся инфраструктурным файлом, корневой подключает как `external: true` — сервисы приложения общаются с GitLab/Keycloak по именам контейнеров
- Порядок запуска: сначала `make infra-init`, затем `make dev-up` (корневой compose не запускается без `bigbug-network`)
- `make dev-clean` удаляет вольюмы только приложения (postgres-backend, redis) и физически не может задеть данные GitLab/Keycloak

**2. Entrypoint backend-контейнера** (`backend/docker/entrypoint.sh` — эталон):

- `app:start` — dev/прод-старт: wait-for-DB (poll `pg_isready`, `DB_WAIT_TIMEOUT`, по умолчанию 60s) → миграции → seeding → uvicorn
- `app:init` — без uvicorn; повторная инициализация без рестарта стека (`make dev-init`)
- wait-for-DB дублирует compose-healthcheck намеренно: `pg_isready`-поллинг работает и вне compose (CI, `docker run`)
- миграции и seeding — idempotent, безопасны при каждом старте; сбой seeding не валит контейнер (WARN)
- dev-режим (`ENVIRONMENT=development`): uvicorn `--reload`; иначе — без watcher

### Consequences

* Good, because `make dev-up` (секунды) не зависит от GitLab/Keycloak (минуты) — быстрый цикл правки кода
* Good, because опасные операции (`down -v`) в dev-целях не затрагивают вольюмы инфраструктуры с данными GitLab
* Good, because контейнер сам доводит схему до актуальной — нет ручных «не забудь прогнать миграции»
* Bad, because два файла = две команды запуска и общий шаг «сначала infra» — новый разработчик без README может запустить корневой compose в отрыве и получить `external network not found`
* Bad, потому что рассинхрон между двумя файлами (версии образов, имена сервисов) не ловится линтером — только ручная проверка
* Neutral, потому что entrypoint дублирует healthcheck compose — небольшое усложнение ради переносимости за пределы compose

### Confirmation

Факты ADR проверяются против кода при ревью (чеклист):

1. Список сервисов и портов: `docker compose -f infrastructure/docker-compose.yml --env-file infrastructure/.env config --services` → `gitlab gitlab-runner keycloak postgres-keycloak`; `docker compose config --services` → `backend frontend postgres-backend redis`. Порты — в таблице Context.
2. Поведение entrypoint: `backend/docker/entrypoint.sh`, секция `case` в `main()` — ровно три ветки (`app:start` / `app:init` / exec произвольной команды); коды выхода 0/1/2.
3. Идемпотентность миграций как предпосылка auto-migration — зафиксирована в ADR-0006 (Confirmation).
4. Независимость dev-чистки от инфраструктуры: `make dev-clean` = `docker compose down -v --remove-orphans` (проект корневого compose), вольюмы `gitlab_*` принадлежат инфраструктурному compose-проекту и не затрагиваются.

## Pros and Cons of the Options

### Два compose-файла (infra vs app) + entrypoint с auto-migration

Фактический стандарт кода.

* Good, because жизненный цикл сервисов разделён по частоте рестарта — главный драйвер DX
* Good, because `dev-clean` безопасен по построению (разные compose-проекты → разные вольюмы)
* Good, because infra-файл изолирует тяжёлые конфиги GitLab (omnibus) и лимиты памяти от кода приложения
* Bad, because две точки входа и внешняя сеть — порядок запуска не выражен в самих файлах
* Neutral, because entrypoint-скрипт полезен и вне этого решения (CI, prod) — не привязан к compose-схеме

### Один общий compose-файл

* Good, because одна команда `docker compose up -d` поднимает всё, порядок в `depends_on`
* Bad, because любой правкой `docker-compose.yml` разработчик рискует зацепить конфиг GitLab/Keycloak; `down -v` стирает данные GitLab вместе с dev-БД
* Bad, because рестарт одного backend-сервиса требует фильтров (`up -d backend`) или тянет за собой healthcheck-цепочку инфраструктуры с `start_period: 300s`
* Neutral, потому что внешняя сеть всё равно потребовалась бы для harbor (kind) вне compose

### Kubernetes/kind для dev

* Good, because dev-окружение ближе к целевому (если prod — k8s)
* Bad, because текущий prod-таргет — docker compose-хостинг; k8s в dev — сложность без потребителя (манифесты, ingress, storage class ради локальной разработки)
* Bad, because цикл «правка → проверка» длиннее: образы вместо bind-mount, пересборка вместо reload
* Neutral, because миграция на k8s позже возможна без изменения кода приложения (12-factor контейнеры уже)

### Dev-скрипты без compose (нативный uvicorn/vite + compose только для БД)

* Good, because минимальная задержка отклика: нет docker-прослойки для backend/frontend
* Bad, because воспроизводимость: версии Python/Node, системные пакеты (`pg_isready`, postgres-client) на хосте расходятся между машинами — часть болей, которую compose уже решил
* Bad, because `DATABASE_URL`/`VITE_API_URL` и hosts-алиасы (harbor.local → host-gateway) пришлось бы настраивать вручную на каждом хосте
* Neutral, потому что нативный запуск остаётся доступным через exec-ветку entrypoint (`docker compose run --rm backend pytest`)

## More Information

- Источники: `infrastructure/docker-compose.yml`, `docker-compose.yml`, `backend/docker/entrypoint.sh`
- ADR-0001 (backend-стек), ADR-0006 (PostgreSQL/Alembic — идемпотентность миграций), ADR-0003 (Keycloak OIDC — почему Keycloak в инфраструктуре)
- Владение: compose-структура этого ADR; `plans/development/infrastructure.md` удалён [ADR-0013](0013-opentofu-iac-keycloak-gitlab-harbor.md); make-цели (`dev-*`/`infra-*`) — за ADR-0019
- Revisit-триггеры: появление k8s как целевого prod; третий класс сервисов по частоте рестарта; переход harbor из kind в compose
