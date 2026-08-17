# Changelog

All notable changes to BigBug will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Makefile — единая точка входа для запуска всех скриптов:**
  - Корневой [`Makefile`](Makefile) с 6 группами команд: `dev-*` (build/up/init/down/clean), `infra-*` (up/init/down/clean + чистка compose/harbor/tofu), `test-*` (unit/integrations/e2e/all по стеку), `lint-*`/`format-*`/`typecheck-*`, `coverage-*` (код + эндпоинты), `dead-code-*`
  - Self-documenting help (`make help`), проброс аргументов в тесты через `TEST_ARGS`
  - Backend typecheck: [`backend/scripts/type-check.sh`](backend/scripts/type-check.sh) + `[tool.mypy]` в [`pyproject.toml`](backend/pyproject.toml) (зелёный прогон на 132 файлах)
  - Frontend dead-code: `knip` devDependency + [`frontend/knip.json`](frontend/knip.json) + [`frontend/scripts/dead-code.sh`](frontend/scripts/dead-code.sh)

- **Финальная зачистка и сквозная проверка (2026-08-16):**
  - Сброс миграций Alembic: 40 старых ревизий забэкаплены в [`backend/alembic/versions_backup_20260816/`](backend/alembic/versions_backup_20260816/), новая цепочка — [`initial_schema`](backend/alembic/versions/20260816_1159_37590bb4a2ec_initial_schema.py) → [`seed_initial_data`](backend/alembic/versions/20260816_1200_a1b2c3d4e5f6_seed_initial_data.py)
  - Dev-БД пересоздана на новой цепочке миграций
  - OpenAPI-контракт: [`backend/openapi.json`](backend/openapi.json) (137 paths / 195 operations), экспорт через [`backend/scripts/export-openapi.sh`](backend/scripts/export-openapi.sh) + [`export_openapi.py`](backend/scripts/export_openapi.py), guard-тест [`test_openapi_contract.py`](backend/tests/unit/test_openapi_contract.py)
  - E2E переписаны на живой HTTP к `localhost:8000` (без sqlite/моков), валидация ответов по `openapi.json` ([`openapi_utils.py`](backend/tests/e2e/openapi_utils.py)), endpoint-coverage отчёт ([`backend/reports/endpoint-coverage.md`](backend/reports/endpoint-coverage.md), мягкий порог 30%)
  - Покрытие кода e2e-тестами: [`backend/scripts/test-e2e-coverage.sh`](backend/scripts/test-e2e-coverage.sh)
  - Vulture: [`backend/scripts/vulture.sh`](backend/scripts/vulture.sh) + whitelist [`backend/vulture-whitelist.py`](backend/vulture-whitelist.py), отчёт [`backend/reports/vulture-report.txt`](backend/reports/vulture-report.txt), `vulture>=2.11` в dev-deps

- **Providers V3 — миграция на единую сущность `resource_providers`:**
  - Единый реестр провайдеров (таблица `resource_providers` + реестр подтипов в коде + `/api/providers`) вместо 5 legacy-таблиц инстансов (`gitlab_instances`, `harbor_instances`, `github_instances`, `docker_registry_instances`, `helm_repository_instances`) и V2-системы `source_providers`
  - Подтипы `github`/`gitlab`/`generic_git`/`docker_hub`/`quay`/`gcr`/`ecr`/`acr`/`ghcr`/`harbor`/`generic_registry`/`helm_repo`; категории `system`/`public`/`private`; направления `external`/`internal`
  - Расширенная RBAC: `providers:read/write/delete/use/read_all/share`, `providers_system:write`, `teams:read/write/manage_members`, `credentials:write`; scope-providers
  - Команды (`teams`) и шаринг провайдеров (`visibility`, `team_id`, `/api/teams`, `/api/providers/{id}/share|unshare`)

- **Git Mirroring V2 Finalization — Этап 9:**
  - Reports: 4 типа отчётов по зеркалам (Summary, Sync History, Failures, Performance) с экспортом в CSV/JSON
  - Bulk Operations: 3 типа массовых операций (Sync, Validate Integrity, Delete) с подтверждением
  - Финальная актуализация роутинга: редиректы со старых URL (`/mirrors`, `/helm-charts`, `/docker-images`, `/pipelines`, `/gold-images`, `/app-images`) на новую структуру
- **Git Mirroring V2 — Этап 8:**
  - Soft Delete + Restore для зеркал (модель `MirrorReleaseLog`, API `DELETE /api/mirrors/{id}` + `POST /api/mirrors/{id}/restore`)
  - CleanupService + APScheduler: фоновая очистка GitLab проектов для soft-deleted зеркал старше 7 дней
  - HealthCheck + Integrity Check + Orphaned API: проверка целостности target-репозиториев и обнаружение осиротевших зеркал
  - Orphaned Mirrors страница + RelinkModal: UI для управления осиротевшими зеркалами

### Removed

- Удалены legacy-роутеры `api/integrations/`, `services/integrations.py`, 5 instance-моделей, модель `SourceProvider` + таблица `source_providers` (enum `ProviderType` перенесён в нейтральное место)
- Удалены legacy-сторы (`integrations.ts`, `git-mirroring/providers.ts`, `mirrors-legacy.ts`) и страницы (`Settings/Integrations`, `GitMirroring/Providers`, `Admin/Integrations`, `Mirrors`, `Projects`)
- Удалены legacy-права (`integrations:*`, `docker_registry:manage`, `helm_repository:manage`, `pipelines:manage`, `credentials:use`)

### Changed

- **Багфиксы (2026-08-16):**
  - Rate-limiter: настройка через env-переменные `RATE_LIMIT_*`, отключён на dev
  - FK `audit_logs` при удалении пользователя (`ondelete=SET NULL`)
  - Rollback в [`audit.py`](backend/app/services/audit.py)
