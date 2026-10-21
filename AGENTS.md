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
│   ├── docker-compose.yml    # Infrastructure services (Keycloak, GitLab)
│   ├── init.sh               # Initialization script
│   ├── update-env.sh         # Environment update script
│   ├── terraform/            # Root OpenTofu module + sub-modules (keycloak, harbor, gitlab)
│   ├── harbor/               # Harbor deployment in kind
│   └── gitlab-components/ # GitLab CI/CD component examples (not used by app; see backend presets.py)
├── docs/
│   └── architecture/    # Detailed design docs (for human review)
├── plans/               # Implementation plans for agents
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
| Dev environment (Compose split) | [ADR-0012](docs/adr/infrastructure/0012-docker-compose-split-dev-env.md) |
| IaC (OpenTofu: Keycloak, GitLab, Harbor) | [ADR-0013](docs/adr/infrastructure/0013-opentofu-iac-keycloak-gitlab-harbor.md) |

**Инфраструктурные сервисы dev-стенда** (детали — [ADR-0012](docs/adr/infrastructure/0012-docker-compose-split-dev-env.md)/[0013](docs/adr/infrastructure/0013-opentofu-iac-keycloak-gitlab-harbor.md)): GitLab CE (+ Runner), Keycloak, Harbor (в kind), PostgreSQL 17 (2 инстанса), Redis 7.

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

See: [`/plans/development/backend.md`](plans/development/backend.md)

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

See: [`/plans/development/frontend.md`](plans/development/frontend.md)

### Make-команды (единая точка входа)

Все скрипты запускаются через корневой [`Makefile`](Makefile). Справка: `make help`.

| Группа | Примеры |
|---|---|
| `dev-*` | `make dev-up`, `make dev-init`, `make dev-down`, `make dev-clean` |
| `infra-*` | `make infra-up`, `make infra-init`, `make infra-clean` |
| `test-*` | `make test-unit-backend`, `make test-e2e-backend`, `make test-all` |
| `lint-*`/`format-*`/`typecheck-*` | `make lint`, `make format`, `make typecheck` |
| `coverage-*` | `make coverage-all` |
| `dead-code-*` | `make dead-code` |

See: [ADR-0013](docs/adr/infrastructure/0013-opentofu-iac-keycloak-gitlab-harbor.md) — IaC (OpenTofu) для Keycloak/GitLab/Harbor; troubleshooting инфраструктуры — ниже.

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

### Testing

**Backend** (pytest):
```python
# tests/test_feature.py
async def test_feature_success(async_client):
    response = await async_client.post("/api/endpoint", json={...})
    assert response.status_code == 200
```

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
- Code-coverage e2e: `cd backend && ./scripts/test-e2e-coverage.sh` (backend под coverage на порту 8011; `COVERAGE_PORT` переопределяет).
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
# GitLab API доступен / токен валиден
curl -H "PRIVATE-TOKEN: glpat-xyz" http://localhost:8080/api/v4/user
curl -H "PRIVATE-TOKEN: glpat-xyz" http://localhost:8080/api/v4/personal_access_tokens/self

# Harbor доступен / SSL
curl -u admin:Harbor12345 https://harbor.local/api/v2.0/systeminfo
curl -k -u admin:Harbor12345 https://harbor.local/api/v2.0/systeminfo

# Helm index.yaml парсится (скачать и проверить)
curl https://charts.helm.sh/stable/index.yaml | head -50
```

Диагностика в BigBug: `POST /api/providers/{id}/test` обновляет `status_flag`/`status_text` провайдера; `GET /api/providers/{id}/usage` показывает потребителей перед удалением.

### Infrastructure Troubleshooting

Ручная диагностика инфраструктурных сервисов (compose-слой — [ADR-0012](docs/adr/infrastructure/0012-docker-compose-split-dev-env.md), IaC — [ADR-0013](docs/adr/infrastructure/0013-opentofu-iac-keycloak-gitlab-harbor.md)):

```bash
# Сервисы не стартуют: логи, сеть, volumes
docker compose -f infrastructure/docker-compose.yml logs keycloak
docker network inspect bigbug-infra-network
docker volume ls | grep bigbug

# Конфликты портов
lsof -i :8000; lsof -i :5432; lsof -i :8080

# GitLab: полная загрузка занимает 2-5 минут; root password для fresh-инстанса
docker compose -f infrastructure/docker-compose.yml logs -f gitlab
docker compose -f infrastructure/docker-compose.yml exec gitlab grep 'Password:' /etc/gitlab/initial_root_password

# OpenTofu: сброс state и повторная инициализация с нуля
make infra-clean && make infra-init

