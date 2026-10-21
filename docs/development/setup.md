# Development Setup - BigBug

## Prerequisites

### Required
- **Python** 3.14+ ([ADR-0001](../adr/backend/0001-choose-backend-stack.md))
- **Node.js** LTS ([ADR-0002](../adr/frontend/0002-frontend-stack-react-antd-rtk.md); dev-контейнеры собираются на node:20-alpine)
- **Docker** & **Docker Compose** (compose-слой: GitLab; остальное — kind, [ADR-0022](../adr/infrastructure/0022-dev-stand-on-kind.md))
- **Git**

### Optional
- **OpenTofu** (для Keycloak/GitLab инициализации)
- **nvm** (для управления версиями Node.js)

## Initial Setup

### Quick start (через Makefile)

Для быстрого подъёма окружения используйте корневой [`Makefile`](../../Makefile):

```bash
make infra-init    # keycloak → harbor → gitlab + OpenTofu (первый раз)
make dev-up        # postgres, redis, backend, frontend

# Остальное — по мере необходимости:
make help          # полный список команд
make test-all      # все тесты
make lint          # линт обоих стеков
```

### 1. Clone Repository

```bash
git clone https://github.com/your-org/BigBug.git
cd BigBug
```

### 2. Environment Configuration

```bash
cp .env.example .env
# Edit .env with your values
```

**Минимальные настройки** (`.env`) — ключи выверены с [`/.env.example`](../../.env.example):

```bash
# PostgreSQL (compose собирает из них DATABASE_URL для backend)
POSTGRES_USER=bigbug
POSTGRES_PASSWORD=bigbug
POSTGRES_DB=bigbug

# Backend API
SECRET_KEY=your-secret-key-here              # generate with: openssl rand -hex 32
ENCRYPTION_KEY=                              # generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENVIRONMENT=development                      # не FERNET_KEY — см. ADR-0010
DB_WAIT_TIMEOUT=60

# Rate limiting (на dev-стенде выключен, чтобы e2e не упирались в лимит логина)
RATE_LIMIT_ENABLED=false
RATE_LIMIT_LOGIN=5/minute
RATE_LIMIT_OIDC_EXCHANGE=3/minute
RATE_LIMIT_GLOBAL=1000/minute

# Initial admin (создаётся автоматически при первом старте)
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@bigbug.local
ADMIN_PASSWORD=admin
```

> Переменных `DATABASE_URL`/`REDIS_URL` в `.env` нет — compose собирает их сам из `POSTGRES_*` (см. `docker-compose.yml`). Конфигурация Keycloak/GitLab/GitHub — env-переменные бэкенда с дефолтами в `backend/app/config.py` (`keycloak_*`, `gitlab_url` — по умолчанию `http://gitlab.local:8080`, `gitlab_token`, `github_token`); в `.env` их задавать не обязательно. Runtime-конфиг SSO — в БД (ADR-0003).

### 3. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv .venv

# Activate (Linux/Mac)
source .venv/bin/activate

# Activate (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -e .

# Install dev dependencies
pip install -e ".[dev]"

# Run migrations
alembic upgrade head

# Verify setup
python -c "from app.database import engine; print('Database connection OK')"
```

### 4. Frontend Setup

```bash
# Setup nvm (if not installed)
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

cd frontend

# Install dependencies
yarn install

# Verify setup
yarn --version
node --version
```

### 5. Infrastructure Setup (Docker Compose)

**Option A: Split compose files** (recommended)

```bash
# Start infrastructure services
make infra-up

# Initialize infrastructure (optional, with OpenTofu)
make infra-init

# Start application services
make dev-up
```

**Option B: Single-shot via init.sh**

```bash
make infra-init    # = ./infrastructure/init.sh
```

Подробности dev-стенда — [ADR-0022](../adr/infrastructure/0022-dev-stand-on-kind.md) (kind), [ADR-0013](../adr/infrastructure/0013-opentofu-iac-keycloak-gitlab-harbor.md) (IaC); полный список make-команд — [ADR-0019](../adr/common/0019-makefile-tooling-single-entrypoint.md) и `make help`.

### 6. Verify Installation

```bash
# Check all services
docker compose -f infrastructure/docker-compose.yml ps
docker compose ps

