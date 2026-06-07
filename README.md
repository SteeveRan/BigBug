# BigBug

> DevOps sync & build service for GitHub mirrors, Docker images, and Helm charts

[![Backend Tests](https://img.shields.io/badge/backend%20tests-111%20passed-brightgreen)]()
[![Frontend Tests](https://img.shields.io/badge/frontend%20tests-88%20passed-brightgreen)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()

## Overview

BigBug is a fullstack DevOps service that automates the synchronization and lifecycle management of infrastructure artifacts — **GitHub repositories**, **Docker images**, and **Helm charts**. It mirrors source repositories to GitLab with CI/CD pipelines, builds layered Docker images (base OS/runtime Gold Images + application images), and keeps Docker registries and Helm chart repositories in sync.

Designed for DevOps teams and enterprises that need a single pane of glass for artifact distribution, BigBug replaces ad-hoc scripts with a unified REST API and React UI. It supports scheduled syncs, manual triggers, pipeline-driven executions via GitLab Runner, and SSO authentication through Keycloak OIDC.

## ✨ Features

- **GitHub → GitLab mirroring** with automated CI/CD pipeline creation
- **Gold Images** — base OS/runtime Docker image building
- **App Images** — application image building on top of Gold Images
- **Helm chart repository synchronization** — index, track versions, detect drift
- **Docker registry image synchronization** — resolve tags, digests, architectures
- **SSO/OIDC authentication** via Keycloak with PKCE S256
- **RBAC** — three-tier role model (admin, operator, viewer)
- **Scheduled sync & build jobs** with configurable cron expressions
- **Build/sync logs** with status tracking and pipeline URLs
- **REST API + React UI** — full management interface
- **Import existing mirrors** — adopt pre-existing GitLab mirrors without re-creating them

## 🏗️ Architecture

```
┌─────────────────┐      ┌──────────────┐      ┌──────────────────┐
│   React UI      │ ────▶│  FastAPI     │ ────▶│ PostgreSQL × 2   │
│   (Material UI) │      │  (Backend)   │      │ (app + keycloak) │
└─────────────────┘      └──────────────┘      └──────────────────┘
        │                        │                        │
        │                        ▼                        ▼
        │                ┌──────────────┐      ┌─────────────┐
        └───────────────▶│  Keycloak    │      │   Redis 7   │
                         │  (SSO/OIDC)  │      │   (Cache)   │
                         └──────────────┘      └─────────────┘
                                   │
                                   ▼
                          ┌──────────────┐
                          │ GitLab CE    │
                          │ + Runner     │
                          └──────────────┘
```

Detailed architecture: [`plans/architecture.md`](plans/architecture.md)

## 🚀 Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/engine/install/) 24+
- [OpenTofu](https://opentofu.org/docs/intro/install/) 1.6+ or [Terraform](https://www.terraform.io/downloads) 1.5+

### One-command Setup

```bash
# 1. Clone repository
git clone https://github.com/user/BigBug.git
cd BigBug

# 2. Configure environment
cp .env.example .env
# Edit .env — set ENCRYPTION_KEY, GitHub tokens, etc.

# 3. Full initialization (infrastructure + application)
./infrastructure/init.sh
```

### Manual Step-by-Step

```bash
# 1. Start infrastructure
docker compose -f infrastructure/docker-compose.yml up -d

# 2. Wait for readiness (check health)
docker compose -f infrastructure/docker-compose.yml ps

# 3. Initialize infrastructure (Keycloak → Harbor → GitLab)
cd infrastructure/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — set gitlab_token (root PAT with "api" scope)
tofu init && tofu apply

# 4. Update .env with outputs
cd ../..
./infrastructure/update-env.sh

# 5. Start application
docker compose up -d

# 7. Access UI
open http://localhost:5173
# Login: bigbug / bigbug
```

Services will start on:

| Service | URL |
|---------|-----|
| Frontend UI | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| GitLab | http://localhost:8080 |
| Keycloak | http://localhost:8180 |
| PostgreSQL (backend) | localhost:5432 |
| PostgreSQL (keycloak) | localhost:5433 |

> **Note:** The old `docker compose up -d` + `docker compose --profile init up keycloak-init` workflow is deprecated. Use the new split-compose + OpenTofu approach. See [`infrastructure/README.md`](infrastructure/README.md) for full documentation.

## 📦 Tech Stack

### Backend
- **FastAPI** — REST API framework
- **SQLAlchemy 2.x** (async) — ORM with asyncpg
- **Alembic** — database migrations
- **PostgreSQL 17** — primary database (separate instances for backend and Keycloak)
- **Redis 7** — cache and session store
- **APScheduler** (AsyncIOScheduler) — cron-based job scheduling
- **python-gitlab** / **PyGithub** — GitLab and GitHub API clients
- **python-jose** + **bcrypt** — JWT and password hashing
- **authlib** + **httpx** — OIDC/OAuth2 (Keycloak SSO)
- **cryptography** (Fernet) — at-rest secret encryption
- **pytest** + **pytest-asyncio** + **httpx** — testing

### Frontend
- **React 19** + **TypeScript** — UI framework
- **Redux Toolkit** + **RTK Query** — state management and API layer
- **Material UI v9** — component library
- **React Router v7** — client-side routing
- **Vite** — build tool with HMR
- **keycloak-js** — Keycloak OIDC adapter
- **Vitest** + **@testing-library/react** — testing
- **ESLint** + **@typescript-eslint** — linting

### Infrastructure (dev)
- **GitLab CE** + **GitLab Runner** — mirror target and CI/CD executor
- **Keycloak 24** — SSO provider
- **Harbor** (in kind) — local OCI registry for testing
- **Docker Compose** — local development orchestration (split into [infra](infrastructure/docker-compose.yml) and [app](docker-compose.yml))
- **OpenTofu** / **Terraform** — declarative infrastructure provisioning (Keycloak → Harbor → GitLab)

## 🗂️ Project Structure

```
BigBug/
├── backend/                # FastAPI application
│   ├── alembic/            # Database migrations
│   ├── app/
│   │   ├── api/            # REST API routers
│   │   ├── core/           # Security, RBAC, exceptions, secrets
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   └── services/       # Business logic layer
│   ├── docker/             # Dockerfile + entrypoint
│   ├── scripts/            # Format, lint, test scripts
│   ├── tests/              # pytest test suite (111 tests)
│   └── pyproject.toml      # Python dependencies
├── frontend/               # React UI
│   ├── src/
│   │   ├── components/     # Shared UI components
│   │   ├── hooks/          # Custom React hooks
│   │   ├── pages/          # Page components per feature
│   │   ├── router/         # React Router configuration
│   │   ├── services/       # External service adapters (Keycloak)
│   │   ├── store/          # Redux store + RTK Query
│   │   ├── tests/          # Vitest test suite (88 tests)
│   │   └── types/          # TypeScript type definitions
│   ├── docker/             # Dockerfile
│   ├── scripts/            # Format, lint, test scripts
│   └── package.json        # Node dependencies
├── infrastructure/          # Infrastructure initialization
│   ├── init.sh              # Full environment initialization script
│   ├── update-env.sh        # Update .env from OpenTofu outputs
│   ├── docker-compose.yml   # Infrastructure services (postgres-keycloak, Keycloak, GitLab)
│   ├── terraform/           # Root OpenTofu module + sub-modules (keycloak, harbor, gitlab)
│   ├── harbor/              # Harbor deployment in kind
│   └── gitlab-components/   # GitLab CI/CD component templates
├── docker-compose.yml       # Application services (postgres-backend, redis, backend, frontend)
├── gitlab-ci/               # CI/CD pipeline templates (legacy)
├── plans/                  # Architecture documentation
├── .env.example             # Environment variables template
└── CHANGELOG.md             # Version history
```

## 🔧 Development

### Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .

# Run migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload

# Run tests
./run_tests.sh
```

### Frontend

```bash
cd frontend

# Install dependencies
yarn install

# Start development server
yarn dev

# Run tests
./run_tests.sh

# TypeScript check
npx tsc --noEmit

# Lint
yarn lint
```

## 🐳 Docker Compose Services

### Infrastructure (`infrastructure/docker-compose.yml`)

| Service | Port | Description |
|---------|------|-------------|
| `postgres-keycloak` | 5433 | Keycloak database (separate instance) |
| `keycloak` | 8180 | SSO/OIDC identity provider |
| `gitlab` | 8080 | GitLab CE for CI/CD |
| `gitlab-runner` | — | Pipeline executor |

### Application (`docker-compose.yml`)

| Service | Port | Description |
|---------|------|-------------|
| `postgres-backend` | 5432 | Application database (Alembic-managed schema) |
| `redis` | 6379 | Cache and session store |
| `backend` | 8000 | FastAPI REST API with hot reload |
| `frontend` | 5173 | React dev server with HMR |

## 🔐 Authentication

### Local Login

```bash
POST /api/auth/login     # username + password → JWT access token
```

Default admin user (created by `keycloak-init`): `bigbug` / `bigbug`

### SSO Login (Keycloak OIDC)

- **Realm:** `bigbug`
- **Clients:**
  - `bigbug-frontend` — public client, PKCE S256 enforced
  - `bigbug-backend` — confidential client, client secret auth
- **Roles:** synced from `realm_access.roles` → admin, operator, viewer

### RBAC

| Role | Permissions |
|------|-------------|
| `admin` | Full access + user/role management |
| `operator` | Manage projects, mirrors, images, helm charts, docker images, trigger syncs |
| `viewer` | Read-only access to all resources |

## 🧪 Testing

```bash
# Backend (111 tests)
cd backend && ./run_tests.sh

# Frontend (88 tests)
cd frontend && ./run_tests.sh
```

### Test Coverage

**Backend:** OIDC service (19), Helm service (14), Docker service (16), Secrets (11), Helm API (15), Docker API (16), Auth (7), Projects (6), Images (7)

**Frontend:** Keycloak service (17), `useKeycloakAuth` hook (10), SSO callback (9), Helm charts pages (19), Docker images pages (21), Auth slice (6), StatusChip (6)

## 🌊 Harbor Deployment

Local OCI registry for development and testing, deployed in a [kind](https://kind.sigs.k8s.io/) Kubernetes cluster.

```bash
cd infrastructure/harbor

# Deploy Harbor
./deploy.sh

# Verify push/pull works
./test-push.sh

# Tear down
./teardown.sh --all
```

Access: `https://harbor.local:30443` (admin / Harbor12345)

See [`infrastructure/harbor/README.md`](infrastructure/harbor/README.md) for prerequisites, troubleshooting, and manual setup instructions.

## 📝 API Documentation

After starting the backend:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

### Key Endpoints

| Group | Prefix | Description |
|-------|--------|-------------|
| Auth | `/api/auth` | Login, token refresh, SSO config & exchange |
| Projects | `/api/projects` | GitHub project CRUD |
| Mirrors | `/api/mirrors` | GitLab mirror management |
| Gold Images | `/api/gold-images` | Base image CRUD |
| App Images | `/api/app-images` | App image CRUD |
| Helm Charts | `/api/helm-charts` | Chart source CRUD, indexing, versions |
| Docker Images | `/api/docker-images` | Registry source CRUD, indexing, tags |
| Schedules | `/api/schedules` | Sync and build schedule management |
| Webhooks | `/api/webhooks` | GitLab pipeline status callbacks |
| Admin | `/api/admin` | User and role management (admin only) |

## 🗺️ Roadmap

- [ ] Cosign image signing integration
- [ ] Advanced scheduling — retry policies, concurrency limits, backoff
- [ ] Metrics & monitoring — Prometheus metrics + Grafana dashboards
- [ ] Multi-tenancy — isolated projects and resources per team
- [ ] Notification channels — Slack, Discord, email alerts
- [ ] Helm OCI registry support
- [ ] Harbor-native replication policies

## 🤝 Contributing

See [`CHANGELOG.md`](CHANGELOG.md) for the full version history.

Pull requests are welcome. Please:

- Follow the existing code style and patterns documented in [`plans/architecture.md`](plans/architecture.md)
- Add tests for new features (pytest for backend, Vitest for frontend)
- Update documentation for any user-facing changes
- Keep PR scope focused — one feature or fix per PR

### Code Patterns

The project follows consistent patterns:

- **Backend:** SQLAlchemy 2.0 Column-style models → Pydantic v2 schemas → domain service layer (throws `RuntimeError` subclasses, never `HTTPException`) → API router (maps to HTTP status codes).
- **Frontend:** TypeScript interfaces in `types/` → RTK Query endpoints in `store/api.ts` → page components in `pages/FeatureName/` → routes in `router/index.tsx`.
- **RBAC:** `require_admin`, `require_operator`, `require_viewer` FastAPI dependencies.
- **Secrets:** `encrypt_secret()` / `decrypt_secret()` via Fernet for registry passwords.

## 📄 License

MIT License — see the [LICENSE](LICENSE) file.

## 🙏 Acknowledgments

- [Harbor](https://goharbor.io/) — CNCF-graduated container registry
- [Keycloak](https://www.keycloak.org/) — open source identity and access management
- [GitLab](https://about.gitlab.com/) — complete DevOps platform
- [FastAPI](https://fastapi.tiangolo.com/) — modern Python web framework
- [Material UI](https://mui.com/) — React component library
