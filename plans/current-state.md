# BigBug — Текущее состояние

> Обновление: 2026-06-07

## Что реализовано

### Backend API

| Группа | Эндпоинты | Файл |
|--------|-----------|------|
| Auth | `POST /login`, `GET /me`, `GET /me/permissions`, `GET /sso/config`, `POST /oidc/exchange` | [`backend/app/api/auth.py`](backend/app/api/auth.py) |
| Admin | Users CRUD, Roles CRUD, `GET /permissions` | [`backend/app/api/admin.py`](backend/app/api/admin.py) |
| OIDC Config | `GET/PATCH /auth/admin/oidc-config`, `GET .../public` | [`backend/app/api/auth.py`](backend/app/api/auth.py) |
| Helm Charts | Источники CRUD, версии, индексация, sync trigger | [`backend/app/api/integrations/helm_repository.py`](backend/app/api/integrations/helm_repository.py) |
| Docker Images | Источники CRUD, теги, индексация, sync trigger | [`backend/app/api/integrations/docker_registry.py`](backend/app/api/integrations/docker_registry.py) |
| Mirrors | GitHub→GitLab зеркала, расписания, sync история | [`backend/app/api/mirrors.py`](backend/app/api/mirrors.py) |
| Gold/App Images | Образы CRUD, версии, build schedules, scan/sign статус | [`backend/app/api/gold_images.py`](backend/app/api/gold_images.py), [`backend/app/api/app_images.py`](backend/app/api/app_images.py) |
| Projects | GitHub projects | [`backend/app/api/projects.py`](backend/app/api/projects.py) |
| Integrations | CRUD для 5 типов: GitLab, Harbor, GitHub, Docker Registry, Helm Repository (30 эндпоинтов) | [`backend/app/api/integrations/`](backend/app/api/integrations/) |
| Pipelines | `GET` список, `POST` trigger, `GET`/{id}, `POST`/{id}/cancel, `POST`/{id}/retry | [`backend/app/api/pipelines.py`](backend/app/api/pipelines.py) |
| GitLab Components | CRUD компонентов CI/CD | [`backend/app/api/components.py`](backend/app/api/components.py) |
| Audit Log | `GET` с фильтрацией (user, action, resource, date range) | [`backend/app/api/audit.py`](backend/app/api/audit.py) |
| Webhooks | GitLab webhook: sync/build/helm/docker статусы | [`backend/app/api/webhooks.py`](backend/app/api/webhooks.py) |

**Сервисный слой** (бизнес-логика): [`backend/app/services/`](backend/app/services/)
`audit.py`, `build.py`, `cosign.py`, `docker.py`, `github.py`, `gitlab.py`, `harbor_scan.py`, `helm.py`, `integrations.py`, `oidc.py`, `oidc_config.py`, `pipeline.py`, `rbac_service.py`, `scheduler.py`

**Безопасность**: [`backend/app/core/`](backend/app/core/)
`rbac.py` (permission-based, JWT-кэширование), `rate_limit.py` (fastapi-limiter + pyrate_limiter), `secrets.py` (Fernet-шифрование credentials)

### Frontend UI

**Страницы** (все в [`frontend/src/pages/`](frontend/src/pages/)):
- `/` — Dashboard
- `/login`, `/sso/callback` — аутентификация
- `/projects` — GitHub проекты
- `/mirrors` — GitLab зеркала
- `/gold-images` — Gold образы
- `/app-images` — App образы
- `/helm-charts` — Helm чарты (список + детали)
- `/docker-images` — Docker образы (список + детали)
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
| `users` | Пользователи (local + SSO) |
| `roles` | Роли с `is_custom`, `created_by_user_id` |
| `user_roles` | M2M пользователи ↔ роли |
| `permissions` | 32 permission `resource:action` |
| `role_permissions` | M2M роли ↔ permissions |
| `oidc_config` | OIDC конфигурация (Fernet-encrypted client_secret) |
| `github_orgs`, `github_projects`, `github_releases` | GitHub интеграция |
| `gitlab_mirrors`, `sync_schedules`, `sync_logs` | Зеркалирование |
| `gold_images`, `app_images`, `image_versions`, `build_schedules`, `build_logs` | Образы и сборки |
| `helm_chart_sources`, `helm_chart_versions`, `helm_sync_logs` | Helm чарты |
| `docker_image_sources`, `docker_image_tags`, `docker_sync_logs` | Docker образы |
| `gitlab_instances`, `harbor_instances`, `github_instances`, `docker_registry_instances`, `helm_repository_instances` | Multi-instance интеграции |
| `pipeline_runs` | История запусков GitLab pipelines |
| `gitlab_components` | GitLab CI/CD компоненты |
| `audit_logs` | Аудит действий пользователей |

### Infrastructure

- **Docker Compose**: `docker-compose.infra.yml` + `docker-compose.app.yml`
- **Keycloak**: Realm `bigbug`, 3 роли, OpenTofu конфигурация в [`infrastructure/keycloak/`](infrastructure/keycloak/)
- **GitLab**: OpenTofu конфигурация в [`infrastructure/gitlab/`](infrastructure/gitlab/)
- **Harbor**: Deployment + Terraform в [`infrastructure/harbor/`](infrastructure/harbor/)
- **GitLab CI Templates** ([`infrastructure/gitlab-components/`](infrastructure/gitlab-components/)):
  - `gold-image-template.yml` — build → sign (cosign) → notify
  - `app-image-template.yml` — build → sign (cosign) → notify
  - `mirror-template.yml`, `helm-sync-template.yml`, `docker-sync-template.yml`

### Тесты

**Backend** ([`backend/tests/`](backend/tests/)):
- Unit: `test_audit_service.py`, `test_cosign_service.py`, `test_docker_service.py`, `test_harbor_scan_service.py`, `test_helm_service.py`, `test_integrations.py`, `test_oidc.py`, `test_pipeline_service.py`, `test_secrets.py`
- E2E: `test_oidc_config.py` (20), `test_integrations.py` (87) + файлы блоков 1-5

**Frontend** ([`frontend/src/tests/`](frontend/src/tests/)):
- ✅ Admin, AuditLog, AuthenticationSettings, authSlice, DockerImageDetail, DockerImages, HelmChartDetail, HelmCharts, Integrations, keycloak.service, Pipelines, SignatureBadge, SsoCallback, StatusChip, useKeycloakAuth, VulnerabilityBadge
- ❌ Отсутствуют: `Login.test.tsx`, `Dashboard.test.tsx`, `Mirrors.test.tsx`, `GoldImages.test.tsx`, `AppImages.test.tsx`, `Projects.test.tsx`

## Что осталось

### Недостающие frontend-тесты

Написать unit-тесты для страниц:
1. [`frontend/src/pages/Login/`](frontend/src/pages/Login/index.tsx) → `Login.test.tsx`
2. [`frontend/src/pages/Dashboard/`](frontend/src/pages/Dashboard/index.tsx) → `Dashboard.test.tsx`
3. [`frontend/src/pages/Mirrors/`](frontend/src/pages/Mirrors/index.tsx) → `Mirrors.test.tsx`
4. [`frontend/src/pages/GoldImages/`](frontend/src/pages/GoldImages/index.tsx) → `GoldImages.test.tsx`
5. [`frontend/src/pages/AppImages/`](frontend/src/pages/AppImages/index.tsx) → `AppImages.test.tsx`
6. [`frontend/src/pages/Projects/`](frontend/src/pages/Projects/index.tsx) → `Projects.test.tsx`
