# Infrastructure Guide

Руководство по инфраструктуре и deployment BigBug.

## Компоненты инфраструктуры

### Development окружение

- **PostgreSQL 17** - основная БД (backend)
- **PostgreSQL 17** - БД для Keycloak (отдельный инстанс)
- **Redis 7** - кеш и очереди задач
- **Keycloak 26** - SSO / OIDC provider
- **GitLab CE** - Git хостинг, CI/CD, зеркала
- **GitLab Runner** - выполнение пайплайнов
- **Harbor** (опционально) - Docker Registry

## Docker Compose структура

### Разделение на файлы

**Infrastructure services** ([`docker-compose.infra.yml`](../../docker-compose.infra.yml)):
- PostgreSQL (backend + keycloak)
- Redis
- Keycloak
- GitLab CE
- GitLab Runner

**Application services** ([`docker-compose.app.yml`](../../docker-compose.app.yml)):
- BigBug Backend (FastAPI)
- BigBug Frontend (React + Vite)

### Запуск инфраструктуры

```bash
# 1. Запустить инфраструктурные сервисы
docker compose -f docker-compose.infra.yml up -d

# 2. Дождаться готовности
# Keycloak: http://localhost:8180
# GitLab: http://localhost:8080
# PostgreSQL: localhost:5432 (backend), localhost:5433 (keycloak)
# Redis: localhost:6379

# 3. Инициализировать Keycloak и GitLab (первый раз)
cd infrastructure
./init.sh

# 4. Запустить приложение
docker compose -f docker-compose.app.yml up -d

# Приложение: http://localhost:3000
# API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Управление сервисами

```bash
# Остановить
docker compose -f docker-compose.infra.yml stop
docker compose -f docker-compose.app.yml stop

# Перезапустить
docker compose -f docker-compose.infra.yml restart keycloak
docker compose -f docker-compose.app.yml restart backend

# Логи
docker compose -f docker-compose.infra.yml logs -f postgres-backend
docker compose -f docker-compose.app.yml logs -f backend

# Статус
docker compose -f docker-compose.infra.yml ps
docker compose -f docker-compose.app.yml ps

# Полное удаление (с volumes)
docker compose -f docker-compose.infra.yml down -v
docker compose -f docker-compose.app.yml down -v
```

## Инициализация инфраструктуры

### OpenTofu конфигурации

#### Keycloak ([`infrastructure/keycloak/`](../../infrastructure/keycloak/))

Создаёт realm, клиентов, роли, пользователей через OpenTofu.

```bash
cd infrastructure/keycloak

# 1. Скопировать и настроить переменные
cp terraform.tfvars.example terraform.tfvars
# Отредактировать terraform.tfvars

# 2. Применить конфигурацию
tofu init
tofu plan
tofu apply

# 3. Сохранить outputs
tofu output -json > outputs.json
```

Структура:
- `main.tf` - provider конфигурация
- `realm.tf` - создание realm bigbug
- `clients.tf` - bigbug-backend, bigbug-frontend клиенты
- `roles.tf` - admin, operator, viewer роли
- `users.tf` - тестовые пользователи (admin/bigbug, operator/bigbug)
- `outputs.tf` - client secrets, user IDs

#### GitLab ([`infrastructure/gitlab/`](../../infrastructure/gitlab/))

Создаёт группу, токены, настройки через OpenTofu.

```bash
cd infrastructure/gitlab

# 1. Получить root token из GitLab UI или Docker logs
docker compose -f ../../docker-compose.infra.yml logs gitlab | grep "Password:"

# 2. Настроить переменные
cp terraform.tfvars.example terraform.tfvars
# Установить GITLAB_TOKEN в terraform.tfvars

# 3. Применить конфигурацию
tofu init
tofu plan
tofu apply