- Updated Material UI from v6 to v9 (`@mui/material ^9.0.1`, `@mui/icons-material ^9.0.1`)
- Updated `@emotion/react` to `^11.14.0`, `@emotion/styled` to `^11.14.1`
- **Реструктуризация инфраструктуры:**
  - Terraform конфигурации собраны в [`infrastructure/terraform/`](infrastructure/terraform/) с подмодулями в [`infrastructure/terraform/modules/`](infrastructure/terraform/modules/) (keycloak, harbor, gitlab)
  - Единый `tofu apply` с передачей outputs между модулями (Keycloak → Harbor → GitLab)
  - Compose разделён: корневой [`docker-compose.yml`](docker-compose.yml) — dev-сборка приложения (postgres-backend, redis, backend, frontend), [`infrastructure/docker-compose.yml`](infrastructure/docker-compose.yml) — инфраструктурные сервисы (postgres-keycloak, keycloak, gitlab, gitlab-runner)
  - `postgres-backend` и `redis` перенесены из инфраструктурного compose в корневой
  - Harbor setup файлы (`deploy.sh`, `teardown.sh`, etc.) перенесены из `infrastructure/harbor/setup/` → `infrastructure/harbor/`
  - [`init.sh`](infrastructure/init.sh) переписан: единый `tofu apply` из `infrastructure/terraform/`, idempotent compose up
  - [`update-env.sh`](infrastructure/update-env.sh) переписан: читает единый `terraform.tfstate`
  - Старые директории удалены: `infrastructure/keycloak/`, `infrastructure/gitlab/`, `infrastructure/harbor/terraform/`, `infrastructure/harbor/setup/`

## [0.7.0] - 2026-06-07

### Added

- **OIDC & Advanced (Phase 3):**
  - OIDC/SSO configuration management via database and UI
  - New `OIDCConfig` model with fields: `issuer_url`, `client_id`, `client_secret` (Fernet-encrypted), `frontend_client_id`, `enabled`, `public_url`, `role_mapping` (JSON)
  - Alembic migration [`20260607_0106_c7d8e9f0a1b2_add_oidc_config.py`](backend/alembic/versions/20260607_0106_c7d8e9f0a1b2_add_oidc_config.py) — создание таблицы `oidc_config`
  - [`OIDCConfigService`](backend/app/services/oidc_config.py) — CRUD + 60-секундный кэш конфигурации с инвалидацией
  - API эндпоинты для управления OIDC конфигурацией (только admin):
    - `GET /api/auth/admin/oidc-config` — полная конфигурация
    - `PATCH /api/auth/admin/oidc-config` — обновление конфигурации
    - `GET /api/auth/admin/oidc-config/public` — конфигурация без `client_secret`
  - Authentication Settings страница [`/settings/authentication`](frontend/src/pages/Settings/Authentication/index.tsx):
    - Toggle включения/отключения OIDC
    - Поля: Issuer URL, Client ID, Client Secret, Frontend Client ID, Public URL
    - CRUD-таблица Role Mapping (Provider Role → BigBug Role)
    - Маскирование `client_secret` (отображается пустым, отправляется только при изменении)
  - RTK Query эндпоинты: `getOidcConfig`, `updateOidcConfig` в [`store/api.ts`](frontend/src/store/api.ts)
  - Навигационный пункт "Authentication" в Settings sidebar ([`Layout`](frontend/src/components/Layout/index.tsx))
  - Backend e2e тесты: 20 тестов для OIDC Config API ([`test_oidc_config.py`](backend/tests/e2e/test_oidc_config.py))
  - Frontend unit тесты: 39 тестов для Authentication Settings (7 категорий) ([`AuthenticationSettings.test.tsx`](frontend/src/tests/AuthenticationSettings.test.tsx))

### Changed

- Рефакторинг [`KeycloakOIDCService`](backend/app/services/oidc.py) — читает OIDC конфигурацию из БД вместо env vars
- OIDC провайдер теперь можно изменить в runtime без перезапуска сервера
- Role mapping (Keycloak roles → BigBug roles) теперь настраивается через UI вместо hardcoded frozenset

[0.7.0]: https://github.com/user/BigBug/compare/v0.6.0...v0.7.0

## [0.6.0] - 2026-06-07

### Added

- **Multi-instance Integrations (Phase 2):**
  - Модели для управления несколькими инстансами интеграций: [`GitlabInstance`](backend/app/models/gitlab_instance.py), [`HarborInstance`](backend/app/models/harbor_instance.py), [`GithubInstance`](backend/app/models/github_instance.py), [`DockerRegistryInstance`](backend/app/models/docker_registry_instance.py), [`HelmRepositoryInstance`](backend/app/models/helm_repository_instance.py)
  - Поля `name`, `url`, `token` (Fernet-шифрование), `is_default`, `is_active`, `verify_ssl`, `status_flag`, `status_text`, `last_checked_at` во всех моделях инстансов
  - Миграция [`20260606_2145_a66daaecc2fa_add_integration_instances.py`](backend/alembic/versions/20260606_2145_a66daaecc2fa_add_integration_instances.py) — создание таблиц `gitlab_instances`, `harbor_instances`, `github_instances`
  - Миграция [`20260606_2220_b0714dde902c_add_docker_registry_and_helm_repo_.py`](backend/alembic/versions/20260606_2220_b0714dde902c_add_docker_registry_and_helm_repo_.py) — создание таблиц `docker_registry_instances`, `helm_repository_instances`
  - Миграция [`20260607_0105_a1b2c3d4e5f6_add_integration_instance_fields.py`](backend/alembic/versions/20260607_0105_a1b2c3d4e5f6_add_integration_instance_fields.py) — добавление полей `verify_ssl`, `is_active`, `last_checked_at`, `status_flag`, `status_text`
  - Pydantic схемы в [`backend/app/schemas/integrations.py`](backend/app/schemas/integrations.py): `*Create`, `*Update`, `*Out`, `ConnectionTestResult` для всех 5 типов инстансов; `_DatetimeStrOut` mixin для конвертации datetime→isoformat
  - [`IntegrationsService`](backend/app/services/integrations.py) — CRUD + `test_connection()` для каждого типа инстанса (httpx для проверки connectivity)
  - [`ServiceFactory`](backend/app/services/integrations.py) — статическое создание API-клиентов (GitLab/GitHub/Harbor/Docker/Helm) с передачей расшифрованных credentials

