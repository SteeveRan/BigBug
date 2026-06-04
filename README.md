# BigBug — DevOps Sync & Build Service

A fullstack DevOps service for:
- **Mirroring** GitHub repositories to GitLab with CI/CD pipelines
- **Building** base OS/runtime Docker images (Gold Images)
- **Building** application Docker images on top of Gold Images
- **Tracking** sync/build status, logs, and schedules

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, SQLAlchemy 2.x (async), Alembic, PostgreSQL 17 |
| Auth | JWT (local), Keycloak OIDC (SSO) |
| Scheduling | APScheduler |
| Integrations | python-gitlab, PyGithub |
| Frontend | React 19, TypeScript, Vite, Yarn |
| UI | Material UI v6 |
| State | Redux Toolkit + RTK Query |
| Routing | React Router 7 |
| Testing | pytest (backend), Vitest (frontend) |
| Dev Infra | GitLab CE, GitLab Runner, Keycloak, Redis |

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Git

### 1. Clone and configure

```bash
git clone <repo-url>
cd BigBug
cp .env.example .env
# Edit .env with your settings
```

### 2. Start dev environment

```bash
docker compose up -d
```

Services will be available at:
| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000/api/docs |
| GitLab | http://localhost:8080 |
| Keycloak | http://localhost:8180 |
| PostgreSQL | localhost:5432 |

### 3. Run database migrations

```bash
docker compose exec backend alembic upgrade head
```

### 4. Create initial admin user

```bash
docker compose exec backend python -c "
import asyncio
from app.database import AsyncSessionLocal
from app.models.user import User
from app.models.role import Role, UserRole
from app.core.security import get_password_hash

async def create_admin():
    async with AsyncSessionLocal() as db:
        role = Role(name='admin', description='Administrator')
        db.add(role)
        await db.flush()
        user = User(
            username='admin',
            email='admin@example.com',
            hashed_password=get_password_hash('changeme'),
        )
        db.add(user)
        await db.flush()
        db.add(UserRole(user_id=user.id, role_id=role.id))
        await db.commit()
        print('Admin user created: admin / changeme')

asyncio.run(create_admin())
"
```

## Development

### Backend

```bash
cd backend

# Install dependencies
pip install uv
uv pip install -e ".[dev]"

# Run migrations
alembic upgrade head

# Start dev server
uvicorn app.main:app --reload

# Run tests
pytest --cov=app tests/
```

### Frontend

```bash
cd frontend

# Install dependencies
yarn install

# Start dev server
yarn dev

# Run tests
yarn test

# Lint
yarn lint
```

## Project Structure

```
BigBug/
├── docker-compose.yml          # Dev environment
├── .env.example                # Environment variables template
├── plans/
│   └── architecture.md         # Architecture documentation
├── backend/
│   ├── alembic/                # Database migrations
│   ├── app/
│   │   ├── api/                # FastAPI routers
│   │   ├── core/               # Security, RBAC, exceptions
│   │   ├── models/             # SQLAlchemy models
│   │   ├── schemas/            # Pydantic schemas
│   │   └── services/           # Business logic
│   └── tests/                  # pytest tests
└── frontend/
    └── src/
        ├── components/         # Shared components
        ├── pages/              # Page components
        ├── router/             # React Router config
        ├── store/              # Redux store + RTK Query
        ├── tests/              # Vitest tests
        └── types/              # TypeScript types
```

## Database Schema

See [`plans/architecture.md`](plans/architecture.md) for the full ER diagram.

Key models:
- **GithubOrg / GithubProject / GithubRelease** — GitHub metadata
- **GitlabMirror** — GitLab mirror configuration
- **SyncSchedule / SyncLog** — Mirror sync scheduling and history
- **GoldImage / AppImage** — Docker image definitions
- **ImageVersion** — Unified version table (gold + app)
- **BuildSchedule / BuildLog** — Build scheduling and history
- **User / Role / UserRole** — Authentication and RBAC

## API Documentation

After starting the backend, visit:
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

## Roles

| Role | Permissions |
|------|-------------|
| `admin` | Full access + user management |
| `operator` | Manage projects, mirrors, images, trigger syncs/builds |
| `viewer` | Read-only access |

## GitLab CI Templates

See `gitlab-ci/` directory for pipeline templates:
- `mirror-template.yml` — Repository mirroring pipeline
- `gold-image-template.yml` — Gold image build pipeline
- `app-image-template.yml` — App image build pipeline

## Webhook Integration

GitLab pipelines report status back via:
```
POST /api/webhooks/gitlab
```

Configure this URL in your GitLab project's webhook settings.
