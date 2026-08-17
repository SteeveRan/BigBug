# Development Setup - BigBug

## Prerequisites

### Required
- **Python** 3.14+
- **Node.js** 26 LTS
- **Docker** & **Docker Compose**
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

**Минимальные настройки** (`.env`):
```bash
# Database
DATABASE_URL=postgresql+asyncpg://bigbug:bigbug@localhost:5432/bigbug

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT Secret (generate with: openssl rand -hex 32)
SECRET_KEY=your-secret-key-here

# Encryption Key for secrets (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
ENCRYPTION_KEY=your-fernet-key-here

# Keycloak (optional, for SSO)
KEYCLOAK_URL=http://localhost:8180
KEYCLOAK_REALM=bigbug
KEYCLOAK_CLIENT_ID=bigbug-backend
KEYCLOAK_CLIENT_SECRET=bigbug-backend-secret
KEYCLOAK_FRONTEND_CLIENT_ID=bigbug-frontend

# GitLab
GITLAB_URL=http://localhost:8080
GITLAB_TOKEN=your-gitlab-token

# GitHub
GITHUB_TOKEN=your-github-token
```

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
docker compose -f infrastructure/docker-compose.yml up -d

# Wait for services to be healthy
docker compose -f infrastructure/docker-compose.yml ps

# Initialize infrastructure (optional, with OpenTofu)
./infrastructure/init.sh

# Start application services
docker compose up -d
```

**Option B: Single-shot via init.sh**

```bash
./infrastructure/init.sh
```

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

```bash
# Backend
cd backend
source .venv/bin/activate
pytest

# Frontend
cd frontend
yarn test
```

### Code Quality

```bash
# Backend
cd backend
ruff format .              # Format
ruff check --fix .         # Lint
pytest                     # Test

# Frontend
cd frontend
yarn format                # Prettier
yarn lint                  # ESLint
npx tsc --noEmit          # Type check
./scripts/test.sh          # Test (unit + integrations)
```

### Reset Database

```bash
cd backend
source .venv/bin/activate

# Downgrade all migrations
alembic downgrade base

# Re-apply all migrations
alembic upgrade head
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

# Force revision (危険)
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

# Remove volumes and restart (危険: удаляет данные)
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
- [`database.md`](database.md) - database management
- [`testing.md`](testing.md) - testing strategies
