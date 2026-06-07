# PRD: Phase 4 — Production Readiness & Pipeline Management

> **Дата**: 2026-06-07
> **Контекст**: Фазы 1-3 завершены (RBAC, Multi-instance Integrations, OIDC). Реализована базовая функциональность платформы.
> **Цель Phase 4**: Production-ready платформа — управление пайплайнами, аудит, безопасность, подпись образов.

---

## 1. Role Management UI

### Введение

API для управления кастомными ролями реализован в Phase 1 (CRUD через [`/api/admin/roles`](../backend/app/api/admin.py)), но отсутствует фронтенд. Администратор не может создавать, редактировать или удалять кастомные роли через UI — только через API.

### Goals

- Администратор управляет ролями через UI без обращения к API напрямую
- Создание роли с произвольным набором permissions
- Редактирование только кастомных ролей (builtin защищены)
- Визуальная группировка 32 permissions по ресурсам

### User Stories

1. Как администратор, я хочу видеть список всех ролей (builtin + custom), чтобы понимать доступные уровни доступа
2. Как администратор, я хочу создать кастомную роль с выбранными permissions, чтобы делегировать ограниченный доступ
3. Как администратор, я хочу редактировать permissions кастомной роли, чтобы адаптировать доступ под изменившиеся требования
4. Как администратор, я хочу удалить неиспользуемую кастомную роль, чтобы поддерживать порядок

### Functional Requirements

1. Вкладка «Roles» на странице [`/admin`](../frontend/src/pages/Admin/index.tsx) (рядом с существующей «User Management»)
2. Таблица ролей: Name, Description, Type (Builtin/Custom), Permissions count, Created by, Actions
3. Builtin-роли отмечены иконкой 🔒, кнопки Edit/Delete заблокированы
4. Форма создания/редактирования: Name, Description, 32 чекбокса, сгруппированных по ресурсам (mirrors, projects, helm, docker, gold_images, app_images, users, roles, system) с «Select All» для каждой группы
5. Удаление с подтверждением (диалог), backend должен вернуть ошибку если у роли есть пользователи
6. RTK Query endpoints уже существуют — нужно только задействовать их во фронтенде

### Non-Goals

- Изменение состава permissions (32 фиксированных)
- Массовые операции над ролями

### Technical Considerations

- Использовать существующие RTK Query endpoints: `getAllRoles`, `createRole`, `updateRole`, `deleteRole`
- [`PermissionGate`](../frontend/src/components/PermissionGate.tsx) для кнопок Edit/Delete: `roles:write` / `roles:delete`
- MUI: Tabs (Users / Roles), Table, Dialog, Checkbox groups

### Success Metrics

- Администратор может создать кастомную роль за < 1 минуты
- 100% кастомных ролей управляются через UI (не через curl)

---

## 2. Rate Limiting

### Введение

Платформа не имеет защиты от brute-force атак на логин и злоупотребления API. Требуется добавить rate limiting как минимум на auth endpoints.

### Goals

- Защита `/api/auth/login` от перебора паролей
- Общие лимиты на API для предотвращения злоупотреблений
- Настраиваемые лимиты через конфигурацию

### User Stories

1. Как администратор, я хочу чтобы система блокировала повторные попытки логина, чтобы предотвратить brute-force атаки
2. Как DevOps, я хочу настраивать лимиты через переменные окружения без изменения кода

### Functional Requirements

1. `slowapi` с Redis backend для хранения счётчиков
2. Лимит `5/minute` на `POST /api/auth/login`
3. Лимит `3/minute` на `POST /api/auth/oidc/exchange`
4. Общий лимит `100/minute` на все API (настраиваемый)
5. Заголовки `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` в ответах
6. Ответ 429 с телом `{"detail": "Too many requests", "retry_after": 30}`
7. Конфигурация через `config.py`: `RATE_LIMIT_ENABLED`, `RATE_LIMIT_LOGIN`, `RATE_LIMIT_GLOBAL`

