# BigBug - Current State

> Последнее обновление: 2026-06-07
> Статус: Блоки 1-5 завершены, RBAC Phase 1 реализован, Phase 2 (Multi-instance Integrations) завершён, Phase 3 (OIDC & Advanced) завершён

## Что работает сейчас

### ✅ Backend API

**Auth** (`/api/auth/`):
- `POST /api/auth/login` - локальный логин (username/password → JWT)
- `GET /api/auth/me` - текущий пользователь
- `GET /api/auth/sso/config` - конфигурация SSO
- `POST /api/auth/oidc/exchange` - обмен OIDC кода на JWT

**Helm Charts** (`/api/helm-charts/`):
- CRUD для источников чартов
- Индексация (парсинг index.yaml)
- Просмотр версий и логов синхронизации
- Триггер GitLab pipeline

**Docker Images** (`/api/docker-images/`):
- CRUD для источников образов
- Индексация (теги из registry)
- Просмотр тегов и логов синхронизации
- Триггер GitLab pipeline

**Mirrors** (`/api/mirrors/`):
- GitHub → GitLab зеркалирование
- Управление расписаниями
- История синхронизации

**Gold/App Images** (`/api/gold-images/`, `/api/app-images/`):
- CRUD для образов
- Версионирование
- Build schedules

**Admin** (`/api/admin/`):
- Управление пользователями
- Управление ролями
- `GET /api/admin/permissions` — список всех permissions
- `GET /api/admin/roles` — список ролей с permissions
- `POST /api/admin/roles` — создание кастомной роли
- `PATCH /api/admin/roles/{id}` — обновление роли
- `DELETE /api/admin/roles/{id}` — удаление кастомной роли

**Auth (расширение)**:
- `GET /api/auth/me/permissions` — permissions текущего пользователя

**OIDC Config Admin** (`/api/auth/admin/`):
- `GET /api/auth/admin/oidc-config` — полная конфигурация OIDC (admin only)
- `PATCH /api/auth/admin/oidc-config` — обновление конфигурации OIDC
- `GET /api/auth/admin/oidc-config/public` — конфигурация без client_secret

**Webhooks** (`/api/webhooks/`):
- GitLab webhook для обновления статусов
- Поддержка 4 типов: sync_log, build_log, helm_sync_log, docker_sync_log

### ✅ Frontend UI

**Страницы**:
- `/login` - логин (local + SSO)
- `/sso/callback` - SSO callback
- `/` - Dashboard
- `/projects` - GitHub проекты
- `/mirrors` - GitLab зеркала
- `/gold-images` - Gold образы
- `/app-images` - App образы
- `/helm-charts` - Helm чарты (список + детали)
- `/docker-images` - Docker образы (список + детали)
- `/admin` - Admin панель
- `/settings/authentication` - Настройки аутентификации (OIDC)

**Компоненты**:
- `Layout` - навигация + sidebar
- `StatusChip` - унифицированный статус
- `ProtectedRoute` - защищённые маршруты
- `PermissionGate` — условный рендер на основе permissions (`permission`/`anyOf`/`allOf` props)

**Hooks**:
- `usePermissions` — `hasPermission()`, `hasAnyPermission()`, `hasAllPermissions()` из Redux store

### ✅ Infrastructure

**Docker Compose**:
- `docker-compose.infra.yml` - инфраструктурные сервисы
- `docker-compose.app.yml` - приложение
- `docker-compose.yaml` - legacy (deprecated)

**Keycloak**:
- Realm `bigbug`
- Роли: admin, operator, viewer
- Clients: bigbug-backend (confidential), bigbug-frontend (public + PKCE)
- OpenTofu конфигурация в `infrastructure/keycloak/`

**GitLab**:
- OpenTofu конфигурация в `infrastructure/gitlab/`
- Группа для зеркал
- Personal Access Token для backend

**GitLab CI Templates** (`gitlab-ci/`):
- `mirror-template.yml` - зеркалирование репозиториев
- `gold-image-template.yml` - сборка Gold образов
- `app-image-template.yml` - сборка App образов
- `helm-sync-template.yml` - синхронизация Helm чартов
- `docker-sync-template.yml` - синхронизация Docker образов

### ✅ Database

