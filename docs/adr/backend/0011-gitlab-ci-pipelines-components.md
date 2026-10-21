---
status: proposed
date: 2026-10-21
decision-makers: SteeveRan
---

# Управлять GitLab CI/CD-интеграцией (проекты, компоненты, пресеты, пайплайны) внутри приложения

## Context and Problem Statement

Где должно жить управление GitLab CI/CD-сущностями — проектами, компонентами и пайплайнами — в инфраструктурном provisioning-слое (bash-скрипты + OpenTofu) или в самом приложении BigBug через его API?

Домен прошёл три итерации, зафиксированные в spec-документах (удалены вместе с этим ADR, история — в `More Information`):

1. **Provisioning-спека** (2026-08-17): GitLab CI/CD Components создаются вне приложения — bash-скриптом `provision-gitlab.sh` (GitLab REST API + `docker exec gitlab-runner register`) или OpenTofu-модулем; шаблоны компонентов — YAML-файлы в `infrastructure/gitlab-components/`.
2. **docker-import-fix-спека** (2026-08-17): починка импорта Docker Hub → Harbor через CI-компонент (разделение source/target провайдеров, нормализация repository path, OCI token handshake, зеркало через `crane`) — на тот момент ещё поверх provisioning-подхода.
3. **Project-management-спека** (2026-08-20): замена provisioning-подхода на управление через приложение — сущность `GitlabProject`, python-gitlab, пресеты в коде.

Решение не было зафиксировано как ADR; три спеки и гайд `plans/features/pipelines.md` были единственными источниками. Вопрос финализирован: **финальная архитектура — вариант 3, промежуточные подходы отклонены и документируются здесь**.

