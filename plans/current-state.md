# BigBug - Current State

> Последнее обновление: 2026-06-05
> Статус: Блоки 1-5 завершены, идёт рефакторинг архитектуры

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

**Компоненты**:
- `Layout` - навигация + sidebar
- `StatusChip` - унифицированный статус
- `ProtectedRoute` - защищённые маршруты

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
- `roles` - роли (admin/operator/viewer)
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

**Миграции**:
- `20260605_0449_39774f94ac35_initial_schema.py` - базовая схема
- `20260605_0747_add_helm_tables.py` - Helm таблицы
- `20260605_1200_add_docker_tables.py` - Docker таблицы

## Что в процессе (рефакторинг)

### 🚧 RBAC (Phase 1)

**Цель**: Переход от role-based к permission-based модели

**Новые таблицы** (планируются):
- `permissions` - глобальные permissions (`resource:action`)
- `role_permissions` - M2M роли ↔ permissions
- Расширение `roles` (кастомные роли)
- Расширение `users` (email как primary identifier)

**Новые API** (планируются):
- `GET/POST /api/v1/admin/roles` - управление ролями
- `GET/POST /api/v1/admin/permissions` - управление permissions
- `GET /api/v1/auth/me/permissions` - permissions текущего пользователя

**Текущий RBAC**: [`backend/app/core/rbac.py`](../backend/app/core/rbac.py)
- `require_admin()`, `require_operator()`, `require_viewer()` dependencies
- Простая role-based проверка

### 🚧 Multi-instance Integrations (Phase 2)

**Цель**: Управление несколькими инстансами GitLab/Harbor/GitHub через UI

**Новые таблицы** (планируются):
- `gitlab_instances` - несколько GitLab серверов
- `harbor_instances` - несколько Harbor registry
- `github_integrations` - GitHub конфигурации
- `docker_registry_integrations` - Docker registry
- `helm_repository_integrations` - Helm репозитории
- `oidc_config` - OIDC конфигурация

**Текущее состояние**: конфигурации жёстко закодированы в `.env`

## Известные ограничения

1. **Одиночные интеграции**: только один GitLab, один GitHub, один Docker registry
2. **Простой RBAC**: только 3 роли без кастомизации
3. **Нет Harbor**: Harbor интеграция не реализована
4. **Нет Pipeline UI**: управление пайплайнами только через GitLab
5. **Нет Audit Log**: история изменений не ведётся
6. **Нет Rate Limiting**: нет защиты от злоупотреблений

## Известные технические особенности

- `keycloak-js` 24.x не типизирует `codeChallenge` → URL для PKCE строится вручную
- `_NonClosingClient` в `oidc.py` — адаптер для тестирования httpx клиентов
- `Column` типы в SQLAlchemy дают false-positive в Pylance → `# type: ignore`
- `select(Role).where(False)` не работает → используется условное ветвление

## Следующие шаги

Согласно [`/docs/architecture/11-migration-strategy.md`](../docs/architecture/11-migration-strategy.md):

1. **Phase 1**: RBAC Foundation (permissions, custom roles, JWT update)
2. **Phase 2**: Multi-instance integrations (GitLab, Harbor, GitHub, Docker, Helm)
3. **Phase 3**: OIDC & Advanced (configurable OIDC, role mapping)
4. **Phase 4**: Polish (audit log, rate limiting, Admin UI)
