# Актуализация документации BigBug (пост-Providers V3 + GitLab Projects + Helm mirror)

## Контекст

Последний коммит `ecfda09` (2026-08-20). Документация отстаёт от кода:

- **README.md** описывает состояние ~июня 2026: Material UI v9 (факт: `antd ^6.4.3`), бейджи «111/88 тестов», несуществующая директория `gitlab-ci/`, `run_tests.sh` вместо Makefile, старый список эндпоинтов и RBAC на 3 ролях.
- **plans/current-state.md** датирован 2026-06-13 (до Providers V3): ссылки на удалённые `api/integrations/`, `api/mirrors.py` (факт: `mirroring.py`), 5 instance-таблиц, `source_providers`.
- **AGENTS.md** содержит битые ссылки (`gitlab-ci/`, `plans/handoff-summary.md`) и устаревшую цепочку миграций («две миграции», факт: 6).
- **CHANGELOG.md** `[Unreleased]` не покрывает коммиты `7956508` (GitLab Projects/Components/Pipelines API), `7fd87a1` (Helm mirror workflow), `ecfda09`.
- **plans/README.md** (навигационный индекс, НЕ дубликат AGENTS.md) ссылается на несуществующие `features/mirroring.md`, `handoff-summary.md`, `infrastructure-init-redesign.md` и не перечисляет 8 существующих файлов.

## Решения (подтверждены пользователем)

