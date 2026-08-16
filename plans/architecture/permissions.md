# Permissions Index

> Единый источник истины для всех permissions. **Обязательно обновлять** при добавлении/изменении любых прав.
> 
> **Последняя сверка:** 2026-08-16 — сброс миграций Alembic. Единый канонический сид RBAC теперь находится в миграции [`20260816_1200_a1b2c3d4e5f6_seed_initial_data.py`](backend/alembic/versions/20260816_1200_a1b2c3d4e5f6_seed_initial_data.py) (61 право, 110 связей `role_permissions`: admin=61, operator=34, viewer=15). Ранее права `providers:*`/`providers_system:*`/`teams:*`/`credentials:write` вставляла миграция `20260815_1108_0cce18c6c867_seed_providers_teams_permissions` — она удалена в составе сброса вместе с легаси-правами (`integrations:*`, `credentials:use`, `docker_registry:manage`, `helm_repository:manage`, `pipelines:manage`).

## Сводная таблица

| # | Permission | Назначение | Backend (seed) | Frontend (router) | Статус |
|---|-----------|------------|----------------|-------------------|--------|
| 1 | `mirrors:read` | Просмотр mirrors | A, O, V | `/git-mirroring/mirrors`, `/git-mirroring/dashboard` | ✅ |
| 2 | `mirrors:write` | Создание/изменение mirrors | A, O | — | только бэкенд |
| 3 | `mirrors:delete` | Удаление mirrors (soft delete) | A | — | только бэкенд |
| 4 | `mirrors:sync` | Запуск синхронизации | A, O | — | только бэкенд |
| 5 | `mirrors:import` | Импорт существующего зеркала | A, O | — | только бэкенд |
| 6 | `mirrors:integrity_check` | Проверка целостности target | A, O | — | только бэкенд |
| 7 | `mirrors:manage_orphaned` | Управление осиротевшими зеркалами | A | `/git-mirroring/orphaned` | ✅ |
| 8 | `projects:read` | Просмотр проектов (GithubProject) | A, O, V | `/projects`, `/:id` | ✅ |
| 9 | `projects:write` | Создание/изменение проектов | A, O | — | только бэкенд |
| 10 | `projects:delete` | Удаление проектов | A | — | только бэкенд |
| 11 | `source_groups:read` | Просмотр Source Groups и репозиториев | A, O, V | `/git-mirroring/sources` | ✅ |
| 12 | `source_groups:write` | Импорт/изменение Source Groups | A, O | — | только бэкенд |
| 13 | `source_groups:refresh` | Обновление списка репозиториев | A, O | — | только бэкенд |
| 14 | `helm:read` | Просмотр Helm charts | A, O, V | `/helm-charts`, `/:id` | ✅ |
| 15 | `helm:write` | Создание/изменение sources | A, O | — | только бэкенд |
| 16 | `helm:delete` | Удаление sources | A | — | только бэкенд |
| 17 | `helm:sync` | Запуск синхронизации | A, O | — | только бэкенд |
| 18 | `helm:index` | Индексация index.yaml | A, O | — | только бэкенд |
| 19 | `docker:read` | Просмотр Docker images | A, O, V | `/docker-images`, `/:id` | ✅ |
| 20 | `docker:write` | Создание/изменение sources | A, O | — | только бэкенд |
| 21 | `docker:delete` | Удаление sources | A | — | только бэкенд |
| 22 | `docker:sync` | Запуск синхронизации | A, O | — | только бэкенд |
| 23 | `docker:index` | Индексация через Registry API | A, O | — | только бэкенд |
| 24 | `gold_images:read` | Просмотр Gold Images | A, O, V | `/builds/gold-images` | ✅ |
| 25 | `gold_images:write` | Создание/изменение | A, O | — | только бэкенд |
| 26 | `gold_images:delete` | Удаление | A | — | только бэкенд |
| 27 | `gold_images:build` | Запуск сборки | A, O | — | только бэкенд |
| 28 | `app_images:read` | Просмотр App Images | A, O, V | `/builds/app-images` | ✅ |
| 29 | `app_images:write` | Создание/изменение | A, O | — | только бэкенд |
| 30 | `app_images:delete` | Удаление | A | — | только бэкенд |
| 31 | `app_images:build` | Запуск сборки | A, O | — | только бэкенд |
| 32 | `pipelines:read` | Просмотр запусков, компонентов и конфигураций | A, O, V | `/pipelines/runs`, `/pipelines/components` | ✅ |
| 33 | `pipelines:write` | Создание конфигураций и запуск пайплайнов | A, O | — | только бэкенд |
| 34 | `pipelines:delete` | Удаление конфигураций и отмена запусков | A | — | только бэкенд |
| 35 | `sync_groups:read` | Просмотр Sync Groups | A, O, V | `/git-mirroring/sync-groups` | ✅ |
| 36 | `sync_groups:write` | Создание/изменение Sync Groups | A, O | — | только бэкенд |
| 37 | `sync_groups:delete` | Удаление Sync Groups | A | — | только бэкенд |
| 38 | `credentials:read` | Просмотр учётных данных (list/get) | A | `/admin/credentials` | ✅ (проверяется с фазы 5) |
| 39 | `credentials:write` | Создание/изменение/удаление/тест учётных данных | A | `/admin/credentials` | ✅ (проверяется с фазы 5) |
| 40 | `reports:read` | Генерация отчётов зеркалирования | A | `/git-mirroring/reports` | ✅ |
| 41 | `users:read` | Просмотр пользователей | A, V | `/admin/users` | ✅ |
| 42 | `users:write` | Создание/изменение пользователей | A | — | только бэкенд |
| 43 | `users:delete` | Удаление пользователей | A | — | только бэкенд |
| 44 | `roles:read` | Просмотр ролей и scope | A, V | — | только бэкенд |
| 45 | `roles:write` | Создание/изменение ролей (включая scope) | A | — | только бэкенд |
| 46 | `roles:delete` | Удаление ролей | A | — | только бэкенд |
| 47 | `system:config` | Изменение конфигурации системы (cleanup) | A | — | только бэкенд |
| 48 | `oidc:read` | Просмотр OIDC/OAuth2 конфигурации | A, V | `/admin/authentication` | ✅ |
| 49 | `oidc:write` | Управление OIDC/OAuth2 конфигурацией | A | — | только бэкенд |
| 50 | `audit:read` | Просмотр аудит лога | A, O, V | `/admin/audit` | ✅ |
| 51 | `admin:panel:access` | Доступ к Admin Panel (отдельный интерфейс) | A | Header кнопка «Admin Panel» → `AdminLayout` | ✅ |
| 52 | `providers:read` | list/get public+system (+ private свои) | A, O, V | `/settings/providers` | ✅ |
| 53 | `providers:write` | create/update/test public+свои private (кроме `is_default`) | A, O | — | только бэкенд |
| 54 | `providers:delete` | delete public+свои private | A | — | только бэкенд |
| 55 | `providers:use` | доменные действия (list_repositories и т.д.) | A, O | — | только бэкенд |
| 56 | `providers:read_all` | видеть все private всех пользователей | A | — | только бэкенд |
| 57 | `providers_system:write` | create/update/delete system-категории + назначение default-провайдера (`is_default`) | A | — | только бэкенд |
| 58 | `providers:share` | share/unshare своих провайдеров команде | A, O | — | только бэкенд |
| 59 | `teams:read` | список своих команд + карточка | A, O, V | `/profile` (My teams) | ✅ |
| 60 | `teams:write` | создание/изменение/удаление команд (админ) | A | `/admin/teams` | ✅ |
| 61 | `teams:manage_members` | добавление/удаление участников (админ; лид — scope) | A | — | только бэкенд |

