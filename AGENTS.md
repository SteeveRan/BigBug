# BigBug - Guide for AI Agents

Quick reference for AI agents working on BigBug project.

## Project Overview

**BigBug** — централизованная DevOps платформа для управления:
- **Docker образами**: Gold Images (базовые OS/runtime), App Images (приложения)
- **Зеркалированием**: GitHub → GitLab с автоматическими CI/CD пайплайнами
- **Синхронизацией**: Docker Registry образов и Helm Repository чартов
- **CI/CD**: GitLab Pipelines и Components через UI

**Архитектура**: FastAPI backend + React frontend + PostgreSQL + Redis + GitLab CI/CD

**Текущее состояние**: Проект проходит масштабный рефакторинг. Реализована базовая функциональность (блоки 1-5), идёт миграция на новую архитектуру с расширенной RBAC и управляемыми интеграциями.

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
│   ├── tests/           # pytest tests
│   └── pyproject.toml   # Python dependencies
├── frontend/            # React + TypeScript SPA
│   ├── src/
│   │   ├── components/  # Reusable UI components
│   │   ├── pages/       # Page components
│   │   ├── router/      # React Router config
│   │   ├── store/       # Redux + RTK Query
│   │   ├── services/    # API clients
│   │   └── types/       # TypeScript interfaces
│   └── package.json     # Node dependencies
├── gitlab-ci/           # GitLab CI/CD templates
├── infrastructure/      # Infrastructure setup (OpenTofu, scripts, configs)
│   ├── keycloak/       # OpenTofu Keycloak config
│   ├── gitlab/         # OpenTofu GitLab config
│   ├── harbor/         # Harbor deployment (setup + terraform)
│   └── gitlab-components/ # GitLab CI/CD component templates
├── docs/
│   └── architecture/    # Detailed design docs (for human review)
├── plans/               # Implementation plans for agents
└── .roo/                # Kiro AI rules and guidelines
```

## Technology Stack

### Backend (Python 3.14+)
- **FastAPI** - async REST API framework
- **SQLAlchemy 2.x** - ORM with async support
- **Alembic** - database migrations
- **PostgreSQL 17** - primary database
- **Redis 7** - caching and task queues
- **APScheduler** - scheduled jobs (AsyncIOScheduler)
- **python-gitlab** - GitLab API client
- **PyGithub** - GitHub API client
- **httpx** - async HTTP client for Harbor/Docker/Helm APIs
- **authlib** - OIDC/OAuth2 (Keycloak SSO)
- **cryptography** - Fernet encryption for secrets
- **pytest** + **pytest-asyncio** + **httpx** - testing

### Frontend (Node.js 24.16.0 LTS)
- **React 19** + **TypeScript**
- **Vite** - build tool
- **Yarn 4.3.1** - package manager
- **Redux Toolkit** + **RTK Query** - state management
- **Material UI v6** - component library
- **React Router v7** - routing
- **ESLint** + `@typescript-eslint` - linting
- **Vitest** + `@testing-library/react` - unit tests
- **Cypress** - e2e tests (planned)
- **keycloak-js** - SSO adapter

### Infrastructure (dev)
- **GitLab CE** - CI/CD platform + mirror target
- **GitLab Runner** - pipeline executor
- **Keycloak** - SSO / OIDC provider
- **Harbor** (optional) - container registry
- **PostgreSQL 17** (2 instances: backend + keycloak)
- **Redis 7**

## Development Workflow

### Backend (Python/FastAPI)

**Location**: [`/backend/`](backend/)

**Setup**:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
pip install -e .
```

**Development**:
```bash
# Run migrations
alembic upgrade head

# Start dev server (auto-reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest

# Run specific test
pytest tests/test_auth.py -v

# Code quality (in order)
ruff format .              # Format
ruff check --fix .         # Lint & auto-fix
pytest                     # Test
```

**Key conventions**:
- Models: one file per model in [`app/models/`](backend/app/models/)
- Schemas: Pydantic v2 in [`app/schemas/`](backend/app/schemas/)
- Services: business logic in [`app/services/`](backend/app/services/)
- API routers: in [`app/api/`](backend/app/api/), registered in [`main.py`](backend/app/main.py)
- Migrations: `alembic revision -m "description"` → edit file → `alembic upgrade head`

