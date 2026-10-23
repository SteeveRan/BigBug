---
status: proposed
date: 2026-10-21
decision-makers: SteeveRan
---

# Image builds: домен Gold и App Images — версионирование, CI-сборка, расписания, подпись и сканирование

## Context and Problem Statement

Как устроен домен сборки Docker-образов в BigBug: два типа образов (Gold — базовые OS/runtime, App — приложения), их версии, механизм сборки через GitLab CI, расписания сборок, подпись cosign и сканирование Harbor? Домен полностью реализован в коде, но был задокументирован только гайдом `plans/features/builds.md` (удалён вместе с этим ADR) — без фиксации решений: почему единая таблица версий с дискриминатором, почему сборка триггерится через platform GitLab, почему подпись через subprocess cosign, а сканирование через Harbor API.

Решение фиксирует **финальную архитектуру домена**, проверенную по коду 2026-10-21.

Зависимости:

- [ADR-0011](0011-gitlab-ci-pipelines-components.md) — сборки образа запускают GitLab CI пайплайны; CI-шаблоны `gold_image` и `app_image` — in-code пресеты из `backend/app/services/gitlab_projects/presets.py`
- [ADR-0007](../common/0007-providers-v3-registry.md) — GitLab-подключение резолвится из `resource_providers` (subtype=gitlab, category=system, direction=internal)
- [ADR-0006](0006-database-postgresql-alembic.md) — naming conventions, unified status flags 0–4

## Decision Drivers

- Два типа образов семантически различны (base vs application), но жизненный цикл версий, сборок, подписи и сканирования идентичен — дублирование таблиц нежелательно.
- Сборка — внешняя работа (GitLab Runner), BigBug только оркестрирует: триггер → webhook → статус. Сборка не выполняется внутри backend.
- Статусы версий/сборок должны следовать unified scheme 0–4 (0=ok, 1=failed, 2=warn, 3=in_progress, 4=pending) по всему проекту.
- Расписания: системный cron по умолчанию, но пользователь может переопределить per-image; выключение per-image не должно требовать правки инфраструктуры.
- Подпись cosign и сканирование Harbor — опциональные пост-этапы над версией, не блокирующие сборку.
- Секреты (cosign private key, registry credentials) не должны храниться в БД версий.

## Considered Options

* Единая таблица `image_versions` + `build_logs` с дискриминатором `image_type` (gold/app), отдельные таблицы-родители `gold_images` / `app_images`
* Две пары таблиц (gold_versions/app_versions, gold_build_logs/app_build_logs) — полное дублирование схемы
* Сборка внутри backend (self-hosted docker build из API-процесса)
* Сборка через GitLab CI (chosen)

## Decision Outcome

Chosen option: **«Единая таблица версий с дискриминатором + сборка через GitLab CI»** — потому что жизненный цикл версии идентичен для обоих типов, а вынесение сборки в CI убирает docker-зависимость из backend и переиспользует существующую pipeline-инфраструктуру.

Финальная архитектура (проверена по коду 2026-10-21):

### Модель домена: два родителя, одна таблица версий

- **Родители**: `GoldImage` (`backend/app/models/gold_image.py`, таблица `gold_images` — базовые OS/runtime-образы, `name` уникален, `os_family`, inline `dockerfile`, опциональная привязка `gitlab_project_id`) и `AppImage` (`backend/app/models/app_image.py`, таблица `app_images` — образы приложений, опциональные FK `project_id → github_projects.id` (SET NULL, исходники из GitHub) и `gold_image_id → gold_images.id` (SET NULL, базовый образ)).
- **Версии**: `ImageVersion` (`backend/app/models/image_version.py`, таблица `image_versions`) — единая таблица для обоих типов. Дискриминатор `image_type` (`gold` | `app`); ровно один из FK (`gold_image_id` / `app_image_id`) установлен, другой NULL, `ondelete=CASCADE`. Поля версии: `version_tag` + `arch` (`amd64` | `arm64` | `arm/v7`, default `amd64`), `registry_url`, `sha256_digest`, cosign-поля (`is_signed`, `cosign_signature`), scan-поля (`vulnerabilities`, `vulnerability_severity` — worst severity: `none/negligible/low/medium/high/critical`), `built_at`, unified `status_flag`/`status_text` (default 4=pending).
- **Логи сборок**: `BuildLog` (`backend/app/models/build_log.py`, таблица `build_logs`) — FK `image_version_id` (CASCADE), `pipeline_id`/`pipeline_url`, статус 0–4, `log_output`, `triggered_by` (`scheduler` | `manual` | `webhook`), `started_at`/`finished_at`.
- **Расписания**: `BuildSchedule` (`backend/app/models/build_schedule.py`, таблица `build_schedules`) — та же схема «дискриминатор + один из двух FK». Приоритет конфигурации: `is_enabled=False` → не запускать; `use_default_schedule=True` → системный cron `settings.default_build_cron` (default `0 3 * * 0`); иначе — `cron_expression`. При создании Gold/App Image через API расписание создаётся автоматически (enabled + default).

