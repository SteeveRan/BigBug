# BigBug Implementation Plans

Модульная документация для AI-агентов, работающих с проектом BigBug.

## Навигация

### 📋 Обзор проекта
- [`project-overview.md`](project-overview.md) - краткий обзор платформы BigBug
- [`tech-stack.md`](tech-stack.md) - технологии, версии, зависимости
- [`current-state.md`](current-state.md) - текущее состояние, что работает

### 🛠️ Development
- [`development/setup.md`](development/setup.md) - настройка окружения разработки
- [`development/backend.md`](development/backend.md) - работа с backend (FastAPI)
- [`development/frontend.md`](development/frontend.md) - работа с frontend (React)
- [ADR-0006](../../docs/adr/backend/0006-database-postgresql-alembic.md) - database layer: PostgreSQL 17, SQLAlchemy 2, Alembic, миграции, conventions
- [`development/testing.md`](development/testing.md) - тесты backend и frontend
- [`development/infrastructure.md`](development/infrastructure.md) - Docker Compose, services

### 🎯 Features
- [`features/builds.md`](features/builds.md) - Gold/App images
- [`features/mirroring.md`](features/mirroring.md) - Docker/Helm/Git mirroring
- [`features/pipelines.md`](features/pipelines.md) - CI/CD пайплайны

> Провайдеры интеграций (Git/Docker/Helm): см. [ADR-0007](../docs/adr/common/0007-providers-v3-registry.md) — единая сущность `resource_providers`.

### 🏗️ Architecture
- [`architecture/decisions.md`](architecture/decisions.md) - Architecture Decision Records (ADR)

### 📚 Legacy Documentation
- [`architecture.md`](architecture.md) - устаревшая архитектура (архив)
- [`handoff-summary.md`](handoff-summary.md) - handoff блоков 1-5 (архив)
- [`infrastructure-init-redesign.md`](infrastructure-init-redesign.md) - OpenTofu миграция

## Как использовать

**Для AI-агентов**:
1. Начните с [`/AGENTS.md`](../AGENTS.md) в корне репозитория
2. Читайте только релевантные секции по мере необходимости
3. НЕ читайте `/docs/` в контекст (для человеческого ревью)

**Для людей**:
1. Обзор: [`/AGENTS.md`](../AGENTS.md)
2. Детальная архитектура: [`/docs/architecture/`](../docs/architecture/)
3. Планы реализации: этот каталог `/plans/`

## Принципы документации

- **Краткость**: агенты должны быстро находить информацию
- **Модульность**: читать только нужные секции
- **Актуальность**: поддерживать в синхронизации с кодом
- **Практичность**: фокус на "как сделать"