### Non-Goals

- Per-user неравномерные лимиты
- IP whitelist
- Rate limiting на уровне nginx/reverse-proxy (это отдельно)

### Technical Considerations

- `slowapi` использует `limits` декоратор, интегрируется с FastAPI через `Limiter` + `@limiter.limit`
- Redis уже есть в инфраструктуре — используется как storage
- Добавить `slowapi` и `redis` (python client) в [`pyproject.toml`](../backend/pyproject.toml)

### Success Metrics

- 5 неудачных попыток логина за 1 минуту → 429 на 6-й
- Отсутствие влияния на latency (< 1ms overhead)

---

## 3. Pipeline Runs API + UI

### Введение

BigBug управляет CI/CD через GitLab, но не предоставляет UI для просмотра и запуска пайплайнов. Пользователи вынуждены переходить в GitLab. Требуется API и UI для управления пайплайнами из BigBug.

### Goals

- Просмотр истории запусков пайплайнов в BigBug UI
- Запуск пайплайнов из BigBug (manual trigger)
- Отслеживание статуса через webhook от GitLab
- Управление GitLab Components (переиспользуемые CI/CD блоки)

### User Stories

1. Как оператор, я хочу видеть историю всех пайплайнов с фильтрацией по статусу, чтобы отслеживать состояние сборок
2. Как оператор, я хочу запустить пайплайн из BigBug UI с указанием ветки и переменных, чтобы не переключаться в GitLab
3. Как оператор, я хочу отменить или повторить пайплайн, чтобы управлять ошибочными запусками
4. Как администратор, я хочу управлять GitLab Components (добавлять, редактировать), чтобы предоставлять переиспользуемые CI/CD блоки командам

### Functional Requirements

**Модели:**

1. `pipeline_runs` — история запусков:
   - `id`, `gitlab_instance_id`, `gitlab_project_id`, `gitlab_pipeline_id`
   - `triggered_by_user_id`, `trigger_type` (manual/scheduled/webhook)
   - `ref` (branch/tag/commit), `variables` (JSON)
   - `status_flag`, `status_text`, `duration`
   - `web_url` (ссылка на GitLab), `created_at`, `started_at`, `finished_at`

2. `gitlab_components` — каталог компонентов:
   - `id`, `name`, `description`
   - `gitlab_instance_id`, `project_path`, `component_path`
   - `version`, `inputs_schema` (JSON Schema), `is_enabled`