- **Integrations REST API:**
  - `GET/POST /api/integrations/gitlab` — список/создание GitLab инстансов
  - `GET/PATCH/DELETE /api/integrations/gitlab/{id}` — CRUD одного инстанса
  - `POST /api/integrations/gitlab/{id}/test` — тест соединения (httpx → GitLab API `/version`)
  - Аналогичные эндпоинты для Harbor, GitHub, Docker Registry, Helm Repository (по 6 эндпоинтов × 5 типов = 30 endpoints)
  - RBAC: все эндпоинты защищены через `require_permission("integrations:manage")`

- **Frontend UI — Settings > Integrations:**
  - [`SettingsIntegrations`](frontend/src/pages/Settings/Integrations/index.tsx) — страница с MUI Tabs (GitLab / Harbor / GitHub / Docker Registry / Helm Repository)
  - `GitlabPanel` / `HarborPanel` / `GithubPanel` / `DockerRegistryPanel` / `HelmRepositoryPanel` — панели с таблицами инстансов, кнопками Add Instance / Edit / Delete / Test Connection
  - Диалоги `*Dialog` для каждого типа — форма с полями (Name, URL, Token, Verify SSL, Active, Default), валидация URL, создание/обновление
  - `handleDelete` с `window.confirm()` подтверждением удаления
  - `handleTest` — тест соединения с отображением success/error в Snackbar (MUI Alert)

- **Тесты:**
  - Backend unit: [`test_integrations.py`](backend/tests/unit/test_integrations.py) — 50 тестов (10 per integration type: CRUD + шифрование + test connection + duplicate detection)
  - Backend e2e: [`test_integrations.py`](backend/tests/e2e/test_integrations.py) — 35 тестов (7 per integration type: CRUD + test connection + unauthorized)
  - Frontend: [`Integrations.test.tsx`](frontend/src/tests/Integrations.test.tsx) — 8 тестов (табы, список инстансов, диалог создания, редактирование, удаление с confirm, test connection success/failure, permission gate)
  - Всего backend-тестов: 197 (110 unit + 87 e2e), все проходят
  - Frontend-тесты: 73 проходят, 1 предсуществующий flaky тест (`SsoCallback.test.tsx` — таймаут загрузки Vite worker при полном прогоне)

### Changed

- **Реорганизация тестов:**
  - Тесты разделены на `tests/unit/` (6 файлов, 110 тестов) и `tests/e2e/` (7 файлов, 87 тестов)
  - Каждая директория имеет собственный `conftest.py` с моком `ENCRYPTION_KEY`
  - `e2e` маркер зарегистрирован в [`pyproject.toml`](backend/pyproject.toml)
  - Скрипты [`test-unit.sh`](backend/scripts/test-unit.sh) и [`test-e2e.sh`](backend/scripts/test-e2e.sh) обновлены для запуска из соответствующих директорий
  - [`seeded_permissions`](backend/tests/e2e/conftest.py:44) fixture (`autouse=True`) — гарантирует наличие permissions для admin-роли во всех e2e тестах

- **Pydantic схемы:** поля `created_at`, `updated_at`, `last_checked_at` в `*Out` схемах объявлены как `str` (isoformat), с автоматической конвертацией из `datetime` через `_DatetimeStrOut` mixin

[0.6.0]: https://github.com/user/BigBug/compare/v0.5.0...v0.6.0

## [0.5.0] - 2026-06-06

### Added

- **Permission-based RBAC система (Phase 1):**
  - Database таблицы: `permissions` (32 granular permissions по паттерну `resource:action`), `role_permissions` (M2M роли ↔ permissions)
  - Поля `is_custom`, `created_by_user_id` в таблице `roles` для поддержки кастомных ролей
  - Миграция [`20260606_1932_bde12d699ca4_add_rbac_permissions.py`](backend/alembic/versions/20260606_1932_bde12d699ca4_add_rbac_permissions.py) — создание таблиц + seed 32 permissions + назначение для builtin-ролей (admin: все, operator: read+write+actions, viewer: read-only)
  - [`require_permission()`](backend/app/core/rbac.py:81) FastAPI dependency с JWT payload caching — permissions читаются из JWT, fallback на DB-запрос для старых токенов
  - [`RBACService`](backend/app/services/rbac_service.py) — бизнес-логика: `get_user_permissions()`, `get_all_permissions()`, `create_role()`, `update_role()`, `delete_role()`, `assign_permissions_to_role()`; встроенная защита builtin-ролей от модификации/удаления
  - Pydantic схемы в [`backend/app/schemas/rbac.py`](backend/app/schemas/rbac.py): `PermissionOut`, `RoleOut`, `RoleDetailOut`, `RoleCreate`, `RoleUpdate`, `UserPermissionsOut`
  - Permissions embedded в JWT payload при login/refresh/OIDC exchange (строки 51-63, 88-100, 185-197 в [`backend/app/api/auth.py`](backend/app/api/auth.py))
  - [`frontend/src/hooks/usePermissions.ts`](frontend/src/hooks/usePermissions.ts) — хук с `hasPermission()`, `hasAnyPermission()`, `hasAllPermissions()`
  - [`frontend/src/components/PermissionGate.tsx`](frontend/src/components/PermissionGate.tsx) — условный рендер с props `permission`, `anyOf`, `allOf`, `fallback`

- **Admin RBAC API:**
  - `GET /api/admin/permissions` — список всех доступных permissions в системе
  - `GET /api/admin/roles` — список ролей с embedded permissions
  - `POST /api/admin/roles` — создание кастомной роли с набором permissions
  - `PATCH /api/admin/roles/{id}` — обновление кастомной роли (builtin-роли защищены)
  - `DELETE /api/admin/roles/{id}` — удаление кастомной роли (проверка что нет assigned пользователей)

