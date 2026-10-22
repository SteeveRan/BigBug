# Architecture Decision Records — актуальные решения

Реестр **действующих** ADR проекта BigBug. Архив отменённых решений: [ARCHIVE.md](ARCHIVE.md).

## Конвенции

- **Формат ADR**: канонический шаблон MADR 4.0 из skill `adr-skill` —
  [`.opencode/skills/adr-skill/assets/templates/adr-madr.md`](../../.opencode/skills/adr-skill/assets/templates/adr-madr.md).
  Свой шаблон не изобретать; секции, front-matter поля и статусы — только как в скилле
  (см. [`adr-conventions.md`](../../.opencode/skills/adr-skill/references/adr-conventions.md)).
- **Front-matter** (по скиллу): `status`, `date`, `decision-makers` (обязательные), `consulted`, `informed` (опциональные, RACI).
- **Статусы** (по скиллу): `proposed | accepted | rejected | deprecated | superseded by ADR-NNNN` (для superseded — markdown-ссылка на заменивший ADR).
- **Язык ADR**: русский; технические термины не переводить (Providers, RBAC, pipeline, webhook).
- **Каталоги компонентов**: `docs/adr/<component>/`, где component ∈ `common` | `backend` | `frontend` | `infrastructure`.
- **Сквозная нумерация** (осознанное отклонение от дефолта скилла «номера локальны в категории», принято владельцем проекта): `NNNN` едина для всех компонентов. Следующий номер = максимальный среди **всех** ADR (активные + `archive/`) + 1. Номера не переиспользуются.
- **Имя файла**: `NNNN-slug.md` (по скиллу: kebab-case, present-tense imperative), например `0007-unify-providers-registry.md`.
- **Архивация** (вместо in-place `deprecated`, по требованию проекта): при `superseded` или `rejected` файл перемещается в `docs/adr/archive/<component>/`, статус в front-matter обновляется (для superseded — со взаимной ссылкой на новый ADR в обе стороны), строка удаляется из этого реестра и добавляется в [ARCHIVE.md](ARCHIVE.md).
- **Confirmation** (опциональна по шаблону): это **доказательство**, что решение воплощено и не деградирует со временем, а не общий прогон тестов. Указывается конкретный артефакт проверки: именованный тест (файл/тест-кейс), покрывающий функционал из Decision; архитектурный тест / fitness function (например, правило, запрещающее обход слоя); правило линтера, отлавливающее нарушение в будущем; чеклист для ревью. Для исполняемой проверки — команда, запускающая **именно этот** тест (существующая make-цель + `TEST_ARGS`), и ожидаемый результат её прогона. «Запусти `make test`» подтверждением не является: непонятно, что и зачем проверяется.
- **Скрипт `scripts/new_adr.js` скилла не используется**: его нумерация локальна внутри каталога и несовместима со сквозной нумерацией и схемой архива этого репозитория. Файл создаётся вручную из канонического шаблона скилла; `set_adr_status.js` использовать можно.
- **Связь с доменами**: в `## Context and Problem Statement` и `## More Information` ссылаться на релевантные ADR, issues и код. Доменные plans-документы удалены (roadmap: `.agents/plans/adr-roadmap.md`).

## Реестр актуальных ADR

### common

