# Backend Development Guide

Руководство по разработке backend части BigBug на FastAPI.

## Технологический стек

- **Python 3.14+**
- **FastAPI 0.115+** - async REST API framework
- **SQLAlchemy 2.0+** - ORM с async поддержкой
- **Alembic** - миграции базы данных
- **PostgreSQL 17** - основная БД
- **Redis 7** - кеширование и очереди задач
- **APScheduler** - планировщик задач (AsyncIOScheduler)
- **pytest** + **pytest-asyncio** + **httpx** - тестирование

## Структура проекта

```
backend/
├── app/
│   ├── main.py              # Точка входа FastAPI приложения
│   ├── config.py            # Конфигурация из переменных окружения
│   ├── database.py          # Async database session management
│   ├── api/                 # REST API endpoints
│   │   ├── __init__.py
│   │   ├── auth.py          # Аутентификация (login, SSO, logout)
│   │   ├── projects.py      # GitHub организации/проекты
│   │   ├── mirrors.py       # GitLab зеркала
│   │   ├── gold_images.py   # Gold Images API
│   │   ├── app_images.py    # App Images API
│   │   ├── helm_charts.py   # Helm Charts API
│   │   ├── docker_images.py # Docker Images API
│   │   ├── admin.py         # Административные endpoints
│   │   └── webhooks.py      # Webhooks для GitLab/GitHub
│   ├── core/                # Базовая функциональность
│   │   ├── exceptions.py    # Доменные исключения
│   │   ├── security.py      # JWT, password hashing, dependencies
│   │   ├── secrets.py       # Fernet encryption для credentials
│   │   └── rbac.py          # Роли и права доступа
│   ├── models/              # SQLAlchemy модели (один файл = одна модель)
│   │   ├── user.py
│   │   ├── role.py
│   │   ├── github_org.py
│   │   ├── github_project.py
│   │   ├── gitlab_mirror.py
│   │   ├── gold_image.py
│   │   ├── app_image.py
│   │   ├── helm_chart_source.py
│   │   └── ...
│   ├── schemas/             # Pydantic модели для валидации
│   │   ├── auth.py
│   │   ├── project.py
│   │   ├── mirror.py
│   │   ├── image.py
│   │   ├── helm.py
│   │   └── docker.py
│   └── services/            # Бизнес-логика
│       ├── github.py        # GitHub API интеграция
│       ├── gitlab.py        # GitLab API интеграция
│       ├── oidc.py          # OIDC/Keycloak интеграция
│       ├── build.py         # Gold/App Image builds
│       ├── helm.py          # Helm Repository синхронизация
│       ├── docker.py        # Docker Registry синхронизация
│       └── scheduler.py     # APScheduler задачи
├── alembic/                 # Миграции базы данных
│   ├── versions/
│   ├── env.py
│   └── script.py.mako
├── tests/                   # Тесты
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_projects.py
│   └── ...
├── Dockerfile
├── entrypoint.sh
└── pyproject.toml           # Зависимости (uv/pip)
```

## Настройка окружения

### Установка зависимостей

```bash
cd backend

# Создать виртуальное окружение
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# или
.venv\Scripts\activate  # Windows

# Установить зависимости
pip install -e .

# Или с помощью uv (быстрее)
pip install uv
uv pip install -e .
```

### Переменные окружения

Создать файл `.env` в корне проекта (см. `.env.example`):

```bash
# Database
DATABASE_URL=postgresql+asyncpg://bigbug:bigbug@localhost:5432/bigbug

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Security
SECRET_KEY=your-secret-key-here
FERNET_KEY=your-fernet-key-base64

# OIDC (опционально)
OIDC_ENABLED=false
OIDC_ISSUER=http://localhost:8180/realms/bigbug
OIDC_CLIENT_ID=bigbug-backend
```

### Запуск для разработки

```bash
# Применить миграции
alembic upgrade head

# Запустить dev server с hot-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Или через gunicorn + uvicorn workers (production-like)
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

Приложение будет доступно по адресу: http://localhost:8000

API документация (Swagger UI): http://localhost:8000/docs

## Работа с базой данных

### Создание модели

**Один файл = одна модель** в [`app/models/`](../../backend/app/models/).

Пример [`app/models/user.py`](../../backend/app/models/user.py):

```python
from sqlalchemy import String, Boolean, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.database import Base

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    role: Mapped["Role"] = relationship("Role", back_populates="users")
```

### Создание миграции

```bash
# Создать новую миграцию
alembic revision -m "add_user_keycloak_sub"