**Обозначения:** A = Admin, O = Operator, V = Viewer. `—` = не используется (нет `PermissionGate` в роутере). `✅` = есть и в seed, и в роутере.

## Распределение по ролям

| Permission | Admin | Operator | Viewer |
|-----------|:-----:|:--------:|:------:|
| `mirrors:read` | ✅ | ✅ | ✅ |
| `mirrors:write` | ✅ | ✅ | |
| `mirrors:delete` | ✅ | | |
| `mirrors:sync` | ✅ | ✅ | |
| `mirrors:import` | ✅ | ✅ | |
| `mirrors:integrity_check` | ✅ | ✅ | |
| `mirrors:manage_orphaned` | ✅ | | |
| `projects:read` | ✅ | ✅ | ✅ |
| `projects:write` | ✅ | ✅ | |
| `projects:delete` | ✅ | | |
| `source_groups:read` | ✅ | ✅ | ✅ |
| `source_groups:write` | ✅ | ✅ | |
| `source_groups:refresh` | ✅ | ✅ | |
| `helm:read` | ✅ | ✅ | ✅ |
| `helm:write` | ✅ | ✅ | |
| `helm:delete` | ✅ | | |
| `helm:sync` | ✅ | ✅ | |
| `helm:index` | ✅ | ✅ | |
| `docker:read` | ✅ | ✅ | ✅ |
| `docker:write` | ✅ | ✅ | |
| `docker:delete` | ✅ | | |
| `docker:sync` | ✅ | ✅ | |
| `docker:index` | ✅ | ✅ | |
| `gold_images:read` | ✅ | ✅ | ✅ |
| `gold_images:write` | ✅ | ✅ | |
| `gold_images:delete` | ✅ | | |
| `gold_images:build` | ✅ | ✅ | |
| `app_images:read` | ✅ | ✅ | ✅ |
| `app_images:write` | ✅ | ✅ | |
| `app_images:delete` | ✅ | | |
| `app_images:build` | ✅ | ✅ | |
| `pipelines:read` | ✅ | ✅ | ✅ |
| `pipelines:write` | ✅ | ✅ | |
| `pipelines:delete` | ✅ | | |
| `sync_groups:read` | ✅ | ✅ | ✅ |
| `sync_groups:write` | ✅ | ✅ | |
| `sync_groups:delete` | ✅ | | |
| `credentials:read` | ✅ | | |
| `credentials:write` | ✅ | | |
| `reports:read` | ✅ | | |
| `users:read` | ✅ | | ✅ |
| `users:write` | ✅ | | |
| `users:delete` | ✅ | | |
| `roles:read` | ✅ | | ✅ |
| `roles:write` | ✅ | | |
| `roles:delete` | ✅ | | |
| `system:config` | ✅ | | |
| `oidc:read` | ✅ | | ✅ |
| `oidc:write` | ✅ | | |
| `audit:read` | ✅ | ✅ | ✅ |
| `admin:panel:access` | ✅ | | |
| `providers:read` | ✅ | ✅ | ✅ |
| `providers:write` | ✅ | ✅ | |
| `providers:delete` | ✅ | | |
| `providers:use` | ✅ | ✅ | |
| `providers:read_all` | ✅ | | |
| `providers_system:write` | ✅ | | |
| `providers:share` | ✅ | ✅ | |
| `teams:read` | ✅ | ✅ | ✅ |
| `teams:write` | ✅ | | |
| `teams:manage_members` | ✅ | | |