**API Endpoints:**

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/api/pipelines` | История (пагинация, фильтр по статусу) |
| `POST` | `/api/pipelines` | Запустить пайплайн |
| `GET` | `/api/pipelines/{id}` | Детали запуска |
| `POST` | `/api/pipelines/{id}/cancel` | Отменить |
| `POST` | `/api/pipelines/{id}/retry` | Повторить |
| `GET` | `/api/components` | Список компонентов |
| `POST` | `/api/components` | Добавить компонент |
| `GET` | `/api/components/{id}` | Детали |
| `PATCH` | `/api/components/{id}` | Обновить |
| `DELETE` | `/api/components/{id}` | Удалить |
| `POST` | `/api/components/{id}/run` | Запустить компонент |

**Webhook:**

- Доработать [`/api/webhooks/gitlab`](../backend/app/api/webhooks.py) для обработки `pipeline` events
- Обновлять `pipeline_runs.status_flag` при получении webhook

**UI Страницы:**

1. `/pipelines` — страница Pipeline Runs:
   - Таблица: #ID, Project, Ref, Status, Duration, Created
   - Фильтр: All / Running / Success / Failed
   - Кнопка «Run Pipeline» → диалог выбора GitLab instance, project, ref, variables
   - Действия: Cancel, Retry

2. `/settings/pipelines/components` — страница GitLab Components:
   - Таблица: Name, Path, Version, Status
   - Кнопка «Add Component» → форма с полями
   - Действия: Edit, Delete

### Non-Goals

- Создание/редактирование `.gitlab-ci.yml` через UI
- Просмотр логов джобов в реальном времени
- Pipeline analytics / статистика (фаза 2)

### Technical Considerations

- Сервис `PipelineService` — вызов GitLab API для trigger/cancel/retry
- Переиспользовать [`ServiceFactory`](../backend/app/services/integrations.py) для получения GitLab instance
- RTK Query + периодический refetch для обновления статуса running-пайплайнов
- Permission: `pipelines:manage` (добавить в permissions)
- Миграция Alembic

### Success Metrics

- Оператор запускает пайплайн из BigBug за < 30 секунд
- Статус пайплайна обновляется в UI в течение 10 секунд после завершения в GitLab

---

## 4. Audit Logging

### Введение

Отсутствует журнал действий — невозможно отследить, кто и когда внёс изменения. Требуется audit log для безопасности и compliance.

### Goals

- Запись всех мутирующих операций (create/update/delete) в БД
- API для просмотра и фильтрации audit-записей
- UI для администратора

### User Stories

1. Как администратор, я хочу видеть кто и когда создал/изменил/удалил ресурс, чтобы расследовать инциденты
2. Как security-офицер, я хочу фильтровать audit-лог по пользователю, типу ресурса и дате
3. Как администратор, я хочу видеть все действия конкретного пользователя, чтобы аудировать его активность

### Functional Requirements

**Модель `audit_logs`:**

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | int PK | — |
| `user_id` | int FK → users | Кто совершил действие |
| `username` | str | Денормализовано для скорости |
| `action` | str | `create`, `update`, `delete`, `login`, `logout`, `sync`, `build` |
| `resource_type` | str | `mirror`, `helm_source`, `docker_source`, `user`, `role`, `integration`, `pipeline`, `oidc_config` |
| `resource_id` | int | ID изменённого ресурса |
| `resource_name` | str | Человекочитаемое имя (денормализовано) |
| `details` | JSON | Детали изменения (старые/новые значения для update) |
| `ip_address` | str | IP адрес клиента |
| `created_at` | datetime | Время события |

**Middleware / Service:**

1. `AuditService.log_event()` — универсальный метод
2. Вызывается из сервисов и API роутеров при мутирующих операциях
3. Не блокирует основной поток (запись через `asyncio.create_task` или фон)
4. `POST /api/auth/login` — запись login/logout событий

**API:**

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/api/admin/audit-logs` | Список с фильтрацией и пагинацией |

Параметры: `user_id`, `action`, `resource_type`, `date_from`, `date_to`, `page`, `page_size`

**UI:**

- Страница `/settings/audit-log` (или вкладка в Admin)
- Таблица: Timestamp, User, Action, Resource Type, Resource Name, Details (expandable)
- Фильтры: Date range, User, Action, Resource Type

### Non-Goals

- Экспорт в SIEM (будет через API)
- Retention policies (в первой версии — forever)
- Алерты на подозрительную активность

### Technical Considerations

- Запись audit log не должна ронять основную операцию при ошибке
- `details` JSON — для update хранить `{"before": {...}, "after": {...}, "changed_fields": [...]}`
- Индексы в БД: `idx_audit_user`, `idx_audit_action`, `idx_audit_resource`, `idx_audit_created_at`
- Permission: только `users:read` (admin) для просмотра
- Миграция Alembic

### Success Metrics

- Каждое мутирующее действие записывается в audit_log (100% coverage)
- API возвращает результаты за < 500ms при 100K записей

---

## 5. Harbor Security Scanning

### Введение

Harbor умеет сканировать Docker образы на уязвимости (CVE). BigBug должен запускать сканирование и отображать результаты.

### Goals

- Запуск Harbor vulnerability scan для Gold/App образов
- Сохранение количества CVE в `image_versions`
- Отображение результатов в UI