# 4. Сохранить outputs
tofu output -json > outputs.json
```

Структура:
- `main.tf` - GitLab provider
- `groups.tf` - создание группы bigbug
- `tokens.tf` - API токен для backend
- `outputs.tf` - group_id, api_token

### Скрипт автоматической инициализации

[`infrastructure/init.sh`](../../infrastructure/init.sh) - полная автоматизация:

```bash
cd infrastructure
./init.sh
```

Что делает:
1. Проверяет зависимости (docker, tofu, jq)
2. Проверяет `.env`
3. Запускает `docker-compose.infra.yml`
4. Ждёт готовности Keycloak и GitLab
5. Инициализирует Keycloak через OpenTofu
6. Инициализирует GitLab через OpenTofu
7. Обновляет `.env` с outputs
8. Запускает `docker-compose.app.yml`

### Скрипт обновления .env

[`infrastructure/update-env.sh`](../../infrastructure/update-env.sh) - обновление переменных окружения из OpenTofu outputs:

```bash
cd infrastructure
./update-env.sh
```

## Networking

### Docker networks

- `bigbug-infra-network` - для инфраструктурных сервисов
- `bigbug-app-network` - для приложения
- Приложение подключается к infra network как external

### Порты

| Сервис | Внутренний | Внешний | Описание |
|--------|-----------|---------|----------|
| Backend | 8000 | 8000 | FastAPI API |
| Frontend | 80 | 3000 | React UI |
| PostgreSQL (backend) | 5432 | 5432 | База данных backend |
| PostgreSQL (keycloak) | 5432 | 5433 | База данных Keycloak |
| Redis | 6379 | 6379 | Cache & queues |
| Keycloak | 8080 | 8180 | SSO provider |
| GitLab | 80/443/22 | 8080/8443/2222 | Git, UI, SSH |

## Secrets Management

### Переменные окружения

Основной `.env` файл в корне проекта:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://bigbug:bigbug@localhost:5432/bigbug

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Security
SECRET_KEY=<generate-with-openssl-rand-hex-32>
FERNET_KEY=<generate-with-python-cryptography>

# OIDC (заполняется после init.sh)
OIDC_ENABLED=true
OIDC_ISSUER=http://localhost:8180/realms/bigbug
OIDC_CLIENT_ID=bigbug-backend
OIDC_CLIENT_SECRET=<from-keycloak-opentofu-output>

# GitLab (заполняется после init.sh)
GITLAB_URL=http://localhost:8080
GITLAB_TOKEN=<from-gitlab-opentofu-output>

# GitHub
GITHUB_TOKEN=<your-github-pat>
```

### Генерация секретов

```bash
# SECRET_KEY (256 бит)
openssl rand -hex 32

# FERNET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Безопасность секретов

- **.env в .gitignore** - не коммитить
- **Fernet encryption** для credentials в БД
- **Не логировать** секреты
- **Rotate tokens** периодически
- **Использовать secrets manager** на production

## OpenTofu State Management

### Local state (dev)

```bash
# State файлы
infrastructure/keycloak/terraform.tfstate
infrastructure/gitlab/terraform.tfstate

# Бэкап
infrastructure/keycloak/terraform.tfstate.backup
infrastructure/gitlab/terraform.tfstate.backup
```

### Remote state (production)

Для production рекомендуется использовать remote backend:

```hcl
# backend.tf
terraform {
  backend "s3" {
    bucket = "bigbug-terraform-state"
    key    = "keycloak/terraform.tfstate"
    region = "us-east-1"
  }
}
```

Или Terraform Cloud / GitLab Terraform Backend.

## Deployment

### Development

```bash
# Локальная разработка (без Docker)
# Backend
cd backend && uvicorn app.main:app --reload

# Frontend
cd frontend && yarn dev
```

### Staging / Production

#### Docker multi-stage builds

Backend ([`backend/Dockerfile`](../../backend/Dockerfile)):
```dockerfile
FROM python:3.14-slim AS builder
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