- **Auth API расширение:**
  - `GET /api/auth/me/permissions` — permissions и роль текущего пользователя

### Changed

- **JWT токены** теперь содержат `permissions: list[str]` в payload для RBAC-кэширования; [`get_current_user`](backend/app/core/rbac.py:21) кэширует их в `user._cached_permissions`
- **Таблица `roles`** расширена: `is_custom` (boolean), `created_by_user_id` (FK на users)

## [0.4.0] - 2026-06-05

### Added

- **OpenTofu/Terraform инфраструктура:**
  - [`infrastructure/keycloak/`](infrastructure/keycloak/) — декларативная конфигурация Keycloak на базе провайдера `mrparkers/keycloak` v4.x
  - [`infrastructure/keycloak/main.tf`](infrastructure/keycloak/main.tf) — конфигурация провайдера
  - [`infrastructure/keycloak/realm.tf`](infrastructure/keycloak/realm.tf) — realm "bigbug"
  - [`infrastructure/keycloak/clients.tf`](infrastructure/keycloak/clients.tf) — confidential client `bigbug-backend` + public client `bigbug-frontend` с PKCE S256
  - [`infrastructure/keycloak/roles.tf`](infrastructure/keycloak/roles.tf) — realm roles: admin, operator, viewer
  - [`infrastructure/keycloak/users.tf`](infrastructure/keycloak/users.tf) — тестовый пользователь `bigbug` с ролью admin
  - [`infrastructure/gitlab/`](infrastructure/gitlab/) — декларативная конфигурация GitLab на базе провайдера `gitlabhq/gitlab` v17.x
  - [`infrastructure/gitlab/main.tf`](infrastructure/gitlab/main.tf) — конфигурация провайдера с data-источником для root пользователя
  - [`infrastructure/gitlab/groups.tf`](infrastructure/gitlab/groups.tf) — группа "bigbug-mirrors" для зеркал
  - [`infrastructure/gitlab/tokens.tf`](infrastructure/gitlab/tokens.tf) — Personal Access Token с правами api, read_repository, write_repository

- **Разделение Docker Compose:**
  - [`docker-compose.infra.yml`](docker-compose.infra.yml) — инфраструктурные сервисы (postgres-backend, postgres-keycloak, redis, keycloak, gitlab, gitlab-runner) с общей сетью `bigbug-network`
  - [`docker-compose.app.yml`](docker-compose.app.yml) — сервисы приложения (backend, frontend) с external-сетью `bigbug-network`

- **Автоматизация:**
  - [`infrastructure/init.sh`](infrastructure/init.sh) — мастер-скрипт полной инициализации: проверка зависимостей (docker, opentofu/terraform, curl, jq), запуск инфраструктуры, ожидание health checks, применение OpenTofu конфигураций, обновление `.env`, запуск приложения
  - [`infrastructure/update-env.sh`](infrastructure/update-env.sh) — скрипт обновления `.env` из OpenTofu outputs (GITLAB_TOKEN, KEYCLOAK_REALM, KEYCLOAK_CLIENT_ID, KEYCLOAK_CLIENT_ID_FRONTEND)

- **Документация:**
  - [`infrastructure/README.md`](infrastructure/README.md) — общий обзор, Quick Start, manual setup, troubleshooting
  - [`infrastructure/keycloak/README.md`](infrastructure/keycloak/README.md) — что создаётся, переменные, проверка через UI
  - [`infrastructure/gitlab/README.md`](infrastructure/gitlab/README.md) — что создаётся, получение root PAT, security notes
  - Обновлён корневой [`README.md`](README.md) — новый Quick Start с OpenTofu, обновлённая структура проекта, таблица сервисов разделена на infra/app

### Changed

- **Реорганизация структуры проекта:**
  - [`harbor/`](harbor/) перемещён → [`infrastructure/harbor/setup/`](infrastructure/harbor/setup/)
  - [`infrastructure/keycloak/`](infrastructure/keycloak/) содержит OpenTofu-конфигурацию вместо bash-скрипта
  - [`infrastructure/gitlab/`](infrastructure/gitlab/) содержит OpenTofu-конфигурацию

- **Документация использует новые пути:**
  - Harbor: `cd infrastructure/harbor/setup` вместо `cd harbor`
  - Keycloak: `cd infrastructure/keycloak && tofu apply` вместо `docker compose --profile init up keycloak-init`

### Removed

- **Удалён bash-скрипт инициализации Keycloak:**
  - Папка [`keycloak/`](keycloak/) с файлом [`init-keycloak.sh`](keycloak/init-keycloak.sh) удалена
  - Сервис `keycloak-init` с `profiles: ["init"]` удалён из [`docker-compose.yml`](docker-compose.yml)
  - Keycloak теперь инициализируется через OpenTofu (`cd infrastructure/keycloak && tofu apply`)

### Deprecated

- [`docker-compose.yml`](docker-compose.yml) помечен как deprecated — используйте [`docker-compose.infra.yml`](docker-compose.infra.yml) и [`docker-compose.app.yml`](docker-compose.app.yml)

### Breaking Changes

- `docker compose --profile init up keycloak-init` больше не работает
- `docker compose up -d` запускает только старый единый compose-файл, который помечен deprecated
- Требуется установка OpenTofu или Terraform для инициализации инфраструктуры
- Путь к harbor изменился с `harbor/` на `infrastructure/harbor/setup/`

## [0.3.0] - 2026-06-05

### Added

