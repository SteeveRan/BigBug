# BigBug - Technology Stack

## Backend

### Core Framework
| Технология | Версия | Назначение |
|-----------|--------|-----------|
| Python | 3.14 | Runtime |
| FastAPI | latest | Async REST API framework |
| SQLAlchemy | 2.x | ORM с async поддержкой |
| Alembic | latest | Database migrations |
| Pydantic | v2 | Data validation, schemas |
| Uvicorn | latest | ASGI server |

### Database & Cache
| Технология | Версия | Назначение |
|-----------|--------|-----------|
| PostgreSQL | 17 | Primary database |
| Redis | 7 | Caching, task queues |
| asyncpg | latest | Async PostgreSQL driver |
| psycopg2-binary | latest | Sync PostgreSQL driver (Alembic) |

### External Integrations
| Технология | Версия | Назначение |
|-----------|--------|-----------|
| python-gitlab | latest | GitLab API client |
| PyGithub | latest | GitHub API client |
| httpx | latest | Async HTTP (Harbor, Docker, Helm) |
| authlib | latest | OIDC/OAuth2 (Keycloak) |
| PyYAML | latest | Helm index.yaml parsing |

### Security
| Технология | Версия | Назначение |
|-----------|--------|-----------|
| cryptography | latest | Fernet encryption for secrets |
| python-jose[cryptography] | latest | JWT tokens |
| passlib[bcrypt] | latest | Password hashing |

### Scheduling
| Технология | Версия | Назначение |
|-----------|--------|-----------|
| APScheduler | latest | AsyncIOScheduler для cron jobs |

### Testing
| Технология | Версия | Назначение |
|-----------|--------|-----------|
| pytest | latest | Test framework |
| pytest-asyncio | latest | Async test support |
| httpx | latest | Test HTTP client |

### Code Quality
| Технология | Версия | Назначение |
|-----------|--------|-----------|
| ruff | latest | Formatter (ruff format) + linter + auto-fix |

## Frontend

### Core
| Технология | Версия | Назначение |
|-----------|--------|-----------|
| Node.js | 26 LTS | Runtime |
| Yarn | 4.3.1 | Package manager |
| React | 19 | UI framework |
| TypeScript | latest | Type safety |
| Vite | latest | Build tool, dev server |

### State Management
| Технология | Версия | Назначение |
|-----------|--------|-----------|
| Redux Toolkit | latest | State management |
| RTK Query | latest | API caching, data fetching |

### UI Components
| Технология | Версия | Назначение |
|-----------|--------|-----------|
| Material UI | v9 | Component library |
| React Router | v7 | Client-side routing |

### Auth
| Технология | Версия | Назначение |
|-----------|--------|-----------|
| keycloak-js | 26+ | Keycloak SSO adapter |

### Testing
| Технология | Версия | Назначение |
|-----------|--------|-----------|
| Vitest | latest | Unit test framework |
| @testing-library/react | latest | Component testing |
| Cypress | latest | E2E tests (planned) |

### Code Quality
| Технология | Версия | Назначение |
|-----------|--------|-----------|
| ESLint | latest | Linter |
| @typescript-eslint | latest | TypeScript ESLint rules |
| Prettier | latest | Code formatter |

## Infrastructure

### Development
| Технология | Версия | Назначение |
|-----------|--------|-----------|
| Docker | latest | Containerization |
| Docker Compose | latest | Local orchestration |
| GitLab CE | latest | CI/CD platform + mirror target |
| GitLab Runner | latest | Pipeline executor |
| Keycloak | 26 | SSO / OIDC provider |
| Harbor | latest | Container registry (optional) |
| Helm | 4 | Helm CLI (для CI/CD templates) |

### Infrastructure as Code
| Технология | Версия | Назначение |
|-----------|--------|-----------|
| OpenTofu | latest | Keycloak + GitLab provisioning |

## Ports (Development)

| Сервис | Порт | URL |
|--------|------|-----|
| Frontend | 5173 | http://localhost:5173 |
| Backend | 8000 | http://localhost:8000 |
| Backend API docs | 8000 | http://localhost:8000/docs |
| Keycloak | 8180 | http://localhost:8180 |
| GitLab | 8080 | http://localhost:8080 |
| GitLab SSH | 2222 | ssh://localhost:2222 |
| PostgreSQL (backend) | 5432 | localhost:5432 |
| PostgreSQL (keycloak) | 5433 | localhost:5433 |
| Redis | 6379 | localhost:6379 |

## Key Dependencies (pyproject.toml)

```toml
[project]
dependencies = [
    "fastapi",
    "uvicorn[standard]",
    "sqlalchemy[asyncio]",
    "alembic",
    "asyncpg",
    "psycopg2-binary",
    "pydantic-settings",
    "redis",
    "httpx",
    "python-gitlab",
    "PyGithub",
    "authlib",
    "python-jose[cryptography]",
    "passlib[bcrypt]",
    "cryptography",
    "PyYAML",
    "apscheduler",
]
```

## Key Dependencies (package.json)

```json
{
  "dependencies": {
    "react": "^19.0.0",
    "@reduxjs/toolkit": "^2.12+",
    "@mui/material": "^9.0.0",
    "react-router-dom": "^7.0.0",
    "keycloak-js": "^26.0.0"
  },
  "devDependencies": {
    "vite": "latest",
    "vitest": "latest",
    "@testing-library/react": "latest",
    "eslint": "latest",
    "typescript": "latest"
  }
}
```

## Версионирование

- **Backend**: semantic versioning через git tags
- **Docker images**: `{name}:{version}-{arch}` (e.g., `ubuntu:22.04-amd64`)
- **Helm charts**: semver (e.g., `1.2.3`)
- **API**: пока без версионирования (планируется `/api/v1/`)