# Отредактировать файл в alembic/versions/YYYYMMDD_HHMM_<hash>_add_user_keycloak_sub.py
# Пример:
def upgrade():
    op.add_column('users', sa.Column('keycloak_sub', sa.String(255), nullable=True))
    op.create_index('ix_users_keycloak_sub', 'users', ['keycloak_sub'])

def downgrade():
    op.drop_index('ix_users_keycloak_sub', 'users')
    op.drop_column('users', 'keycloak_sub')

# Применить миграцию
alembic upgrade head

# Откатить последнюю миграцию
alembic downgrade -1

# Посмотреть текущую версию
alembic current

# История миграций
alembic history
```

### Работа с сессиями

Используем async sessions через dependency injection:

```python
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db

@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
```

## Создание API endpoint

### 1. Определить Pydantic схемы

В [`app/schemas/resource.py`](../../backend/app/schemas/):

```python
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

class ResourceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None

class ResourceCreate(ResourceBase):
    pass

class ResourceUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None

class ResourceOut(ResourceBase):
    id: int
    created_at: datetime
    status_flag: int
    status_text: str
    
    model_config = {"from_attributes": True}
```

### 2. Создать service layer

В [`app/services/resource.py`](../../backend/app/services/):

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.resource import Resource
from app.schemas.resource import ResourceCreate, ResourceUpdate
from app.core.exceptions import ResourceNotFoundError

class ResourceService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_all(self) -> list[Resource]:
        result = await self.db.execute(select(Resource))
        return list(result.scalars().all())
    
    async def get_by_id(self, resource_id: int) -> Resource:
        result = await self.db.execute(
            select(Resource).where(Resource.id == resource_id)
        )
        resource = result.scalar_one_or_none()
        if not resource:
            raise ResourceNotFoundError(f"Resource {resource_id} not found")
        return resource
    
    async def create(self, data: ResourceCreate) -> Resource:
        resource = Resource(**data.model_dump())
        self.db.add(resource)
        await self.db.commit()
        await self.db.refresh(resource)
        return resource
```

### 3. Создать API router

В [`app/api/resource.py`](../../backend/app/api/):

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.core.security import require_operator
from app.models.user import User
from app.schemas.resource import ResourceOut, ResourceCreate
from app.services.resource import ResourceService
from app.core.exceptions import ResourceNotFoundError

router = APIRouter()