Источник: [`backend/docker/seed_admin.py`](backend/docker/seed_admin.py) — словари `ADMIN_PERMISSIONS`, `OPERATOR_PERMISSIONS`, `VIEWER_PERMISSIONS` (декларируют канонический набор). С 2026-08-16 фактический сидинг в БД выполняет миграция [`20260816_1200_a1b2c3d4e5f6_seed_initial_data.py`](backend/alembic/versions/20260816_1200_a1b2c3d4e5f6_seed_initial_data.py) (вставляет 61 право и 110 связей и назначает их ролям: admin=61, operator=34, viewer=15). `seed_admin.py` списки декларирует, но сам их в БД не применяет — он создаёт только админ-пользователя; миграции для этого достаточно, поскольку entrypoint всегда выполняет `alembic upgrade head` до запуска сида.

## Легаси-права (удалены в фазе 5)

Эти permissions были созданы предыдущими миграциями и удалены чистящей миграцией фазы 5 ([`20260815_0000_b8d4e5f6a7c9_remove_legacy_permissions.py`](backend/alembic/versions/20260815_0000_b8d4e5f6a7c9_remove_legacy_permissions.py)). Физически отсутствуют в БД после `alembic upgrade head`.

| Удалённое право | Бывшая миграция | Заменён на |
|---|---|---|
| `integrations:read` | `745f271b2faf` | `providers:read` |
| `integrations:write` | `745f271b2faf` | `providers:write` + `providers_system:write` |
| `integrations:manage` | [`a66daaecc2fa`](backend/alembic/versions/20260606_2145_a66daaecc2fa_add_integration_instances.py:27) | `providers:read` + `providers:write` |
| `docker_registry:manage` | `b0714dde902c` | — (управляется через providers) |
| `helm_repository:manage` | `b0714dde902c` | — (управляется через providers) |
| `pipelines:manage` | `d1e2f3a4b5c6` | `pipelines:write` + `pipelines:delete` |
| `credentials:use` | `b214fda62040` | внутренняя логика провайдеров (не проверяется) |