- **Backend тесты (111 тестов):**
  - [`test_oidc.py`](backend/tests/test_oidc.py) — 19 тестов: обмен кода авторизации, валидация ID-токенов (подпись JWKS, issuer, audience, expiry), provisioning пользователей, синхронизация ролей из `realm_access.roles`, TTL-кэш JWKS
  - [`test_helm_service.py`](backend/tests/test_helm_service.py) — 14 тестов: импорт источника, индексация через `index.yaml` (httpx + PyYAML), `_sync_chart_entries()` upsert, `_normalize_repo_url()`, обработка ошибок сети
  - [`test_docker_service.py`](backend/tests/test_docker_service.py) — 16 тестов: импорт источника, индексация тегов через `/v2/<image>/tags/list`, разрешение digest через HEAD-запросы, `_normalize_registry_url()`, обработка ошибок сети
  - [`test_secrets.py`](backend/tests/test_secrets.py) — 11 тестов: шифрование/дешифрование Fernet (roundtrip), `None`-safe обработка, `SecretEncryptionError` при неверном ключе/токене, `MultiFernet`-совместимость
  - [`test_helm_api.py`](backend/tests/test_helm_api.py) — 15 тестов: CRUD эндпоинты `/api/helm-charts`, индексация, версии, логи синхронизации, RBAC-проверки (viewer/operator)
  - [`test_docker_api.py`](backend/tests/test_docker_api.py) — 16 тестов: CRUD эндпоинты `/api/docker-images`, индексация по `image_name`, теги, логи синхронизации, RBAC-проверки (viewer/operator)
  - [`test_auth.py`](backend/tests/test_auth.py) — 7 тестов: локальный логин, неверный пароль, неизвестный пользователь, истечение токенов
  - [`test_projects.py`](backend/tests/test_projects.py) — 6 тестов: CRUD GitHub-проектов, RBAC-проверки
  - [`test_images.py`](backend/tests/test_images.py) — 7 тестов: Gold/App images CRUD, версионирование, RBAC-проверки

- **Frontend тесты (88 тестов):**
  - [`keycloak.service.test.ts`](frontend/src/tests/keycloak.service.test.ts) — 17 тестов: singleton Keycloak instance, `generateCodeVerifier()`, `computeCodeChallenge()` (SHA-256), `redirectToKeycloakLogin()`, `resetKeycloakInstance()`
  - [`useKeycloakAuth.test.tsx`](frontend/src/tests/useKeycloakAuth.test.tsx) — 10 тестов: хук `useKeycloakAuth`, состояния `ready`/`enabled`/`error`, `login()` редирект, `handleCallback()` exchange
  - [`SsoCallback.test.tsx`](frontend/src/tests/SsoCallback.test.tsx) — 9 тестов: обработка callback, обмен кода на токены, обработка ошибок exchange, StrictMode double-mount guard, редирект на `/login?error=`
  - [`HelmCharts.test.tsx`](frontend/src/tests/HelmCharts.test.tsx) — 8 тестов: список источников, диалог создания, кнопка Re-index, отображение статусов
  - [`HelmChartDetail.test.tsx`](frontend/src/tests/HelmChartDetail.test.tsx) — 11 тестов: карточка деталей источника, таблица версий (Chart, Version, App Version, Status), история синхронизации
  - [`DockerImages.test.tsx`](frontend/src/tests/DockerImages.test.tsx) — 8 тестов: список источников, диалог создания с опциональным `image_name`, кнопка Index Image
  - [`DockerImageDetail.test.tsx`](frontend/src/tests/DockerImageDetail.test.tsx) — 13 тестов: карточка деталей источника, таблица тегов (Image, Tag, Architecture, Size), диалог "Index Image" с вводом имени образа, история синхронизации
  - [`authSlice.test.ts`](frontend/src/tests/authSlice.test.ts) — 6 тестов: Redux slice (setCredentials, clearCredentials, начальное состояние)
  - [`StatusChip.test.tsx`](frontend/src/tests/StatusChip.test.tsx) — 6 тестов: отображение всех 5 статусов (OK, Failed, Warning, In Progress, Pending), цветовая индикация

- **Harbor инфраструктура:**
  - [`harbor/kind-config.yaml`](harbor/kind-config.yaml) — конфигурация локального Kubernetes-кластера (kind) для развёртывания Harbor
  - [`harbor/harbor-values.yaml`](harbor/harbor-values.yaml) — Helm-значения для Harbor (persistence, ingress, admin-credentials)
  - [`harbor/deploy.sh`](harbor/deploy.sh) — скрипт развёртывания: `kind create cluster` + `helm install harbor`
  - [`harbor/teardown.sh`](harbor/teardown.sh) — скрипт удаления: `kind delete cluster`
  - [`harbor/test-push.sh`](harbor/test-push.sh) — скрипт тестового пуша Docker-образа в Harbor
  - [`harbor/README.md`](harbor/README.md) — документация по развёртыванию и использованию Harbor

### Fixed

- **MissingGreenlet в `get_current_user`:** добавлен `selectinload` для ролей пользователя при асинхронной загрузке, устраняющий `MissingGreenlet` ошибку при доступе к `user.roles` вне сессии
- **passlib → bcrypt:** заменён `passlib` на нативный [`bcrypt`](backend/app/core/security.py:4) для совместимости с Python 3.14 (passlib не поддерживает `bcrypt` ≥ 4.1)

### Security

- Все пароли хешируются через [`bcrypt`](backend/app/core/security.py:11) с автоматической генерацией соли ([`gensalt()`](backend/app/core/security.py:18))

## [0.2.0] - 2026-06-05

### Added

- **Docker Images — модели (Блок 4):**
  - [`DockerImageSource`](backend/app/models/docker_image_source.py) — источник Docker-образов (name, registry_url, gitlab_project_id, status_flag default=4 Pending)
  - [`DockerImageTag`](backend/app/models/docker_image_tag.py) — тег Docker-образа (image_name, tag, digest из `docker-content-digest`, size_bytes, architectures JSON)
  - [`DockerSyncLog`](backend/app/models/docker_sync_log.py) — лог синхронизации (pipeline_id, status_flag, triggered_by: scheduler/manual/webhook)
  - Миграция [`add_docker_tables`](backend/alembic/versions/20260605_1200_add_docker_tables.py) — 3 таблицы с индексами

