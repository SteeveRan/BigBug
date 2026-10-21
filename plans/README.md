# BigBug Implementation Plans

Модульная документация для AI-агентов, работающих с проектом BigBug.

Архитектурные решения зафиксированы в реестре [ADR](../docs/adr/README.md) — здесь только операционные гайды и индексы.

## Навигация

### 📋 Обзор проекта
- [`/AGENTS.md`](../AGENTS.md) — quick reference для агентов: структура репо, конвенции, make-команды, точки входа в код

> Обзор платформы и домены (Image builds, Git Mirroring, GitLab CI/CD, Providers, профиль пользователя) — в реестре [ADR](../docs/adr/README.md).

### 🛠️ Development
- [`development/setup.md`](development/setup.md) - настройка окружения разработки
- [`development/backend.md`](development/backend.md) - работа с backend (FastAPI)
- [`development/frontend.md`](development/frontend.md) - работа с frontend (React)
- Infrastructure (kind dev-стенд, IaC, init flow): [ADR-0022](../docs/adr/infrastructure/0022-dev-stand-on-kind.md), [ADR-0023](../docs/adr/infrastructure/0023-bigbug-helm-chart.md), [ADR-0013](../docs/adr/infrastructure/0013-opentofu-iac-keycloak-gitlab-harbor.md)
- Testing: ADR-0014…0018 — см. [`docs/adr/README.md`](../docs/adr/README.md)

### 🎯 Features
- Image builds (Gold/App images): [ADR-0020](../docs/adr/backend/0020-image-builds-gold-app.md)
- Git Mirroring (GitHub → GitLab): [ADR-0008](../docs/adr/backend/0008-git-mirroring-github-gitlab.md), синхронизация: [ADR-0009](../docs/adr/backend/0009-pull-sync-apscheduler-webhooks.md)
- GitLab CI/CD (пайплайны, компоненты, пресеты): [ADR-0011](../docs/adr/backend/0011-gitlab-ci-pipelines-components.md)
- Личный кабинет: [ADR-0021](../docs/adr/frontend/0021-user-profile-cabinet.md)

> Провайдеры интеграций (Git/Docker/Helm): [ADR-0007](../docs/adr/common/0007-providers-v3-registry.md) — единая сущность `resource_providers`.

### 🏗️ Architecture
- Реестр ADR: [`docs/adr/README.md`](../docs/adr/README.md)
- Permissions index: [`architecture/permissions.md`](architecture/permissions.md) — операционный индекс прав (не решение, ADR не нужен)

### 🗺️ Roadmap
- [`.agents/plans/adr-roadmap.md`](../.agents/plans/adr-roadmap.md) — план разработки ADR (принцип «один домен — один ADR», правило трёх корзин при удалении plans-файлов)

## Как использовать

**Для AI-агентов**:
1. Начните с [`/AGENTS.md`](../AGENTS.md) в корне репозитория
2. Читайте только релевантные секции по мере необходимости
3. НЕ читайте [`docs/runbooks/`](../docs/runbooks/) в контекст (для людей; точка входа агентов — AGENTS.md и реестр ADR)

**Для людей**:
1. Обзор: [`/AGENTS.md`](../AGENTS.md)
2. Архитектурные решения: [реестр ADR](../docs/adr/README.md); эксплуатационные процедуры: [`docs/runbooks/`](../docs/runbooks/)
3. Планы реализации: этот каталог `/plans/`

## Принципы документации

- **Краткость**: агенты должны быстро находить информацию
- **Модульность**: читать только нужные секции
- **Актуальность**: поддерживать в синхронизации с кодом; решения — в ADR, не здесь
- **Практичность**: фокус на "как сделать"