**Текущие таблицы**:
- `users` - пользователи (local + SSO)
- `roles` - роли (admin/operator/viewer), расширена полями `is_custom`, `created_by_user_id`
- `user_roles` - M2M связь
- `github_orgs` - GitHub организации
- `github_projects` - GitHub репозитории
- `github_releases` - релизы для delta tracking
- `gitlab_mirrors` - GitLab зеркала
- `sync_schedules` - расписания синхронизации
- `sync_logs` - история синхронизации
- `gold_images` - Gold образы
- `app_images` - App образы
- `image_versions` - версии образов
- `build_schedules` - расписания сборок
- `build_logs` - история сборок
- `helm_chart_sources` - источники Helm чартов
- `helm_chart_versions` - версии чартов
- `helm_sync_logs` - логи синхронизации
- `docker_image_sources` - источники Docker образов
- `docker_image_tags` - теги образов
- `docker_sync_logs` - логи синхронизации
- `permissions` - 32 permission по паттерну `resource:action`
- `role_permissions` - M2M роли ↔ permissions
- `oidc_config` - конфигурация OIDC провайдера (issuer_url, client_id, client_secret, role_mapping JSON)

**Миграции**:
- `20260605_0449_39774f94ac35_initial_schema.py` - базовая схема
- `20260605_0747_add_helm_tables.py` - Helm таблицы
- `20260605_1200_add_docker_tables.py` - Docker таблицы
- `20260606_1932_bde12d699ca4_add_rbac_permissions.py` - RBAC: permissions, role_permissions, расширение roles
- `20260607_0106_c7d8e9f0a1b2_add_oidc_config.py` - таблица oidc_config

## ✅ Завершённые этапы рефакторинга

### ✅ RBAC Phase 1 — ЗАВЕРШЁН (2026-06-06)

**Реализовано**:

**Новые таблицы**:
- `permissions` — 32 permission по паттерну `resource:action` (mirrors, projects, helm, docker, gold_images, app_images, users, roles, system)
- `role_permissions` — M2M роли ↔ permissions
- Поля `is_custom`, `created_by_user_id` в таблице `roles`

**Backend**:
- [`backend/app/core/rbac.py`](../backend/app/core/rbac.py) — `require_permission()` dependency factory с JWT-кэшированием; `require_roles()`, `require_admin()`, `require_operator()`, `require_viewer()` сохранены
- [`backend/app/services/rbac_service.py`](../backend/app/services/rbac_service.py) — `RBACService`: `get_user_permissions()`, `get_all_permissions()`, `get_all_roles()`, `create_role()`, `update_role()`, `delete_role()`, `assign_permissions_to_role()`; встроенная защита builtin-ролей
- [`backend/app/schemas/rbac.py`](../backend/app/schemas/rbac.py) — `PermissionOut`, `RoleOut`, `RoleDetailOut`, `RoleCreate`, `RoleUpdate`, `UserPermissionsOut`
- Permissions вшиты в JWT payload при `login` / `refresh` / `oidc/exchange`; `get_current_user` кэширует их в `user._cached_permissions`

**Admin API**:
- `GET /api/admin/permissions` — список всех permissions
- `GET /api/admin/roles` — список ролей с permissions
- `POST /api/admin/roles` — создание кастомной роли
- `PATCH /api/admin/roles/{id}` — обновление роли (только кастомные)
- `DELETE /api/admin/roles/{id}` — удаление роли (только кастомные, без пользователей)

**Auth API (расширение)**:
- `GET /api/auth/me/permissions` — permissions и роль текущего пользователя

**Frontend**:
- [`frontend/src/hooks/usePermissions.ts`](../frontend/src/hooks/usePermissions.ts) — `hasPermission()`, `hasAnyPermission()`, `hasAllPermissions()`
- [`frontend/src/components/PermissionGate.tsx`](../frontend/src/components/PermissionGate.tsx) — условный рендер с props `permission`, `anyOf`, `allOf`, `fallback`

### ✅ Multi-instance Integrations (Phase 2) — ЗАВЕРШЁН (2026-06-07)

**Реализовано**:

**Новые таблицы**:
- `gitlab_instances` — несколько GitLab серверов
- `harbor_instances` — несколько Harbor registry
- `github_instances` — несколько GitHub конфигураций
- `docker_registry_instances` — несколько Docker registry
- `helm_repository_instances` — несколько Helm репозиториев

**Backend**:
- [`backend/app/schemas/integrations.py`](../backend/app/schemas/integrations.py) — Pydantic схемы для Create/Update/Out всех 5 типов инстансов + `ConnectionTestResult`
- [`backend/app/services/integrations.py`](../backend/app/services/integrations.py) — `IntegrationsService` (CRUD + test_connection для каждого типа), `ServiceFactory` (API-клиенты)
- [`backend/app/api/integrations.py`](../backend/app/api/integrations.py) — 30 REST эндпоинтов (6 per type × 5 types), защищены `require_permission("integrations:manage")`

**Frontend**:
- [`frontend/src/pages/Settings/Integrations/index.tsx`](../frontend/src/pages/Settings/Integrations/index.tsx) — страница с MUI Tabs, 5 панелей (GitLab/Harbor/GitHub/Docker Registry/Helm Repository), каждая с таблицей инстансов и операциями (Add/Edit/Delete/Test Connection)