- **Docker Registry Service (Блок 4):**
  - [`DockerRegistryService`](backend/app/services/docker.py) — индексация тегов через Docker Registry API v2: `GET /v2/<image>/tags/list` + `HEAD /v2/<image>/manifests/<tag>` для digest
  - `_sync_tags()` — upsert по `(source_id, image_name, tag)`, идемпотентная повторная индексация
  - `_normalize_registry_url()` — автоматическое добавление `/v2` к registry URL
  - Pydantic-схемы: [`docker.py`](backend/app/schemas/docker.py) — `DockerImageSourceOut`, `DockerImageSourceDetailOut` (с вложенными tags), `DockerImageTagOut`, `DockerSyncLogOut`

- **Docker Images API (Блок 4):**
  - [`docker_images.py`](backend/app/api/docker_images.py) — 8 эндпоинтов: `GET /api/docker-images`, `GET /api/docker-images/{id}`, `POST`, `PATCH`, `DELETE`, `POST .../index?image_name=...`, `GET .../tags`, `GET .../logs`
  - RBAC: чтение — `require_viewer`, изменение — `require_operator`

- **Frontend UI — Docker Images (Блок 5):**
  - [`DockerImages/index.tsx`](frontend/src/pages/DockerImages/index.tsx) — список источников с таблицей (Name, Registry URL, Last Synced, Status, Actions), диалог создания
  - [`DockerImageDetail.tsx`](frontend/src/pages/DockerImages/DockerImageDetail.tsx) — карточка Source Info, таблица тегов (Image, Tag, Architecture, Size с форматированием байт), история синхронизации, диалог "Index Image"

- **Frontend UI — Helm Charts (Блок 5):**
  - [`HelmCharts/index.tsx`](frontend/src/pages/HelmCharts/index.tsx) — список источников чартов с таблицей (Name, Repo URL, Last Synced, Status, Actions), диалог создания
  - [`HelmChartDetail.tsx`](frontend/src/pages/HelmCharts/HelmChartDetail.tsx) — карточка Source Info, таблица версий чарта (Chart, Version, App Version, Status + индикатор Synced), история синхронизации

- **RTK Query — 16 эндпоинтов (Блок 5):**
  - [`api.ts`](frontend/src/store/api.ts) — `tagTypes: ['HelmChart', 'DockerImage']`, 8 эндпоинтов для Helm (CRUD + index + versions + logs), 8 эндпоинтов для Docker (CRUD + index + tags + logs)
  - Экспортированы хуки: `useListHelmChartsQuery`, `useGetHelmChartQuery`, `useCreateHelmChartMutation`, `useUpdateHelmChartMutation`, `useDeleteHelmChartMutation`, `useIndexHelmChartMutation`, `useGetHelmChartVersionsQuery`, `useGetHelmChartLogsQuery` и аналогичные для Docker

- **TypeScript-типы (Блок 5):**
  - [`types/index.ts`](frontend/src/types/index.ts) — интерфейсы: `HelmChartSource`, `HelmChartSourceDetail`, `HelmChartVersion`, `HelmSyncLog`, `DockerImageSource`, `DockerImageSourceDetail`, `DockerImageTag`, `DockerSyncLog`

- **Маршрутизация и меню (Блок 5):**
  - [`router/index.tsx`](frontend/src/router/index.tsx) — маршруты `/helm-charts`, `/helm-charts/:id`, `/docker-images`, `/docker-images/:id`
  - [`Layout/index.tsx`](frontend/src/components/Layout/index.tsx) — пункты меню "Helm Charts" (иконка `Sailing`) и "Docker Images" (иконка `Dock`)

- **GitLab CI шаблоны (Блок 4):**
  - [`docker-sync-template.yml`](gitlab-ci/docker-sync-template.yml) — CI-шаблон синхронизации Docker-образов (stages: `sync`, `notify`; образ `docker:27-dind`; переменные: `DOCKER_REGISTRY_URL`, `DOCKER_IMAGE_NAME`, `TAG_FILTER`, `TAG_LIMIT`)
  - [`helm-sync-template.yml`](gitlab-ci/helm-sync-template.yml) — CI-шаблон синхронизации Helm-чартов (образ `alpine/helm`; переменные: `HELM_REPO_URL`, `SYNC_STRATEGY`, `CHART_FILTER`)

### Changed

- **Webhook расширен до 4 типов логов:**
  - [`webhooks.py`](backend/app/api/webhooks.py) — добавлены обработчики `HelmSyncLog` и `DockerSyncLog` (поиск по `pipeline_id`, обновление статуса и `last_synced_at` родительской сущности)
  - Поддерживаемые типы: `sync_log` (gitlab mirror), `build_log` (docker build), `helm_sync_log` (helm chart sync), `docker_sync_log` (docker image sync)

- **Модели:**
  - [`models/__init__.py`](backend/app/models/__init__.py) — добавлены `HelmChartSource`, `HelmChartVersion`, `HelmSyncLog`, `DockerImageSource`, `DockerImageTag`, `DockerSyncLog`
- **Main:**
  - [`main.py`](backend/app/main.py) — зарегистрированы роутеры `helm_charts` (`/api/helm-charts`) и `docker_images` (`/api/docker-images`)

## [0.1.0] - 2026-06-05

### Added

- **SSO/OIDC интеграция (Блок 2):**
  - [`KeycloakOIDCService`](backend/app/services/oidc.py) — обмен кода авторизации (`exchange_code()`), валидация ID-токенов (подпись JWKS, issuer, audience, expiry), provisioning пользователей (`provision_or_update_user()`), синхронизация ролей из `realm_access.roles` (`_sync_roles()`)
  - [`OIDCClaims`](backend/app/services/oidc.py:52) — frozen dataclass (subject, username, email, roles)
  - [`_JWKSCache`](backend/app/services/oidc.py:62) — TTL-кэш JWKS с `time.monotonic()`, автосброс при ошибках
  - [`_NonClosingClient`](backend/app/services/oidc.py:313) — адаптер для инъекции тестовых httpx-клиентов
  - 4 доменных исключения: `OIDCError`, `OIDCExchangeError`, `OIDCInvalidTokenError`, `OIDCProvisioningError` ([`exceptions.py`](backend/app/core/exceptions.py))
  - API эндпоинты: [`GET /auth/sso/config`](backend/app/api/auth.py:83) (конфигурация SSO), [`POST /auth/oidc/exchange`](backend/app/api/auth.py:99) (обмен кода на JWT)
  - Pydantic-схемы: `OIDCExchangeRequest` (code, redirect_uri, code_verifier), `SSOConfig` (enabled, url, realm, client_id)

