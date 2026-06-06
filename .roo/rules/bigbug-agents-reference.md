---
name: BigBug Project Reference
globs: "**/*"
alwaysApply: true
description: Quick reference to BigBug project documentation for AI agents
---

# BigBug Project - AI Agent Quick Reference

When working with the BigBug project, you should:

## Primary Documentation

1. **Start here**: [`/AGENTS.md`](../../AGENTS.md) - Comprehensive quick reference guide
   - Project overview and architecture
   - Technology stack with correct versions
   - Development workflows
   - Key conventions
   - Common tasks and troubleshooting

2. **Implementation plans**: [`/plans/`](../../plans/) - Modular documentation
   - Read only relevant sections as needed
   - Organized by: Overview, Development, Features, Architecture
   - See [`/plans/README.md`](../../plans/README.md) for navigation

3. **DO NOT read into context**: [`/docs/architecture/`](../../docs/architecture/)
   - Detailed architecture docs for human review only
   - Too large for AI agent context
   - Reference specific sections only when needed

## Key Technology Versions

- Python 3.14+, FastAPI 0.115+, Gunicorn 26+ + Uvicorn 0.30+
- Node.js 26, React 19, Material UI v9, Keycloak 26
- PostgreSQL 17, Redis 7, Docker Compose, Helm 4
- **bcrypt** for password hashing (NOT passlib - legacy)
- **Fernet** for credentials encryption
- **JWT** for API authentication

## Project Conventions

- Backend: snake_case (Python/DB), Service Layer pattern, one model = one file
- Frontend: PascalCase (components), Redux Toolkit + RTK Query, Material UI v9
- Database: Alembic migrations, async SQLAlchemy 2.0+, unified status flags (0-4)
- Testing: pytest (backend), Vitest (frontend)

## Before Making Changes

1. Read [`/AGENTS.md`](../../AGENTS.md) first
2. Check relevant section in [`/plans/`](../../plans/)
3. Examine actual code files to understand current implementation
4. Ask clarifying questions if requirements are unclear

## Common File References

- Backend entrypoint: [`backend/app/main.py`](../../backend/app/main.py)
- Frontend entrypoint: [`frontend/src/main.tsx`](../../frontend/src/main.tsx)
- Dependencies: [`backend/pyproject.toml`](../../backend/pyproject.toml), [`frontend/package.json`](../../frontend/package.json)
- RBAC: [`backend/app/core/rbac.py`](../../backend/app/core/rbac.py)
- Secrets: [`backend/app/core/secrets.py`](../../backend/app/core/secrets.py)
- OIDC: [`backend/app/services/oidc.py`](../../backend/app/services/oidc.py)
- Redux store: [`frontend/src/store/api.ts`](../../frontend/src/store/api.ts)
- Frontend routing: [`frontend/src/router/index.tsx`](../../frontend/src/router/index.tsx)
