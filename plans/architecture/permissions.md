# Permissions Index

> Единый источник истины для всех permissions. **Обязательно обновлять** при добавлении/изменении любых прав.
> 
> **Последняя сверка:** 2026-06-14 — все бэкенд-эндпоинты и фронтенд-роуты сверены с этой таблицей.

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
| 11 | `source_groups:read` | Просмотр Source Groups и репозиториев | A, O, V | `/git-mirroring/repositories`, `/git-mirroring/groups`, `/git-mirroring/providers` | ✅ |
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
| 38 | `credentials:read` | Просмотр учётных данных | A | `/admin/integrations` (credentials tab) | ⚠️ см. примечание |
| 39 | `credentials:use` | Использование учётных данных (для source providers) | A, O | — | ⚠️ см. примечание |
| 40 | `reports:read` | Генерация отчётов зеркалирования | A | `/git-mirroring/reports` | ✅ |
| 41 | `users:read` | Просмотр пользователей | A, V | `/admin/users` | ✅ |
| 42 | `users:write` | Создание/изменение пользователей | A | — | только бэкенд |
| 43 | `users:delete` | Удаление пользователей | A | — | только бэкенд |
| 44 | `roles:read` | Просмотр ролей и scope | A, V | — | только бэкенд |
| 45 | `roles:write` | Создание/изменение ролей (включая scope) | A | — | только бэкенд |
| 46 | `roles:delete` | Удаление ролей | A | — | только бэкенд |
| 47 | `system:config` | Изменение конфигурации системы (cleanup) | A | — | только бэкенд |
| 48 | `integrations:read` | Просмотр конфигураций интеграций | A, V | `/admin/integrations` | ✅ |
| 49 | `integrations:write` | Управление интеграциями | A | — | только бэкенд |
| 50 | `oidc:read` | Просмотр OIDC/OAuth2 конфигурации | A, V | `/admin/authentication` | ✅ |
| 51 | `oidc:write` | Управление OIDC/OAuth2 конфигурацией | A | — | только бэкенд |
| 52 | `audit:read` | Просмотр аудит лога | A, O, V | `/admin/audit` | ✅ |
| 53 | `admin:panel:access` | Доступ к Admin Panel (отдельный интерфейс) | A | Header кнопка «Admin Panel» → `AdminLayout` | ✅ |
**Обозначения:** A = Admin, O = Operator, V = Viewer. `—` = не используется (нет `PermissionGate` в роутере). `✅` = есть и в seed, и в роутере. `⚠️` = см. примечание.

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
| `credentials:use` | ✅ | ✅ | |
| `reports:read` | ✅ | | |
| `users:read` | ✅ | | ✅ |
| `users:write` | ✅ | | |
| `users:delete` | ✅ | | |
| `roles:read` | ✅ | | ✅ |
| `roles:write` | ✅ | | |
| `roles:delete` | ✅ | | |
| `system:config` | ✅ | | |
| `integrations:read` | ✅ | | ✅ |
| `integrations:write` | ✅ | | |
| `oidc:read` | ✅ | | ✅ |
| `oidc:write` | ✅ | | |
| `audit:read` | ✅ | ✅ | ✅ |
| `admin:panel:access` | ✅ | | |
Источник: [`backend/docker/seed_admin.py`](backend/docker/seed_admin.py) — словари `ADMIN_PERMISSIONS`, `OPERATOR_PERMISSIONS`, `VIEWER_PERMISSIONS`.

## Легаси-права (существуют в БД, но не используются в API)

Эти permissions созданы предыдущими миграциями, но заменены на более гранулярные аналоги в новой модели RBAC. `seed_admin.py` их не назначает ролям, API не проверяет.

| Legacy Permission | Миграция | Заменён на |
|---|---|---|
| `integrations:manage` | [`a66daaecc2fa`](backend/alembic/versions/20260606_2145_a66daaecc2fa_add_integration_instances.py:27) | `integrations:read` + `integrations:write` |
| `docker_registry:manage` | [`b0714dde902c`](backend/alembic/versions/20260606_2220_b0714dde902c_add_docker_registry_and_helm_repo_.py:28) | — (управляется через integrations) |
| `helm_repository:manage` | [`b0714dde902c`](backend/alembic/versions/20260606_2220_b0714dde902c_add_docker_registry_and_helm_repo_.py:32) | — (управляется через integrations) |
| `pipelines:manage` | [`d1e2f3a4b5c6`](backend/alembic/versions/20260607_0352_d1e2f3a4b5c6_add_pipeline_runs_and_components.py:46) | `pipelines:write` + `pipelines:delete` |

## Примечания

### ⚠️ `credentials:read` и `credentials:use`

Эти права назначены ролям через [`seed_admin.py`](backend/docker/seed_admin.py), но **фактически не проверяются** ни в одном API-эндпоинте. Эндпоинты [`credentials.py`](backend/app/api/credentials.py) используют `integrations:read` (list/get) и `integrations:write` (create/update/delete/test). Права `credentials:read`/`credentials:use` зарезервированы для будущего использования — когда credentials получат собственный permission check вместо проксирования через integrations.

Фронтенд в [`RoleModal.tsx`](frontend/src/pages/Admin/Roles/RoleModal.tsx:89) группирует их под лейблом «Credentials» для UI-редактора ролей.

### Системные эндпоинты

[`health_check.py`](backend/app/api/health_check.py) использует `require_admin()` (проверка роли, не permission), так как health-check — системная операция, не привязанная к конкретному ресурсу. Это единственное оставшееся использование `require_admin()` во всём API.

### Механизм проверки

Фронт получает permissions из JWT (`parseJwtPermissions()` в [`authSlice.ts`](frontend/src/store/authSlice.ts)). Бэкенд проверяет через `require_permission()` в [`rbac.py`](backend/app/core/rbac.py). Несовпадение имён → `PermissionGate` блокирует контент.

### История изменений

| Дата | Изменение |
|------|-----------|
| 2026-06-14 | Глобальная сверка и исправление: заменены `require_admin()` → `require_permission()` в `admin.py` и `auth.py`; исправлены `PermissionGate` в роутере для git-mirroring; интеграции переведены с легаси-прав на `integrations:read`/`integrations:write`; `audit.py`: `users:read` → `audit:read`; `seed_admin.py`: добавлено 6 прав оператору; все `require_operator()`/`require_viewer()` заменены на `require_permission()` в domain API |