- **Frontend SSO (Блок 2):**
  - [`keycloak.ts`](frontend/src/services/keycloak.ts) — singleton Keycloak instance, `redirectToKeycloakLogin()` с ручным построением PKCE-URL, `generateCodeVerifier()` (64 случайных байта → base64url), `computeCodeChallenge()` (SHA-256 → base64url), `resetKeycloakInstance()` для тестов
  - [`useKeycloakAuth.ts`](frontend/src/hooks/useKeycloakAuth.ts) — хук аутентификации: `ready` (конфиг загружен), `enabled` (SSO включён), `login()` (редирект на Keycloak), `handleCallback()` (обмен кода)
  - [`SsoCallback/index.tsx`](frontend/src/pages/SsoCallback/index.tsx) — страница обработки SSO-callback: обмен кода → получение токена → редирект, `useRef` guard против StrictMode double-mount
  - [`Login/index.tsx`](frontend/src/pages/Login/index.tsx) — кнопка "Sign in with SSO" (показывается при `ready && enabled`), обработка `?error=` query-параметра
  - [`router/index.tsx`](frontend/src/router/index.tsx) — маршрут `/sso/callback`
  - [`api.ts`](frontend/src/store/api.ts) — `getSsoConfig` query, `ssoExchange` mutation

- **Модель пользователя (Блок 2):**
  - [`user.py`](backend/app/models/user.py) — `hashed_password` → `nullable=True` (SSO-пользователи без пароля), добавлено поле `keycloak_sub` (уникальный идентификатор Keycloak-identity)

- **Helm Charts — модели (Блок 3):**
  - [`HelmChartSource`](backend/app/models/helm_chart_source.py) — репозиторий Helm-чартов (name unique, repo_url, gitlab_project_id, status_flag)
  - [`HelmChartVersion`](backend/app/models/helm_chart_version.py) — версия чарта (chart_name, version, app_version, digest SHA-256, urls JSON, is_synced)
  - [`HelmSyncLog`](backend/app/models/helm_sync_log.py) — лог синхронизации (pipeline_id, status_flag, triggered_by: scheduler/manual/webhook)
  - Миграция [`add_helm_tables`](backend/alembic/versions/20260605_0747_add_helm_tables.py) — 3 таблицы с индексами

- **Helm Service (Блок 3):**
  - [`HelmService`](backend/app/services/helm.py) — индексация чартов через парсинг `index.yaml` (httpx + PyYAML `safe_load()`), `_sync_chart_entries()` upsert по `(source_id, chart_name, version)`, `_normalize_repo_url()`, `_validate_repo_url()`
  - Pydantic-схемы: [`helm.py`](backend/app/schemas/helm.py) — `HelmChartSourceOut`, `HelmChartSourceDetailOut`, `HelmChartVersionOut`, `HelmSyncLogOut`

- **Helm Charts API (Блок 3):**
  - [`helm_charts.py`](backend/app/api/helm_charts.py) — 8 эндпоинтов: `GET /helm-charts`, `GET /helm-charts/{id}`, `POST`, `PATCH`, `DELETE`, `POST .../index`, `GET .../versions`, `GET .../logs`
  - RBAC: чтение — `require_viewer`, изменение — `require_operator`

- **Шифрование секретов (Блок 2):**
  - [`SecretCipher`](backend/app/core/secrets.py) — симметричное шифрование на базе Fernet (AES-128-CBC + HMAC-SHA256)
  - [`encrypt_secret()`](backend/app/core/secrets.py:78) / [`decrypt_secret()`](backend/app/core/secrets.py:85) — хелперы, `None`-safe (пустые строки и `None` проходят прозрачно)
  - [`get_cipher()`](backend/app/core/secrets.py:59) — `@lru_cache(maxsize=1)`, падает громко если `ENCRYPTION_KEY` не задан
  - `SecretEncryptionError` — доменное исключение для ошибок расшифровки

### Changed

- **Модели:**
  - [`models/__init__.py`](backend/app/models/__init__.py) — добавлены `HelmChartSource`, `HelmChartVersion`, `HelmSyncLog`
- **Main:**
  - [`main.py`](backend/app/main.py) — зарегистрирован роутер `helm_charts` (`/api/helm-charts`)
- **Webhook:**
  - [`webhooks.py`](backend/app/api/webhooks.py) — добавлена обработка `HelmSyncLog`: поиск по `pipeline_id`, обновление `status_flag`/`status_text`/`finished_at`, обновление `HelmChartSource.last_synced_at` при success

### Security

- **PKCE S256:** фронтенд генерирует `code_verifier` (64 случайных байта) и `code_challenge` (SHA-256), бэкенд передаёт `code_verifier` в Keycloak token endpoint; Keycloak-клиент `bigbug-frontend` создан как public client с обязательным PKCE S256
- **Fernet-шифрование:** registry-пароли для Helm/Docker хранятся в зашифрованном виде, спроектировано для будущего перехода на `MultiFernet` (ротация ключей)

## [0.0.1] - 2026-06-05

### Added

