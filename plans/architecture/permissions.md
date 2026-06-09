# Permissions Index

> Единый источник истины для всех permissions. **Обязательно обновлять** при добавлении/изменении любых прав.

## Сводная таблица

| # | Permission | Назначение | Backend (seed) | Frontend (router) | Статус |
|---|-----------|------------|----------------|-------------------|--------|
| 1 | `mirrors:read` | Просмотр mirrors | A, O, V | — | только бэкенд |
| 2 | `mirrors:write` | Создание/изменение mirrors | A, O | — | только бэкенд |
| 3 | `mirrors:delete` | Удаление mirrors | A | — | только бэкенд |
| 4 | `mirrors:sync` | Запуск синхронизации | A, O | — | только бэкенд |
| 5 | `projects:read` | Просмотр проектов | A, O, V | `/mirroring/repositories`, `/:id` | ✅ |
| 6 | `projects:write` | Создание/изменение проектов | A, O | — | только бэкенд |
| 7 | `projects:delete` | Удаление проектов | A | — | только бэкенд |
| 8 | `helm:read` | Просмотр Helm charts | A, O, V | `/mirroring/helm-charts`, `/:id` | ✅ |
| 9 | `helm:write` | Создание/изменение sources | A, O | — | только бэкенд |
| 10 | `helm:delete` | Удаление sources | A | — | только бэкенд |
| 11 | `helm:sync` | Запуск синхронизации | A, O | — | только бэкенд |
| 12 | `helm:index` | Индексация index.yaml | A, O | — | только бэкенд |
| 13 | `docker:read` | Просмотр Docker images | A, O, V | `/mirroring/docker-images`, `/:id` | ✅ |
| 14 | `docker:write` | Создание/изменение sources | A, O | — | только бэкенд |
| 15 | `docker:delete` | Удаление sources | A | — | только бэкенд |
| 16 | `docker:sync` | Запуск синхронизации | A, O | — | только бэкенд |
| 17 | `docker:index` | Индексация через Registry API | A, O | — | только бэкенд |
| 18 | `gold_images:read` | Просмотр Gold Images | A, O, V | `/builds/gold-images` | ✅ |
| 19 | `gold_images:write` | Создание/изменение | A, O | — | только бэкенд |
| 20 | `gold_images:delete` | Удаление | A | — | только бэкенд |
| 21 | `gold_images:build` | Запуск сборки | A, O | — | только бэкенд |
| 22 | `app_images:read` | Просмотр App Images | A, O, V | `/builds/app-images` | ✅ |
| 23 | `app_images:write` | Создание/изменение | A, O | — | только бэкенд |
| 24 | `app_images:delete` | Удаление | A | — | только бэкенд |
| 25 | `app_images:build` | Запуск сборки | A, O | — | только бэкенд |
| 26 | `pipelines:read` | Просмотр запусков и компонентов | A, O, V | `/pipelines/runs`, `/pipelines/components` | ✅ |
| 27 | `pipelines:write` | Создание и запуск пайплайнов | A, O | — | только бэкенд |
| 28 | `pipelines:delete` | Отмена и удаление пайплайнов | A | — | только бэкенд |
| 29 | `users:read` | Просмотр пользователей | A, V | `/admin/users` | ✅ |
| 30 | `users:write` | Создание/изменение пользователей | A | — | только бэкенд |
| 31 | `users:delete` | Удаление пользователей | A | — | только бэкенд |
| 32 | `roles:read` | Просмотр ролей | A, V | — | только бэкенд |
| 33 | `roles:write` | Создание/изменение ролей | A | — | только бэкенд |
| 34 | `roles:delete` | Удаление ролей | A | — | только бэкенд |
| 35 | `system:config` | Изменение конфигурации системы | A | — | только бэкенд |
| 36 | `integrations:read` | Просмотр конфигураций интеграций | A, V | `/admin/integrations` | ✅ |
| 37 | `integrations:write` | Управление интеграциями | A | — | только бэкенд |
| 38 | `oidc:read` | Просмотр OIDC/OAuth2 конфигурации | A, V | `/admin/authentication` | ✅ |
| 39 | `oidc:write` | Управление OIDC/OAuth2 конфигурацией | A | — | только бэкенд |
| 40 | `audit:read` | Просмотр аудит лога | A, O, V | `/admin/audit` | ✅ |

**Обозначения:** A = Admin, O = Operator, V = Viewer. `—` = не используется (нет `PermissionGate` в роутере). `✅` = есть и в seed, и в роутере.

## Распределение по ролям

| Permission | Admin | Operator | Viewer |
|-----------|:-----:|:--------:|:------:|
| `mirrors:read` | ✅ | ✅ | ✅ |
| `mirrors:write` | ✅ | ✅ | |
| `mirrors:delete` | ✅ | | |
| `mirrors:sync` | ✅ | ✅ | |
| `projects:read` | ✅ | ✅ | ✅ |
| `projects:write` | ✅ | ✅ | |
| `projects:delete` | ✅ | | |
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

Источник: [`backend/docker/seed_admin.py`](backend/docker/seed_admin.py) — словари `ADMIN_PERMISSIONS`, `OPERATOR_PERMISSIONS`, `VIEWER_PERMISSIONS`.

## Легаси-права (существуют в БД, но не используются в API)

Эти permissions созданы предыдущими миграциями, но заменены на более гранулярные аналоги в новой модели RBAC. `seed_admin.py` их не назначает ролям, API не проверяет.

| Legacy Permission | Миграция | Заменён на |
|---|---|---|
| `integrations:manage` | [`a66daaecc2fa`](backend/alembic/versions/20260606_2145_a66daaecc2fa_add_integration_instances.py:27) | `integrations:read` + `integrations:write` |
| `docker_registry:manage` | [`b0714dde902c`](backend/alembic/versions/20260606_2220_b0714dde902c_add_docker_registry_and_helm_repo_.py:28) | — (управляется через integrations) |
| `helm_repository:manage` | [`b0714dde902c`](backend/alembic/versions/20260606_2220_b0714dde902c_add_docker_registry_and_helm_repo_.py:32) | — (управляется через integrations) |
| `pipelines:manage` | [`d1e2f3a4b5c6`](backend/alembic/versions/20260607_0352_d1e2f3a4b5c6_add_pipeline_runs_and_components.py:46) | `pipelines:write` + `pipelines:delete` |

## Примечание

Фронт получает permissions из JWT (`parseJwtPermissions()` в [`authSlice.ts`](frontend/src/store/authSlice.ts)). Бэкенд проверяет через `require_permission()` в [`rbac.py`](backend/app/core/rbac.py). Несовпадение имён → `PermissionGate` блокирует контент.
