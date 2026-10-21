# Architecture Decision Records — актуальные решения

Реестр **действующих** ADR проекта BigBug. Архив отменённых решений: [ARCHIVE.md](ARCHIVE.md).

## Конвенции

- **Формат ADR**: канонический шаблон MADR 4.0 из skill `adr-skill` —
  [`.opencode/skills/adr-skill/assets/templates/adr-madr.md`](../../.opencode/skills/adr-skill/assets/templates/adr-madr.md).
  Свой шаблон не изобретать; секции, front-matter поля и статусы — только как в скилле
  (см. [`adr-conventions.md`](../../.opencode/skills/adr-skill/references/adr-conventions.md)).
- **Front-matter** (по скиллу): `status`, `date`, `decision-makers` (обязательные), `consulted`, `informed` (опциональные, RACI).
- **Статусы** (по скиллу): `proposed | accepted | rejected | deprecated | superseded by [ADR-NNNN](NNNN-slug.md)`.
- **Язык ADR**: русский; технические термины не переводить (Providers, RBAC, pipeline, webhook).
- **Каталоги компонентов**: `docs/adr/<component>/`, где component ∈ `common` | `backend` | `frontend` | `infrastructure`.
- **Сквозная нумерация** (осознанное отклонение от дефолта скилла «номера локальны в категории», принято владельцем проекта): `NNNN` едина для всех компонентов. Следующий номер = максимальный среди **всех** ADR (активные + `archive/`) + 1. Номера не переиспользуются.
- **Имя файла**: `NNNN-slug.md` (по скиллу: kebab-case, present-tense imperative), например `0007-unify-providers-registry.md`.
- **Архивация** (вместо in-place `deprecated`, по требованию проекта): при `superseded` или `rejected` файл перемещается в `docs/adr/archive/<component>/`, статус в front-matter обновляется (для superseded — со взаимной ссылкой на новый ADR в обе стороны), строка удаляется из этого реестра и добавляется в [ARCHIVE.md](ARCHIVE.md).
- **Confirmation** (опциональна по шаблону): это **доказательство**, что решение воплощено и не деградирует со временем, а не общий прогон тестов. Указывается конкретный артефакт проверки: именованный тест (файл/тест-кейс), покрывающий функционал из Decision; архитектурный тест / fitness function (например, правило, запрещающее обход слоя); правило линтера, отлавливающее нарушение в будущем; чеклист для ревью. Для исполняемой проверки — команда, запускающая **именно этот** тест (существующая make-цель + `TEST_ARGS`), и ожидаемый результат её прогона. «Запусти `make test`» подтверждением не является: непонятно, что и зачем проверяется.
- **Скрипт `scripts/new_adr.js` скилла не используется**: его нумерация локальна внутри каталога и несовместима со сквозной нумерацией и схемой архива этого репозитория. Файл создаётся вручную из канонического шаблона скилла; `set_adr_status.js` использовать можно.
- **Связь с доменами**: в `## Context and Problem Statement` и `## More Information` ссылаться на `plans/features/<домен>.md` и `plans/architecture/decisions.md`.

## Реестр актуальных ADR

### common

| ADR | Статус | Название | Дата |
|---|---|---|---|
| [ADR-0003](common/0003-keycloak-oidc-dual-auth.md) | proposed | Выбрать dual-mode аутентификацию: локальный email/password JWT + опциональный Keycloak OIDC SSO | 2026-10-21 |
| [ADR-0004](common/0004-permission-based-rbac-scope-providers.md) | proposed | Авторизация: permission-based RBAC (`resource:action`) со scope-providers | 2026-10-21 |
| [ADR-0007](common/0007-providers-v3-registry.md) | proposed | Providers V3: единая сущность `resource_providers` с реестром подтипов в коде вместо 5 инстанс-таблиц и V2 `source_providers` | 2026-10-21 |

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

### frontend

| ADR | Статус | Название | Дата |
|---|---|---|---|
| [ADR-0002](frontend/0002-frontend-stack-react-antd-rtk.md) | proposed | Выбрать frontend-стек: React 19 + TypeScript + Ant Design 6 + Redux Toolkit (RTK Query) + Vite | 2026-10-21 |
| [ADR-0015](frontend/0015-frontend-unit-testing-vitest.md) | proposed | Зафиксировать frontend unit-тестирование: Vitest + @testing-library/react + jsdom, layout `src/tests/unit/` | 2026-10-21 |

### infrastructure

| ADR | Статус | Название | Дата |
|---|---|---|---|
| [ADR-0012](infrastructure/0012-docker-compose-split-dev-env.md) | proposed | Dev environment: разделение Docker Compose на infrastructure и application, entrypoint с wait-for-DB и auto-migration | 2026-10-21 |
| [ADR-0013](infrastructure/0013-opentofu-iac-keycloak-gitlab-harbor.md) | proposed | Infrastructure as Code: OpenTofu (root + модули keycloak/harbor/gitlab) для provisioning Keycloak, GitLab, Harbor-конфигурации; Harbor runtime — в kind; init flow `init.sh` → compose → harbor → tofu → update-env | 2026-10-21 |

## Правила для агентов

1. Перед любым архитектурным изменением / новой зависимостью / новым паттерном — прочитать этот реестр и релевантные ADR со статусом `accepted` (по скиллу: accepted обязателен к исполнению, proposed — учитывать, rejected/deprecated — не наследоваться).
2. Новое решение, затрагивающее несколько компонентов, размещается в `common/`.
3. Создание ADR — через команду `/adr` (workflow skill `adr-skill`), а не вручную с нуля.