Зависимость: ADR-0007 «Providers V3 — unified resource_providers registry» (в работе, [issue #8](https://github.com/SteeveRan/BigBug/issues/8)) — все GitLab-подключения являются git-провайдерами реестра `resource_providers`; триггер пайплайнов диспетчеризуется через capabilities провайдеров.

## Decision Drivers

- BigBug — centralized DevOps-платформа: создание CI-сущностей не должно требовать shell-доступа к хосту, root PAT в env и знания двух параллельных provisioning-путей.
- Multi-tenancy: пользователь должен вести свои проекты компонентов и пайплайнов через **свой** git-провайдер (private), а не только через платформенный system GitLab.
- GitLab Components резолвятся по `$CI_SERVER_FQDN` — проект пайплайна и включаемый проект компонентов обязаны быть на одном GitLab-хосте; это ограничение платформы, которое надо валидировать, а не обходить.
- Секреты (registry credentials) — только через encrypted credentials провайдеров в runtime-переменных пайплайна; не в файлах репозитория, не в argv.
- Минимализм зависимостей: Terraform/баш в provisioning-пути — это вторая система state, конфликтующая с приложением.
- Сквозная нумерация ADR и зависимость от Providers V3 (ADR-0007, issue #8).

## Considered Options

* Infrastructure provisioning: bash-скрипт `provision-gitlab.sh` + OpenTofu-модуль gitlab (provisioning-спека)
* Управление через приложение: сущность `GitlabProject` + python-gitlab + in-code пресеты (project-management-спека)
* Жёстко один платформенный GitLab без сущности «проект» (status quo до V3)

## Decision Outcome

Chosen option: **«Управление через приложение: сущность `GitlabProject` + python-gitlab + in-code пресеты»** — потому что это единственный вариант, дающий multi-tenancy, управление через UI/API без shell-доступа и один источник state (БД приложения). Инфраструктурный provisioning отклонён (обоснование — в Pros and Cons); status quo без сущности «проект» не выражал сценарий «пользователь через своего git-провайдера».

Финальная архитектура (проверена по коду 2026-10-21):

### Сущность GitlabProject

`backend/app/models/gitlab_project.py` — единая таблица `gitlab_projects` с типом `GitlabProjectType` (`components` | `pipelines`); тип отличается семантикой использования и RBAC-гейтами, структура идентична. Поля: `full_path` (уникален в рамках провайдера), `provider_id → resource_providers.id` (RESTRICT — удаление провайдера с проектами блокируется), `owner_user_id`/`team_id`, `visibility` (owner/team/public — копия провайдерной модели), soft delete, статус-флаги 0–4. Сервис — `backend/app/services/gitlab_projects/` (`_service.py` CRUD/доступ, `_files.py` файлы/теги, `_clients.py` фабрика python-gitlab).

Компоненты и конфигурации пайплайнов «живут» в проектах: `gitlab_components.gitlab_project_id` и `pipelines.gitlab_project_id` — FK с `SET NULL` (legacy-строки с NULL работают как раньше); `provider_id` рана вычисляется из проекта.

### Пресеты компонентов — in-code

Библиотека шаблонов вшита в код: `backend/app/services/gitlab_projects/presets.py` — 6 пресетов (`docker_hub_to_harbor`, `gold_image`, `app_image`, `mirror`, `docker_sync`, `helm_sync`) как константы. Отдаются через `GET /api/components/presets` (без вызова GitLab). Рантайм никогда не читает файлы с диска; исходные YAML сохранены только как примеры в `infrastructure/gitlab-components/examples/` (приложением не используются).

### Управление содержимым через GitLab API

Все мутации — через python-gitlab (`Repository Files API`, `Tags API`): create/update/delete файлов (идемпотентно, check-by-content), теги версий компонентов. Правило версионирования: опубликованный тег не двигается — новая версия = новый тег; повторное создание существующего тега → 409.

`.gitlab-ci.yml` для проектов пайплайнов **генерируется сервером** (`backend/app/services/pipeline/_ci.py`): include-строки `component: $CI_SERVER_FQDN/<project-path>/<component-path>@<version>`, в `inputs` — только required-поля; значения опциональных inputs приживляются backend-ом как pipeline variables при триггере (контракт шаблонов — bare `$var`, runtime). Валидация same-host: include с другого GitLab-хоста → 422.

### Триггер пайплайнов и связь с Providers V3

- Ран пайплайна использует **провайдер своего gitlab-проекта** (`trigger_pipeline_by_config`), а не legacy `provider_id` конфигурации; провайдер рана = провайдер проекта.
- Ограничение «только system/internal GitLab» на уровне сервиса триггера **снято**: `_get_pipeline_provider_or_404` допускает любой живой `subtype=gitlab` провайдер; доступ определяется владением проектом в сервисном слое.
- При этом capability `trigger_pipeline` в реестре провайдеров (`CAPABILITY_RESTRICTIONS` в `backend/app/services/providers/registry.py`) остаётся ограниченной парой `(system, internal)` — это ограничение advertised capability при dispatch через общий провайдерный механизм, а не гейт сервисного пути триггера.

### RBAC

8 permissions (сидятся миграцией `20260820_0003_..._seed_gitlab_project_permissions.py`, задекларированы в `backend/docker/seed_admin.py`): `gitlab_projects:read/write/delete/read_all`, `components:read/write/delete/push`. Разделение «владелец компонентов» vs «владелец пайплайнов»: мутация проекта дополнительно требует право типа (`components:push` для components-проектов, `pipelines:write` для pipelines-проектов); владение строкой — owner/team/`read_all`; гранулярно — scope-таблица `role_scope_gitlab_projects` (`require_scope_permission(permission, "gitlab_project")`). Существующие `pipelines:read/write/delete` сохранены для конфигураций и ранов; отдельный `pipelines:trigger` не вводился (триггер = `pipelines:write`).

### Docker-импорт (Docker Hub → Harbor)

Финальное состояние из docker-import-fix-спеки, работающее поверх этой архитектуры:

- Разделение source/target: `get_internal_docker_targets()` (`backend/app/services/docker.py`) отдаёт internal-провайдеры `harbor`/`generic_registry` как mirror-цели; system Harbor сидится `backend/scripts/seed_providers.py` из env (`HARBOR_URL` и др., секрет — Fernet через `app.core.secrets`).
- Нормализация `repository_path_from_ref()` (host/тег/digest отрезаются, Docker Hub → префикс `library/`) — единая для tags/manifest/mirror/source-импорта.
- OCI/Docker Hub token handshake — `backend/app/services/providers/clients/docker_auth.py` (`oci_request`: 401 + `WWW-Authenticate: Bearer` → fetch token → ровно один retry; кэш per-(service, scope) TTL 300s).
- Зеркалирование — `crane copy` (subprocess), секреты в 0600 `DOCKER_CONFIG/config.json` (не argv), `--insecure` при `verify_ssl=False`.

Webhook-контур: `POST /api/webhooks/gitlab` (`backend/app/api/webhooks.py`) принимает pipeline-события и обновляет `PipelineRun.status_flag` (unified 0–4). Пресеты шлют события в BigBug через `BIGBUG_API_URL`/`BIGBUG_WEBHOOK_TOKEN`. Runner-регистрация остаётся инфраструктурной (docker-compose, instance-level ресурс) — из приложения только документация.

### Consequences

* Good, because весь жизненный цикл CI-сущностей (создать проект → залить компонент → тег → сгенерировать `.gitlab-ci.yml` → триггер → webhook-статус) доступен через UI/API, включая сценарии личных git-провайдеров
* Good, because один источник state (БД); нет конфликта «скрипт ↔ tofu ↔ приложение» и import-runbook'ов
* Good, because пресеты в коде версионируются вместе с приложением и не требуют чтения диска в рантайме
* Bad, because python-gitlab-мутации синхронны в HTTP-запросе — долгие операции заливки файлов держат соединение (потолок осознан; при росте — асинхронные задачи)
* Bad, because `CAPABILITY_RESTRICTIONS` для `trigger_pipeline` и сервисный слой триггера расходятся: реестр рекламирует capability только system/internal, тогда как раны через проект допускают любой живой gitlab-провайдер — при расширении dispatch-пути ограничение надо пересмотреть отдельным решением
* Neutral, because runner остаётся инфраструктурным ресурсом — компромисс: ранняя регистрация через приложение не нужна
* Non-goals: кросс-хостовое переиспользование компонентов (fan-out на несколько GitLab); автоматическое создание namespace/групп из приложения (v1 — только существующие); runner-CRUD через API; миграция «заливающих» скриптов в другие домены

### Confirmation

- Пресеты in-code, а не с диска: `make test-unit-backend TEST_ARGS="-k test_list_presets_returns_six"` (`backend/tests/unit/test_gitlab_project_service.py`) — проверяет 6 пресетов из `presets.py` через `list_presets()`.
- Генерация `.gitlab-ci.yml` и same-host: `make test-unit-backend TEST_ARGS="tests/unit/test_pipeline_ci_generator.py"` — include-строки, stages union, host-mismatch → 422.
- Снятое ограничение провайдера триггера: `make test-unit-backend TEST_ARGS="-k test_list_presets"` недоступен — используется `backend/tests/unit/test_pipeline_service.py` (тест «restriction lifted by gitlab-project-management»: любой живой gitlab-провайдер проходит `_get_pipeline_provider_or_404`).
- Docker-import flow: `make test-e2e-backend TEST_ARGS="tests/e2e/test_docker_import_flow.py"` (GitLab мокается; без dev-стека skip).
- Fitness-критерий архитектуры: в репозитории нет `infrastructure/provision-gitlab.sh` и Makefile-цели `infra-provision-gitlab`; греп `grep -rn "provision-gitlab" Makefile infrastructure/` пуст — provisioning-путь не вернулся.

## Pros and Cons of the Options

### Infrastructure provisioning: bash-скрипт + OpenTofu

GitLab-проект `bigbug-mirrors/components` и файлы компонентов создаются вне приложения: скрипт через REST API + `docker exec`, или `tofu apply` с `gitlab_project`/`gitlab_repository_file`/`null_resource local-exec`. Один источник содержимого — YAML-файлы репозитория.

* Good, because IaC-декларативность и воспроизводимость стенда из чистого состояния
* Bad, because создание CI-сущностей требует shell-доступа и root PAT — профиль доступа не соответствует продукту
* Bad, because одноразовость: один захардкоженный проект; второй проект/другой пользователь/другой GitLab — вне модели, multi-tenancy не выражается
* Bad, because `tofu init` блокируется гео-фильтром Cloudflare (403 на `registry.opentofu.org`) — потребовал filesystem-mirror костыль; `null_resource + local-exec` — «тот же bash, только хуже», без идемпотентности и со state-дрейфом
* Bad, because два параллельных пути к одному state конфликтуют (import-runbook) и версионирование компонентов = коммит в репозиторий платформы + перезапуск скрипта
* **Rejected**: заменён вариантом «через приложение»; runner-механика (docker-exec-регистрация) осталась в инфраструктуре как единственный рациональный остаток

### Управление через приложение: GitlabProject + python-gitlab + in-code пресеты — chosen

Описано в Decision Outcome.

* Good, because multi-tenancy и делегирование прав копированием провайдерной модели (owner/team/public + scope), без новых механизмов
* Good, because контракты (идемпотентная заливка файлов, правило тегов, same-host валидация) исполняются сервисом, а не чеклистом скрипта
* Bad, because синхронные мутации через HTTP; при тяжёлых заливках понадобится фоновая очередь
* Bad, because пресеты вшиты в код — изменение шаблона = релиз приложения (принято: шаблоны зрелые, меняются редко)

### Жёстко один платформенный GitLab без сущности «проект» (status quo до V3)

Приложение хранит только «регистрацию ссылки» (`GitLabComponent` без содержимого и проекта), триггерит пайплайны, всё остальное — руками в GitLab/инфраструктуре.

* Good, because нулевая стоимость реализации
* Bad, because нет ни multi-tenancy, ни управления содержимым; UI сводится к кнопке «Run»
* **Rejected**: противоречит продукту (centralized DevOps-платформа)

## More Information

**Эволюция решения** (хронология трёх spec-документов, удалённых вместе с этим ADR):

1. `plans/gitlab-components-provisioning-spec.md` (2026-08-17) — исходное архитектурное решение: два независимых provisioning-пути (bash fast-path / OpenTofu) к одному state, единый источник шаблонов на диске. Зафиксировала полезные root-cause'ы, пережившие подход: `@1.0.0` компонента резолвится только через git-тег; контракт «шаблон читает shell-переменные, значения приходят pipeline variables»; job-контейнерам нужны `extra_hosts: host-gateway` для резолва `gitlab.local`/`harbor.local`; registration-token flow + fallback на authentication token. **Подход отклонён** project-management-спекой.
2. `plans/docker-import-fix-spec.md` (2026-08-17) — параллельная починка импорта Docker Hub → Harbor (5 дефектов: source/target разделение, repository path vs canonical ref, OCI token handshake, crane как зеркало вместо самописного OCI-copy, frontend). Реализована и живёт в текущей архитектуре (см. Decision Outcome); спека удалена — решения зафиксированы здесь.
3. `plans/gitlab-project-management-spec.md` (2026-08-20) — финальный подход, заменивший provisioning: сущность `GitlabProject`, RBAC, генерация `.gitlab-ci.yml`, пресеты in-code. Инфраструктурная чистка выполнена: `provision-gitlab.sh`, Makefile-цель и provisioning-переменные удалены; Terraform-ресурсы проектов не потребовались (модуль gitlab содержит только базовую настройку). Спека удалена — является первоисточником этого ADR.
4. `plans/features/pipelines.md` — гайд по реализованным эндпоинтам; заменён этим ADR + автогенерируемым `http://localhost:8000/docs` (Swagger UI).

Связанные материалы:

- ADR-0007 (Providers V3, issue #8) — провайдеры и capabilities; `CAPABILITY_RESTRICTIONS`
- Индекс прав: `plans/architecture/permissions.md` (секция gitlab-project-management прав)
- Конвенции API/статусов: `AGENTS.md`; миграции: `plans/development/database.md`
- Примеры шаблонов (не используются приложением): `infrastructure/gitlab-components/examples/`

Условие пересмотра: если появится сценарий кросс-хостового fan-out компонентов, потребуется пересмотр same-host правила; если раны пойдут через dispatch-механизм провайдеров — пересмотр `CAPABILITY_RESTRICTIONS` для `trigger_pipeline`.
