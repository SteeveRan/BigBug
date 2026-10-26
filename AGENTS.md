# BigBug - Guide for AI Agents

Quick reference for AI agents working on BigBug project.

## Project Overview

**BigBug** — централизованная DevOps платформа для управления:
- **Docker образами**: Gold Images (базовые OS/runtime), App Images (приложения)
- **Зеркалированием**: GitHub → GitLab с автоматическими CI/CD пайплайнами
- **Синхронизацией**: Docker Registry образов и Helm Repository чартов
- **CI/CD**: GitLab Pipelines и Components через UI

**Архитектура**: FastAPI backend + React frontend + PostgreSQL + Redis + GitLab CI/CD

**Текущее состояние**: Проект прошёл миграцию Providers V3 — единая сущность `resource_providers` (таблица + реестр + `/api/providers`) заменила 5 legacy-таблиц инстансов и V2-систему `source_providers`. Расширенная RBAC (`providers:*`, `teams:*`, scope-providers) активна.

## Repository Structure

```
BigBug/
├── backend/              # FastAPI application
│   ├── app/
│   │   ├── api/         # REST API endpoints
│   │   ├── core/        # Security, RBAC, exceptions
│   │   ├── models/      # SQLAlchemy models
│   │   ├── schemas/     # Pydantic schemas
│   │   └── services/    # Business logic layer
│   ├── alembic/         # Database migrations
│   ├── docker/          # Dockerfile + entrypoint
│   ├── scripts/         # Format, lint, test scripts
│   ├── tests/           # pytest tests
│   └── pyproject.toml   # Python dependencies
├── frontend/            # React + TypeScript SPA
│   ├── src/
│   │   ├── components/  # Reusable UI components
│   │   ├── hooks/       # Custom React hooks
│   │   ├── pages/       # Page components
│   │   ├── router/      # React Router config
│   │   ├── services/    # API clients
│   │   ├── store/       # Redux + RTK Query
│   │   ├── tests/       # Vitest test suite
│   │   └── types/       # TypeScript interfaces
│   ├── docker/          # Dockerfile
│   ├── scripts/         # Format, lint, test scripts
│   └── package.json     # Node dependencies
├── infrastructure/      # Infrastructure setup (OpenTofu, scripts, configs)
│   ├── gitlab/               # GitLab compose zone (gitlab + gitlab-runner — compose-исключение, ADR-0033)
│   ├── init.sh               # Initialization script (certs → compose → kind → base → infra-apps → apps)
│   ├── kind/                 # kind-стенд: bootstrap/certs/trust scripts
│   ├── terraform/            # OpenTofu roots: base/ + infra-apps/ (+GitLab) + apps/ (ADR-0029/0033)
│   └── gitlab-components/ # GitLab CI/CD component examples (not used by app; see backend presets.py)
├── docs/
│   ├── adr/              # ADR registry (decisions)
│   ├── development/      # Operational guides for agents (setup, backend, frontend, permissions index)
│   └── runbooks/         # Operational procedures for humans
├── Makefile             # Single entry point for all scripts (make help)
├── CHANGELOG.md         # Version history
├── .kilo/               # Kilo config (commands, agents, plans)
└── .roo/                # Kiro AI rules and guidelines
```

## Technology Stack

Решения по стеку зафиксированы в реестре [ADR](docs/adr/README.md):