Два родителя вместо одной polymorphic-таблицы осознанно: у типов разные специфичные поля (`os_family` у gold; `project_id`/`gold_image_id` у app) и разные RBAC-пермишены, при этом «версионная» часть вынесена в общую таблицу без дублирования.

### Сборка через GitLab CI

`BuildService` (`backend/app/services/build.py`):

- Триггер требует настроенного `image.gitlab_project_id` — иначе `BadRequestError`. Референс пайплайна жёстко `main`.
- GitLab-клиент строится от **platform GitLab-провайдера** из `resource_providers` (`get_default_gitlab_provider`: subtype=gitlab, category=system, direction=internal), токен — decrypted credential через `app.core.secrets`; fallback на `settings.gitlab_url`/`settings.gitlab_token` для обратной совместимости.
- Flow триггера: создать `ImageVersion` (status 4=pending) → `flush` → `pipelines.create(ref="main", variables=[VERSION_TAG, TARGET_ARCH, IMAGE_VERSION_ID])` → при `GitlabError` версия помечается status 1 и бросается `ExternalServiceError("GitLab", …)` → при успехе версия → 3=running, создаётся `BuildLog` (status 3, `pipeline_id`, `pipeline_url`, `started_at`).
- Pipeline variables передают `IMAGE_VERSION_ID` — CI-джоба затем подписывается/нотифицирует BigBug webhook'ом, замыкая статус по `pipeline_id`.

CI-шаблоны — in-code пресеты `gold_image` и `app_image` из [ADR-0011](0011-gitlab-ci-pipelines-components.md) (`presets.py`): multi-arch buildx build, push в registry, stage `sign` (cosign при наличии `COSIGN_PRIVATE_KEY`), stage `notify` (webhook в BigBug через `BIGBUG_API_URL`/`BIGBUG_WEBHOOK_TOKEN`). App-пресет дополнительно имеет stage `prepare` — валидация доступности базового gold-образа (`GOLD_IMAGE_REF`) перед сборкой.

### Статусы: замыкание через webhook

`POST /api/webhooks/gitlab` (`backend/app/api/webhooks.py`) принимает pipeline-события, находит `BuildLog` по `pipeline_id`, маппит GitLab-статус в unified 0–4 (`success→0`, `failed/canceled→1`, `running→3`, остальное→4) и каскадно обновляет родительскую `ImageVersion` (при `success` — проставляет `built_at`). `log_output` в `BuildLog` остаётся пустым, если CI-шаблон не шлёт его отдельно — источник правды по логам это `pipeline_url` в GitLab.

### Расписания: APScheduler

`SchedulerService` (`backend/app/services/scheduler.py`) — один in-process `AsyncIOScheduler` (запускается в lifespan `main.py`) с job-ами `sync_all`, `build_all` (cron из `settings.default_build_cron`), `cleanup`. Job `build_all` каждое срабатывание сканирует все `BuildSchedule.is_enabled=True` и для каждого проверяет `next_run_at > now` — per-image cron фактически эмулируется проверкой `next_run_at` на общем тике, а не отдельным APScheduler-job на расписание.

Ограничение (осознанное): планировщик триггерит сборку с фиксированными `version_tag="latest"`, `arch="amd64"` — параметризованные scheduled-сборки (версия из git tag, matrix arch) не реализованы; при появлении сценария — расширение `BuildSchedule` отдельным решением.