# Health-чеки сервисов
curl http://localhost:8000/health        # backend
curl http://localhost:8180/realms/bigbug # Keycloak
curl http://localhost:8080/-/health      # GitLab
```

Backup: PostgreSQL — `docker exec bigbug-postgres-backend pg_dump -U bigbug bigbug > backup.sql`; tofu state — local файлы в `infrastructure/terraform/` (gitignored), пересоздаются `infra-init`.

### Modifying RBAC

1. Add permissions to [`backend/app/core/rbac.py`](backend/app/core/rbac.py) or DB
2. Use `require_permission()` dependency in API endpoints
3. Update frontend `usePermissions()` hook
4. Wrap UI components in `<PermissionGate permission="...">`

See: [`/docs/adr/common/0004-permission-based-rbac-scope-providers.md`](docs/adr/common/0004-permission-based-rbac-scope-providers.md) and [`/plans/architecture/permissions.md`](plans/architecture/permissions.md)

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
- Создание ADR — через команду `/adr` в OpenCode (workflow skill `adr-skill`). Статус `accepted` выставляет только человек; при `superseded`/`rejected` ADR перемещается в `docs/adr/archive/<component>/` и реестры обновляются.

## Documentation

### Diagrams
- **Все диаграммы/схемы в документации — только Mermaid** (fenced-блоки ` ```mermaid ` в markdown). Не использовать PlantUML, draw.io, ASCII-арт и т.п.
- **C4 model диаграммы — отдельная категория**: Context/Container/Component диаграммы пишутся на Mermaid C4 syntax (`c4Context`, `c4Container`, `c4Component`, ` ```c4context ` и т.п.) и размещаются отдельно от обычных mermaid-диаграмм — не смешивать C4 и обычные (flow/sequence/ER) диаграммы в одном блоке/разделе.

### For Implementation (agents)
- **Implementation plans**: [`/plans/`](plans/) - модульное чтение по необходимости
- **Permissions index**: [`/plans/architecture/permissions.md`](plans/architecture/permissions.md) — единый источник истины для всех permissions. **Обязательно обновлять** при добавлении/изменении любых прав.
- **This guide**: [`/AGENTS.md`](AGENTS.md) - quick start reference

### For Review (humans)
- **Architecture**: [`/docs/architecture/`](docs/architecture/) - НЕ читать в контекст агентов (слишком объёмно)
- **API docs**: Auto-generated at `http://localhost:8000/docs` (Swagger UI)
- **Migration strategy**: [`/docs/architecture/11-migration-strategy.md`](docs/architecture/11-migration-strategy.md)

### Legacy Documentation
- Legacy plans-документы (`plans/architecture.md`, `plans/current-state.md`, `plans/architecture/decisions.md`, `plans/project-overview.md`, `plans/development/testing.md`) удалены — решения в реестре [`docs/adr/README.md`](docs/adr/README.md), история в git.

## Common Tasks

### Start Development Environment

```bash
make infra-init    # 1. Keycloak → Harbor → GitLab (infrastructure/init.sh)
make dev-up        # 2. postgres, redis, backend, frontend (docker compose up -d)
```

### Run Tests

**Агентам**: Всегда запускать тесты через `make` (см. таблицу выше). Конкретный тест — через `TEST_ARGS`:
```bash
make test-unit-backend TEST_ARGS="-k test_login"
make test-unit-frontend TEST_ARGS="-f Pipelines -t 'should trigger'"
```

### Code Quality Checks

**Агентам**: использовать `make` (скрипты загружают правильное окружение):
```bash
make format      # ruff format + prettier
make lint        # ruff check + eslint
make typecheck   # mypy + tsc --noEmit
make dead-code   # vulture + knip
```

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

**For detailed implementation plans**, read specific files from [`/plans/`](plans/):
- [`/plans/development/`](plans/development/) - setup, backend, frontend
- [`/plans/architecture/`](plans/architecture/) - permissions index (операционный)
- Architecture decisions: реестр [`docs/adr/README.md`](docs/adr/README.md)

**For architectural decisions**, consult реестр [ADR](docs/adr/README.md); детальная архитектура для людей — [`/docs/architecture/README.md`](docs/architecture/README.md).

**For specific task context**, AI agents should:
1. Read [`AGENTS.md`](AGENTS.md) (this file) first
2. Read relevant modular plans from [`/plans/`](plans/) as needed
3. NOT read [`/docs/architecture/`](docs/architecture/) into context (too large, for human reference only)
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
- Permissions index: [`plans/architecture/permissions.md`](plans/architecture/permissions.md)

