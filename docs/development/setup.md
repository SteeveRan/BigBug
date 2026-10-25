# Development Setup - BigBug

## Prerequisites

### Required
- **Python** 3.14+ ([ADR-0001](../adr/backend/0001-choose-backend-stack.md))
- **Node.js** LTS ([ADR-0002](../adr/frontend/0002-frontend-stack-react-antd-rtk.md); dev-контейнеры собираются на node:20-alpine)
- **Docker** & **Docker Compose** (compose-слой: GitLab; остальное — kind, [ADR-0022](../adr/infrastructure/0022-dev-stand-on-kind.md))
- **Git**
- **gitleaks** (сканирование секретов; `make secrets-scan`) — ставьте **свежий release**: `brew install gitleaks` или бинарник с [github.com/gitleaks/gitleaks/releases](https://github.com/gitleaks/gitleaks/releases) в PATH. ⚠️ Пакет `gitleaks` из apt дистрибутива устарел (старые правила дают неверные результаты) — не используйте его.

### Optional
- **OpenTofu** (для Keycloak/GitLab инициализации)
- **nvm** (для управления версиями Node.js)

## Initial Setup

### Quick start (через Makefile)

Для быстрого подъёма окружения используйте корневой [`Makefile`](../../Makefile):

```bash
make infra-init    # certs → GitLab compose → kind → tofu base/infra-apps/apps (первый раз)
make dev-build     # dev-образы bigbug-{backend,frontend}:dev → kind
make dev-up        # деплой приложения (helm chart bigbug)

# Остальное — по мере необходимости:
make help          # полный список команд
make test-all      # все тесты
make lint          # линт обоих стеков
make secrets-scan  # сканирование полной git-истории на секреты
```

### 1. Clone Repository

```bash
git clone https://github.com/your-org/BigBug.git
cd BigBug
```

### 2. Environment Configuration

Корневого `.env` больше нет: секреты приложения доставляются в кластер k8s-секретами через tofu apps root ([ADR-0024](../adr/common/0024-k8s-secrets.md)), GitLab compose-зона читает свой `infrastructure/gitlab/.env` (создаётся `init.sh` из `infrastructure/gitlab/.env.example`). Локальная разработка без Docker — переменные в `backend/.env` (см. [backend guide](backend.md#переменные-окружения)).

### Secret scanning (gitleaks)

Репозиторий сканируется на утечки секретов: pre-commit hook (staged-only) + blocking GitHub Actions + `make secrets-scan` (полная история). Политика и процедура реагирования на утечку — [docs/development/security.md](security.md), решение — [ADR-0032](../adr/common/0032-adopt-gitleaks-secret-scanning.md).

```bash
pip install pre-commit
pre-commit install   # включает gitleaks hook на каждый коммит
```

Обход хука: `git commit --no-verify` — легитимный emergency-exit, но push всё равно сканируется в CI, а утечка разбирается по процедуре [security.md](security.md). Обходить осознанно: bypass оставляет секрет в локальной истории.

Разовый полный скан истории: `make secrets-scan` (требует gitleaks в PATH — см. Required выше).

### 3. Backend Setup

```bash
cd backend

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependencies from uv.lock (creates .venv automatically)
uv sync

# Run migrations
uv run alembic upgrade head

# Verify setup
uv run python -c "from app.database import engine; print('Database connection OK')"
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

### 5. Infrastructure Setup (kind-стенд + GitLab compose-зона)

```bash
# Полный цикл (владелец инфры, первый раз — свежая машина):
make infra-init    # certs → GitLab compose → kind bootstrap → tofu base/infra-apps/apps

# Далее приложение:
make dev-build     # dev-образы → kind
make dev-up        # helm chart bigbug (миграции — pre-upgrade hook job, ADR-0023)
```

Подробности dev-стенда — [ADR-0022](../adr/infrastructure/0022-dev-stand-on-kind.md) (kind), [ADR-0029](../adr/infrastructure/0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md) (IaC), [ADR-0030](../adr/infrastructure/0030-dev-stand-https-self-signed-certs.md) (https; trust проставляется автоматически в init.sh после генерации сертов, ручной вариант — `make infra-trust`); полный список make-команд — [ADR-0019](../adr/common/0019-makefile-tooling-single-entrypoint.md) и `make help`.

### 6. Verify Installation

```bash
# kind-стенд: все поды
kubectl get pods -A --context kind-bigbug-dev

# GitLab compose-зона
docker compose -f infrastructure/gitlab/docker-compose.yml --env-file infrastructure/gitlab/.env ps

# Health-чеки (https-хосты за ingress — ADR-0030; без доверия хоста — добавьте -k)
curl https://api.local/api/health
curl -k https://keycloak.local/realms/bigbug
curl -k https://harbor.local/api/v2.0/systeminfo
curl -k https://gitlab.local:8443/-/health
```

## Development Workflows

### Backend Development

```bash
cd backend

# Run dev server with auto-reload
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run in background
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &

# View logs
tail -f app.log
```

### Frontend Development

```bash
cd frontend

# Run dev server with HMR
yarn dev

# Open in browser: http://localhost:5173 (или https://app.local — ingress)
```

### Full Stack Development

```bash
# Terminal 1: Infrastructure logs (GitLab compose-зона)
docker compose -f infrastructure/gitlab/docker-compose.yml --env-file infrastructure/gitlab/.env logs -f

# Terminal 2: kind-стенд pod'ы
kubectl get pods -A --context kind-bigbug-dev -w
```

Приложение в dev-стенде — helm chart (`make dev-build && make dev-up`), не локальный uvicorn/vite; локальный запуск backend/frontend — для отладки против CNPG/Redis через ручной `kubectl port-forward`.

## Common Tasks

### Create Database Migration

```bash
cd backend

# Auto-generate migration from model changes
uv run alembic revision --autogenerate -m "description"

# Create empty migration
uv run alembic revision -m "description"

# Apply migration
uv run alembic upgrade head

# Rollback
uv run alembic downgrade -1
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

# Downgrade all migrations
uv run alembic downgrade base

# Re-apply all migrations
uv run alembic upgrade head

# Или пересоздать схему в CNPG dev-стенда (только владелец инфры)
make dev-clean CONFIRM=yes && make dev-up
```

### Clean Install

```bash
# Backend
cd backend
rm -rf .venv
uv sync

# Frontend
cd frontend
rm -rf node_modules .yarn/cache
yarn install
```

## Troubleshooting

### Backend Issues

**Import errors**:
```bash
# Resync environment from uv.lock
uv sync
```

**Database connection failed**:
```bash
# CNPG-под в kind-стенде
kubectl get pods -n bigbug --context kind-bigbug-dev -l cnpg.io/cluster=bigbug-dev

# DATABASE_URL (при отладке — ручной kubectl port-forward к CNPG)
echo $DATABASE_URL
```

**Alembic issues**:
```bash
# Check current revision
uv run alembic current

# Show history
uv run alembic history

# Force revision (осторожно — используйте осознанно)
uv run alembic stamp head
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
# Check backend pod / ingress
kubectl get pods -n bigbug --context kind-bigbug-dev
curl https://api.local/api/health
```

### kind / GitLab Issues

**Services not starting**:
```bash
# kind-стенд (ADR-0022)
kubectl get pods -A --context kind-bigbug-dev
kubectl logs -n bigbug --context kind-bigbug-dev deploy/bigbug-backend

# GitLab compose-зона (ADR-0033)
docker compose -f infrastructure/gitlab/docker-compose.yml --env-file infrastructure/gitlab/.env logs -f gitlab
```

**Port conflicts**:
```bash
# Find what's using the port
lsof -i :8443; lsof -i :80; lsof -i :443
```

## Next Steps

- [`backend.md`](backend.md) - detailed backend development
- [`frontend.md`](frontend.md) - detailed frontend development
- [ADR-0006](../adr/backend/0006-database-postgresql-alembic.md) - database layer (PostgreSQL, SQLAlchemy, Alembic)
- Testing decisions: [ADR-0014…0018](../adr/README.md)
