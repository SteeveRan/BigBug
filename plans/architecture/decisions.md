# Architecture Decisions

Ключевые архитектурные решения в BigBug и обоснование выбора.

## Технологический стек

### Backend: FastAPI + Python 3.14

**Решение**: FastAPI как async-first веб-фреймворк.

**Обоснование**:
- Нативная async/await поддержка для I/O-intensive операций
- Автоматическая валидация через Pydantic
- OpenAPI/Swagger документация из коробки
- Высокая производительность (comparable с Node.js, Go)
- Зрелая экосистема Python библиотек

**Альтернативы**:
- Django — слишком тяжелый, sync-first
- Flask — нет встроенной async поддержки
- Node.js/Express — выбрали Python для консистентности с DevOps инструментами

### Database: PostgreSQL 17 + SQLAlchemy 2.0

**Решение**: PostgreSQL с SQLAlchemy 2.0 async ORM.

**Обоснование**:
- PostgreSQL — надёжная ACID-совместимая СУБД
- JSON/JSONB поддержка для динамических данных
- SQLAlchemy 2.0 — modern async API
- Alembic — мощные миграции с версионированием
- asyncpg — fastest async PostgreSQL driver

**Альтернативы**:
- MySQL — менее feature-rich
- MongoDB — не подходит для реляционных данных
- SQLModel — слишком молодой проект

### Frontend: React 19 + TypeScript

**Решение**: React 19 с TypeScript и Material UI v9.

**Обоснование**:
- React — индустриальный стандарт для SPA
- TypeScript — type safety, лучший DX
- Material UI — enterprise-ready компоненты
- Redux Toolkit — проверенный state management
- RTK Query — удобная интеграция с API

**Альтернативы**:
- Vue.js — меньше экосистема
- Angular — избыточная сложность
- Svelte — недостаточная зрелость

## Архитектурные паттерны

### Service Layer

**Решение**: Отделить бизнес-логику от API layer.

```
API Layer (FastAPI routers)
    ↓
Service Layer (business logic)
    ↓
Data Layer (SQLAlchemy models)
```

**Обоснование**:
- Переиспользование логики в разных endpoints
- Тестируемость без HTTP контекста
- Возможность вызова из scheduler, CLI, etc
- Доменные исключения вместо HTTP exceptions

**Пример**:
```python
# Service layer
class MirrorService:
    async def create_mirror(self, data: MirrorCreate) -> Mirror:
        if await self.mirror_exists(data.name):
            raise MirrorAlreadyExistsError(data.name)  # Domain exception
        ...

# API layer
@router.post("/mirrors")
async def create_mirror_endpoint(data: MirrorCreate):
    try:
        return await service.create_mirror(data)
    except MirrorAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))  # HTTP mapping
```

### Repository Pattern: НЕ используется

**Решение**: Работать напрямую с SQLAlchemy ORM, без repository abstraction.

**Обоснование**:
- SQLAlchemy уже абстракция над SQL
- Дополнительный repository слой — overengineering
- Async SQLAlchemy достаточно выразителен
- Упрощение архитектуры

### Один файл = одна модель

**Решение**: Каждая SQLAlchemy модель в отдельном файле.

```
app/models/
├── user.py
├── role.py
├── gitlab_mirror.py
└── ...
```

**Обоснование**:
- Понятная навигация
- Избежание circular imports
- Легче review в PR
- Стандарт в Python community

## Безопасность

### bcrypt для паролей (не passlib)

**Решение**: Использовать bcrypt напрямую.

**Обоснование**:
- passlib — legacy, последний релиз 2020
- bcrypt — активно поддерживается
- Простой API, нет лишних абстракций
- Работает с bcrypt.hashpw() и bcrypt.checkpw()

### Fernet для credentials

**Решение**: Симметричное шифрование Fernet для токенов в БД.

**Обоснование**:
- Fernet — industry standard (cryptography.io)
- Authenticated encryption (AES-128-CBC + HMAC)
- Простой API без ошибок конфигурации
- Timestamp included для rotation

**Альтернативы**:
- AES напрямую — легко сделать ошибку
- Asymmetric encryption — избыточно

### JWT для API, не sessions

**Решение**: Stateless JWT токены.

**Обоснование**:
- Stateless — не нужно хранить в БД/Redis
- Масштабируется горизонтально
- Подходит для SPA + API архитектуры
- 30 минут TTL — баланс безопасности/UX

**Недостатки**:
- Невозможно отозвать до истечения
- Решение: короткий TTL + refresh tokens (future)

## CI/CD

### GitLab CI + Templates

**Решение**: GitLab CI с переиспользуемыми templates.

**Обоснование**:
- GitLab — всё в одном (Git + CI/CD + Registry)
- YAML templates — DRY принцип
- GitLab Components (16+) — переиспользование
- Docker-in-Docker для сборки образов

**Альтернативы**:
- GitHub Actions — нужен отдельный registry
- Jenkins — избыточная сложность

