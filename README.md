# BigBug

> DevOps sync & build service for GitHub mirrors, Docker images, and Helm charts

[![Backend](https://img.shields.io/badge/backend-pytest-blue)]()
[![Frontend](https://img.shields.io/badge/frontend-vitest-blue)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()

## Overview

BigBug is a fullstack DevOps service that automates the synchronization and lifecycle management of infrastructure artifacts — **GitHub repositories**, **Docker images**, and **Helm charts**. It mirrors source repositories to GitLab with CI/CD pipelines, builds layered Docker images (base OS/runtime Gold Images + application images), and keeps Docker registries and Helm chart repositories in sync.

Designed for DevOps teams and enterprises that need a single pane of glass for artifact distribution, BigBug replaces ad-hoc scripts with a unified REST API and React UI. It supports scheduled syncs, manual triggers, pipeline-driven executions via GitLab Runner, and SSO authentication through Keycloak OIDC.

## ✨ Features

- **GitHub → GitLab mirroring** with automated CI/CD pipeline creation
- **GitLab Projects / Components / Pipelines management** through the app API — create projects, manage files/tags, generate component presets and push CI configuration
- **Providers V3** — a single `resource_providers` entity for all external integrations (GitHub/GitLab/Docker registries/Helm repos) with teams, sharing, and scope-based permissions
- **Docker import** — mirror images from public registries (Docker Hub and others) into Harbor
- **Helm chart mirror workflow** — mirror chart sources into a GitLab project with status tracking
- **Gold Images** — base OS/runtime Docker image building
- **App Images** — application image building on top of Gold Images
- **Helm chart repository synchronization** — index, track versions, detect drift
- **Docker registry image synchronization** — resolve tags, digests, architectures
- **SSO/OIDC authentication** via Keycloak with PKCE S256
- **Permission-based RBAC** — `resource:action` permissions, custom roles, teams and scope-providers
- **Teams & Profile** — team management and per-user views of teams and providers
- **Scheduled sync & build jobs** with configurable cron expressions
- **Build/sync logs** with status tracking and pipeline URLs
- **REST API + React UI** — full management interface
- **Import existing mirrors** — adopt pre-existing GitLab mirrors without re-creating them

## 🏗️ Architecture

```
┌─────────────────┐      ┌──────────────┐      ┌──────────────────┐
│   React UI      │ ────▶│  FastAPI     │ ────▶│ PostgreSQL × 2   │
│  (Ant Design)   │      │  (Backend)   │      │ (app + keycloak) │
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

Architecture decisions: [ADR registry](docs/adr/README.md) · Operational runbooks: [`docs/runbooks/`](docs/runbooks/) · Implementation guides: [`docs/development/`](docs/development/).

## 🚀 Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/engine/install/) 24+
- [OpenTofu](https://opentofu.org/docs/intro/install/) 1.6+ or [Terraform](https://www.terraform.io/downloads) 1.5+

### One-command Setup

```bash
# 1. Clone repository
git clone https://github.com/user/BigBug.git
cd BigBug

# 2. Full initialization (certs → trust → GitLab + kind + OpenTofu)
./infrastructure/init.sh

# 3. Build dev images and deploy the app (helm chart bigbug, ADR-0023)
make dev-build
make dev-up
```

### Manual Step-by-Step

```bash
# 1. TLS certs + host trust + GitLab compose zone (init.sh does all: certs → trust → compose)
./infrastructure/init.sh

# 1. TLS certs + host trust + GitLab + kind (init.sh does: certs → trust → GitLab compose → kind)
./infrastructure/init.sh

# 2. OpenTofu: base → infra-apps (2 phases) → apps (ADR-0029) — init.sh runs this too;
#    manual split (if needed step-by-step):
cd infrastructure/terraform/base && tofu init && tofu apply && cd ../..
cd infrastructure/terraform/infra-apps && tofu init \
  && tofu apply -target=module.keycloak_init -target=module.harbor_init \
  && tofu apply && cd ../..
cd infrastructure/terraform/apps && tofu init && tofu apply && cd ../..

# 3. Build dev images and deploy the app
make dev-build
make dev-up

# 4. Access UI
open https://app.local
# Login: bigbug / bigbug
```

Services (https behind the kind ingress — ADR-0030):

| Service | URL |
|---------|-----|
| Frontend UI | https://app.local |
| Backend API | https://api.local |
| GitLab | https://gitlab.local:8443 |
| Keycloak | https://keycloak.local |
| Harbor | https://harbor.local |

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
- **mypy** + **vulture** — static type checking and dead code detection

### Frontend
- **React 19** + **TypeScript** — UI framework
- **Redux Toolkit** + **RTK Query** — state management and API layer
- **Ant Design 6** — component library
- **React Router v7** — client-side routing
- **Vite** — build tool with HMR
- **keycloak-js** — Keycloak OIDC adapter
- **Vitest** + **@testing-library/react** — testing
- **ESLint** + **@typescript-eslint** — linting
- **knip** — dead code detection

### Infrastructure (dev)
- **kind-стенд `bigbug-dev`** ([ADR-0022](docs/adr/infrastructure/0022-dev-stand-on-kind.md)) — haproxy-ingress, операторы CNPG + redis-operator, keycloakx, Harbor (chart), приложение
- **GitLab CE** + **GitLab Runner** — mirror target and CI/CD executor (compose-исключение, [ADR-0033](docs/adr/infrastructure/0033-gitlab-dev-stand-compose-omnibus.md))
- **OpenTofu** / **Terraform** — declarative provisioning of all k8s entities + service config ([ADR-0029](docs/adr/infrastructure/0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md))
- **Helm** — app chart [`charts/bigbug`](charts/bigbug/) ([ADR-0023](docs/adr/infrastructure/0023-bigbug-helm-chart.md))

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
│   ├── tests/              # pytest test suite (unit/ + e2e/)
│   └── pyproject.toml      # Python dependencies
├── frontend/               # React UI
│   ├── src/
│   │   ├── components/     # Shared UI components
│   │   ├── hooks/          # Custom React hooks
│   │   ├── pages/          # Page components per feature
│   │   ├── router/         # React Router configuration
│   │   ├── services/       # External service adapters (Keycloak)
│   │   ├── store/          # Redux store + RTK Query (api/<domain>.ts)
│   │   ├── tests/          # Vitest test suite (unit/ + integrations/)
│   │   └── types/          # TypeScript type definitions
│   ├── docker/             # Dockerfile
│   ├── scripts/            # Format, lint, test scripts
│   └── package.json        # Node dependencies
├── infrastructure/          # Infrastructure initialization
│   ├── init.sh              # Full environment initialization script
│   ├── gitlab/              # GitLab compose zone (gitlab + gitlab-runner, ADR-0033)
│   ├── terraform/           # OpenTofu roots: base / infra-apps (+GitLab) / apps (ADR-0029)
│   ├── kind/                # kind cluster scripts: bootstrap, certs, trust
│   └── gitlab-components/   # GitLab CI/CD component examples (not used by the app —
│                            #   presets live in backend/app/services/gitlab_projects/presets.py)
├── charts/bigbug/           # Helm chart of the app (backend + frontend, ADR-0023)
├── Makefile                 # Single entry point for all scripts (make help)
├── docs/                    # ADR registry, development guides (agents), runbooks (humans)
└── CHANGELOG.md             # Version history
```

## 🔧 Development

All scripts run through the root [`Makefile`](Makefile) (see `make help`).

### Backend

```bash
cd backend

# Install uv (if not already installed): curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies from uv.lock (creates .venv automatically)
uv sync

# Run migrations
uv run alembic upgrade head

# Start development server
uv run uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend

# Install dependencies
yarn install

# Start development server
yarn dev
```

### Tests, lint, typecheck

```bash
make test-unit-backend          # backend unit tests
make test-e2e-backend           # backend e2e (requires dev stack)
make test-unit-frontend         # frontend unit tests
make test-integrations-frontend # frontend integration tests
make lint                       # ruff + eslint
make typecheck                  # mypy + tsc --noEmit
make dead-code                  # vulture + knip
```

## 🐳 Docker Compose Services

Compose — только GitLab-зона ([ADR-0033](docs/adr/infrastructure/0033-gitlab-dev-stand-compose-omnibus.md)); всё остальное — в kind-кластере `bigbug-dev` ([ADR-0022](docs/adr/infrastructure/0022-dev-stand-on-kind.md)).

### GitLab zone (`infrastructure/gitlab/docker-compose.yml`)

| Service | Port | Description |
|---------|------|-------------|
| `gitlab` | 8443 (https) | GitLab CE for CI/CD (compose zone — ADR-0033) |
| `gitlab-runner` | — | Pipeline executor |

### kind-стенд `bigbug-dev` (ADR-0022/0029)

| Component | Где | Description |
|-----------|-----|-------------|
| haproxy-ingress | ns `haproxy-ingress` | TLS-терминирование (ADR-0030) |
| CNPG PostgreSQL 17 | ns `bigbug` / `keycloak` | БД приложения и Keycloak (ADR-0022 §5) |
| Redis | ns `bigbug` | Cache and session store |
| keycloakx | ns `keycloak` | SSO provider (ADR-0034) |
| Harbor | ns `harbor` | OCI registry (ADR-0035) |
| backend + frontend | ns `bigbug` | App (helm chart `charts/bigbug`, ADR-0023) |

## 🔐 Authentication

### Local Login

```bash
POST /api/auth/login     # username + password → JWT access token
```

Default admin user (created by infrastructure init): `bigbug` / `bigbug`

### SSO Login (Keycloak OIDC)

- **Realm:** `bigbug`
- **Clients:**
  - `bigbug-frontend` — public client, PKCE S256 enforced
  - `bigbug-backend` — confidential client, client secret auth
- **Roles:** synced from `realm_access.roles`

### RBAC

BigBug uses a **permission-based** model with `resource:action` permissions (e.g. `providers:write`, `teams:manage_members`). Permissions are grouped into roles (built-in `admin`/`operator`/`viewer` plus custom roles), and extended with **teams** and **scope-providers** for resource-level isolation.

See [`docs/development/permissions.md`](docs/development/permissions.md) for the full permission index.

## 🧪 Testing

```bash
make test-unit-backend          # backend unit
make test-e2e-backend           # backend e2e (requires dev stack)
make test-unit-frontend         # frontend unit
make test-integrations-frontend # frontend integrations
make test-all                   # unit + integrations + e2e
make coverage-all               # coverage for both stacks
```

Pass args to a specific test via `TEST_ARGS`, e.g. `make test-unit-backend TEST_ARGS="-k test_login"`.

## 🌊 Harbor

Local OCI registry for development and testing — Harbor chart in the `bigbug-dev` kind cluster behind the TLS ingress ([ADR-0035](docs/adr/infrastructure/0035-harbor-dev-stand-chart.md)). Install/config managed by OpenTofu (`infrastructure/terraform/infra-apps/modules/harbor_init|harbor_conf`, [ADR-0029](docs/adr/infrastructure/0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md)) — comes up with `make infra-init`, no separate deploy script.

Access: `https://harbor.local` (admin / Harbor12345). Verify push/pull: `./infrastructure/kind/test-push.sh`.

## 📝 API Documentation

After starting the backend:

- **Swagger UI:** https://api.local/api/docs
- **ReDoc:** https://api.local/api/redoc

### Key Endpoints

| Group | Prefix | Description |
|-------|--------|-------------|
| Auth | `/api/auth` | Login, token refresh, SSO config & exchange, OIDC config (admin) |
| Admin | `/api/admin` | User and role management (admin only) |
| Projects | `/api/projects` | GitHub project CRUD |
| Mirroring | `/api/mirroring` | Git mirror management (CRUD, sync, orphaned) |
| Gold Images | `/api/gold-images` | Base image CRUD |
| App Images | `/api/app-images` | App image CRUD |
| Helm Charts | `/api/helm-charts` | Chart source CRUD, indexing, versions, mirror |
| Docker Images | `/api/docker-images` | Registry source CRUD, indexing, tags, mirror |
| Pipelines | `/api/pipelines` | Pipeline runs (trigger, cancel, retry) |
| Components | `/api/components` | GitLab CI/CD components |
| GitLab Projects | `/api/gitlab-projects` | Project CRUD, files, tags, component presets, push-ci |
| Credentials | `/api/credentials` | Credential management |
| Providers | `/api/providers` | Unified resource providers (V3) |
| Teams | `/api/teams` | Team management |
| Schedules | `/api/schedules` | Sync and build schedule management |
| Webhooks | `/api/webhooks` | GitLab pipeline status callbacks |
| Audit | `/api/admin/audit-logs` | Audit log with filtering |
| Reports | `/api/reports` | Mirror reports (summary, history, failures, performance) |
| Health Check | `/api` | Health/readiness endpoints |

## 🗺️ Roadmap

- [ ] Cosign image signing integration
- [ ] Advanced scheduling — retry policies, concurrency limits, backoff
- [ ] Metrics & monitoring — Prometheus metrics + Grafana dashboards
- [ ] Notification channels — Slack, Discord, email alerts
- [ ] Helm OCI registry support
- [ ] Harbor-native replication policies

## 🤝 Contributing

See [`CHANGELOG.md`](CHANGELOG.md) for the full version history.

Pull requests are welcome. Please:

- Follow the existing code style and patterns documented in [`docs/development/`](docs/development/)
- Add tests for new features (pytest for backend, Vitest for frontend)
- Update documentation for any user-facing changes
- Keep PR scope focused — one feature or fix per PR

### Code Patterns

The project follows consistent patterns:

- **Backend:** SQLAlchemy 2.0 Column-style models → Pydantic v2 schemas → domain service layer (throws `DomainError` subclasses, never `HTTPException`) → API router (maps to HTTP status codes).
- **Frontend:** TypeScript interfaces in `types/` → RTK Query endpoints in `store/api/<domain>.ts` (aggregated by `store/api.ts`) → page components in `pages/FeatureName/` → routes in `router/index.tsx`.
- **RBAC:** `require_permission()` FastAPI dependency with `resource:action` permissions.
- **Secrets:** `encrypt_secret()` / `decrypt_secret()` via Fernet for registry passwords.

## 📄 License

MIT License — see the [LICENSE](LICENSE) file.

## 🙏 Acknowledgments

- [Harbor](https://goharbor.io/) — CNCF-graduated container registry
- [Keycloak](https://www.keycloak.org/) — open source identity and access management
- [GitLab](https://about.gitlab.com/) — complete DevOps platform
- [FastAPI](https://fastapi.tiangolo.com/) — modern Python web framework
- [Ant Design](https://ant.design/) — React component library