See: [`/plans/development/backend.md`](plans/development/backend.md)

### Frontend (React/TypeScript)

**Location**: [`/frontend/`](frontend/)

**Setup**:
```bash
# Use nvm for Node.js version management
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

cd frontend
yarn install
```

**Development**:
```bash
# Start dev server (HMR)
yarn dev

# Type check (no emit)
npx tsc --noEmit

# Lint & format
yarn lint
yarn format

# Run tests
yarn test

# Build for production
yarn build
```

**Key conventions**:
- Pages: in [`src/pages/ComponentName/index.tsx`](frontend/src/pages/)
- Components: reusable in [`src/components/`](frontend/src/components/)
- Store: Redux slices + RTK Query in [`src/store/`](frontend/src/store/)
- Types: TypeScript interfaces in [`src/types/index.ts`](frontend/src/types/)
- Routing: in [`src/router/index.tsx`](frontend/src/router/)

See: [`/plans/development/frontend.md`](plans/development/frontend.md)

### Docker Compose

**Infrastructure services** (start once):
```bash
docker compose -f docker-compose.infra.yml up -d
```

**Application services** (rebuild often):
```bash
docker compose -f docker-compose.app.yml up -d
```

**Full environment**:
```bash
# Legacy single file (deprecated, use split files above)
docker compose up -d
```

See: [`/plans/development/infrastructure.md`](plans/development/infrastructure.md)

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
- API endpoints in RTK Query: [`frontend/src/store/api.ts`](frontend/src/store/api.ts)

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
# Creates: 20260605_1234_<hash>_add_user_keycloak_sub.py
```

**Naming conventions**:
- Tables: `users`, `roles`, `gitlab_mirrors` (plural, snake_case)
- Columns: `user_id`, `created_at`, `is_active` (snake_case)
- Foreign keys: `{table}_id`, e.g., `user_id`
- Indexes: `ix_{table}_{column}`, e.g., `ix_users_email`

See: [`/plans/development/database.md`](plans/development/database.md)

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
// src/tests/Component.test.tsx
import { render, screen } from '@testing-library/react';
test('renders component', () => {
  render(<Component />);
  expect(screen.getByText('text')).toBeInTheDocument();
});
```

**Run tests**:
```bash
# Backend
cd backend && pytest

# Frontend
cd frontend && yarn test
```

See: [`/plans/development/testing.md`](plans/development/testing.md)

## Current Migration

🚧 **BigBug проходит масштабный рефакторинг** согласно [`/docs/architecture/`](docs/architecture/).

### Active Changes

**RBAC System** ([docs/architecture/02-rbac-design.md](docs/architecture/02-rbac-design.md)):
- Permission-based модель (`resource:action`)
- 30+ granular permissions
- Кастомные роли + предустановленные (Admin/Operator/Viewer)
- Таблицы: `permissions`, `role_permissions`, расширение `roles`

**Authentication** ([docs/architecture/03-authentication.md](docs/architecture/03-authentication.md)):
- Local auth (email/password) по умолчанию
- Опциональная OIDC интеграция через настройки
- Таблица `oidc_config` для хранения конфигурации
- Синхронизация ролей из Keycloak

**Integrations** ([docs/architecture/04-integrations/](docs/architecture/04-integrations/)):
- Множественные инстансы GitLab, Harbor, GitHub
- Отдельные таблицы: `gitlab_instances`, `harbor_instances`, etc
- Управление через Admin UI
- Шифрование credentials (Fernet)

**Pipelines** ([docs/architecture/08-pipelines.md](docs/architecture/08-pipelines.md)):
- GitLab Pipelines управление через UI
- GitLab Components (переиспользуемые CI/CD блоки)
- Таблица `pipeline_runs` для истории
- Webhook обратная связь

**UI Structure** ([docs/architecture/09-ui-structure.md](docs/architecture/09-ui-structure.md)):
- Новая навигация: Builds / Mirroring / Pipelines / Settings
- Settings разбит на: Integrations / Authentication / Users & Roles
- Permission-based routing и компоненты
- Hook `usePermissions()` и `<PermissionGate>`