### User Stories

1. Как оператор, я хочу видеть количество уязвимостей для каждой версии образа, чтобы принимать решение о деплое
2. Как администратор, я хочу запустить сканирование конкретной версии образа через Harbor API
3. Как администратор, я хочу чтобы сканирование запускалось автоматически при появлении новой версии

### Functional Requirements

1. `HarborScanService`:
   - `scan_image(image_version_id)` — вызвать Harbor API для сканирования
   - `get_scan_results(image_version_id)` — получить результаты из Harbor
   - Сохранить `vulnerabilities.total` в `image_versions.vulnerabilities`
   - Сохранить `vulnerabilities.severity` (critical/high/medium/low) в `image_versions` (добавить поле `vulnerability_severity`)

2. API:
   - `POST /api/gold-images/{id}/versions/{version_id}/scan` — запустить сканирование
   - `POST /api/app-images/{id}/versions/{version_id}/scan` — запустить сканирование
   - Результаты возвращаются в `GET .../versions` (поле `vulnerabilities` уже есть)

3. Интеграция с существующим flow сборки:
   - После `docker push` в GitLab CI триггерить scan через BigBug API или напрямую в Harbor

4. UI:
   - Бейдж с количеством CVE в таблице версий (🟢 0, 🟡 1-5, 🔴 >5)
   - Детальная страница: разбивка по severity

### Non-Goals

- Собственный сканер уязвимостей (используем Harbor: Trivy/Clair)
- Блокировка деплоя при наличии CVE (будет в будущем)

### Technical Considerations

- Harbor API: `POST /api/v2.0/projects/{project}/repositories/{repo}/artifacts/{digest}/scan`
- Результаты: `GET /api/v2.0/projects/{project}/repositories/{repo}/artifacts/{digest}`
- Использовать [`ServiceFactory`](../backend/app/services/integrations.py) для получения Harbor instance
- Модель `ImageVersion`: поле `vulnerabilities` уже есть (int)

### Success Metrics

- Сканирование новой версии образа занимает < 2 минуты
- Результаты отображаются в UI сразу после завершения

---

## 6. Cosign Image Signing

### Введение

