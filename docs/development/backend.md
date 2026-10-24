# Backend Development Guide

Руководство по разработке backend части BigBug на FastAPI.

## Технологический стек

Решения по стеку зафиксированы в [ADR-0001](../adr/backend/0001-choose-backend-stack.md) (backend: Python 3.14 + FastAPI + SQLAlchemy 2 + PostgreSQL 17 / Redis 7), [ADR-0006](../adr/backend/0006-database-postgresql-alembic.md) (database layer, миграции) и [ADR-0003](../adr/common/0003-keycloak-oidc-dual-auth.md) (auth: JWT + Keycloak OIDC). Актуальные версии — [`backend/pyproject.toml`](../../backend/pyproject.toml); источник истины — код и реестр [ADR](../adr/README.md).

## Структура проекта

```
backend/
├── alembic/            # Миграции БД
├── app/
│   ├── api/            # REST API роутеры
│   ├── core/           # Безопасность, RBAC
│   ├── models/         # SQLAlchemy модели
│   ├── schemas/        # Pydantic схемы
│   └── services/       # Бизнес-логика
├── tests/              # pytest тесты
├── Dockerfile
└── pyproject.toml      # Зависимости
```

## Настройка окружения

### Установка зависимостей

```bash
cd backend

# Установить uv (если ещё не установлен)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Установить зависимости из uv.lock (создаёт .venv автоматически)
uv sync
```

### Запуск инструментов

Все скрипты (`backend/scripts/`) вызывают инструменты через `uv run`, который
сам синхронизирует `.venv` с `uv.lock` — вручную активировать окружение не нужно.

Для разовых команд: `uv run python -m pytest`, `uv run python -m alembic upgrade head`.

### Переменные окружения

Для локального запуска без Docker создайте `backend/.env` (pydantic-settings читает его автоматически; в контейнере/charts — env из k8s-секретов, [ADR-0024](../adr/common/0024-k8s-secrets.md)):

```bash
# Database (CNPG dev-стенда; e2e-env.sh экспортирует через port-forward)
DATABASE_URL=postgresql+asyncpg://bigbug:bigbug@localhost:5432/bigbug

# Security
SECRET_KEY=your-secret-key-here

# Encryption Key for secrets (ENCRYPTION_KEY, не FERNET_KEY — см. ADR-0010)
ENCRYPTION_KEY=your-fernet-key-here

# SSO/Keycloak (опционально; полный список keycloak_* — в backend/app/config.py)
# KEYCLOAK_URL=https://keycloak.local
# KEYCLOAK_REALM=bigbug
```

> Именование OIDC-переменных: семейство `keycloak_*` в [`backend/app/config.py`](../../backend/app/config.py) (`keycloak_url`, `keycloak_realm`, `keycloak_client_id`, `keycloak_client_secret`, `keycloak_frontend_client_id`, `keycloak_public_url`, `keycloak_http_timeout_seconds`, `keycloak_jwks_cache_ttl_seconds`). Переменных `OIDC_*` не существует. Runtime-конфиг SSO — в БД (таблица `oidc_config`, ADR-0003), env — только инфраструктурные дефолты.

### Запуск для разработки

