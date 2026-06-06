# Repository Structure - BigBug

## Root Directory

```
BigBug/
├── .env.example                 # Example environment variables
├── .gitignore                   # Git ignore patterns
├── AGENTS.md                    # Quick reference guide for AI agents
├── CHANGELOG.md                 # Version changelog
├── docker-compose.infra.yml     # Infrastructure services
├── docker-compose.app.yml       # Application services
├── docker-compose.yaml          # Legacy (deprecated)
├── backend/                     # FastAPI backend
├── frontend/                    # React frontend
├── gitlab-ci/                   # GitLab CI templates
├── examples/                    # Infrastructure setup examples
├── docs/                        # Detailed documentation
├── plans/                       # Implementation plans (this directory)
└── .roo/                        # Kiro AI rules
```

## Backend Structure

```
backend/
├── pyproject.toml               # Python dependencies & config
├── alembic.ini                  # Alembic configuration
├── Dockerfile                   # Backend Docker image
├── entrypoint.sh                # Docker entrypoint script
├── run_tests.sh                 # Test runner script
├── alembic/                     # Database migrations
│   ├── env.py                   # Alembic environment
│   ├── script.py.mako           # Migration template
│   └── versions/                # Migration files
│       ├── 20260605_0449_..._initial_schema.py
│       ├── 20260605_0747_add_helm_tables.py
│       └── 20260605_1200_add_docker_tables.py
├── app/                         # Application code
│   ├── main.py                  # FastAPI app entrypoint
│   ├── config.py                # Configuration (Pydantic Settings)
│   ├── database.py              # Database session management
│   ├── api/                     # API endpoints (routers)
│   │   ├── auth.py              # Authentication endpoints
│   │   ├── admin.py             # Admin endpoints
│   │   ├── projects.py          # GitHub projects
│   │   ├── mirrors.py           # GitLab mirrors
│   │   ├── gold_images.py       # Gold images
│   │   ├── app_images.py        # App images
│   │   ├── helm_charts.py       # Helm charts
│   │   ├── docker_images.py     # Docker images
│   │   ├── schedules.py         # Schedules management
│   │   └── webhooks.py          # Webhook handlers
│   ├── core/                    # Core utilities
│   │   ├── security.py          # JWT, password hashing
│   │   ├── rbac.py              # Role-based access control
│   │   ├── secrets.py           # Fernet encryption
│   │   └── exceptions.py        # Domain exceptions
│   ├── models/                  # SQLAlchemy models (one per file)
│   │   ├── user.py
│   │   ├── role.py
│   │   ├── github_org.py
│   │   ├── github_project.py
│   │   ├── github_release.py
│   │   ├── gitlab_mirror.py
│   │   ├── sync_schedule.py
│   │   ├── sync_log.py
│   │   ├── gold_image.py
│   │   ├── app_image.py
│   │   ├── image_version.py
│   │   ├── build_schedule.py
│   │   ├── build_log.py
│   │   ├── helm_chart_source.py
│   │   ├── helm_chart_version.py
│   │   ├── helm_sync_log.py
│   │   ├── docker_image_source.py
│   │   ├── docker_image_tag.py
│   │   └── docker_sync_log.py
│   ├── schemas/                 # Pydantic schemas (request/response)
│   │   ├── auth.py
│   │   ├── image.py
│   │   ├── mirror.py
│   │   ├── project.py
│   │   ├── helm.py
│   │   └── docker.py
│   └── services/                # Business logic layer
│       ├── build.py             # Build service
│       ├── docker.py            # Docker registry service
│       ├── github.py            # GitHub API service
│       ├── gitlab.py            # GitLab API service
│       ├── helm.py              # Helm repository service
│       ├── oidc.py              # OIDC/Keycloak service
│       └── scheduler.py         # APScheduler service
└── tests/                       # pytest tests
    ├── conftest.py              # Test fixtures
    ├── test_auth.py
    ├── test_docker_api.py
    ├── test_docker_service.py
    ├── test_helm_api.py
    ├── test_helm_service.py
    ├── test_images.py
    ├── test_oidc.py
    ├── test_projects.py
    └── test_secrets.py
```

## Frontend Structure

