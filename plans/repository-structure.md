# Repository Structure - BigBug

## Root Directory

```
BigBug/
├── .roo/                        # Kiro AI rules
├── backend/                     # FastAPI backend
├── frontend/                    # React frontend
├── examples/                    # Infrastructure setup examples (legacy)
├── docs/                        # Detailed documentation
├── infrastructure               # Infrastructure setup examples
├── plans/                       # Implementation plans (this directory)
├── .env.example                 # Example environment variables
├── .gitignore                   # Git ignore patterns
├── AGENTS.md                    # Quick reference guide for AI agents
├── CHANGELOG.md                 # Version changelog
├── docker-compose.infra.yml     # Infrastructure services
└── docker-compose.app.yml       # Application services
```

## Backend Structure

```
backend/
├── alembic/                     # Database migrations
│   ├── env.py                   # Alembic environment
│   ├── script.py.mako           # Migration template
│   └── versions/                # Migration files
├── app/                         # Application code
│   ├── main.py                  # FastAPI app entrypoint
│   ├── config.py                # Configuration (Pydantic Settings)
│   ├── database.py              # Database session management
│   ├── api/                     # API endpoints (routers)
│   ├── core/                    # Core utilities
│   ├── models/                  # SQLAlchemy models (one per file)
│   ├── schemas/                 # Pydantic schemas (request/response)
│   └── services/                # Business logic layer
├── tests/                       # pytest tests
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   └── e2e/                     # End to end tests
├── pyproject.toml               # Python dependencies & config
├── alembic.ini                  # Alembic configuration
├── Dockerfile                   # Backend Docker image
├── entrypoint.sh                # Docker entrypoint script
└── run_tests.sh                 # Test runner script
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
    ├── store/                   # Redux store
    ├── services/                # External services
    ├── hooks/                   # Custom React hooks
    ├── router/                  # React Router config
    ├── components/              # Reusable components
    ├── pages/                   # Page components (one per route)
    └── tests/                   # Vitest tests
        └── setup.ts             # Test setup
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
├── gitlab/                      # OpenTofu GitLab config
└── harbor/                      # Harbor deployment scripts
```

## Documentation

```
docs/
└── architecture/                # Detailed architecture docs (for humans)
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