- **Docker-инфраструктура (Блок 1):**
  - [`docker-compose.yml`](docker-compose.yml) — 8 сервисов: PostgreSQL 17 × 2 (backend + keycloak), Redis 7, Keycloak 24.0, GitLab CE, GitLab Runner, backend (FastAPI), frontend (React + Vite)
  - [`keycloak-init`](docker-compose.yml) — одноразовый сервис с `profiles: ["init"]` для идемпотентной инициализации Keycloak
  - [`init-keycloak.sh`](keycloak/init-keycloak.sh) — bootstrap Keycloak: создание realm `bigbug`, ролей (admin/operator/viewer), confidential client `bigbug-backend`, public client `bigbug-frontend` (PKCE S256 enforced), тестового пользователя
  - [`backend/Dockerfile`](backend/Dockerfile) — multi-stage build (slim-bookworm → venv → копирование), запуск от `nonroot` пользователя
  - [`backend/entrypoint.sh`](backend/entrypoint.sh) — точка входа: `app:start` (migrate + uvicorn), `app:init` (только migrate), ожидание PostgreSQL через `pg_isready`
  - [`frontend/Dockerfile`](frontend/Dockerfile) — multi-stage build (node:24-alpine → nginx:alpine)
  - [`.env.example`](.env.example) — все переменные окружения с комментариями (БД, Redis, Keycloak, GitLab, GitHub, Harbor, секреты)

- **Backend — ядро (Блок 1):**
  - [`FastAPI`](backend/app/main.py) приложение с CORS, lifespan (startup/shutdown для scheduler)
  - [`SQLAlchemy 2.x`](backend/app/database.py) — асинхронный движок (`asyncpg`), `AsyncSession` фабрика
  - [`Alembic`](backend/alembic/) — система миграций (initial schema [`39774f94ac35`](backend/alembic/versions/20260605_0449_39774f94ac35_initial_schema.py))
  - [`config.py`](backend/app/config.py) — Pydantic Settings с маппингом переменных окружения
  - JWT-аутентификация: [`security.py`](backend/app/core/security.py) — `create_access_token()`, `create_refresh_token()`, `decode_token()`, `verify_password()`, `get_password_hash()`
  - RBAC: [`rbac.py`](backend/app/core/rbac.py) — декоратор `require_roles()` для проверки ролей (admin/operator/viewer)
  - Глобальный обработчик исключений ([`main.py`](backend/app/main.py))

- **Модели (Блок 1):**
  - [`User`](backend/app/models/user.py) — локальные пользователи (username, email, hashed_password)
  - [`Role`](backend/app/models/role.py) + `UserRole` — M2M роли (admin, operator, viewer)
  - [`GithubOrg`](backend/app/models/github_org.py) — GitHub-организация
  - [`GithubProject`](backend/app/models/github_project.py) — GitHub-репозиторий (metadata, stale tracking)
  - [`GithubRelease`](backend/app/models/github_release.py) — релизы для delta tracking
  - [`GitlabMirror`](backend/app/models/gitlab_mirror.py) — зеркало GitLab
  - [`SyncSchedule`](backend/app/models/sync_schedule.py) — cron-расписание синхронизации (is_enabled, use_default, cron_expression)
  - [`SyncLog`](backend/app/models/sync_log.py) — лог синхронизации (pipeline_id, status_flag, log_output)
  - [`GoldImage`](backend/app/models/gold_image.py) + [`AppImage`](backend/app/models/app_image.py) — базовые и прикладные Docker-образы
  - [`ImageVersion`](backend/app/models/image_version.py) — унифицированная таблица версий (gold/app, архитектуры, SHA-256 digest)
  - [`BuildSchedule`](backend/app/models/build_schedule.py) + [`BuildLog`](backend/app/models/build_log.py) — расписание и логи сборок

- **API эндпоинты (Блок 1):**
  - [`auth.py`](backend/app/api/auth.py) — `POST /auth/login`, `GET /auth/me`, `POST /auth/refresh`
  - [`admin.py`](backend/app/api/admin.py) — управление пользователями и ролями (admin only)
  - [`projects.py`](backend/app/api/projects.py) — CRUD GitHub-проектов
  - [`mirrors.py`](backend/app/api/mirrors.py) — управление GitLab-зеркалами
  - [`gold_images.py`](backend/app/api/gold_images.py) + [`app_images.py`](backend/app/api/app_images.py) — управление Docker-образами
  - [`webhooks.py`](backend/app/api/webhooks.py) — приём webhook-уведомлений от GitLab Runner (sync_log, build_log)
  - [`schedules.py`](backend/app/api/schedules.py) — управление расписаниями синхронизации и сборок

- **Сервисы (Блок 1):**
  - [`github.py`](backend/app/services/github.py) — GitHub API клиент (PyGithub)
  - [`gitlab.py`](backend/app/services/gitlab.py) — GitLab API клиент (python-gitlab)
  - [`scheduler.py`](backend/app/services/scheduler.py) — AsyncIOScheduler для периодических задач
  - [`build.py`](backend/app/services/build.py) — логика сборки Docker-образов

- **GitLab CI шаблоны (Блок 1):**
  - [`mirror-template.yml`](gitlab-ci/mirror-template.yml) — шаблон зеркалирования репозиториев
  - [`gold-image-template.yml`](gitlab-ci/gold-image-template.yml) — шаблон сборки Gold-образов
  - [`app-image-template.yml`](gitlab-ci/app-image-template.yml) — шаблон сборки App-образов

- **Frontend — ядро (Блок 1):**
  - React 19 + TypeScript + Vite
  - Redux Toolkit + RTK Query ([`store/`](frontend/src/store/))
  - Material UI v6 ([`theme.ts`](frontend/src/theme.ts))
  - React Router v7 ([`router/`](frontend/src/router/))
  - Страницы: [`Login`](frontend/src/pages/Login/), [`Dashboard`](frontend/src/pages/Dashboard/), [`Projects`](frontend/src/pages/Projects/), [`Mirrors`](frontend/src/pages/Mirrors/), [`GoldImages`](frontend/src/pages/GoldImages/), [`AppImages`](frontend/src/pages/AppImages/), [`Admin`](frontend/src/pages/Admin/)
  - [`ProtectedRoute`](frontend/src/router/ProtectedRoute.tsx) — guard для аутентифицированных маршрутов
  - [`Layout`](frontend/src/components/Layout/index.tsx) — боковое меню с навигацией

[0.5.0]: https://github.com/user/BigBug/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/user/BigBug/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/user/BigBug/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/user/BigBug/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/user/BigBug/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/user/BigBug/releases/tag/v0.0.1
