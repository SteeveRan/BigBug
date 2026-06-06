# Database Guide

Руководство по работе с базой данных в BigBug (PostgreSQL 17 + SQLAlchemy 2.0 + Alembic).

## Технологии

- **PostgreSQL 17** - основная база данных
- **SQLAlchemy 2.0+** - ORM с async поддержкой (asyncpg driver)
- **Alembic** - миграции базы данных
- **asyncpg 0.29+** - async PostgreSQL driver
- **psycopg2-binary** - sync driver (для Alembic)

## Текущая схема

### Таблицы (реализованные)

| Таблица | Описание |
|---------|----------|
| `users` | Пользователи системы |
| `roles` | Роли (admin, operator, viewer) |
| `github_orgs` | GitHub организации |
| `github_projects` | GitHub репозитории |
| `github_releases` | Релизы GitHub проектов |
| `gitlab_mirrors` | GitLab зеркала репозиториев |
| `gold_images` | Gold Images (базовые OS/runtime образы) |
| `image_versions` | Версии Gold Images |
| `app_images` | App Images (образы приложений) |
| `build_logs` | Логи сборок образов |
| `build_schedules` | Расписания сборок |
| `sync_schedules` | Расписания синхронизации |
| `sync_logs` | Логи синхронизации |
| `helm_chart_sources` | Источники Helm чартов |
| `helm_chart_versions` | Версии Helm чартов |
| `helm_sync_logs` | Логи синхронизации Helm |
| `docker_image_sources` | Источники Docker образов |
| `docker_image_tags` | Теги Docker образов |
| `docker_sync_logs` | Логи синхронизации Docker |

### Планируемые таблицы (рефакторинг)

| Таблица | Описание |
|---------|----------|
| `permissions` | Гранулярные права доступа |
| `role_permissions` | Связь ролей и прав |
| `oidc_config` | Конфигурация OIDC/Keycloak |
| `gitlab_instances` | Множественные GitLab инстансы |
| `harbor_instances` | Множественные Harbor инстансы |
| `pipeline_runs` | История запусков пайплайнов |

## Соглашения по именованию

### Таблицы
- Множественное число, snake_case: `users`, `gitlab_mirrors`, `helm_chart_sources`

### Колонки
- snake_case: `user_id`, `created_at`, `is_active`, `status_flag`
- Булевые: `is_active`, `is_enabled`, `is_synced`
- Временные метки: `created_at`, `updated_at`, `synced_at`, `last_seen_at`
- Статус: `status_flag` (int), `status_text` (str)

### Внешние ключи
- `{table_singular}_id`: `user_id`, `role_id`, `mirror_id`

### Индексы
- `ix_{table}_{column}`: `ix_users_email`, `ix_gitlab_mirrors_project_id`

### Ограничения
- Уникальные: `uq_{table}_{column}`: `uq_users_email`
- Проверочные: `ck_{table}_{constraint}`: `ck_users_status_flag`

## Модели SQLAlchemy

### Базовый класс

```python
# app/database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

### Пример модели

```python
# app/models/gitlab_mirror.py
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.database import Base

class GitLabMirror(Base):
    __tablename__ = "gitlab_mirrors"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Основные поля
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    gitlab_project_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Зашифрованные credentials
    gitlab_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Статус
    status_flag: Mapped[int] = mapped_column(Integer, default=4)  # 4 = Pending
    status_text: Mapped[str] = mapped_column(String(255), default="Pending")
    
    # Флаги
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    mirror_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Внешние ключи
    github_project_id: Mapped[int] = mapped_column(
        ForeignKey("github_projects.id", ondelete="CASCADE")
    )
    
    # Relationships
    github_project: Mapped["GitHubProject"] = relationship(
        "GitHubProject", back_populates="mirrors"
    )