```
frontend/
├── package.json                 # Node dependencies & scripts
├── tsconfig.json                # TypeScript config
├── tsconfig.app.json            # App-specific TS config
├── tsconfig.node.json           # Node-specific TS config
├── vite.config.ts               # Vite configuration
├── vitest.config.ts             # Vitest test config
├── eslint.config.js             # ESLint configuration
├── Dockerfile                   # Frontend Docker image
├── run_tests.sh                 # Test runner script
├── index.html                   # HTML template
├── yarn.lock                    # Yarn lockfile
├── .yarnrc.yml                  # Yarn configuration
└── src/                         # Application source
    ├── main.tsx                 # Entry point
    ├── App.tsx                  # Root component
    ├── theme.ts                 # MUI theme configuration
    ├── types/                   # TypeScript type definitions
    │   └── index.ts             # Centralized types
    ├── store/                   # Redux store
    │   ├── index.ts             # Store configuration
    │   ├── authSlice.ts         # Auth state slice
    │   └── api.ts               # RTK Query API endpoints
    ├── services/                # External services
    │   └── keycloak.ts          # Keycloak SSO service
    ├── hooks/                   # Custom React hooks
    │   └── useKeycloakAuth.ts   # Keycloak auth hook
    ├── router/                  # React Router config
    │   ├── index.tsx            # Routes definition
    │   └── ProtectedRoute.tsx   # Auth guard component
    ├── components/              # Reusable components
    │   ├── StatusChip.tsx       # Status indicator
    │   └── Layout/              # App layout
    │       └── index.tsx
    ├── pages/                   # Page components (one per route)
    │   ├── Login/
    │   │   └── index.tsx
    │   ├── SsoCallback/
    │   │   └── index.tsx
    │   ├── Dashboard/
    │   │   └── index.tsx
    │   ├── Projects/
    │   │   ├── index.tsx
    │   │   └── ProjectDetail.tsx
    │   ├── Mirrors/
    │   │   ├── index.tsx
    │   │   └── MirrorDetail.tsx
    │   ├── GoldImages/
    │   │   └── index.tsx
    │   ├── AppImages/
    │   │   └── index.tsx
    │   ├── HelmCharts/
    │   │   ├── index.tsx
    │   │   └── HelmChartDetail.tsx
    │   ├── DockerImages/
    │   │   ├── index.tsx
    │   │   └── DockerImageDetail.tsx
    │   └── Admin/
    │       └── index.tsx
    └── tests/                   # Vitest tests
        ├── setup.ts             # Test setup
        ├── authSlice.test.ts
        ├── DockerImages.test.tsx
        ├── DockerImageDetail.test.tsx
        ├── HelmCharts.test.tsx
        ├── HelmChartDetail.test.tsx
        ├── keycloak.service.test.ts
        ├── SsoCallback.test.tsx
        ├── StatusChip.test.tsx
        └── useKeycloakAuth.test.tsx
```

## GitLab CI Templates

```
gitlab-ci/
├── mirror-template.yml          # GitHub → GitLab mirroring
├── gold-image-template.yml      # Gold image builds
├── app-image-template.yml       # App image builds
├── helm-sync-template.yml       # Helm chart synchronization
└── docker-sync-template.yml     # Docker image synchronization
```

## Infrastructure Examples

```
examples/
├── README.md                    # General setup instructions
├── init.sh                      # Master initialization script
├── update-env.sh                # Update .env from outputs
├── keycloak/                    # OpenTofu Keycloak config
│   ├── main.tf
│   ├── realm.tf
│   ├── clients.tf
│   ├── roles.tf
│   ├── users.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── terraform.tfvars.example
│   ├── .gitignore
│   └── README.md
├── gitlab/                      # OpenTofu GitLab config
│   ├── main.tf
│   ├── groups.tf
│   ├── tokens.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── terraform.tfvars.example
│   ├── .gitignore
│   └── README.md
└── harbor/                      # Harbor deployment scripts
    ├── deploy.sh
    ├── teardown.sh
    ├── test-push.sh
    ├── init-harbor.sh
    ├── kind-config.yaml
    ├── harbor-values.yaml
    ├── keycloak-integration.md
    └── README.md
```

## Documentation

```
docs/
└── architecture/                # Detailed architecture docs (for humans)
    ├── README.md
    ├── 01-executive-summary.md
    ├── 02-rbac-design.md
    ├── 03-authentication.md
    ├── 04-integrations/
    │   ├── gitlab.md
    │   ├── harbor.md
    │   ├── github.md
    │   ├── docker-registry.md
    │   └── helm-repository.md
    ├── 05-database-schema.md
    ├── 06-api-design.md
    ├── 07-service-layer.md
    ├── 08-pipelines.md
    ├── 09-ui-structure.md
    ├── 10-security.md
    └── 11-migration-strategy.md
```

## Plans (For AI Agents)

```
plans/                           # Implementation plans (modular)
├── README.md                    # Index of all plans
├── project-overview.md          # What BigBug does
├── tech-stack.md                # Technologies and versions
├── current-state.md             # Current status
├── repository-structure.md      # This file
├── development/                 # Development guides
│   ├── setup.md
│   ├── backend.md
│   ├── frontend.md
│   ├── database.md
│   ├── testing.md
│   └── infrastructure.md
├── features/                    # Feature-specific guides
│   ├── auth-rbac.md
│   ├── builds.md
│   ├── mirroring.md
│   ├── integrations.md
│   ├── pipelines.md
│   └── security.md
└── architecture/                # Architecture decisions
    └── decisions.md
```

## Key Conventions

### Backend
- **One model per file** in `app/models/`
- **Services separate from API** - business logic in `services/`, HTTP in `api/`
- **Domain exceptions** in services (not `HTTPException`)
- **Pydantic schemas** for request/response validation
- **Alembic migrations** with descriptive names

### Frontend
- **Page per route** in `src/pages/ComponentName/index.tsx`
- **Centralized types** in `src/types/index.ts`
- **RTK Query** for API calls in `src/store/api.ts`
- **Component folders** for complex components
- **One test file per component** alongside source

### Naming
- **snake_case**: Python files, variables, functions, database tables/columns
- **PascalCase**: Python classes, React components, TypeScript interfaces
- **kebab-case**: URLs, Docker image names, file directories
- **SCREAMING_SNAKE_CASE**: Constants, environment variables