```bash
# Применить миграции
alembic upgrade head

# Запустить dev server с hot-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Приложение будет доступно по адресу: http://localhost:8000

API документация (Swagger UI): http://localhost:8000/api/docs

### Запуск taskiq worker локально

Фоновые задачи (ADR-0039) исполняются отдельным процессом-воркером, не в
API-процессе. В k8s его поднимает chart (`charts/bigbug/templates/worker-deployment.yaml`,
grace 360s / `--wait-tasks-timeout 300`); локально — та же команда, что в
образе:

```bash
# Нужны DATABASE_URL, REDIS_URL (см. раздел «Переменные окружения»)
taskiq worker --wait-tasks-timeout 300 app.tasks.broker:broker app.tasks
```

Без запущенного воркера задачи копятся в Redis-стриме и не исполняются
(планировщики в API только enqueue'ят).

## OpenAPI-контракт (источник истины фронт-бэк)

Фиксированная OpenAPI-схема лежит в [`backend/openapi.json`](../../backend/openapi.json) и
является **источником истины контракта** между frontend и backend.

- **Генерация**: схема строится импортом FastAPI-приложения (`from app.main import app`)
  и вызовом `app.openapi()` — без подключения к БД/Redis и без запуска lifespan.
- **Регенерация** (после изменения любого роутера/Pydantic-схемы):

  ```bash
  ./backend/scripts/export-openapi.sh
  ```

  Прямой вызов Python-скрипта (из каталога `backend/`):

  ```bash
  python -m scripts.export_openapi            # -> backend/openapi.json
  python -m scripts.export_openapi -o /tmp/schema.json
  ```

- **Guard актуальности**: тест [`test_openapi_contract.py`](../../backend/tests/unit/test_openapi_contract.py)
  генерирует схему заново и сравнивает её с зафиксированным файлом как объекты
  Python. При расхождении тест падает с подсказкой запустить
  `backend/scripts/export-openapi.sh` — это не даёт схеме устареть незаметно.

Файл детерминирован (сортировка ключей + отступы), поэтому повторный запуск
даёт идентичный результат — его можно безопасно коммитить и ревьюить в diff.

## Поиск мёртвого кода (vulture)

Для обнаружения кандидатов в мёртвый код используется [`vulture`](../../backend/pyproject.toml)
(dev-зависимость). Обёртка — [`backend/scripts/vulture.sh`](../../backend/scripts/vulture.sh).

```bash
./backend/scripts/vulture.sh                  # app/ scripts/ docker/
./backend/scripts/vulture.sh tests/           # + тесты отдельным прогоном
./backend/scripts/vulture.sh --min-confidence 80
```

Полный вывод сохраняется в [`backend/reports/vulture-report.txt`](../../backend/reports/vulture-report.txt),
в stdout печатается сводка (количество находок и разбивка по confidence).
Скрипт всегда завершается с кодом 0, даже при наличии находок.

### Что считаем ложными срабатываниями

Vulture не видит использование кода через механизмы фреймворков, поэтому в
`vulture-whitelist.py` вынесены подтверждённые ложные срабатывания:

- **FastAPI-роутеры/эндпоинты** — вызываются фреймворком через декораторы
  (`@router.get(...)`), а не явно.
- **Pydantic-схемы/поля** — читаются сериализацией (`response_model`,
  `model_validate`, `from_attributes`).
- **SQLAlchemy-модели/колонки/relationship** — маппятся ORM.
- **pydantic-settings поля** — наполняются из env-переменных.
- **entrypoint-функции** (`if __name__ == "__main__":`), фикстуры pytest,
  миграции Alembic.

### Политика whitelist

Каждая запись в [`backend/vulture-whitelist.py`](../../backend/vulture-whitelist.py)
должна сопровождаться комментарием-обоснованием, почему это ложное
срабатывание. Добавлять запись можно только после ручной проверки, что код
действительно используется фреймворком, а не реально мёртв.

### Находки — кандидаты, а не приговор

Вывод vulture — это **кандидаты** в мёртвый код, а не факт удаления. Перед
удалением каждой находки нужно проверить: динамические вызовы, рефлексию,
строковые ссылки (например, имена методов в `getattr`/конфигурации) и вызовы
из тестов. Ничего не удалять только на основании отчёта.

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

Тесты в [`backend/tests/`](../../backend/tests/): `tests/unit/` — unit-тесты (pytest + httpx AsyncClient без живого сервера, ADR-0014), `tests/e2e/` — e2e против живого dev-стенда (ADR-0016/0018), общие fixtures в [`conftest.py`](../../backend/tests/conftest.py).

### Запуск тестов

Агентам каноничен запуск через `make` + `TEST_ARGS` (см. AGENTS.md); вручную:

```bash
# Все unit-тесты
pytest tests/unit

# Конкретный файл
pytest tests/e2e/test_auth.py -v