```

### Статус флаги (унифицированные)

```python
class StatusFlag:
    OK = 0           # Успешно
    FAILED = 1       # Ошибка
    WARNING = 2      # Предупреждение / Устаревшие данные
    IN_PROGRESS = 3  # В процессе
    PENDING = 4      # Ожидает
```

## Миграции Alembic

### Создание миграции

```bash
cd backend

# Создать пустую миграцию
alembic revision -m "add_oidc_config_table"

# Автогенерация из изменений моделей (осторожно!)
alembic revision --autogenerate -m "add_oidc_config_table"
```

Файл создаётся в `alembic/versions/YYYYMMDD_HHMM_<hash>_add_oidc_config_table.py`.

### Структура файла миграции

```python
# alembic/versions/20260606_1200_abc123_add_oidc_config_table.py
"""add_oidc_config_table

Revision ID: abc123
Revises: previous_revision_id
Create Date: 2026-06-06 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'abc123'
down_revision = 'previous_revision_id'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'oidc_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('issuer', sa.String(500), nullable=False),
        sa.Column('client_id', sa.String(255), nullable=False),
        sa.Column('client_secret_encrypted', sa.Text(), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_oidc_config_id', 'oidc_config', ['id'])

def downgrade() -> None:
    op.drop_index('ix_oidc_config_id', 'oidc_config')
    op.drop_table('oidc_config')
```

### Применение миграций

```bash
# Применить все pending миграции
alembic upgrade head

# Применить одну миграцию вперёд
alembic upgrade +1

# Откатить последнюю миграцию
alembic downgrade -1

# Откатить до конкретной версии
alembic downgrade abc123

# Откатить всё
alembic downgrade base

# Текущая версия
alembic current

# История миграций
alembic history --verbose

# Показать SQL без применения
alembic upgrade head --sql
```

### Типичные операции в миграциях

```python
# Добавить колонку
op.add_column('users', sa.Column('keycloak_sub', sa.String(255), nullable=True))

# Удалить колонку
op.drop_column('users', 'old_column')

# Добавить индекс
op.create_index('ix_users_keycloak_sub', 'users', ['keycloak_sub'])

# Удалить индекс
op.drop_index('ix_users_keycloak_sub', 'users')

# Добавить уникальное ограничение
op.create_unique_constraint('uq_users_email', 'users', ['email'])

# Добавить внешний ключ
op.create_foreign_key(
    'fk_mirrors_project_id',
    'gitlab_mirrors', 'github_projects',
    ['github_project_id'], ['id'],
    ondelete='CASCADE'
)

# Изменить тип колонки
op.alter_column('users', 'status_flag',
    existing_type=sa.String(),
    type_=sa.Integer(),
    existing_nullable=True
)

# Выполнить SQL напрямую
op.execute("UPDATE users SET status_flag = 0 WHERE status_flag IS NULL")
```

## Async запросы

### Базовые операции

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from app.models.gitlab_mirror import GitLabMirror

# SELECT - один объект
async def get_mirror(db: AsyncSession, mirror_id: int) -> GitLabMirror | None:
    result = await db.execute(
        select(GitLabMirror).where(GitLabMirror.id == mirror_id)
    )
    return result.scalar_one_or_none()

# SELECT - список
async def get_all_mirrors(db: AsyncSession) -> list[GitLabMirror]:
    result = await db.execute(
        select(GitLabMirror)
        .where(GitLabMirror.is_active == True)
        .order_by(GitLabMirror.created_at.desc())
    )
    return list(result.scalars().all())

# INSERT
async def create_mirror(db: AsyncSession, data: dict) -> GitLabMirror:
    mirror = GitLabMirror(**data)
    db.add(mirror)
    await db.commit()
    await db.refresh(mirror)
    return mirror

# UPDATE
async def update_mirror_status(
    db: AsyncSession, mirror_id: int, status_flag: int, status_text: str
) -> None:
    await db.execute(
        update(GitLabMirror)
        .where(GitLabMirror.id == mirror_id)
        .values(status_flag=status_flag, status_text=status_text)
    )
    await db.commit()

# DELETE
async def delete_mirror(db: AsyncSession, mirror_id: int) -> None:
    await db.execute(
        delete(GitLabMirror).where(GitLabMirror.id == mirror_id)
    )
    await db.commit()
```

### Сложные запросы

```python
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload, joinedload

# JOIN с загрузкой связанных объектов
async def get_mirrors_with_project(db: AsyncSession) -> list[GitLabMirror]:
    result = await db.execute(
        select(GitLabMirror)
        .options(selectinload(GitLabMirror.github_project))
        .where(GitLabMirror.is_active == True)
    )
    return list(result.scalars().all())

# Фильтрация с несколькими условиями
async def search_mirrors(
    db: AsyncSession,
    status_flag: int | None = None,
    search: str | None = None
) -> list[GitLabMirror]:
    query = select(GitLabMirror)
    
    conditions = []
    if status_flag is not None:
        conditions.append(GitLabMirror.status_flag == status_flag)
    if search:
        conditions.append(GitLabMirror.name.ilike(f"%{search}%"))
    
    if conditions:
        query = query.where(and_(*conditions))
    
    result = await db.execute(query)
    return list(result.scalars().all())

# Агрегация
async def count_mirrors_by_status(db: AsyncSession) -> dict:
    result = await db.execute(
        select(GitLabMirror.status_flag, func.count(GitLabMirror.id))
        .group_by(GitLabMirror.status_flag)
    )
    return dict(result.all())

# Пагинация
async def get_mirrors_paginated(
    db: AsyncSession, page: int = 1, per_page: int = 20
) -> tuple[list[GitLabMirror], int]:
    # Общее количество
    count_result = await db.execute(
        select(func.count(GitLabMirror.id))
    )
    total = count_result.scalar()
    
    # Данные с пагинацией
    result = await db.execute(
        select(GitLabMirror)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .order_by(GitLabMirror.created_at.desc())
    )
    items = list(result.scalars().all())
    
    return items, total
```

## Конфигурация подключения

### Настройки в `app/config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://bigbug:bigbug@localhost:5432/bigbug"
    
    # Настройки пула соединений
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
```

### Настройки engine в `app/database.py`

```python
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    echo=False,  # True для debug SQL
)
```

## Troubleshooting

### Конфликты миграций

```bash
# Проверить текущее состояние
alembic current

# Посмотреть историю
alembic history

# Если несколько head ревизий
alembic heads

# Создать merge миграцию
alembic merge -m "merge_heads" head1 head2
```

### Ошибки подключения

```bash
# Проверить PostgreSQL
docker compose -f docker-compose.infra.yml ps postgres-backend

# Проверить логи
docker compose -f docker-compose.infra.yml logs postgres-backend

# Подключиться напрямую
docker exec -it bigbug-postgres-backend psql -U bigbug -d bigbug
```

### Сброс базы данных (dev only)

```bash
# Откатить все миграции
alembic downgrade base

# Применить заново
alembic upgrade head

# Или пересоздать БД
docker compose -f docker-compose.infra.yml down -v
docker compose -f docker-compose.infra.yml up -d postgres-backend
alembic upgrade head
```

### Медленные запросы

```python
# Включить логирование SQL
engine = create_async_engine(settings.DATABASE_URL, echo=True)

# Или через переменную окружения
# SQLALCHEMY_ECHO=true
```

## Best Practices

- **Один файл = одна модель** в `app/models/`
- **Всегда создавать индексы** для колонок в WHERE условиях
- **Использовать `ondelete="CASCADE"`** для связанных записей
- **Не хранить секреты в открытом виде** - использовать Fernet шифрование
- **Всегда писать `downgrade()`** в миграциях
- **Тестировать миграции** на dev базе перед применением на prod
- **Использовать `selectinload`** вместо lazy loading для async
- **Не использовать `session.execute(text(...))`** без параметризации (SQL injection)