## Примечания

### `credentials:read` / `credentials:write`

С фазы 5 эндпоинты [`credentials.py`](backend/app/api/credentials.py) используют `credentials:read` (list/get) и `credentials:write` (create/update/delete/test). Право `credentials:read` ранее было назначено, но не проверялось; `credentials:write` — новое право, заменившее `integrations:write` в этом роутере.

Фронтенд в `RoleModal.tsx` группирует их под лейблом «Credentials» для UI-редактора ролей.

### Системные эндпоинты

[`health_check.py`](backend/app/api/health_check.py) использует `require_admin()` (проверка роли, не permission), так как health-check — системная операция, не привязанная к конкретному ресурсу. Это единственное оставшееся использование `require_admin()` во всём API.

### Механизм проверки

Фронт получает permissions из JWT (`parseJwtPermissions()` в [`authSlice.ts`](frontend/src/store/authSlice.ts)). Бэкенд проверяет через `require_permission()` в [`rbac.py`](backend/app/core/rbac.py). Несовпадение имён → `PermissionGate` блокирует контент.

### История изменений

| Дата | Изменение |
|------|-----------|
| 2026-08-15 | Root-cause fix RBAC: добавлена миграция `20260815_1108_0cce18c6c867_seed_providers_teams_permissions`, реально сидящая `providers:*`/`teams:*`/`credentials:write` в `permissions` + `role_permissions` (ранее были только в `seed_admin.py`, но не в БД). |
| 2026-08-15 | Фаза 7F Providers V3: выпил legacy-таблиц/роутеров (`api/integrations/`, `services/integrations.py`, instance-модели, `source_providers`). Роутеры `/settings/providers`, `/admin/credentials`, `/settings/teams`, `/admin/teams` — окончательные. `source_groups:read` привязан к `/git-mirroring/sources`. |
| 2026-08-15 | Фаза 5 Providers V3: добавлены `providers:read/write/delete/use/read_all`, `providers_system:write`, `providers:share`, `teams:read/write/manage_members`, `credentials:write`; `credentials:read` начат реально проверяться; удалены `integrations:read/write/manage`, `docker_registry:manage`, `helm_repository:manage`, `pipelines:manage`, `credentials:use` |
| 2026-06-14 | Глобальная сверка и исправление: заменены `require_admin()` → `require_permission()` в `admin.py` и `auth.py`; исправлены `PermissionGate` в роутере для git-mirroring; интеграции переведены с легаси-прав на `integrations:read`/`integrations:write`; `audit.py`: `users:read` → `audit:read`; `seed_admin.py`: добавлено 6 прав оператору; все `require_operator()`/`require_viewer()` заменены на `require_permission()` в domain API |