### Docker Compose split

**Решение**: Разделение на `docker-compose.infra.yml` и `docker-compose.app.yml`.

**Обоснование**:
- Инфраструктура (PostgreSQL, Keycloak, GitLab) запускается реже
- Приложение (backend, frontend) пересобирается часто
- Быстрее итерации при разработке
- Изолирование concerns

## Infrastructure as Code

### OpenTofu вместо Terraform

**Решение**: OpenTofu для управления Keycloak и GitLab конфигурациями.

**Обоснование**:
- OpenTofu — open source fork Terraform
- Без лицензионных ограничений
- Совместимость с Terraform providers
- Community-driven development

**Использование**:
- Keycloak realm, clients, roles, users
- GitLab groups, tokens
- Декларативная конфигурация

## State Management (Frontend)

### Redux Toolkit + RTK Query

**Решение**: Redux Toolkit для state, RTK Query для API.

**Обоснование**:
- Redux Toolkit — modern Redux (меньше boilerplate)
- RTK Query — интеграция caching, автоматическая инвалидация
- Стандарт в enterprise React приложениях
- DevTools для debug

**Альтернативы**:
- React Query — хорошо, но Redux Toolkit включает больше
- Zustand — слишком простой для сложного state
- Recoil — экспериментальный статус

## Синхронизация данных

### Pull-based sync через APScheduler

**Решение**: Периодическая синхронизация через APScheduler задачи.

**Обоснование**:
- Контроль частоты синхронизации
- Не зависим от внешних webhooks
- Stale detection (>24 hours)
- Асинхронные задачи на AsyncIOScheduler

**Дополнение**: Webhooks для real-time updates (опционально).

## Статус флаги (унифицированные)

**Решение**: Единая система статусов для всех сущностей.

```python
0 = OK / Success
1 = Failed
2 = Warning / Stale
3 = In Progress
4 = Pending
```

**Обоснование**:
- Консистентность API и UI
- Лёгкая фильтрация в БД: `WHERE status_flag = 0`
- Frontend компонент `StatusChip` переиспользуется везде
- Понятная семантика

## Logging

### Structured logging (планируется)

**Решение**: JSON structured logs с correlation IDs.

**Обоснование**:
- Легче парсить в log aggregation системах
- Correlation ID для трейсинга запросов
- Фильтрация по structured fields

**Библиотека**: structlog или python-json-logger

## Testing Strategy

### pytest + httpx для backend

**Решение**: pytest с async httpx клиентом.

**Обоснование**:
- pytest — стандарт в Python
- pytest-asyncio для async тестов
- httpx AsyncClient — тестирование API без сервера
- Fixtures для setup/teardown

### Vitest + Testing Library для frontend

**Решение**: Vitest вместо Jest.

**Обоснование**:
- Vite-native, faster startup
- ES modules support из коробки
- Совместим с Jest API
- @testing-library/react — best practice для React тестов

## Миграция и deployment

### Alembic migrations

**Решение**: Alembic для версионированных миграций.

**Обоснование**:
- Интеграция с SQLAlchemy
- Автогенерация миграций (с проверкой)
- Rollback поддержка
- История изменений схемы

### Docker multi-stage builds

**Решение**: Multi-stage Dockerfile для production.

**Обоснование**:
- Меньший размер финального образа
- Разделение build и runtime dependencies
- Reproducible builds

## Будущие решения

### RBAC: Permission-based вместо role-based

**Решение**: Переход на гранулярные permissions (`resource:action`).

**Обоснование** (см. [`/docs/architecture/02-rbac-design.md`](../../docs/architecture/02-rbac-design.md)):
- Гибкость в управлении доступом
- Кастомные роли
- Audit trail для permissions
- Масштабируется на сложные сценарии

### Multi-instance integrations

**Решение**: Множественные инстансы GitLab, Harbor, etc.

**Обоснование** (см. [`/docs/architecture/04-integrations/`](../../docs/architecture/04-integrations/)):
- Enterprise use case: dev/staging/prod GitLab
- Гибкость выбора target registry
- Управление через Admin UI
- Шифрование credentials

## Нерешённые вопросы

### Message Queue для background tasks

**Статус**: В обсуждении

**Варианты**:
- Celery + Redis
- arq (async Celery alternative)
- FastAPI BackgroundTasks (текущий, ограниченный)

**Критерии**:
- Async support
- Retry механизм
- Task scheduling

### Audit Logging

**Статус**: Планируется

**Требования**:
- Кто, когда, что изменил
- Immutable log
- Retention policy

**Варианты**:
- Отдельная таблица `audit_log`
- Event sourcing pattern
- External audit service

## Полезные ссылки

- [`/docs/architecture/README.md`](../../docs/architecture/README.md) — подробная архитектура
- [`/plans/tech-stack.md`](../tech-stack.md) — полный список технологий
- [`AGENTS.md`](../../AGENTS.md) — quick reference для разработки