**Тесты**:
- Backend unit: 10 тестов (service layer + encryption)
- Backend e2e: 87 тестов (CRUD + test connection + unauthorized для всех типов)
- Frontend: 8 тестов (tabs, instances list, CRUD dialog, delete confirmation, test connection success/failure)

**Миграции**:
- `20260606_2145_a66daaecc2fa_add_integration_instances.py` — gitlab/harbor/github
- `20260606_2220_b0714dde902c_add_docker_registry_and_helm_repo_.py` — docker registry/helm repo
- `20260607_0105_a1b2c3d4e5f6_add_integration_instance_fields.py` — verify_ssl, is_active, last_checked_at, status fields

### ✅ OIDC & Advanced (Phase 3) — ЗАВЕРШЁН (2026-06-07)

**Реализовано**:

**Новые таблицы**:
- `oidc_config` — конфигурация OIDC провайдера: `issuer_url`, `client_id`, `client_secret` (Fernet-зашифрован), `frontend_client_id`, `enabled`, `public_url`, `role_mapping` (JSON)

**Backend**:
- [`backend/app/models/oidc_config.py`](../backend/app/models/oidc_config.py) — модель `OIDCConfig`
- [`backend/app/schemas/oidc_config.py`](../backend/app/schemas/oidc_config.py) — `OIDCConfigOut`, `OIDCConfigUpdate`, `OIDCConfigPublicOut`
- [`backend/app/services/oidc_config.py`](../backend/app/services/oidc_config.py) — `OIDCConfigService`: CRUD + 60-секундный кэш с инвалидацией
- [`backend/app/services/oidc.py`](../backend/app/services/oidc.py) — `KeycloakOIDCService` рефакторен: читает конфигурацию из БД вместо env vars
- `role_mapping` (Keycloak roles → BigBug roles) теперь настраивается через UI вместо hardcoded frozenset

**Admin API**:
- `GET /api/auth/admin/oidc-config` — полная конфигурация (только admin)
- `PATCH /api/auth/admin/oidc-config` — обновление конфигурации
- `GET /api/auth/admin/oidc-config/public` — конфигурация без client_secret

**Frontend**:
- [`frontend/src/pages/Settings/Authentication/index.tsx`](../frontend/src/pages/Settings/Authentication/index.tsx) — страница настроек аутентификации: toggle OIDC, поля (Issuer URL, Client ID, Client Secret, Frontend Client ID, Public URL), таблица Role Mapping (CRUD)
- RTK Query endpoints: `getOidcConfig`, `updateOidcConfig`
- Навигационный пункт "Authentication" в Settings sidebar
- Маскирование client_secret (отображается пустым, отправляется только при изменении)

**Тесты**:
- Backend e2e: 20 тестов для OIDC Config API ([`backend/tests/e2e/test_oidc_config.py`](../backend/tests/e2e/test_oidc_config.py))
- Frontend unit: 39 тестов для страницы Authentication Settings ([`frontend/src/tests/AuthenticationSettings.test.tsx`](../frontend/src/tests/AuthenticationSettings.test.tsx)) — 7 категорий

**Миграции**:
- `20260607_0106_c7d8e9f0a1b2_add_oidc_config.py` — таблица oidc_config

## Что в процессе (рефакторинг)

## Известные ограничения

1. **Базовый RBAC**: 3 предустановленные роли + кастомные (Phase 1 завершён); нет UI для управления кастомными ролями
2. **Нет Pipeline UI**: управление пайплайнами только через GitLab
3. **Нет Audit Log**: история изменений не ведётся
4. **Нет Rate Limiting**: нет защиты от злоупотреблений

## Известные технические особенности

- `keycloak-js` 24.x не типизирует `codeChallenge` → URL для PKCE строится вручную
- `_NonClosingClient` в `oidc.py` — адаптер для тестирования httpx клиентов
- `Column` типы в SQLAlchemy дают false-positive в Pylance → `# type: ignore`
- `select(Role).where(False)` не работает → используется условное ветвление

## Следующие шаги

Согласно [`/docs/architecture/11-migration-strategy.md`](../docs/architecture/11-migration-strategy.md):

1. **Phase 1**: ✅ RBAC Foundation (permissions, custom roles, JWT update) — ЗАВЕРШЁН
2. **Phase 2**: ✅ Multi-instance integrations (GitLab, Harbor, GitHub, Docker, Helm) — ЗАВЕРШЁН
3. **Phase 3**: ✅ OIDC & Advanced (configurable OIDC, role mapping) — ЗАВЕРШЁН
4. **Phase 4**: Harbor integration, Pipeline management UI, Audit logging — следующий приоритет