1. Объём: **все доки** — README.md, CHANGELOG.md, AGENTS.md, plans/*.
2. Устаревшие файлы: **чистка + обновление**; legacy-архивы (`plans/architecture.md`) не трогать.
3. Числовые метрики (счётчики тестов): **убрать точные числа**, заменить командами запуска.

## Проверенные факты для исполнителя

**Роутеры API** (`backend/app/api/`, префиксы взять из `main.py`): admin, app_images, audit, auth, components, credentials, docker_images, gitlab_projects, gold_images, health_check, helm_charts, mirroring, orphaned, pipelines, projects, providers, reports, schedules, teams, webhooks. Сверять с `backend/openapi.json`.

**UI-библиотека**: Ant Design 6 (`antd ^6.4.3`, `@ant-design/icons ^6.2.5` из `frontend/package.json`). Никакого MUI.

**Цепочка миграций** (6, `backend/alembic/versions/`): `initial_schema` → `seed_initial_data` → `add_gitlab_projects` → `link_components_pipelines_to_gitlab_projects` → `seed_gitlab_project_permissions` → `add_helm_mirror_fields`.

**Страницы frontend** (`frontend/src/pages/`): Overview, Dashboard, Login, SsoCallback, Profile (MyTeams/MyProviders), GitMirroring (Dashboard, Mirrors+Process, Sources [Groups/Repositories tabs], SyncGroups, Repositories/Detail, Orphaned, Reports, Groups), Pipelines (Runs, Components, Configurations, Projects+Detail), DockerImages, HelmCharts, GoldImages, AppImages, Builds, Admin (Users, Roles, Permissions, Teams+TeamDetail, Credentials, SystemProviders, AuditLog, Authentication), Settings (Authentication, AuditLog, Pipelines, Providers).

**RTK Query**: доменные файлы в `frontend/src/store/api/` (19 файлов + `git-mirroring/`), `api.ts` — агрегатор.

**Сервисы**: `gitlab_projects/` (_service, _files, _clients, presets), `pipeline/` (_ci, _clients, _components, _configs, _runs, _status), `providers/` (registry, service, clients/), `source_providers/` (legacy, ещё в коде).

## Задания

### 1. README.md (корень)

- Убрать бейджи «111/88 passed» (заменить статическими pytest/vitest или оставить только License).
- Tech Stack → Frontend: Material UI v9 заменить на **Ant Design 6**; версии сверить с `frontend/package.json` и `backend/pyproject.toml`.
- Features: добавить управление GitLab Projects/Components/Pipelines через API, Providers V3 (единая сущность + teams + шаринг), Docker-импорт (Docker Hub → Harbor), Helm mirror workflow, Profile/Teams.
- Структура проекта: удалить `gitlab-ci/` (не существует); шаблоны CI теперь в `infrastructure/gitlab-components/examples/` (не используются приложением — пресеты в `backend/app/services/gitlab_projects/presets.py`).
- Development: `./run_tests.sh` → Make-команды (`make test-*`, `make lint`, `make typecheck`, `make dead-code`).
- Key Endpoints: перегенерировать группами по `main.py`/`openapi.json` (providers, teams, credentials, gitlab-projects, mirroring, orphaned, audit, reports, components, pipelines, health-check — новые относительно текущего README).
- RBAC: permission-based (`resource:action`), кастомные роли, teams + scope-providers; ссылка на `plans/architecture/permissions.md`.
- Testing: без чисел — только команды `make test-unit-backend`, `make test-unit-frontend`, `make test-integrations-frontend`, `make test-e2e-backend` (нужен dev-стек).
- Code Patterns: frontend — RTK Query в `src/store/api/<домен>.ts`, не в одном `api.ts`.

### 2. CHANGELOG.md — дополнить `[Unreleased]`

Добавить в **Added**:
- **Управление GitLab Projects/Components/Pipelines через API** (`7956508`): модель `GitlabProject` + scope-таблица + RBAC-права; API `/api/gitlab-projects` (CRUD, file/tag ops, component presets/push/pull, push-ci генерация); сервисы `gitlab_projects/` и реструктуризация `pipeline.py` → `pipeline/`; frontend `Pipelines/Projects` (+Detail, CreateModal) и `Pipelines/Configurations`; RTK `store/api/gitlab-projects.ts`; миграции `add_gitlab_projects`, `link_components_pipelines_to_gitlab_projects`, `seed_gitlab_project_permissions`.
- **Helm charts mirror workflow** (`7fd87a1`): `gitlab_project_id` у HelmChartSource, mirror-поля, webhook, миграция `add_helm_mirror_fields`; фронт HelmCharts (Mirror-UI).

Добавить в **Changed**:
- Docker: `_sync_tags` оставляет status_flag=4 (Pending) вместо «synced» при индексации (`7fd87a1`).
- Fix gitlab project service (`ecfda09`, мелкий).

Добавить в **Removed**:
- `infrastructure/provision-gitlab.sh` (заменён app API); YAML-шаблоны перенесены в `infrastructure/gitlab-components/examples/`.

### 3. AGENTS.md

- Дерево структуры: удалить `gitlab-ci/`; добавить `CHANGELOG.md`, `Makefile`, `.kilo/` рядом с `.roo/`.
- Секция «Creating Pipeline»: шаг «Define GitLab CI template in gitlab-ci/» заменить на актуальный флоу — пресеты `presets.py` + `/api/gitlab-projects` push-ci, YAML-примеры в `infrastructure/gitlab-components/examples/`.
- Frontend conventions: RTK Query — `src/store/api/<домен>.ts` (19 файлов + `git-mirroring/`), `api.ts` — агрегатор.
- «Legacy Documentation»: убрать битую ссылку `plans/handoff-summary.md` (файла нет).
- Database note: цепочка миграций — 6 ревизий (см. факты), не «две».
- Добавить краткий пункт «Managing GitLab Projects» в «Working with Specific Features» (модель + API + presets).
- Common file references: добавить `backend/app/api/gitlab_projects.py`, `backend/app/services/gitlab_projects/presets.py`.

### 4. plans/current-state.md — переписать

- Дата обновления → 2026-09-10.
- Backend API: убрать `api/integrations/`, `mirrors.py` → `mirroring.py`; полный список роутеров из `main.py`.
- Сервисный слой: фактический список `services/` (включая `gitlab_projects/`, `pipeline/`, `providers/`; пометить `source_providers/` + `source_provider.py` как legacy).
- Frontend: фактические страницы/роуты (см. факты выше).
- Database: убрать 5 instance-таблиц и `source_providers`; добавить `resource_providers`, `credentials`, `teams`, `team_members`, `role_scopes`, `gitlab_projects` (+scope).
- Тесты: без счётчиков; структура (backend: `tests/unit/`, `tests/e2e/`; frontend: `src/tests/unit/`, `src/tests/integrations/`).
- «Этапы Git Mirroring V2» свернуть в строку «завершены (см. CHANGELOG)».

### 5. plans/README.md — починить индекс

- `features/mirroring.md` → `features/git-mirroring-v2.md` (пометить legacy).
- Убрать ссылки на несуществующие `handoff-summary.md`, `infrastructure-init-redesign.md`.
- Добавить существующие: `architecture/permissions.md`, `features/providers-unified.md`, `features/user-profile.md`, `gitlab-project-management-spec.md` (пометить «реализовано»), `gitlab-components-provisioning-spec.md` (реализовано), `docker-import-fix-spec.md` (реализовано), `makefile-tooling.md`.

### 6. plans/project-overview.md и plans/tech-stack.md — переписать

- project-overview: Providers V3, GitLab Projects management, Docker-импорт, Helm mirror, Teams/Profile; текущая структура репо.
- tech-stack: antd 6 (не MUI), версии из `package.json`/`pyproject.toml`, mypy/vulture/knip/Yarn 4.3.1/Make-инструментарий.

### 7. Финальная проверка ссылок

- Пройти по всем markdown-ссылкам `[...](path)` в изменённых файлах и проверить существование целей (использовать `rg -o '\]\([^)#]+\)' <файлы>` + проверка путей).
- Сверить упомянутые пути кода с реальными файлами.

## Out of scope

- `docs/architecture/` (human review, своя нумерация).
- `plans/development/*`, `plans/architecture/permissions.md`, `plans/architecture/decisions.md` (актуальны, авг 2026).
- `plans/architecture.md` (legacy-архив, уже помечен).
- `infrastructure/README.md` (обновлён в `7956508`).
- Спеки `plans/*-spec.md` — не переписывать, только статус в индексе (задание 5).
- Коммит изменений (не запрашивался).

## Валидация

1. Все внутренние ссылки в изменённых .md ведут на существующие файлы.
2. Список эндпоинтов соответствует `backend/openapi.json` / `app/main.py`.
3. Версии библиотек соответствуют `package.json` / `pyproject.toml`.
4. Упомянутые пути к коду существуют.
5. Точечные счётчики тестов/путей OpenAPI в тексте отсутствуют (антикоррозийное решение).