@router.get("/", response_model=list[ResourceOut])
async def list_resources(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    service = ResourceService(db)
    resources = await service.get_all()
    return resources

@router.post("/", response_model=ResourceOut, status_code=201)
async def create_resource(
    data: ResourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    service = ResourceService(db)
    resource = await service.create(data)
    return resource

@router.get("/{resource_id}", response_model=ResourceOut)
async def get_resource(
    resource_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    service = ResourceService(db)
    try:
        resource = await service.get_by_id(resource_id)
        return resource
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Resource not found")
```

### 4. Зарегистрировать router

В [`app/main.py`](../../backend/app/main.py):

```python
from app.api import resource

app.include_router(
    resource.router,
    prefix="/api/resources",
    tags=["resources"]
)
```

## Тестирование

### Структура тестов

```
tests/
├── conftest.py           # Fixtures (test DB, async client, etc.)
├── test_auth.py
├── test_projects.py
├── test_mirrors.py
├── test_images.py
└── test_resource.py
```

### Запуск тестов

```bash
# Все тесты
pytest

# Конкретный файл
pytest tests/test_auth.py -v

# Конкретный тест
pytest tests/test_auth.py::test_login_success -v

# С покрытием
pytest --cov=app --cov-report=html

# С выводом print()
pytest -s
```

### Пример теста

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_resource(async_client: AsyncClient, operator_token: str):
    """Test creating a new resource"""
    response = await async_client.post(
        "/api/resources",
        json={"name": "Test Resource", "description": "Test"},
        headers={"Authorization": f"Bearer {operator_token}"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Resource"
    assert "id" in data
    assert data["status_flag"] == 0

@pytest.mark.asyncio
async def test_get_resource_not_found(async_client: AsyncClient, operator_token: str):
    """Test getting non-existent resource returns 404"""
    response = await async_client.get(
        "/api/resources/99999",
        headers={"Authorization": f"Bearer {operator_token}"}
    )
    
    assert response.status_code == 404
```

## Качество кода

### Форматирование и линтинг

```bash
# Black - форматирование кода
black .

# Ruff - линтинг и автофикс
ruff check --fix .

# Полная проверка (в таком порядке)
black . && ruff check --fix . && pytest
```

### Pre-commit hooks (опционально)

Создать `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.4.2
    hooks:
      - id: black
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.4
    hooks:
      - id: ruff
        args: [--fix]
```

Установить:

```bash
pip install pre-commit
pre-commit install
```

## Безопасность

### Хеширование паролей

Используем **bcrypt** (НЕ passlib):

```python
import bcrypt

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
```

### Шифрование секретов

Используем **Fernet** для хранения токенов и credentials:

```python
from app.core.secrets import encrypt_secret, decrypt_secret

# Сохранить
gitlab_token = "glpat-xyz123"
encrypted = encrypt_secret(gitlab_token)
mirror.gitlab_token_encrypted = encrypted
await db.commit()

# Получить
decrypted_token = decrypt_secret(mirror.gitlab_token_encrypted)
```

### JWT токены

```python
from app.core.security import create_access_token, verify_token

# Создать токен
token = create_access_token({"sub": user.email, "user_id": user.id})

# Проверить токен
payload = verify_token(token)  # Raises HTTPException if invalid
```

## Интеграции

### GitHub API

```python
from app.services.github import GitHubService

service = GitHubService(github_token)
repos = await service.list_repos(org_name)
releases = await service.get_releases(owner, repo)
```

### GitLab API

```python
from app.services.gitlab import GitLabService

service = GitLabService(gitlab_url, gitlab_token)
project = await service.create_mirror(source_repo, target_name)
await service.trigger_pipeline(project_id)
```

### OIDC / Keycloak

```python
from app.services.oidc import OIDCService

service = OIDCService()
config = await service.get_config(db)
user_info = await service.verify_token(access_token)
```

## Планировщик задач

APScheduler для периодических задач (синхронизация, stale detection):

```python
from app.services.scheduler import scheduler, schedule_mirror_sync

# Запланировать задачу
schedule_mirror_sync(mirror_id, cron_expression="0 2 * * *")

# Отменить задачу
scheduler.remove_job(f"mirror_sync_{mirror_id}")

# Запустить сразу
scheduler.add_job(
    func=sync_mirror_task,
    args=[mirror_id],
    id=f"mirror_sync_{mirror_id}_now",
)
```

## Troubleshooting

### Проблемы с импортами

```bash
# Переустановить зависимости
pip install -e .
```

### База данных не подключается

```bash
# Проверить PostgreSQL
docker compose -f docker-compose.infra.yml ps postgres-backend

# Проверить DATABASE_URL в .env
echo $DATABASE_URL
```

### Конфликты миграций

```bash
# Проверить текущую версию
alembic current

# Откатить
alembic downgrade -1

# Удалить конфликтующую миграцию и пересоздать
rm alembic/versions/YYYYMMDD_HHMM_*.py
alembic revision -m "new_migration"
```

### Тесты падают

```bash
# Проверить тестовую БД
pytest tests/test_auth.py -v -s

# Пересоздать фикстуры
pytest --setup-show tests/test_auth.py
```

## Best Practices

- **Один файл = одна модель** в `app/models/`
- **Services отделены от API layer**: бизнес-логика в `app/services/`
- **Доменные исключения**: не `HTTPException` в service layer, используем кастомные исключения из `app/core/exceptions.py`
- **HTTP mapping в роутерах**: API layer ловит доменные исключения и возвращает HTTP статусы
- **Async везде**: все I/O операции через `async`/`await`
- **Type hints**: используем аннотации типов
- **Валидация через Pydantic**: все входящие данные проходят через schemas
- **Безопасность**: bcrypt для паролей, Fernet для секретов, JWT для токенов

## Полезные ссылки

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [pytest Documentation](https://docs.pytest.org/)
- [`backend/pyproject.toml`](../../backend/pyproject.toml) - актуальные зависимости
- [`AGENTS.md`](../../AGENTS.md) - quick reference