### Подпись: cosign через subprocess

`CosignService` (`backend/app/services/cosign.py`) — CLI cosign как subprocess (`cosign sign --key env://COSIGN_KEY --yes <ref>` / `cosign verify --key env://COSIGN_PUB_KEY <ref>`), ключ передаётся через env процесса, не в argv и не на диск. При успехе `sign_image` обновляет `ImageVersion.is_signed=True`, `cosign_signature=<ref>`. Dev-fallback: cosign CLI не установлен → `is_signed=True` с пометкой `simulated:<ref>` (только для dev-стенда, не production-поведение). Требования: cosign предустановлен в backend Docker-образе.

`cosign_private_key` приходит в теле запроса `POST …/sign` и не сохраняется в БД (никаких stored key material в `image_versions`).

### Сканирование: Harbor API, pull-модель

`HarborScanService` (`backend/app/services/harbor_scan.py`) работает поверх Harbor `ResourceProvider` (domain=docker, subtype=harbor):

- Trigger: `POST /api/v2.0/projects/{p}/repositories/{r}/artifacts/{digest}/scan` → версия → 3=Scanning.
- Results: `GET …/artifacts/{digest}?with_scan_overview=true` → парсинг `scan_overview` (MIME `application/vnd.security.vulnerability.report; version=1.1`) → нормализация ключей (`Critical→critical`), total count + worst severity (`_worst_severity`, ранжирование `none=0 … critical=5`) → запись в `ImageVersion.vulnerabilities` / `vulnerability_severity`, версия → 0=ok.
- Нет scan-данных → версия → 1, severity=`unknown`.
- Клиент — httpx с basic-auth из decrypted credential провайдера, `verify=provider.verify_ssl`.

Сканирование pull-based (BigBug опрашивает Harbor), в отличие от статуса сборки (push-based webhook из GitLab). Причина: Harbor не шлёт webhook по scan-событиям в используемой конфигурации, а результаты нужны on-demand (кнопка «Get results» в UI), а не в реальном времени.

### RBAC

8 permissions (сидируются в `20260816_1200_…_seed_initial_data` и `backend/bin/seed_admin.py`): `gold_images:read/write/delete/build` и `app_images:read/write/delete/build`. Разделение: `write` — CRUD/schedule/sign/scan-trigger, `build` — триггер сборки, `read` — просмотр и scan-results. Все эндпоинты — `require_permission(...)` (`backend/app/api/gold_images.py`, `backend/app/api/app_images.py`).

### Consequences

* Good, because единая таблица версий исключает дублирование: любые будущие возможности (retention, digest-сравнение, mirror) реализуются один раз для обоих типов
* Good, because backend не выполняет docker build — только оркестрация; нет docker socket / dind внутри API-контейнера
* Good, because статусы следуют unified 0–4, webhook-контур переиспользуется всеми доменами (builds, mirrors, helm sync, pipelines)
* Bad, because `BuildService.trigger_gold_build` и `trigger_app_build` — практически идентичные методы, различающиеся только `image_type` и FK; при добавлении поля в flow — правка в двух местах (принято: методов два, а не generic-метод с union-типом)
* Bad, because scheduled-сборки захардкожены на `latest`/`amd64` — расписание без параметризации ограничено
* Bad, because per-image cron эмулируется проверкой `next_run_at` на общем тике — точность срабатывания равна периоду `default_build_cron`, а не минутному тику
* Bad, because cosign dev-fallback (`simulated`) может маскировать отсутствие CLI в production при невнимательном деплое
* Neutral, because `log_output` в `BuildLog` обычно пуст — детальные логи в GitLab; поле оставлено для CI-шаблонов, шлющих логи webhook'ом
* Non-goals: мультиархитектурные scheduled-матрицы (buildx manifest list как отдельная версия на arch — поддержано моделью, но не планировщиком); signature storage в отдельном sigstore/OCI-реестре (хранится только reference); автоматический re-scan по расписанию; интеграция с системами policy-as-code (Kyverno, Connaisseur).

### Confirmation