| Слой | ADR |
|---|---|
| Backend (Python 3.14 + FastAPI + SQLAlchemy 2 + PostgreSQL 17 / Redis 7) | [ADR-0001](docs/adr/backend/0001-choose-backend-stack.md) |
| Frontend (React 19 + TypeScript + AntD 6 + RTK/RTK Query + Vite, Node.js) | [ADR-0002](docs/adr/frontend/0002-frontend-stack-react-antd-rtk.md) |
| Auth (JWT + Keycloak OIDC) | [ADR-0003](docs/adr/common/0003-keycloak-oidc-dual-auth.md) |
| Dev environment (kind-стенд) | [ADR-0022](docs/adr/infrastructure/0022-dev-stand-on-kind.md) |
| IaC (OpenTofu: base/infra-apps/apps root'ы) | [ADR-0029](docs/adr/infrastructure/0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md) |
| GitLab (compose-исключение, https) | [ADR-0033](docs/adr/infrastructure/0033-gitlab-dev-stand-compose-omnibus.md) |
| Keycloak в kind (keycloakx + CNPG) | [ADR-0034](docs/adr/infrastructure/0034-keycloak-dev-stand-keycloakx.md) |
| Harbor в kind (chart + TLS) | [ADR-0035](docs/adr/infrastructure/0035-harbor-dev-stand-chart.md) |

**Инфраструктурные сервисы dev-стенда** (детали — [ADR-0022](docs/adr/infrastructure/0022-dev-stand-on-kind.md)/[0029](docs/adr/infrastructure/0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md)): Keycloak (keycloakx в kind), Harbor (chart в kind за TLS-ingress), PostgreSQL 17 (CNPG), Valkey — всё в кластере `bigbug-dev`; **GitLab CE omnibus + gitlab-runner — compose-исключение** ([ADR-0033](docs/adr/infrastructure/0033-gitlab-dev-stand-compose-omnibus.md), `https://gitlab.local:8443`, серт из `kind/certs.sh` → `~/.local/state/bigbug/certs`).

Актуальные версии — [`backend/pyproject.toml`](backend/pyproject.toml), [`frontend/package.json`](frontend/package.json).

## Development Workflow

### Backend (Python/FastAPI)

**Location**: [`/backend/`](backend/)

**Key conventions**:
- Models: one file per model in [`app/models/`](backend/app/models/)
- Schemas: Pydantic v2 in [`app/schemas/`](backend/app/schemas/)
- Services: business logic in [`app/services/`](backend/app/services/)
- API routers: in [`app/api/`](backend/app/api/), registered in [`main.py`](backend/app/main.py)
- Migrations: `alembic revision -m "description"` → edit file → `alembic upgrade head`

See: [`/docs/development/backend.md`](docs/development/backend.md)

### Frontend (React/TypeScript)

**Location**: [`/frontend/`](frontend/)

**Test structure** ([`src/tests/`](frontend/src/tests/)):
```
src/tests/
├── unit/               # Изолированные тесты (функции, хуки, редьюсеры)
├── integrations/       # Тесты страниц/компонентов с Redux store и RTK Query моками
└── e2e/                # E2E тесты (Cypress — planned, пока пусто)
```

**Где размещать новые тесты:**
- **Unit**: изолированная логика без рендеринга React-компонентов (редьюсеры, сервисы, утилиты, хуки через `renderHook`). Файл: `src/tests/unit/Имя.test.ts`
- **Integrations**: тесты страниц и компонентов, которым нужен Redux store, RTK Query моки и jsdom-окружение. Файл: `src/tests/integrations/Имя.test.tsx`
- **E2E**: пока не реализованы, будут в `src/tests/e2e/`

**Key conventions**:
- Pages: in [`src/pages/ComponentName/index.tsx`](frontend/src/pages/)
- Components: reusable in [`src/components/`](frontend/src/components/)
- Store: Redux slices + RTK Query in [`src/store/`](frontend/src/store/)
- Types: TypeScript interfaces in [`src/types/index.ts`](frontend/src/types/)
- Routing: in [`src/router/index.tsx`](frontend/src/router/)

See: [`/docs/development/frontend.md`](docs/development/frontend.md)

### Make-команды (единая точка входа)

Все скрипты запускаются через корневой [`Makefile`](Makefile). Справка: `make help`.

| Группа | Примеры |
|---|---|
| `dev-*` | `make dev-up`, `make dev-down`, `make dev-clean` (dev-build — сборка dev-образов) |
| `infra-*` | `make infra-up`, `make infra-init`, `make infra-clean` |
| `test-*` | `make test-unit-backend`, `make test-e2e-backend`, `make test-all` |
| `lint-*`/`format-*`/`typecheck-*` | `make lint`, `make lint-infra`, `make format`, `make typecheck` |
| `coverage-*` | `make coverage-all` |
| `dead-code-*` | `make dead-code` |

**Форматирование — quality gate**: `ruff format --check` (backend) и `prettier --check` (frontend) входят в `make lint` и CI. Правило для агентов: **форматируй файлы, которые трогаешь** (`ruff format <путь>` / `prettier --write <путь>`); не запускай `ruff format app tests` на весь репо в feature-диффах — это drive-by (проверка `--check` всё равно провалится на чужих файлах, чинить их нужно отдельным коммитом `make format`).

See: [ADR-0029](docs/adr/infrastructure/0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md) — IaC-разрезка (base/infra-apps/apps root'ы, инструментальное ядро бывшего ADR-0013); [ADR-0022](docs/adr/infrastructure/0022-dev-stand-on-kind.md) — dev-стенд на kind; troubleshooting инфраструктуры — ниже.

## Key Conventions

### File Organization

**Backend**:
- One model per file: [`backend/app/models/user.py`](backend/app/models/user.py)
- Services separate from API layer: [`backend/app/services/`](backend/app/services/)
- Domain exceptions (not `HTTPException`) in services: [`backend/app/core/exceptions.py`](backend/app/core/exceptions.py)
- HTTP layer maps exceptions to status codes in routers

**Frontend**:
- Component folder with `index.tsx`: [`frontend/src/pages/Login/index.tsx`](frontend/src/pages/Login/index.tsx)
- Types centralized: [`frontend/src/types/index.ts`](frontend/src/types/)
- API endpoints in RTK Query: domain files in [`frontend/src/store/api/`](frontend/src/store/api/) (one file per domain, e.g. `gitlab-projects.ts`; `git-mirroring/` subfolder), with [`frontend/src/store/api.ts`](frontend/src/store/api.ts) as the aggregator

### API Design

**REST conventions**:
- `GET /api/resource` - list
- `GET /api/resource/{id}` - detail
- `POST /api/resource` - create
- `PATCH /api/resource/{id}` - partial update
- `DELETE /api/resource/{id}` - delete
- `POST /api/resource/{id}/action` - custom action (trigger sync, index, etc)

**Response format**:
```json
{
  "id": 1,
  "name": "example",
  "status_flag": 0,
  "status_text": "OK",
  "created_at": "2026-01-01T00:00:00Z"
}
```

**Status flags** (unified):
- `0` - OK / Success
- `1` - Failed
- `2` - Warning / Stale
- `3` - In Progress
- `4` - Pending

### Database

**Models**: SQLAlchemy 2.0 declarative style with async support

**Migrations**: Alembic with naming convention:
```bash
alembic revision -m "add_user_keycloak_sub"
# Creates: YYYYMMDD_HHMM_<hash>_add_user_keycloak_sub.py
```

> Текущая цепочка — 6 ревизий после сброса 2026-08-16: `initial_schema` → `seed_initial_data` → `add_gitlab_projects` → `link_components_pipelines_to_gitlab_projects` → `seed_gitlab_project_permissions` → `add_helm_mirror_fields` (старые 40 ревизий в [`backend/alembic/versions_backup_20260816/`](backend/alembic/versions_backup_20260816/)). Новые изменения схемы — новыми миграциями поверх `add_helm_mirror_fields`, см. [ADR-0006](docs/adr/backend/0006-database-postgresql-alembic.md).

**Naming conventions**:
- Tables: `users`, `roles`, `gitlab_mirrors` (plural, snake_case)
- Columns: `user_id`, `created_at`, `is_active` (snake_case)
- Foreign keys: `{table}_id`, e.g., `user_id`
- Indexes: `ix_{table}_{column}`, e.g., `ix_users_email`

See: [ADR-0006](docs/adr/backend/0006-database-postgresql-alembic.md)

### Multi-Agent Worktree Discipline

Несколько агентов работают в разных git worktree на одной машине; инфраструктура (kind-кластер `bigbug-dev`, GitLab compose-зона, Keycloak) — **общая**. Правила, чтобы агенты не мешали друг другу:

### Роли

- **Владелец инфры** — один ворктрий (по умолчанию `main`, `/home/vnosov/Projects/BigBug`). Только он запускает: `infra-init`, `infra-clean`, `dev-clean`, tofu-команды, пересоздание секретов, `down -v`.
- **Feature-агенты** (все остальные ворктрии) — код, unit/integrations-тесты, lint, typecheck.

### Разрешено feature-агентам: dev-образ и деплой приложения

Изменение `backend/`/`frontend/`/`charts/bigbug/` доходит до живого стенда только через пересборку образа + helm upgrade — без этого e2e-прогон гоняет чужой/старый код. Поэтому feature-агенту **разрешено**:

- собирать dev-образы: `docker build -t bigbug-backend:dev backend/` (и frontend аналогично);
- заливать в kind: `kind load docker-image bigbug-backend:dev --name bigbug-dev`;
- деплоить чарт: `helm upgrade --install bigbug charts/bigbug -n bigbug --kube-context kind-bigbug-dev -f charts/bigbug/values-dev.yaml`;
- обновлять app-level ресурсы ns `bigbug` (ConfigMap bigbug-ca-bundle и т.п.) kubectl'ом из локальных сертов/state — без tofu apply.

Стенд один на всех: образ `:dev` — последний загруженный. Перед e2e-прогоном пересобирайте образ со СВОИМ кодом и объявляйте стенд занятым (см. «E2E — по очереди»); конфликтов tofu-стейта нет — helm/kubectl стейт не шарят.

### Запрещено feature-агентам

- `make dev-clean` / `make infra-clean` / `docker compose down -v` — гасят общий стенд (защищены CONFIRM-гвардом, обходить его нельзя)
- `alembic downgrade` на общей БД `bigbug`
- Tofu apply / пересоздание секретов / изменение `infrastructure/gitlab/.env`

Нужен пересозданный секрет, свежее окружение или чистка — issue владельцу инфры, не самодеятельность.

### Миграции: своя БД на ворктрий

- БД приложения — CNPG Cluster `bigbug-dev` в kind; каждая фича-ветка работает со **своей БД** в нём: `make dev-db-create DB=feat_<branch>`, затем `DATABASE_URL` ветки указывает на `feat_<branch>` (локальный env-override, gitignored). Alembic-головы веток не конфликтуют.
- Каноническая БД `bigbug` — только владелец инфры; перед мержем ветка проходит `make dev-migrate-check` (накат всех миграций на чистую копию БД) — ловит разошедшиеся головы до мержа.
- `make dev-db-drop DB=<name>` — удалить свою БД, когда фича смержена. Удалять `bigbug` скрипт запрещает.

### E2E — по очереди

- Живой стенд поднимает владелец инфры (`make infra-init`); код приложения — dev-образы этого ворктрия (`make dev-build && make dev-up`). `make test-e2e-backend` гоняет против ingress (https://api.local).
- Остальные агенты обходятся unit/integrations (стенд не нужен). Перед e2e — объявить стенд занятым, пересобрать образы со СВОИМ кодом (`dev-build` + `dev-up`), после — освободить (дисциплина, без локов).

## Testing

**Backend** (pytest):
```python
# tests/test_feature.py
async def test_feature_success(async_client):
    response = await async_client.post("/api/endpoint", json={...})
    assert response.status_code == 200
```

**Per-worktree DATABASE_URL** (multi-agent): в `backend/.env` ворктрия пропишите свою БД:
```
DATABASE_URL=postgresql+asyncpg://bigbug:bigbug@localhost:5432/feat_<branch>
```
(создание БД — `make dev-db-create DB=feat_<branch>`)

**Frontend** (vitest + testing-library):
```typescript
// src/tests/unit/Component.test.ts
import { render, screen } from '@testing-library/react';
test('renders component', () => {
  render(<Component />);
  expect(screen.getByText('text')).toBeInTheDocument();
});
```

**Run tests** (через [`Makefile`](Makefile), полный список — `make help`):
```bash
make test-unit-backend          # backend unit
make test-e2e-backend           # backend e2e (нужен dev-стек)
make test-unit-frontend         # frontend unit
make test-integrations-frontend # frontend integrations
make test-all                   # unit + integrations + e2e
make coverage-all               # покрытие обоих стеков

# Конкретные тесты — через TEST_ARGS (проброс в скрипты):
make test-unit-backend TEST_ARGS="-k test_login"
make test-e2e-backend TEST_ARGS="tests/e2e/test_auth.py -v"
make test-unit-frontend TEST_ARGS="-f Admin -t 'should render'"
```

**pytest cheat-sheet** (ручной запуск из `backend/`; для агентов каноничен make + `TEST_ARGS`):

```bash
pytest tests/test_auth.py -v              # конкретный файл
pytest tests/test_auth.py::test_login     # конкретный тест
pytest -k "test_login" -v                 # фильтр по имени
pytest --cov=app --cov-report=term-missing  # покрытие
pytest -x                                 # стоп на первой ошибке
pytest -s                                 # показать print()
pytest --lf                               # только упавшие в прошлый раз
pytest --fixtures                         # список фикстур
```

**Backend e2e runbook** (требует живой dev-стек — `make dev-up`):

```bash
make dev-up                                        # 1. поднять dev-стек
make test-e2e-backend                              # 2. полный e2e-прогон
make test-e2e-backend TEST_ARGS="-k test_login"    #    фильтр по имени
```

- Без dev-стенда прогон падает fast: `E2E backend is not reachable` — это норма, unit-тесты работают без стенда.
- Переменные окружения: `BIGBUG_E2E_BASE_URL` (default `http://localhost:8000`), `E2E_ADMIN_USERNAME`/`E2E_ADMIN_PASSWORD` (default `admin`/`admin`).
- После прогона в teardown пишется отчёт покрытия эндпоинтов: `backend/reports/endpoint-coverage.{json,md}` (порог 90%, мягкий).
- E2E-учётки (e2e-admin/e2e-viewer/e2e-operator) создаются и удаляются через публичный API фикстурами `backend/tests/e2e/conftest.py` (issue #134) — отдельный seed и доступ к БД из e2e-инфраструктуры не нужны.
- Rate limiting на dev-стенде отключается `RATE_LIMIT_ENABLED=false` (иначе лимит логина 5/min ломает прогон).

See: Testing ADRs — [ADR-0014](docs/adr/backend/0014-backend-unit-testing-pytest.md), [ADR-0015](docs/adr/frontend/0015-frontend-unit-testing-vitest.md), [ADR-0016](docs/adr/backend/0016-backend-integration-testing.md), [ADR-0017](docs/adr/frontend/0017-frontend-integration-testing.md), [ADR-0018](docs/adr/common/0018-e2e-testing-strategy.md) (реестр: [docs/adr/README.md](docs/adr/README.md))

## Working with Specific Features

### Adding New Provider Subtype

Все внешние интеграции управляются через единую сущность `resource_providers` (реестр подтипов в коде).

1. Добавьте подтип в реестр [`backend/app/services/providers/registry.py`](backend/app/services/providers/registry.py) (поля, типы credentials, действия, правила категорий)
2. При необходимости — HTTP-клиент в [`backend/app/services/providers/clients/`](backend/app/services/providers/clients/)
3. Доменные действия (`list_repositories` и т.д.) диспатчатся через [`backend/app/services/providers/service.py`](backend/app/services/providers/service.py)
4. API уже унифицирован: [`backend/app/api/providers.py`](backend/app/api/providers.py) (`/api/providers`)
5. Frontend получает метаданные через `GET /api/providers/types` — новые формы генерируются автоматически

See: [ADR-0007](docs/adr/common/0007-providers-v3-registry.md)

### Provider Troubleshooting

Быстрые curl-проверки внешних интеграций (внешние системы, не BigBug API):

```bash
# GitLab API доступен / токен валиден (https, self-signed — ADR-0030 §9/ADR-0033)
curl -k -H "PRIVATE-TOKEN: glpat-xyz" https://gitlab.local:8443/api/v4/user
curl --cacert ~/.local/state/bigbug/certs/gitlab.local/tls.crt \
     -H "PRIVATE-TOKEN: glpat-xyz" https://gitlab.local:8443/api/v4/personal_access_tokens/self

# Harbor доступен / SSL
curl -u admin:Harbor12345 https://harbor.local/api/v2.0/systeminfo
curl -k -u admin:Harbor12345 https://harbor.local/api/v2.0/systeminfo

# Helm index.yaml парсится (скачать и проверить)
curl https://charts.helm.sh/stable/index.yaml | head -50
```

Диагностика в BigBug: `POST /api/providers/{id}/test` обновляет `status_flag`/`status_text` провайдера; `GET /api/providers/{id}/usage` показывает потребителей перед удалением.

### Infrastructure Troubleshooting

Ручная диагностика инфраструктурных сервисов (kind dev-стенд — [ADR-0022](docs/adr/infrastructure/0022-dev-stand-on-kind.md), IaC — [ADR-0029](docs/adr/infrastructure/0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md)):

```bash
# kind-стенд: все сервисы видно через kubectl (ADR-0022)
kubectl get pods -A --context kind-bigbug-dev   # keycloakx, harbor, ingress, app — в kind
kubectl logs -n bigbug --context kind-bigbug-dev deploy/bigbug-backend

# GitLab compose-зона (compose-исключение — ADR-0033): логи, сеть, volumes
docker compose -f infrastructure/gitlab/docker-compose.yml logs gitlab
docker network inspect bigbug-network
docker volume ls | grep gitlab

# Конфликты портов
lsof -i :8443; lsof -i :80; lsof -i :443

# GitLab: полная загрузка занимает 2-5 минут; root password для fresh-инстанса
docker compose -f infrastructure/gitlab/docker-compose.yml logs -f gitlab
docker compose -f infrastructure/gitlab/docker-compose.yml exec gitlab grep 'Password:' /etc/gitlab/initial_root_password

# OpenTofu: сброс state и повторная инициализация с нуля
make infra-clean && make infra-init

# Health-чеки сервисов (https — ADR-0030; доверие хоста: kind/trust-host.sh, иначе -k)
curl https://api.local/api/health               # backend (ingress, https)
curl -k https://keycloak.local/realms/bigbug    # Keycloak (https)
curl -k https://harbor.local/api/v2.0/systeminfo  # Harbor (https)
curl -k https://gitlab.local:8443/-/health      # GitLab (https omnibus, ADR-0033)
```

Backup: PostgreSQL (CNPG-под) — `kubectl exec -n bigbug --context kind-bigbug-dev <cnpg-pod> -c postgres -- pg_dump -U bigbug bigbug > backup.sql`; tofu state — local файлы в `~/.local/state/bigbug/{base,infra-apps,apps}/` (gitignored), пересоздаются `infra-init`.

### Modifying RBAC

1. Add permissions to [`backend/app/core/rbac.py`](backend/app/core/rbac.py) or DB
2. Use `require_permission()` dependency in API endpoints
3. Update frontend `usePermissions()` hook
4. Wrap UI components in `<PermissionGate permission="...">`

See: [`/docs/adr/common/0004-permission-based-rbac-scope-providers.md`](docs/adr/common/0004-permission-based-rbac-scope-providers.md) and [`/docs/development/permissions.md`](docs/development/permissions.md)

### Creating Pipeline

1. Component/pipeline projects are managed via the app: [`backend/app/services/gitlab_projects/`](backend/app/services/gitlab_projects/)
2. CI templates are in-code presets: [`backend/app/services/gitlab_projects/presets.py`](backend/app/services/gitlab_projects/presets.py) (served via `GET /api/components/presets`)
3. Use service to trigger via GitLab API
4. Handle webhook callback in [`backend/app/api/webhooks.py`](backend/app/api/webhooks.py)
5. Update status in database
6. Display in frontend

See: [`/docs/adr/backend/0011-gitlab-ci-pipelines-components.md`](docs/adr/backend/0011-gitlab-ci-pipelines-components.md)

### Working with Secrets

Use encryption for sensitive data:
```python
from app.core.secrets import encrypt_secret, decrypt_secret

# Store
encrypted = encrypt_secret("my-token")
# Retrieve
token = decrypt_secret(encrypted)
```

See: [ADR-0010](docs/adr/backend/0010-fernet-secrets-encryption.md) — Fernet encryption for stored credentials; key via `ENCRYPTION_KEY` env (not `FERNET_KEY`)

## Architecture Decision Records (ADR)

Единственный источник архитектурных решений — реестр [`docs/adr/README.md`](docs/adr/README.md) (конвенции формата, нумерации, архивации — там же; архив — [`docs/adr/ARCHIVE.md`](docs/adr/ARCHIVE.md)).

- **ПЕРЕД** любым изменением архитектуры, новой зависимостью, новым паттерном: прочитай реестр и релевантные ADR со статусом `accepted`. **accepted ADR обязательны к соблюдению**, proposed — учитывать.
- Если решение противоречит ADR со статусом `accepted` — остановись и предложи новый ADR, не ломай код молча.
- **Триггеры «предложить ADR»**: новая зависимость; новый паттерн (обработка ошибок, data access, API convention); выбор между ≥2 альтернативами с нетривиальным tradeoff; противоречие существующему Accepted ADR.
- **Порядок: запрос → ADR → разработка.** Запрос, влекущий архитектурное решение, порождает ADR на этапе планирования — ДО реализации. ADR мержится отдельным docs-PR, и только после этого пишется код (PR реализации ссылается на ADR). Ретро-ADR («задокументируем, что уже сделали») запрещён: PR с новым ADR и изменениями реализации возвращается — это ловит CI-гейт `adr-order` (`scripts/check-adr-order.sh`, `make check-adr-order`). ADR-секция «Confirmation» описывает, как решение будет проверено после реализации, но сам ADR существует до неё.
- Создание ADR — через команду `/adr` в OpenCode (workflow skill `adr-skill`). Статус `accepted` выставляет только человек; при `superseded`/`rejected` ADR перемещается в `docs/adr/archive/<component>/` и реестры обновляются.

## Development Pipeline (request → release)

Единица работы — GitHub issue (`docs/agents/issue-tracker.md`). Порядок шагов обязателен:

| # | Шаг | Артефакт / источник | Гейт |
|---|---|---|---|
| 1 | **Запрос** — фиксация потребности | чат с агентом, issue, грилл (`/grill-me`); сырое намерение | — |
| 2 | **Аналитика** (при необходимости) | user stories / use cases / edge cases (`/user-stories`, `/use-cases`, `/edge-cases`) в `docs/analitics/`; источник — issue; деонтические формулировки | аналитика — норматив (см. ниже) |
| 3 | **Сверка с архитектурой** | реестр ADR: выпускаются новые ADR, корректируются ещё не принятые (`proposed`), устаревшие отменяются (`superseded`/`rejected` → `archive/`); ВСЁ — до реализации, новый ADR — отдельным docs-PR | CI `adr-order`: новый ADR + код в одном PR падает |
| 4 | **Задание на разработку** | issue (sub-issues + native `blocked_by`), со ссылками на `US-`/`UC-`/edge-case и ADR | — |
| 5 | **Разработка** | feature-агент в воркспейсе → PR, ссылающийся на issue; per-worktree БД `feat_<branch>` | `make lint-*`, `typecheck-*`, `test-unit-*`, `dev-migrate-check`, CI |
| 6 | **Проверка соответствия** | review: PR против аналитики (шаг 2) и ADR (шаг 3) — и функционально, и архитектурно | противоречит — PR возвращается, аналитика/ADR не «догоняют код» |
| 7 | **Закрытие** | merge PR → закрытие issue → `CHANGELOG.md` → fast-forward воркспейсов | — |

Пропуск шагов не допускается: нельзя начинать разработку (5) без закрытых шагов 2–4, нельзя закрывать PR (7) без шага 6.

## Documentation

### Diagrams
- **Все диаграммы/схемы в документации — только Mermaid** (fenced-блоки ` ```mermaid ` в markdown). Не использовать PlantUML, draw.io, ASCII-арт и т.п.
- **C4 model диаграммы — отдельная категория**: Context/Container/Component диаграммы пишутся на Mermaid C4 syntax (`c4Context`, `c4Container`, `c4Component`, ` ```c4context ` и т.п.) и размещаются отдельно от обычных mermaid-диаграмм — не смешивать C4 и обычные (flow/sequence/ER) диаграммы в одном блоке/разделе.

### For Implementation (agents)
- **Implementation guides**: [`/docs/development/`](docs/development/) - setup, backend, frontend
- **Permissions index**: [`/docs/development/permissions.md`](docs/development/permissions.md) — единый источник истины для всех permissions. **Обязательно обновлять** при добавлении/изменении любых прав.
- **This guide**: [`/AGENTS.md`](AGENTS.md) - quick start reference

### For Review (humans)
- **Architecture decisions**: [ADR registry](docs/adr/README.md) — single source of truth for architectural decisions
- **API contract**: OpenAPI — Swagger UI at `http://localhost:8000/docs`, schema in `backend/openapi.json` (guarded by `backend/tests/unit/test_openapi_contract.py`, regenerated via `backend/scripts/export-openapi.sh`)
- **Operational procedures**: [`docs/runbooks/`](docs/runbooks/) (deploy security checklist, external provider API notes)

### Legacy Documentation
- Legacy plans-документы (`plans/architecture.md`, `plans/current-state.md`, `plans/architecture/decisions.md`, `plans/project-overview.md`, `plans/development/testing.md`) удалены — решения в реестре [`docs/adr/README.md`](docs/adr/README.md), история в git.

## Common Tasks

### Start Development Environment

```bash
make infra-init    # 1. certs → GitLab compose → kind → tofu base/infra-apps/apps (infrastructure/init.sh)
make dev-build     # 2. собрать dev-образы и залить в kind
make dev-up        # 3. задеплоить приложение (helm chart bigbug)
```

**Fresh-машина** (порядок обязателен, ADR-0030): `make infra-init` (сам генерит серты и добавляет их в trust store через trust-host.sh) → `make dev-build` → `make dev-up`. Или всё сразу: `make fresh-up`.

### Run Tests

**Агентам**: Всегда запускать тесты через `make` (см. таблицу выше). Конкретный тест — через `TEST_ARGS`:
```bash
make test-unit-backend TEST_ARGS="-k test_login"
make test-unit-frontend TEST_ARGS="-f Pipelines -t 'should trigger'"
```

### Code Quality Checks

**Агентам: гоняйте срез по стеку, который трогали.** Агрегатные таргеты (`make lint`, `make typecheck`, `make format`) включают все стеки; упавший frontend-срез из-за отсутствующего `node_modules` в worktree — не повод красить проверку чужого стека. Канонический набор для backend-фичи:

```bash
make lint-backend        # ruff check + ruff format --check (backend-срез)
make typecheck-backend   # mypy (backend-срез)
make test-unit-backend   # backend unit
```

Для frontend-фичи — зеркально: `lint-frontend`, `typecheck-frontend`, `test-unit-frontend` / `test-integrations-frontend`. Агрегаты (`make lint`, `make typecheck`) — для полных изменений или перед мержем. Прямые вызовы ruff/mypy/eslint через `.venv/bin` или `node_modules/.bin` вместо make-таргетов запрещены: скрипты загружают правильное окружение.

```bash
make lint        # ruff check + eslint + lint-infra (tofu fmt -check, tflint, tofu validate, yamllint)
make lint-infra  # инфра-срез: lint-terraform (tofu + tflint) + lint-helm (yamllint)
make format      # ruff format + prettier
make typecheck   # mypy + tsc --noEmit
make dead-code   # vulture + knip
```

CI: GitHub Actions workflow [`.github/workflows/lint.yml`](.github/workflows/lint.yml) гоняет те же проверки параллельными джобами (backend, frontend, terraform: tofu 1.13.2 + tflint >= 0.65, helm-yaml: yamllint >= 1.38) на `push` в `main` и всех `pull_request`. Инфра-линтинг конфигурируется `.tflint.hcl` и `.yamllint` в корне (см. [ADR-0038](docs/adr/common/0038-linting-infra-tflint-yamllint.md)).

### Adding New API Endpoint

**Backend**:
```python
# 1. Define schema in app/schemas/resource.py
class ResourceCreate(BaseModel):
    name: str

# 2. Create endpoint in app/api/resource.py
@router.post("/", response_model=ResourceOut)
async def create_resource(
    data: ResourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    # Implementation
    pass

# 3. Register router in app/main.py
from app.api import resource
app.include_router(resource.router, prefix="/api/resources", tags=["resources"])
```

**Frontend**:
```typescript
// 1. Add type in src/types/index.ts
export interface Resource {
  id: number;
  name: string;
}

// 2. Add RTK Query endpoint in src/store/api.ts
createResource: builder.mutation<Resource, { name: string }>({
  query: (data) => ({
    url: '/resources',
    method: 'POST',
    body: data,
  }),
  invalidatesTags: ['Resource'],
}),

// 3. Use in component
const [createResource] = useCreateResourceMutation();
await createResource({ name: 'test' });
```

## Getting Help

**For detailed implementation guides**, read [`/docs/development/`](docs/development/) (setup, backend, frontend, permissions index); architecture decisions: реестр [`docs/adr/README.md`](docs/adr/README.md)

**For architectural decisions**, consult реестр [ADR](docs/adr/README.md); эксплуатационные процедуры — [`docs/runbooks/`](docs/runbooks/).

**For specific task context**, AI agents should:
1. Read [`AGENTS.md`](AGENTS.md) (this file) first
2. Read relevant guides from [`/docs/development/`](docs/development/) as needed
3. NOT read [`docs/runbooks/`](docs/runbooks/) into context (human operational reference; for agents the entry points are AGENTS.md and the ADR registry)
4. Examine actual code files to understand current implementation
5. Ask clarifying questions if requirements are unclear
6. Перед архитектурными изменениями — реестр [ADR](docs/adr/README.md)

**Common file references**:
- Current RBAC: [`backend/app/core/rbac.py`](backend/app/core/rbac.py)
- Secrets encryption: [`backend/app/core/secrets.py`](backend/app/core/secrets.py)
- OIDC service: [`backend/app/services/oidc.py`](backend/app/services/oidc.py)
- API entrypoint: [`backend/app/main.py`](backend/app/main.py)
- Providers API: [`backend/app/api/providers.py`](backend/app/api/providers.py)
- Providers registry: [`backend/app/services/providers/registry.py`](backend/app/services/providers/registry.py)
- Providers service: [`backend/app/services/providers/service.py`](backend/app/services/providers/service.py)
- Frontend store: [`frontend/src/store/api.ts`](frontend/src/store/api.ts)
- Frontend routing: [`frontend/src/router/index.tsx`](frontend/src/router/index.tsx)
- Permissions index: [`docs/development/permissions.md`](docs/development/permissions.md)

## Agent skills

### Issue tracker

Issues are tracked in GitHub Issues (`SteeveRan/BigBug`, via `gh` CLI). See `docs/agents/issue-tracker.md`.

### Triage labels

Default triage vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` at the repo root (created lazily), ADRs in `docs/adr/`. See `docs/agents/domain.md`.

### Analytics vs architecture: two independent processes

Analytics (requirements) and architecture (decisions) are SEPARATE processes - do not merge them, do not derive one from the other automatically:

| Process | Artifacts | Skills | Output location |
|---|---|---|---|
| **Analytics** — capture user needs and behavior | user stories (`US-<module>-NNN`), use cases (`UC-<module>-NNN`), edge-case catalogs | `/user-stories`, `/use-cases`, `/edge-cases` | `docs/analitics/stories/`, `docs/analitics/use-cases/`, `docs/analitics/edge-cases/` |
| **Architecture** — capture decisions | ADRs (MADR 4.0) | `/adr` | `docs/adr/<component>/` |

Rules:

- **Analytics is NORMATIVE — it is the user's request, not documentation.** It specifies what the system MUST do (requirements for the code), never what the code currently does. Write analytics deontically ("system must show X"), verify with tests. Analytics changes ONLY when the user's request changes — never as a side effect of a code change.
- Analytics describes WHAT the system must do for users; it never justifies itself with ADRs. Architecture describes WHY a technical choice was made; it MUST trace to analytics - the ADR's `## Context and Problem Statement` references the motivating `US-`/`UC-`/edge-case artifacts (see `docs/adr/README.md`).
- A PR must comply with analytics (and ADRs). A PR that contradicts a story, use case, or catalog row is INCORRECT and is returned - analytics does not bend to match written code.
- Implementation may ADD analytics artifacts/rows for requirements gaps discovered while building (additively, explicit reviewer acceptance in the same PR). Changing existing requirements always requires an explicit, reviewed decision.
- Architecture-relevant changes (hard to reverse + surprising + real trade-off) additionally require an ADR.
- Analytics artifacts are living repo documents with stable IDs - never store them in issues, never renumber IDs; retire in place with `status: retired`.