| ADR | Статус | Название | Дата |
|---|---|---|---|
| [ADR-0003](common/0003-keycloak-oidc-dual-auth.md) | proposed | Выбрать dual-mode аутентификацию: локальный email/password JWT + опциональный Keycloak OIDC SSO | 2026-10-21 |
| [ADR-0004](common/0004-permission-based-rbac-scope-providers.md) | proposed | Авторизация: permission-based RBAC (`resource:action`) со scope-providers | 2026-10-21 |
| [ADR-0007](common/0007-providers-v3-registry.md) | proposed | Providers V3: единая сущность `resource_providers` с реестром подтипов в коде вместо 5 инстанс-таблиц и V2 `source_providers` | 2026-10-21 |
| [ADR-0018](common/0018-e2e-testing-strategy.md) | proposed | E2E-стратегия: backend — pytest-suite против живого dev-стенда (CI-политика, отчёт покрытия эндпоинтов), frontend — Cypress как planned direction; удаление `docs/development/testing.md` | 2026-10-22 |
| [ADR-0019](common/0019-makefile-tooling-single-entrypoint.md) | proposed | Developer tooling: корневой Makefile — единая точка входа (тонкая обёртка, `make help`); mypy в backend, knip во frontend, vulture в backend | 2026-10-21 |
| [ADR-0024](common/0024-k8s-secrets.md) | proposed | Secrets в k8s: OpenTofu (kubernetes provider) управляет Secret'ами dev-стенда; e2e — только seeded-учётки из отдельного скрипта | 2026-10-22 |
| [ADR-0028](common/0028-security-transport-cors-jwt-ttl.md) | proposed | Модель безопасности транспорта и периметра: TLS на reverse proxy, per-provider `verify_ssl`, CORS (hardcode dev-origin'ов), JWT TTL/refresh без server-side отзыва | 2026-10-22 |

### backend

| ADR | Статус | Название | Дата |
|---|---|---|---|
| [ADR-0001](backend/0001-choose-backend-stack.md) | proposed | Выбрать backend-стек: Python 3.14 + FastAPI + SQLAlchemy 2 (async) + PostgreSQL 17 / Redis 7 | 2026-10-21 |
| [ADR-0005](backend/0005-service-layer-no-repository.md) | proposed | Сервисный слой без repository pattern: бизнес-логика в `app/services/`, доменные исключения, прямой SQLAlchemy ORM | 2026-10-21 |
| [ADR-0006](backend/0006-database-postgresql-alembic.md) | proposed | Зафиксировать database layer: PostgreSQL 17 + SQLAlchemy 2 (async) + Alembic, naming conventions, status flags, политика миграций | 2026-10-21 |
| [ADR-0008](backend/0008-git-mirroring-github-gitlab.md) | proposed | Архитектура Git Mirroring: pull-based синхронизация GitHub → GitLab с оркестрацией через GitLab CI/CD pipeline | 2026-10-21 |
| [ADR-0009](backend/0009-pull-sync-apscheduler-webhooks.md) | proposed | Фоновая синхронизация: pull-based через APScheduler с опциональными webhooks | 2026-10-21 |
| [ADR-0010](backend/0010-fernet-secrets-encryption.md) | proposed | Зашифровывать stored credentials в БД симметричным Fernet с ключом из переменной окружения `ENCRYPTION_KEY` | 2026-10-21 |
| [ADR-0011](backend/0011-gitlab-ci-pipelines-components.md) | proposed | Управлять GitLab CI/CD-интеграцией (проекты, компоненты, пресеты, пайплайны) внутри приложения | 2026-10-21 |
| [ADR-0014](backend/0014-backend-unit-testing-pytest.md) | proposed | Тестировать backend unit-уровень стеком pytest + pytest-asyncio + httpx AsyncClient (без запущенного сервера) | 2026-10-21 |
| [ADR-0016](backend/0016-backend-integration-testing.md) | proposed | Считать интеграционным уровнем backend существующий e2e-suite против живого dev-стенда — без отдельного каталога `tests/integration/` и без testcontainers | 2026-10-21 |
| [ADR-0020](backend/0020-image-builds-gold-app.md) | proposed | Image builds: домен Gold/App Images — единая таблица версий с дискриминатором, сборка через GitLab CI, APScheduler-расписания, cosign-подпись, Harbor-сканирование | 2026-10-21 |
| [ADR-0025](backend/0025-verify-incoming-webhooks-shared-secret.md) | proposed | Верифицировать входящие webhooks shared-secret токеном (`Authorization: Bearer` + `hmac.compare_digest`); текущий код endpoint'а не проверяет ничего — security gap | 2026-10-22 |
| [ADR-0026](backend/0026-audit-logging-service-call.md) | proposed | Аудит действий: явные вызовы `AuditService.log_event` (service-call, не middleware) в таблицу `audit_logs`, never-raise политика, чтение через `audit:read` | 2026-10-22 |
| [ADR-0027](backend/0027-rate-limiting-pyrate-limiter.md) | proposed | Rate limiting: pyrate-limiter с собственной FastAPI-обёрткой (обход бага fastapi-limiter), in-memory, kill-switch `RATE_LIMIT_ENABLED` | 2026-10-22 |

### frontend

| ADR | Статус | Название | Дата |
|---|---|---|---|
| [ADR-0002](frontend/0002-frontend-stack-react-antd-rtk.md) | proposed | Выбрать frontend-стек: React 19 + TypeScript + Ant Design 6 + Redux Toolkit (RTK Query) + Vite | 2026-10-21 |
| [ADR-0015](frontend/0015-frontend-unit-testing-vitest.md) | proposed | Зафиксировать frontend unit-тестирование: Vitest + @testing-library/react + jsdom, layout `src/tests/unit/` | 2026-10-21 |
| [ADR-0017](frontend/0017-frontend-integration-testing.md) | proposed | Зафиксировать frontend integration-тестирование: страницы с реальным Redux store, RTK Query-хуки в моках, jsdom, layout `src/tests/integrations/` | 2026-10-21 |
| [ADR-0021](frontend/0021-user-profile-cabinet.md) | proposed | Личный кабинет пользователя `/profile`: профиль, мои команды, мои провайдеры вместо `/settings/teams` | 2026-10-21 |

### infrastructure

| ADR | Статус | Название | Дата |
|---|---|---|---|
| [ADR-0013](infrastructure/0013-opentofu-iac-keycloak-gitlab-harbor.md) | proposed | Infrastructure as Code: OpenTofu (root + модули keycloak/harbor/gitlab) для provisioning Keycloak, GitLab, Harbor-конфигурации; Harbor runtime — в kind; init flow `init.sh` → compose → harbor → tofu → update-env | 2026-10-21 |
| [ADR-0022](infrastructure/0022-dev-stand-on-kind.md) | proposed | Dev-стенд на kind: единый кластер `bigbug-dev`, haproxy-ingress, операторы CNPG + redis-operator (инстансы — в apps-слое), keycloakx; GitLab omnibus остаётся в compose (исключение) | 2026-10-22 |
| [ADR-0023](infrastructure/0023-bigbug-helm-chart.md) | proposed | Helm chart приложения BigBug: backend + frontend, external postgres/redis (CNPG/redis-operator), hot-reload через extraMounts, миграции — helm hook Job | 2026-10-22 |
| [ADR-0029](infrastructure/0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md) | proposed | In-cluster сущности через OpenTofu: root'ы `terraform/base` (платформа: ingress + только операторы CNPG/redis-operator, one-shot без внешних значений — на preprod как есть) и `terraform/apps` (инстансы сервисов + k8s-секреты приложения); кластер и hosts — императивно; 3 изолированных state'а, оркестрация init.sh | 2026-10-22 |

## Правила для агентов

1. Перед любым архитектурным изменением / новой зависимостью / новым паттерном — прочитать этот реестр и релевантные ADR со статусом `accepted` (по скиллу: accepted обязателен к исполнению, proposed — учитывать, rejected/deprecated — не наследоваться).
2. Новое решение, затрагивающее несколько компонентов, размещается в `common/`.
3. Создание ADR — через команду `/adr` (workflow skill `adr-skill`), а не вручную с нуля.