- Модель версий/дискриминатор: `make test-unit-backend TEST_ARGS="tests/unit/test_image_models.py"` — если файл отсутствует, фактическое покрытие: `make test-e2e-backend TEST_ARGS="tests/e2e/test_images.py"` (CRUD gold/app images + versions, GitLab мокается; без dev-стека skip).
- Cosign: `make test-unit-backend TEST_ARGS="tests/unit/test_cosign_service.py"` — sign/verify, отсутствие CLI → simulated.
- Harbor scan: `make test-unit-backend TEST_ARGS="tests/unit/test_harbor_scan_service.py"` — парсинг scan_overview, worst severity, no-data → failed.
- Webhook-замыкание статуса: `make test-e2e-backend TEST_ARGS="tests/e2e/test_webhooks.py"`.
- Fitness-критерий: сборка не выполняется в backend — греп `grep -rn "docker.*build\|subprocess" backend/app/services/build.py` не находит docker-команд (только python-gitlab триггер); cosign subprocess — только в `cosign.py`.

## Pros and Cons of the Options

### Единая таблица версий + GitLab CI — chosen

Описано в Decision Outcome.

* Good, because нет дублирования схемы версий/логов/расписаний на два типа
* Good, because переиспользование pipeline-инфраструктуры и webhook-контура [ADR-0011](0011-gitlab-ci-pipelines-components.md)
* Bad, because nullable FK-пара (`gold_image_id`/`app_image_id`) — инвариант «ровно один установлен» держится кодом, не constraint'ом БД
* Bad, because scheduled-сборки упрощены (latest/amd64)

### Две пары таблиц (gold_versions / app_versions, …)

Полное дублирование: два набора `image_versions`/`build_logs`/`build_schedules`.

* Good, because строгая типизация на уровне БД, нет дискриминатора
* Bad, because каждая фича (подпись, сканирование, retention) реализуется и тестируется дважды
* Bad, because сравнение/миграция между gold и app версиями (App build от Gold) требует UNION-запросов
* **Rejected**: дублирование не оправдано — специфичные поля типов живут в таблицах-родителях

### Сборка внутри backend (docker build в API-процессе)

BigBug сам выполняет `docker build` из HTTP-хендлера или фоновой задачи.

* Good, because нет зависимости от GitLab CI и runner'ов
* Bad, because docker socket / dind в API-контейнере — разрастание attack surface и ресурсный конфликт с веб-нагрузкой
* Bad, because теряется аудит и логи пайплайнов, retry-механика GitLab, кэши слоёв
* Bad, because дублирует CI-шаблоны пресетов, которые уже стандартизуют сборку
* **Rejected**: противоречит принципу «backend — оркестратор», ломает переиспользование [ADR-0011](0011-gitlab-ci-pipelines-components.md)

## More Information

Домен задокументирован гайдом `plans/features/builds.md` (удалён вместе с этим ADR — содержимое было частично устаревшим: описывал sync-flow с `source_registry`/`target_registry` полями, которых в текущих моделях нет, и standalone gitlab-ci шаблоны, заменённые in-code пресетами).

Связанные материалы:

- [ADR-0011](0011-gitlab-ci-pipelines-components.md) — GitLab CI интеграция: пресеты `gold_image`/`app_image`, webhook-контур, RBAC пайплайнов
- [ADR-0007](../common/0007-providers-v3-registry.md) — `resource_providers`: platform GitLab (build trigger) и Harbor (scan) — оба провайдеры реестра
- [ADR-0006](0006-database-postgresql-alembic.md) — статус-флаги 0–4, naming conventions
- [ADR-0010](0010-fernet-secrets-encryption.md) — шифрование stored credentials (GitLab токен, Harbor basic-auth); cosign private key в БД не хранится
- Индекс прав: `docs/development/permissions.md`
- API reference: автогенерируемый `http://localhost:8000/docs` (Swagger UI), теги `gold-images`, `app-images`

Условие пересмотра: появление сценария параметризованных scheduled-сборок (version from git tag, arch matrix) — расширение `BuildSchedule`; перенос подписи в CI-stage-only (убрать API-эндпоинт sign) — при стандартизации ключей; Harbor webhook'и для scan-событий — при переходе на push-модель сканирования.
