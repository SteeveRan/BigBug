# BigBug — System Design Documentation

## Обзор

Комплексная архитектурная документация для **BigBug** — платформы управления Docker образами (Gold, App), Helm чартами, Git зеркалированием и CI/CD пайплайнами.

**Стек:** FastAPI + SQLAlchemy 2.x async + PostgreSQL 17 + Redis 7 + React 18 + MUI

---

## Структура документации

```
docs/architecture/
├── README.md                          ← Этот файл (индекс)
├── 01-executive-summary.md            ← Обзор и ключевые решения
├── 02-rbac-design.md                  ← RBAC: роли, permissions, схема БД
├── 03-authentication.md               ← Local auth + OIDC/Keycloak
├── 04-integrations/
│   ├── gitlab.md                      ← GitLab API v4
│   ├── harbor.md                      ← Harbor API v2.0
│   ├── github.md                      ← GitHub API v3
│   ├── docker-registry.md             ← Docker Registry API v2
│   └── helm-repository.md             ← Helm Repository / ChartMuseum
├── 05-database-schema.md              ← Полная схема БД + DDL
├── 06-api-design.md                   ← REST API endpoints
├── 07-service-layer.md                ← Архитектура сервисов
├── 08-pipelines.md                    ← GitLab Pipelines & Components
├── 09-ui-structure.md                 ← UI навигация и компоненты
├── 10-security.md                     ← Безопасность и шифрование
└── 11-migration-strategy.md           ← План миграции по фазам
```

---

## Быстрый навигатор

### [1. Executive Summary](./01-executive-summary.md)
Краткий обзор системы, текущее vs целевое состояние, ключевые архитектурные решения, технологический стек, риски.

### [2. RBAC Design](./02-rbac-design.md)
- **30+ permissions** в формате `resource:action`
- Роли: **Admin / Operator / Viewer / Custom**
- Таблицы: `permissions`, `role_permissions`, расширение `roles` и `users`
- FastAPI `require_permission()` dependency
- Mermaid ER-диаграмма и sequence diagram

### [3. Authentication](./03-authentication.md)
- **Local auth**: email/password → bcrypt → JWT
- **OIDC**: Authorization Code + PKCE → Keycloak → role sync
- Стратегия мерджа пользователей: `keycloak_sub` → email → create
- Таблица `oidc_config` для хранения настроек
- Mermaid flow диаграммы для обоих методов

### [4. Integrations Research](./04-integrations/)

| Интеграция | Файл | Auth | Ключевые возможности |
|------------|------|------|----------------------|
| [GitLab](./04-integrations/gitlab.md) | `gitlab.md` | PAT | Groups, Projects, Pipelines, Variables, Webhooks, Components |
| [Harbor](./04-integrations/harbor.md) | `harbor.md` | Robot Account | Projects, Repositories, Artifacts, Replication, Scanning |
| [GitHub](./04-integrations/github.md) | `github.md` | PAT | Orgs, Repos, Releases, Webhooks |
| [Docker Registry](./04-integrations/docker-registry.md) | `docker-registry.md` | Bearer Token | Catalog, Tags, Manifests |
| [Helm Repository](./04-integrations/helm-repository.md) | `helm-repository.md` | Basic/None | index.yaml, ChartMuseum API |

### [5. Database Schema](./05-database-schema.md)
- Полная Mermaid ER-диаграмма всех сущностей
- DDL для всех новых таблиц с индексами
- Таблицы: `permissions`, `role_permissions`, `oidc_config`, `gitlab_instances`, `harbor_instances`, `github_integrations`, `docker_registry_integrations`, `helm_repository_integrations`
- Миграционная стратегия (3 фазы)

### [6. API Design](./06-api-design.md)
- **Auth**: `/api/v1/auth/*` — login, logout, me, OIDC callback
- **Users**: `/api/v1/admin/users/*` — CRUD
- **Roles**: `/api/v1/admin/roles/*` — CRUD
- **Integrations**: `/api/v1/admin/integrations/{gitlab,harbor,github,docker-registry,helm-repository}/*`
- **OIDC Config**: `/api/v1/admin/auth/oidc/*`
- **Pipelines**: `/api/v1/pipelines/*`
- **Builds**: `/api/v1/builds/{gold-images,app-images}/*`
- **Mirroring**: `/api/v1/mirroring/*`
- **Webhooks**: `/api/v1/webhooks/{gitlab,harbor,github}`