FROM python:3.14-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Gunicorn + Uvicorn workers
CMD ["gunicorn", "app.main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000"]
```

Frontend ([`frontend/Dockerfile`](../../frontend/Dockerfile)):
```dockerfile
FROM node:26-alpine AS builder
WORKDIR /app
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile
COPY . .
RUN yarn build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

#### Production deployment

```bash
# 1. Сборка образов
docker build -t bigbug-backend:latest ./backend
docker build -t bigbug-frontend:latest ./frontend

# 2. Push в registry
docker tag bigbug-backend:latest registry.example.com/bigbug-backend:latest
docker push registry.example.com/bigbug-backend:latest

# 3. Deploy (Kubernetes, Docker Swarm, etc.)
kubectl apply -f k8s/
```

## Monitoring и Logging

### Логирование

Backend логи через uvicorn/gunicorn:

```bash
# Docker logs
docker compose -f docker-compose.app.yml logs -f backend

# Файлы логов (если настроено)
tail -f /var/log/bigbug/backend.log
```

Frontend логи через nginx:

```bash
docker compose -f docker-compose.app.yml logs -f frontend
```

### Health checks

```bash
# Backend health
curl http://localhost:8000/health

# Frontend
curl http://localhost:3000

# Keycloak
curl http://localhost:8180/realms/bigbug

# GitLab
curl http://localhost:8080/-/health
```

### Мониторинг (планируется)

- **Prometheus** - сбор метрик
- **Grafana** - визуализация
- **Loki** - логи
- **Alertmanager** - алерты

## Backup и Recovery

### База данных

```bash
# Backup PostgreSQL
docker exec bigbug-postgres-backend pg_dump -U bigbug bigbug > backup_$(date +%Y%m%d).sql

# Restore
docker exec -i bigbug-postgres-backend psql -U bigbug bigbug < backup_20260606.sql
```

### OpenTofu state

```bash
# Backup state files
cp infrastructure/keycloak/terraform.tfstate backups/keycloak_$(date +%Y%m%d).tfstate
cp infrastructure/gitlab/terraform.tfstate backups/gitlab_$(date +%Y%m%d).tfstate
```

## Troubleshooting

### Сервисы не стартуют

```bash
# Проверить логи
docker compose -f docker-compose.infra.yml logs keycloak

# Проверить сеть
docker network ls
docker network inspect bigbug-infra-network

# Проверить volumes
docker volume ls
docker volume inspect bigbug_postgres-backend-data
```

### Конфликты портов

```bash
# Проверить занятые порты
lsof -i :8000
lsof -i :5432

# Изменить порты в docker-compose или .env
```

### GitLab не инициализируется

```bash
# Ждать пока GitLab полностью запустится (может занять 2-5 минут)
docker compose -f docker-compose.infra.yml logs -f gitlab

# Получить root password
docker exec -it bigbug-gitlab grep 'Password:' /etc/gitlab/initial_root_password
```

### OpenTofu ошибки

```bash
# Пересоздать state
rm -rf infrastructure/keycloak/.terraform*
cd infrastructure/keycloak && tofu init

# Import существующих ресурсов
tofu import keycloak_realm.bigbug bigbug
```

## Best Practices

- **Разделять infra и app** сервисы
- **Использовать named volumes** для данных
- **Не запускать всё в одном compose** файле
- **Версионировать образы** (не latest в production)
- **Логировать в stdout** для Docker
- **Health checks** для всех сервисов
- **Secrets через переменные окружения** или secrets manager
- **Backup регулярно** (БД, state файлы)

## Полезные ссылки

- [`docker-compose.infra.yml`](../../docker-compose.infra.yml)
- [`docker-compose.app.yml`](../../docker-compose.app.yml)
- [`infrastructure/README.md`](../../infrastructure/README.md)
- [`infrastructure/init.sh`](../../infrastructure/init.sh)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [OpenTofu Documentation](https://opentofu.org/docs/)
- [Keycloak Documentation](https://www.keycloak.org/documentation)
- [GitLab Documentation](https://docs.gitlab.com/)
