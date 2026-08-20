# BigBug — Текущее состояние

> Обновление: 2026-06-13

## Что реализовано

### Backend API

| Группа | Эндпоинты | Файл |
|--------|-----------|------|
| | Auth | `POST /login`, `GET /me`, `GET /me/permissions`, `GET /sso/config`, `POST /oidc/exchange` | [`backend/app/api/auth.py`](backend/app/api/auth.py) |
| | Admin | Users CRUD, Roles CRUD, `GET /permissions` | [`backend/app/api/admin.py`](backend/app/api/admin.py) |
| | OIDC Config | `GET/PATCH /auth/admin/oidc-config`, `GET .../public` | [`backend/app/api/auth.py`](backend/app/api/auth.py) |
| | Helm Charts | Источники CRUD, версии, индексация, sync trigger | [`backend/app/api/integrations/helm_repository.py`](backend/app/api/integrations/helm_repository.py) |
| | Docker Images | Источники CRUD, теги, индексация, sync trigger | [`backend/app/api/integrations/docker_registry.py`](backend/app/api/integrations/docker_registry.py) |
| | Mirrors | GitHub→GitLab зеркала, расписания, sync история, soft delete/restore, orphaned, reports, bulk ops, integrity check | [`backend/app/api/mirrors.py`](backend/app/api/mirrors.py) |
| | Gold/App Images | Образы CRUD, версии, build schedules, scan/sign статус | [`backend/app/api/gold_images.py`](backend/app/api/gold_images.py), [`backend/app/api/app_images.py`](backend/app/api/app_images.py) |
| | Projects | GitHub projects | [`backend/app/api/projects.py`](backend/app/api/projects.py) |
| | Integrations | CRUD для 5 типов: GitLab, Harbor, GitHub, Docker Registry, Helm Repository (30 эндпоинтов) | [`backend/app/api/integrations/`](backend/app/api/integrations/) |
| | Pipelines | `GET` список, `POST` trigger, `GET`/{id}, `POST`/{id}/cancel, `POST`/{id}/retry | [`backend/app/api/pipelines.py`](backend/app/api/pipelines.py) |
| | GitLab Components | CRUD компонентов CI/CD | [`backend/app/api/components.py`](backend/app/api/components.py) |
| | Audit Log | `GET` с фильтрацией (user, action, resource, date range) | [`backend/app/api/audit.py`](backend/app/api/audit.py) |
| | Webhooks | GitLab webhook: sync/build/helm/docker статусы | [`backend/app/api/webhooks.py`](backend/app/api/webhooks.py) |
| | Reports | 4 типа отчётов: summary, sync history, failures, performance + CSV/JSON экспорт | [`backend/app/api/reports.py`](backend/app/api/reports.py) |
| | Bulk Operations | Массовые операции: sync, validate integrity, delete | [`backend/app/api/mirrors.py`](backend/app/api/mirrors.py) |
| | Orphaned Mirrors | Обнаружение осиротевших зеркал + relink API | [`backend/app/api/mirrors.py`](backend/app/api/mirrors.py) |
| | Cleanup Service | Фоновая очистка GitLab проектов для soft-deleted зеркал старше 7 дней (APScheduler) | [`backend/app/services/cleanup.py`](backend/app/services/cleanup.py) |

**Сервисный слой** (бизнес-логика): [`backend/app/services/`](backend/app/services/)
`audit.py`, `build.py`, `cleanup.py`, `cosign.py`, `docker.py`, `github.py`, `gitlab.py`, `harbor_scan.py`, `helm.py`, `integrations.py`, `oidc.py`, `oidc_config.py`, `pipeline.py`, `rbac_service.py`, `reports.py`, `scheduler.py`

**Безопасность**: [`backend/app/core/`](backend/app/core/)
`rbac.py` (permission-based, JWT-кэширование), `rate_limit.py` (fastapi-limiter + pyrate_limiter), `secrets.py` (Fernet-шифрование credentials)