### [7. Service Layer](./07-service-layer.md)
- Компонентная диаграмма всех сервисов
- Описание каждого сервиса с сигнатурами методов
- Паттерны: Dependency Injection, Error Handling, Credential Encryption, Logging
- Sequence diagram взаимодействия сервисов

| Сервис | Статус | Файл |
|--------|--------|------|
| `AuthService` | Новый | `services/auth.py` |
| `UserService` | Новый | `services/user.py` |
| `RoleService` | Новый | `services/role.py` |
| `OIDCService` | Существующий | `services/oidc.py` |
| `GitLabService` | Расширить | `services/gitlab.py` |
| `HarborService` | Новый | `services/harbor.py` |
| `GitHubService` | Существующий | `services/github.py` |
| `DockerRegistryService` | Существующий | `services/docker.py` |
| `HelmService` | Существующий | `services/helm.py` |
| `BuildService` | Существующий | `services/build.py` |
| `MirrorService` | Новый | `services/mirror.py` |
| `SchedulerService` | Существующий | `services/scheduler.py` |
| `WebhookService` | Новый | `services/webhook.py` |

### [8. Pipelines](./08-pipelines.md)
- Типы пайплайнов: mirror, gold_image, app_image, helm_sync, docker_sync
- GitLab CI шаблоны в `gitlab-ci/`
- GitLab Components структура и использование
- Webhook обратная связь (state machine диаграмма)
- Polling статуса для пайплайнов без webhook
- Таблица `pipeline_runs`
- APScheduler для расписаний

### [9. UI Structure](./09-ui-structure.md)
- Полная структура страниц и маршрутов
- Permission-based навигация в sidebar
- Hook `usePermissions()` и компонент `PermissionGate`
- Обновлённый `ProtectedRoute` с permission check
- Расширение `authSlice` с `permissions[]`
- RTK Query endpoints для всех новых API
- Планируемые Admin подстраницы

### [10. Security](./10-security.md)
- Модель угроз и митигации
- JWT структура и TTL
- bcrypt для паролей (cost factor 12)
- Fernet шифрование credentials at rest
- HMAC верификация webhooks (GitLab, GitHub, Harbor)
- Rate limiting через `slowapi`
- Audit log таблица и аудируемые действия
- Security checklist для деплоя

### [11. Migration Strategy](./11-migration-strategy.md)
- **Phase 1** (10 дней): RBAC Foundation — таблицы, JWT, API, UI
- **Phase 2** (13 дней): Integrations — multi-instance support
- **Phase 3** (9 дней): OIDC & Advanced — Keycloak, role mapping
- **Phase 4** (10 дней): Polish — audit log, rate limiting, Admin UI
- Rollback plan для каждой фазы
- Data migration scripts
- Pre/post migration checklists

---

## Ключевые архитектурные решения

| Решение | Выбор | Обоснование |
|---------|-------|-------------|
| RBAC модель | Permission-based (`resource:action`) | Гибкость, кастомные роли |
| Auth по умолчанию | Local (email/password) | Работает без внешних зависимостей |
| OIDC провайдер | Keycloak (опционально) | Корпоративный стандарт |
| Шифрование credentials | Fernet (AES-128-CBC) | Симметричное, быстрое, надёжное |
| Multi-instance | Отдельные `*_instances` таблицы | Изоляция конфигураций |
| Pipeline execution | GitLab CI | Уже используется в проекте |
| Webhook security | HMAC-SHA256 / token | Стандарт для каждой платформы |
| Frontend state | Redux Toolkit + RTK Query | Типизация, кэширование |

---

## Связанные файлы проекта

- [`backend/app/core/rbac.py`](../../backend/app/core/rbac.py) — текущий RBAC
- [`backend/app/core/secrets.py`](../../backend/app/core/secrets.py) — шифрование
- [`backend/app/services/oidc.py`](../../backend/app/services/oidc.py) — OIDC сервис
- [`backend/app/services/gitlab.py`](../../backend/app/services/gitlab.py) — GitLab сервис
- [`backend/alembic/versions/`](../../backend/alembic/versions/) — миграции БД
- [`gitlab-ci/`](../../gitlab-ci/) — CI/CD шаблоны
- [`examples/`](../../examples/) — примеры настройки GitLab, Harbor, Keycloak
- [`plans/architecture.md`](../../plans/architecture.md) — высокоуровневый план