# Test backend
curl http://localhost:8000/docs

# Test frontend
curl http://localhost:5173

# Test Keycloak
curl http://localhost:8180/realms/bigbug

# Test GitLab
curl http://localhost:8080/-/health
```

## Development Workflows

### Backend Development

```bash
cd backend
source .venv/bin/activate

# Run dev server with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run in background
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &

# View logs
tail -f app.log
```

### Frontend Development

```bash
cd frontend

# Run dev server with HMR
yarn dev

# Open in browser: http://localhost:5173
```

### Full Stack Development

```bash
# Terminal 1: Backend
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload

# Terminal 2: Frontend
cd frontend && yarn dev

# Terminal 3: Infrastructure logs
docker compose -f infrastructure/docker-compose.yml logs -f
```

## Common Tasks

### Create Database Migration

```bash
cd backend
source .venv/bin/activate

# Auto-generate migration from model changes
alembic revision --autogenerate -m "description"

# Create empty migration
alembic revision -m "description"

# Apply migration
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Run Tests

Через корневой Makefile ([ADR-0019](../adr/common/0019-makefile-tooling-single-entrypoint.md)):

```bash
make test-unit-backend       # backend unit
make test-e2e-backend        # backend e2e (нужен dev-стек: make dev-up)
make test-unit-frontend      # frontend unit
make test-all                # все тесты
```

### Code Quality

Через корневой Makefile (см. [ADR-0019](../adr/common/0019-makefile-tooling-single-entrypoint.md)):

```bash
make format      # ruff format + prettier
make lint        # ruff check + eslint
make typecheck   # mypy + tsc --noEmit
```

### Reset Database

```bash
cd backend
source .venv/bin/activate

# Downgrade all migrations
alembic downgrade base

# Re-apply all migrations
alembic upgrade head

# Или без захода в контейнер
make dev-init
```

### Clean Install

```bash
# Backend
cd backend
rm -rf .venv
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Frontend
cd frontend
rm -rf node_modules .yarn/cache
yarn install
```

## Troubleshooting

### Backend Issues

**Import errors**:
```bash
pip install -e .
```

**Database connection failed**:
```bash
# Check PostgreSQL is running
docker compose ps postgres-backend

# Check DATABASE_URL in .env
echo $DATABASE_URL
```

**Alembic issues**:
```bash
# Check current revision
alembic current

# Show history
alembic history

# Force revision (осторожно — используйте осознанно)
alembic stamp head
```

### Frontend Issues

**Type errors**:
```bash
rm yarn.lock
yarn install
```

**Port already in use**:
```bash
# Kill process on port 5173
lsof -ti:5173 | xargs kill -9

# Or use different port
yarn dev --port 5174
```

**API connection issues**:
```bash
# Check backend is running
curl http://localhost:8000/docs

# Check proxy in vite.config.ts
```

### Docker Issues

**Services not starting**:
```bash
# Check logs
docker compose -f infrastructure/docker-compose.yml logs keycloak

# Restart specific service
docker compose -f infrastructure/docker-compose.yml restart keycloak

# Remove volumes and restart (осторожно: удаляет данные)
docker compose -f infrastructure/docker-compose.yml down -v
docker compose -f infrastructure/docker-compose.yml up -d
```

**Port conflicts**:
```bash
# Find what's using the port
lsof -i :8000

# Change port in docker-compose or .env
```

## Next Steps

- [`backend.md`](backend.md) - detailed backend development
- [`frontend.md`](frontend.md) - detailed frontend development
- [ADR-0006](../adr/backend/0006-database-postgresql-alembic.md) - database layer (PostgreSQL, SQLAlchemy, Alembic)
- Testing decisions: [ADR-0014…0018](../adr/README.md)