### Frontend UI

**Страницы** (все в [`frontend/src/pages/`](frontend/src/pages/)):
- `/` — Dashboard
- `/login`, `/sso/callback` — аутентификация
- `/projects` — GitHub проекты
- `/git-mirroring` — Git Mirroring Dashboard (этап 9)
- `/git-mirroring/mirrors` — Зеркала (список, создание, импорт, процесс)
- `/git-mirroring/repositories` — Репозитории (список + детали)
- `/git-mirroring/source-groups` — Source Groups (импорт групп)
- `/git-mirroring/sync-groups` — Sync Groups
- `/git-mirroring/providers` — Source Providers (управление)
- `/git-mirroring/orphaned` — Осиротевшие зеркала + RelinkModal (этап 8.4)
- `/git-mirroring/reports` — Отчёты (4 типа + CSV/JSON экспорт) (этап 9)
- `/mirrors` — Редирект → `/git-mirroring/mirrors`
- `/helm-charts` — Редирект → `/git-mirroring` (устаревшие URL)
- `/docker-images` — Редирект → `/git-mirroring` (устаревшие URL)
- `/gold-images` — Gold образы
- `/app-images` — App образы
- `/pipelines` — Pipeline Runs (запуск, cancel, retry, фильтрация)
- `/admin` — Users + Roles (кастомные роли с permission-группами)
- `/settings/authentication` — OIDC настройки
- `/settings/integrations` — 5 типов интеграций (GitLab/Harbor/GitHub/Docker/Helm)
- `/settings/audit-log` — аудит (фильтрация, пагинация, детали)
- `/settings/pipelines` — GitLab CI/CD Components (CRUD)

**Компоненты**: `Layout`, `StatusChip`, `VulnerabilityBadge`, `SignatureBadge`, `ProtectedRoute`, `PermissionGate`

**Hooks**: `usePermissions` (`hasPermission`, `hasAnyPermission`, `hasAllPermissions`), `useKeycloakAuth`

### Database

**Таблицы** (см. [`backend/app/models/`](backend/app/models/) и Alembic миграции):

| Таблица | Назначение |
|---------|------------|
| | `users` | Пользователи (local + SSO) |
| | `roles` | Роли с `is_custom`, `created_by_user_id` |
| | `user_roles` | M2M пользователи ↔ роли |
| | `permissions` | 52 permission `resource:action` |
| | `role_permissions` | M2M роли ↔ permissions |
| | `oidc_config` | OIDC конфигурация (Fernet-encrypted client_secret) |
| | `github_orgs`, `github_projects`, `github_releases` | GitHub интеграция |
| | `gitlab_mirrors`, `sync_schedules`, `sync_logs` | Зеркалирование (GitHub→GitLab) |
| | `mirror_release_logs` | История soft-delete и release зеркал |
| | `sync_groups` | Группы синхронизации зеркал |
| | `source_providers` | Провайдеры источников (GitHub/GitLab) |
| | `gold_images`, `app_images`, `image_versions`, `build_schedules`, `build_logs` | Образы и сборки |
| | `helm_chart_sources`, `helm_chart_versions`, `helm_sync_logs` | Helm чарты |
| | `docker_image_sources`, `docker_image_tags`, `docker_sync_logs` | Docker образы |
| | `gitlab_instances`, `harbor_instances`, `github_instances`, `docker_registry_instances`, `helm_repository_instances` | Multi-instance интеграции |
| | `pipeline_runs` | История запусков GitLab pipelines |
| | `gitlab_components` | GitLab CI/CD компоненты |
| | `audit_logs` | Аудит действий пользователей |

### Infrastructure