### Migration Status

**Completed** (blocks 1-5):
- ✅ Docker infrastructure + SSO
- ✅ OIDC service + backend API
- ✅ Keycloak frontend integration
- ✅ Helm Charts (sources, versions, sync)
- ✅ Docker Images (sources, tags, sync)
- ✅ Frontend UI для Helm и Docker

**In Progress**:
- 🚧 RBAC implementation (Phase 1)
- 🚧 Multi-instance integrations (Phase 2)

**Planned**:
- ⏳ Tests (backend + frontend)
- ⏳ Harbor integration
- ⏳ Pipeline management UI
- ⏳ Audit logging

See: [`/docs/architecture/11-migration-strategy.md`](docs/architecture/11-migration-strategy.md)

## Working with Specific Features

### Adding New Integration

1. Define model in [`backend/app/models/`](backend/app/models/)
2. Create Alembic migration
3. Create Pydantic schemas in [`backend/app/schemas/`](backend/app/schemas/)
4. Implement service in [`backend/app/services/`](backend/app/services/)
5. Create API router in [`backend/app/api/`](backend/app/api/)
6. Add RTK Query endpoints in [`frontend/src/store/api.ts`](frontend/src/store/api.ts)
7. Create UI pages in [`frontend/src/pages/`](frontend/src/pages/)

See: [`/plans/features/integrations.md`](plans/features/integrations.md)

### Modifying RBAC

1. Add permissions to [`backend/app/core/rbac.py`](backend/app/core/rbac.py) or DB
2. Use `require_permission()` dependency in API endpoints
3. Update frontend `usePermissions()` hook
4. Wrap UI components in `<PermissionGate permission="...">`

See: [`/plans/features/auth-rbac.md`](plans/features/auth-rbac.md)

### Creating Pipeline

1. Define GitLab CI template in [`gitlab-ci/`](gitlab-ci/)
2. Use service to trigger via GitLab API
3. Handle webhook callback in [`backend/app/api/webhooks.py`](backend/app/api/webhooks.py)
4. Update status in database
5. Display in frontend

See: [`/plans/features/pipelines.md`](plans/features/pipelines.md)

### Working with Secrets

Use encryption for sensitive data:
```python
from app.core.secrets import encrypt_secret, decrypt_secret

# Store
encrypted = encrypt_secret("my-token")
# Retrieve
token = decrypt_secret(encrypted)
```

See: [`/plans/features/security.md`](plans/features/security.md)

## Documentation

### For Implementation (agents)
- **Implementation plans**: [`/plans/`](plans/) - модульное чтение по необходимости
- **This guide**: [`/AGENTS.md`](AGENTS.md) - quick start reference

### For Review (humans)
- **Architecture**: [`/docs/architecture/`](docs/architecture/) - НЕ читать в контекст агентов (слишком объёмно)
- **API docs**: Auto-generated at `http://localhost:8000/docs` (Swagger UI)
- **Migration strategy**: [`/docs/architecture/11-migration-strategy.md`](docs/architecture/11-migration-strategy.md)

### Legacy Documentation
- [`/plans/architecture.md`](plans/architecture.md) - устаревшая архитектура (сохранено для истории)
- [`/plans/handoff-summary.md`](plans/handoff-summary.md) - handoff блоков 1-5 (архив)

## Common Tasks

### Start Development Environment

```bash
# 1. Start infrastructure
docker compose -f docker-compose.infra.yml up -d

# 2. Wait for services (check http://localhost:8180, http://localhost:8080)

# 3. Initialize Keycloak (if first time)
cd infrastructure && ./init.sh

# 4. Start application
docker compose -f docker-compose.app.yml up -d

# Or run locally:
# Backend
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload

# Frontend
cd frontend && yarn dev
```

### Run Tests

**Агентам**: Всегда запускать тесты через скрипты:

```bash
# Backend unit tests (+ format + lint)
./backend/scripts/test-unit.sh -v

# Backend e2e tests
./backend/scripts/test-e2e.sh -v

# Frontend unit tests (Vitest)
./frontend/scripts/test-unit.sh
```