# Конкретный тест
pytest tests/e2e/test_auth.py::TestAuth::test_login_success -v

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
async def test_create_resource(client: AsyncClient, login_headers: dict):
    """Test creating a new resource"""
    response = await client.post(
        "/api/resources",
        json={"name": "Test Resource", "description": "Test"},
        headers=login_headers,
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Resource"
    assert "id" in data
    assert data["status_flag"] == 0

@pytest.mark.asyncio
async def test_get_resource_not_found(client: AsyncClient, login_headers: dict):
    """Test getting non-existent resource returns 404"""
    response = await client.get(
        "/api/resources/99999",
        headers=login_headers,
    )
    
    assert response.status_code == 404
```

## Качество кода

### Форматирование и линтинг

```bash
# Ruff format - форматирование кода
ruff format .

# Ruff check - линтинг и автофикс
ruff check --fix .

# Полная проверка (в таком порядке)
ruff format . && ruff check --fix . && pytest
```

### 3. Создать API router

В [`app/api/resource.py`](../../backend/app/api/):

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.core.rbac import require_permission  # не app.core.security!
from app.models.user import User
from app.schemas.resource import ResourceOut, ResourceCreate
from app.services.resource import ResourceService
from app.core.exceptions import ResourceNotFoundError

router = APIRouter()

@router.get("/", response_model=list[ResourceOut])
async def list_resources(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("resources:read"))
):
    service = ResourceService(db)
    resources = await service.get_all()
    return resources

@router.post("/", response_model=ResourceOut, status_code=201)
async def create_resource(
    data: ResourceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("resources:write"))
):
    service = ResourceService(db)
    resource = await service.create(data)
    return resource

@router.get("/{resource_id}", response_model=ResourceOut)
async def get_resource(
    resource_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("resources:read"))
):
    service = ResourceService(db)
    try:
        resource = await service.get_by_id(resource_id)
        return resource
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Resource not found")
```

> Авторизация: новые endpoint'ы защищаются через `require_permission("resource:action")` из [`app/core/rbac.py`](../../backend/app/core/rbac.py) (ADR-0004). Legacy-зависимости `require_operator`/`require_admin`/`require_viewer` тоже живут в `app/core/rbac.py` (не в `security.py`), но для новых endpoint'ов не используются — исключение одно: `app/api/health_check.py`.</think><tool_call>edit<arg_key>newString</arg_key><arg_value>### Pre-commit hooks

Pre-commit конфигурации в репозитории нет — проверки качества выполняются
вручную/агентом через `make lint`, `make format`, `make typecheck` (см. ADR-0019).

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
from app.core.security import create_access_token, decode_token

# Создать токен
token = create_access_token({"sub": str(user.id), "username": user.username, "permissions": [...]})

# Проверить/декодировать токен
try:
    payload = decode_token(token)  # raises ValueError if invalid/expired
except ValueError as e:
    ...  # маппится в 401: UnauthorizedError(str(e)) — см. app/core/rbac.py
```

> Функция проверки токена — `decode_token` (поднимает `ValueError`
> при невалидном/просроченном токене); в API-слое исключение маппится в 401
> (`app/core/rbac.py: get_current_user`).

## Интеграции

Интеграции с внешними системами (GitLab, Harbor, GitHub, Docker Registry, Helm-репозитории) унифицированы через Providers V3 (ADR-0007): реестр подтипов — [`app/services/providers/registry.py`](../../backend/app/services/providers/registry.py), HTTP-клиенты — [`app/services/providers/clients/`](../../backend/app/services/providers/clients/), доменные действия — через диспетчер в [`app/services/providers/service.py`](../../backend/app/services/providers/service.py).

```python
# Доменное действие провайдера — через единый service-диспетчер
from app.services.providers.service import ProviderService

service = ProviderService(db)
result = await service.dispatch_action(
    provider_id,
    action="list_repositories",  # ProviderCapability
    user=current_user,
    params={...},
)
```

Клиент конкретного подтипа создаётся по метаданным провайдера (`base_url`, credential, `verify_ssl`) — руками инстанцировать классы клиентов из API-слоя не нужно.

OIDC-логика — в [`app/services/oidc.py`](../../backend/app/services/oidc.py) (Keycloak-OIDC сервис: обмен кода, валидация id_token, provisioning — ADR-0003); GitLab/mirror-логика — в соответствующих сервисах `app/services/`.

## Планировщик задач

APScheduler для периодических задач:

- **[`app/services/scheduler.py`](../../backend/app/services/scheduler.py)** — `SchedulerService`: глобальные cron-джобы из настроек (`default_sync_cron` — sync schedules, `default_build_cron` — build schedules, `cleanup_cron_hour` — soft-delete cleanup).
- **[`app/services/sync_scheduler.py`](../../backend/app/services/sync_scheduler.py)** — `SyncScheduler`: per-SyncGroup джобы (sync + freshness check по `sync_cron`/`freshness_cron` групп), динамическое добавление/удаление при изменении конфигурации групп, свой `AsyncSession` на каждый job.

Пер-зеркальное API вида `schedule_mirror_sync(mirror_id, cron_expression=...)` не существует — расписание задаётся на уровне SyncGroup/SyncSchedule.

## Troubleshooting

### Проблемы с импортами

```bash
# Пересоздать окружение с нуля
rm -rf .venv && uv sync
```

### База данных не подключается

```bash
# CNPG-под в kind-стенде
kubectl get pods -n bigbug --context kind-bigbug-dev -l cnpg.io/cluster=bigbug-dev

# DATABASE_URL в backend/.env (или экспортированная e2e-env.sh через port-forward)
echo $DATABASE_URL
```

### Конфликты миграций

```bash
# Проверить текущую версию
alembic current

# Откатить
alembic downgrade -1
```

> Политика миграций (ADR-0006): миграции после применения не удаляются и не
> редактируются — цепочка append-only. «Удалить файл миграции и пересоздать»
> — недопустимый совет: на стендах, где миграция уже применена, это ломает
> `alembic_version`. Конфликт разрешается новой миграцией поверх `head`.

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