Для верификации целостности Docker образов используется [Cosign](https://github.com/sigstore/cosign) — подпись образов с хранением сигнатуры в OCI-совместимом registry. Модель `ImageVersion` уже имеет поля `cosign_signature` и `is_signed`.

### Goals

- Автоматическая подпись образов после сборки в GitLab CI
- Верификация подписи через API
- Отображение статуса подписи в UI

### User Stories

1. Как администратор, я хочу чтобы все собираемые образы автоматически подписывались Cosign, чтобы гарантировать их целостность
2. Как оператор, я хочу видеть статус подписи для каждой версии образа в UI
3. Как security-офицер, я хочу верифицировать подпись образа через API

### Functional Requirements

**1. CosignService (`backend/app/services/cosign.py`):**

- `sign_image(image_version_id)` — вызвать `cosign sign` (через subprocess)
- `verify_image(image_version_id)` — вызвать `cosign verify`
- Сохранить сигнатуру в `image_version.cosign_signature`
- Выставить `image_version.is_signed = True`

**2. CI/CD шаблоны:**

- В [`gold-image-template.yml`](../infrastructure/gitlab-components/gold-image-template.yml): добавить stage `sign` после `push`
- В [`app-image-template.yml`](../infrastructure/gitlab-components/app-image-template.yml): добавить stage `sign` после `push`
- Cosign key передаётся через GitLab CI variable `COSIGN_PRIVATE_KEY`
- `cosign sign --key env://COSIGN_PRIVATE_KEY ${IMAGE_NAME}`

**3. API (опционально):**

| Метод | Путь | Описание |
|-------|------|----------|
| `POST` | `/api/images/{id}/versions/{version_id}/sign` | Подписать версию |
| `POST` | `/api/images/{id}/versions/{version_id}/verify` | Проверить подпись |

**4. UI:**

- Иконка замка 🔒 в таблице версий (зелёный = подписан, серый = нет)
- Информация о сигнатуре в деталях версии

### Non-Goals

- Keyless signing (OIDC-based) — только key-based в первой версии
- Управление ключами через BigBug UI
- Проверка подписи при docker pull (это на стороне рантайма)

### Technical Considerations

- Cosign CLI должен быть доступен в GitLab Runner (образ `bitnami/cosign` или `alpine/cosign`)
- Для серверной подписи через subprocess — cosign должен быть установлен в backend Docker образе
- `COSIGN_PRIVATE_KEY` хранится в GitLab CI Variables (не в BigBug)
- Сигнатура хранится в OCI registry рядом с образом, поле `cosign_signature` в БД — только для быстрого отображения

### Success Metrics

- 100% образов, собранных через платформу, подписаны
- Верификация подписи возвращает результат за < 5 секунд

---

## 7. Расширение тестового покрытия (фоновая задача)

### Введение

Текущее покрытие тестами неравномерно: хорошо покрыты OIDC Config и Integrations, но отсутствуют тесты для mirrors, helm, docker, builds, auth flow.

### Goals

- Unit-тесты для всех сервисов
- E2E тесты для всех API эндпоинтов
- Фронтенд тесты для всех страниц

### Functional Requirements

**Backend unit tests (добавить):**

| Сервис | Ожидаемое кол-во тестов |
|--------|------------------------|
| `GitLabService` | 10+ (create project, trigger mirror, pipeline) |
| `GitHubService` | 8+ (list orgs, repos, releases) |
| `DockerService` | 8+ (tags, sync, registry auth) |
| `HelmService` | 8+ (index.yaml parsing, versions, sync) |
| `BuildService` | 10+ (gold sync, app build trigger) |
| `RBACService` | 5+ (permissions, role CRUD, protection) |

**Backend E2E tests (добавить):**

| Ресурс | Ожидаемое кол-во |
|--------|-----------------|
| Auth (login, refresh, me) | 10+ |
| Mirrors CRUD + sync | 15+ |
| Helm Charts CRUD + index | 10+ |
| Docker Images CRUD + index | 10+ |
| Gold/App Images CRUD + build | 15+ |
| Admin users management | 8+ |

**Frontend tests (добавить):**

| Страница | Ожидаемое кол-во |
|----------|-----------------|
| Login | 5+ |
| Dashboard | 3+ |
| Mirrors | 8+ |
| HelmCharts | 8+ (уже есть частично) |
| DockerImages | 8+ (уже есть частично) |
| GoldImages | 5+ |
| AppImages | 5+ |
| Projects | 5+ |
| Admin | 8+ |

### Technical Considerations

- Backend: `pytest` + `pytest-asyncio` + `httpx.AsyncClient`
- Frontend: `vitest` + `@testing-library/react`
- Моки: `unittest.mock` для httpx-запросов в сервисах
- CI: запуск тестов в GitLab CI пайплайне

### Success Metrics

- Backend coverage ≥ 80%
- Frontend coverage ≥ 70%
- Все тесты проходят в CI

---

## Сводный порядок выполнения

| # | Задача | Оценка | Зависит от |
|---|--------|--------|------------|
| 1 | Role Management UI | 3-5 дней | — |
| 2 | Rate Limiting | 1-2 дня | — |
| 3 | Pipeline Runs API + UI | 5-8 дней | — |
| 4 | Audit Logging | 3-5 дней | — |
| 5 | Harbor Security Scanning | 3-5 дней | — |
| 6 | Cosign Signing | 2-3 дня | — |
| 7 | Тестовое покрытие | Непрерывно | Каждая задача добавляет тесты |

**Общая оценка**: ~20-30 дней на всю Phase 4.