**Вручную** (требуется активировать окружение):

```bash
# Backend
cd backend
source .venv/bin/activate
pytest                          # All tests
pytest tests/test_auth.py -v   # Specific file
pytest -k "test_login" -v      # By name pattern

# Frontend (требуется nvm: export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh")
cd frontend
yarn test                       # Watch mode
yarn test:run                   # Single run
yarn test:coverage              # With coverage
```

### Database Migrations

```bash
cd backend

# Create migration
alembic revision -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Show current revision
alembic current

# Show migration history
alembic history
```

### Code Quality Checks

**Агентам**: использовать скрипты (они загружают правильное окружение):

```bash
# Backend
./backend/scripts/format.sh
./backend/scripts/lint.sh
./backend/scripts/test-unit.sh

# Frontend
./frontend/scripts/format.sh
./frontend/scripts/lint.sh
./frontend/scripts/test-unit.sh

# Type check frontend
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && cd frontend && npx tsc --noEmit
```

**Вручную** (требуется активировать окружение):

```bash
# Backend
cd backend && source .venv/bin/activate
ruff format .              # Format
ruff check --fix .         # Lint and auto-fix
pytest                     # Test

# Frontend (требуется nvm)
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh"
cd frontend
yarn format                # Prettier
yarn lint                  # ESLint
npx tsc --noEmit          # Type check
yarn test:run              # Test
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

## Troubleshooting

### Backend Issues

**Import errors**:
```bash
# Reinstall dependencies
pip install -e .
```

**Database connection failed**:
```bash
# Check PostgreSQL is running
docker compose -f docker-compose.infra.yml ps postgres-backend

# Check connection in .env
DATABASE_URL=postgresql+asyncpg://bigbug:bigbug@localhost:5432/bigbug
```

**Migration conflicts**:
```bash
# Check current state
alembic current

# Resolve conflicts manually in alembic/versions/
# Then: alembic upgrade head
```

### Frontend Issues

**Type errors**:
```bash
# Regenerate lock file
rm yarn.lock && yarn install

# Clear cache
rm -rf node_modules/.vite
```

**API connection issues**:
```bash
# Check backend is running
curl http://localhost:8000/api/health

# Check VITE_API_URL in .env or vite.config.ts proxy
```

**Keycloak SSO not working**:
```bash
# Check Keycloak is running
curl http://localhost:8180/realms/bigbug

# Verify configuration in backend
curl http://localhost:8000/api/auth/sso/config
```

### Docker Issues

**Services not starting**:
```bash
# Check logs
docker compose -f docker-compose.infra.yml logs -f keycloak

# Restart service
docker compose -f docker-compose.infra.yml restart keycloak
```

**Port conflicts**:
```bash
# Check what's using the port
lsof -i :8000

# Change port in docker-compose or .env
```

## Getting Help

**For detailed implementation plans**, read specific files from [`/plans/`](plans/):
- [`/plans/development/`](plans/development/) - setup, testing, deployment
- [`/plans/features/`](plans/features/) - feature-specific guides
- [`/plans/architecture/`](plans/architecture/) - architecture decisions

**For architectural decisions**, consult [`/docs/architecture/README.md`](docs/architecture/README.md) (human review).

**For specific task context**, AI agents should:
1. Read [`AGENTS.md`](AGENTS.md) (this file) first
2. Read relevant modular plans from [`/plans/`](plans/) as needed
3. NOT read [`/docs/architecture/`](docs/architecture/) into context (too large, for human reference only)
4. Examine actual code files to understand current implementation
5. Ask clarifying questions if requirements are unclear

**Common file references**:
- Current RBAC: [`backend/app/core/rbac.py`](backend/app/core/rbac.py)
- Secrets encryption: [`backend/app/core/secrets.py`](backend/app/core/secrets.py)
- OIDC service: [`backend/app/services/oidc.py`](backend/app/services/oidc.py)
- API entrypoint: [`backend/app/main.py`](backend/app/main.py)
- Frontend store: [`frontend/src/store/api.ts`](frontend/src/store/api.ts)
- Frontend routing: [`frontend/src/router/index.tsx`](frontend/src/router/index.tsx)