- **Docker Compose**: [`infrastructure/docker-compose.yml`](infrastructure/docker-compose.yml) (infra) + [`docker-compose.yml`](docker-compose.yml) (app)
- **OpenTofu**: Root модуль в [`infrastructure/terraform/`](infrastructure/terraform/), подмодули в [`infrastructure/terraform/modules/`](infrastructure/terraform/modules/) (keycloak, harbor, gitlab)
- **Keycloak**: Realm `bigbug`, 3 роли, OpenTofu модуль [`infrastructure/terraform/modules/keycloak/`](infrastructure/terraform/modules/keycloak/)
- **GitLab**: OpenTofu модуль [`infrastructure/terraform/modules/gitlab/`](infrastructure/terraform/modules/gitlab/)
- **Harbor**: Deployment в kind ([`infrastructure/harbor/`](infrastructure/harbor/)) + OpenTofu модуль [`infrastructure/terraform/modules/harbor/`](infrastructure/terraform/modules/harbor/)
- **GitLab CI Templates** — рабочие пресеты вшиты в код ([`backend/app/services/gitlab_projects/presets.py`](backend/app/services/gitlab_projects/presets.py), отдаются через `GET /api/components/presets`). Исходные YAML сохранены как примеры в [`infrastructure/gitlab-components/examples/`](infrastructure/gitlab-components/examples/) (не используются приложением).

### Тесты

**Актуальные метрики (2026-06-13):**
- Backend: 723 теста
- Frontend: 323 теста
- Всего: 1046 тестов

**Backend** ([`backend/tests/`](backend/tests/)):
- Unit: `test_audit_service.py`, `test_cosign_service.py`, `test_docker_service.py`, `test_harbor_scan_service.py`, `test_helm_service.py`, `test_integrations.py`, `test_mirror_release_log_model.py`, `test_oidc.py`, `test_pipeline_service.py`, `test_reports.py`, `test_secrets.py`, `test_source_provider_gitlab.py`
- E2E: `test_oidc_config.py` (20), `test_integrations.py` (87) + файлы блоков 1-5 + этапов 8-9

**Frontend** ([`frontend/src/tests/`](frontend/src/tests/)):
- Unit: `Admin/`, `AuditLog/`, `AuthenticationSettings/`, `authSlice/`, `DockerImageDetail/`, `DockerImages/`, `HelmChartDetail/`, `HelmCharts/`, `Integrations/`, `keycloak.service/`, `Pipelines/`, `SignatureBadge/`, `SsoCallback/`, `StatusChip/`, `useKeycloakAuth/`, `VulnerabilityBadge/`
- Integration: `GitMirroringDashboard/`, `GitMirroringMirrors/`, `GitMirroringOrphaned/`, `GitMirroringProviders/`, `GitMirroringReports/`, `GitMirroringRepositories/`, `GitMirroringSyncGroups/`, `GitMirroringSourceGroups/`, `NavigationMenu/`

## Этапы Git Mirroring V2 (завершены)

| Этап | Описание | Статус |
|------|----------|--------|
| 1 | Source Providers API + модель | ✅ |
| 2 | Repository Discovery (Source Groups) | ✅ |
| 3 | Mirrors CRUD + Sync Schedules | ✅ |
| 4 | Sync Groups (групповая синхронизация) | ✅ |
| 5 | Integrity Check (проверка целостности) | ✅ |
| 6 | Frontend: Providers, Repositories, Source Groups | ✅ |
| 7 | Frontend: Mirrors, Sync Groups, Dashboard | ✅ |
| 8.1 | Soft Delete + Restore | ✅ |
| 8.2 | CleanupService + APScheduler | ✅ |
| 8.3 | HealthCheck + Integrity Check + Orphaned API | ✅ |
| 8.4 | Orphaned Mirrors страница + RelinkModal | ✅ |
| 9 | Reports, Bulk Operations, Роутинг, Редиректы | ✅ |

## Что осталось

### Финальные доработки
- Мониторинг и observability (Prometheus метрики)
- Производительность (оптимизация запросов, кэширование)
- E2E тесты (Cypress)
- CI/CD пайплайн для самого BigBug
