# Testing Guide

Руководство по тестированию BigBug (backend и frontend).

## Backend Testing (pytest)

### Технологии

- **pytest 8.2+** - фреймворк для тестирования
- **pytest-asyncio 0.23+** - поддержка async тестов
- **pytest-cov 5.0+** - покрытие кода
- **httpx** - async HTTP клиент для тестирования API
- **pytest-mock** - мокирование

### Структура тестов

Тесты в [`backend/tests/`](../../backend/tests/): организованы по модулям с общими fixtures в [`conftest.py`](../../backend/tests/conftest.py).

**Отсутствующие тесты (нужно написать для RBAC Phase 1)**:
- `test_rbac_service.py` — тесты `RBACService` (CRUD ролей, permissions, защита builtin-ролей)
- `test_rbac_api.py` — тесты Admin RBAC API (`GET /admin/permissions`, `/admin/roles`, CRUD)

### Запуск тестов

```bash
cd backend

# Все тесты
pytest

# Конкретный файл
pytest tests/test_auth.py -v

# Конкретный тест
pytest tests/test_auth.py::test_login_success -v

# Тесты по паттерну
pytest -k "test_login" -v

# С покрытием кода
pytest --cov=app --cov-report=html

# С выводом print()
pytest -s

# Остановить на первой ошибке
pytest -x

# Подробный вывод
pytest -vv

# Показать fixtures
pytest --fixtures

# Только failed тесты (после неудачного прогона)
pytest --lf

# Параллельный запуск (требует pytest-xdist)
pytest -n auto
```

### Fixtures

В [`tests/conftest.py`](../../backend/tests/conftest.py):

```python
import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.main import app
from app.database import Base, get_db
from app.models.user import User
from app.models.role import Role
from app.core.security import create_access_token
import bcrypt

# Test database URL
TEST_DATABASE_URL = "postgresql+asyncpg://bigbug:bigbug@localhost:5432/bigbug_test"

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def db_session():
    """Create test database session"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    AsyncTestingSession = async_sessionmaker(engine, expire_on_commit=False)
    async with AsyncTestingSession() as session:
        yield session
    
    # Cleanup
    await engine.dispose()

@pytest.fixture
async def async_client(db_session):
    """Create async HTTP client with test DB"""
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    
    app.dependency_overrides.clear()

@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create admin user"""
    role = Role(name="admin")
    db_session.add(role)
    await db_session.flush()
    
    user = User(
        email="admin@test.com",
        hashed_password=bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode(),
        is_active=True,
        role_id=role.id
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest.fixture
def admin_token(admin_user: User) -> str:
    """Create JWT token for admin user"""
    return create_access_token({"sub": admin_user.email, "user_id": admin_user.id})

@pytest.fixture
async def operator_user(db_session: AsyncSession) -> User:
    """Create operator user"""
    role = Role(name="operator")
    db_session.add(role)
    await db_session.flush()
    
    user = User(
        email="operator@test.com",
        hashed_password=bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode(),
        is_active=True,
        role_id=role.id
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user

@pytest.fixture
def operator_token(operator_user: User) -> str:
    """Create JWT token for operator user"""
    return create_access_token({"sub": operator_user.email, "user_id": operator_user.id})
```

### Примеры тестов

#### Тестирование API endpoints

**Примечание**: Файл `tests/test_mirrors.py` не существует в проекте. Пример ниже показывает паттерн для будущих тестов.

```python
# tests/test_mirrors.py (пример, файл не существует)
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_list_mirrors_empty(async_client: AsyncClient, operator_token: str):
    """Test listing mirrors when none exist"""
    response = await async_client.get(
        "/api/mirrors",
        headers={"Authorization": f"Bearer {operator_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0

@pytest.mark.asyncio
async def test_create_mirror(async_client: AsyncClient, operator_token: str, db_session):
    """Test creating a new mirror"""
    # Сначала создать GitHub проект
    from app.models.github_org import GitHubOrg
    from app.models.github_project import GitHubProject
    
    org = GitHubOrg(name="test-org", github_org_id=12345)
    db_session.add(org)
    await db_session.flush()
    
    project = GitHubProject(
        name="test-repo",
        github_id=67890,
        github_org_id=org.id,
        clone_url="https://github.com/test-org/test-repo.git"
    )
    db_session.add(project)
    await db_session.commit()
    
    # Создать зеркало
    response = await async_client.post(
        "/api/mirrors",
        json={
            "github_project_id": project.id,
            "name": "test-mirror",
            "gitlab_token": "glpat-test-token"
        },
        headers={"Authorization": f"Bearer {operator_token}"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "test-mirror"
    assert data["status_flag"] == 4  # Pending
    assert "gitlab_project_id" not in data  # Ещё не создан

@pytest.mark.asyncio
async def test_get_mirror_not_found(async_client: AsyncClient, operator_token: str):
    """Test getting non-existent mirror returns 404"""
    response = await async_client.get(
        "/api/mirrors/99999",
        headers={"Authorization": f"Bearer {operator_token}"}
    )
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_unauthorized_access(async_client: AsyncClient):
    """Test that endpoints require authentication"""
    response = await async_client.get("/api/mirrors")
    assert response.status_code == 401
```

#### Тестирование Service Layer

```python
# tests/test_github_service.py
import pytest
from unittest.mock import AsyncMock, patch
from app.services.github import GitHubService

@pytest.mark.asyncio
async def test_list_repos_success():
    """Test listing GitHub repositories"""
    mock_response = [
        {"id": 1, "name": "repo1", "clone_url": "https://..."},
        {"id": 2, "name": "repo2", "clone_url": "https://..."}
    ]
    
    with patch('httpx.AsyncClient.get') as mock_get:
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: mock_response
        )
        
        service = GitHubService("fake-token")
        repos = await service.list_repos("test-org")
        
        assert len(repos) == 2
        assert repos[0]["name"] == "repo1"

@pytest.mark.asyncio
async def test_list_repos_auth_error():
    """Test GitHub API authentication error"""
    with patch('httpx.AsyncClient.get') as mock_get:
        mock_get.return_value = AsyncMock(status_code=401)
        
        service = GitHubService("invalid-token")
        
        with pytest.raises(Exception) as exc_info:
            await service.list_repos("test-org")
        
        assert "authentication" in str(exc_info.value).lower()
```

#### Тестирование шифрования

```python
# tests/test_secrets.py
import pytest
from app.core.secrets import encrypt_secret, decrypt_secret

def test_encrypt_decrypt_roundtrip():
    """Test that encryption and decryption work correctly"""
    original = "my-secret-token-12345"
    
    encrypted = encrypt_secret(original)
    decrypted = decrypt_secret(encrypted)
    
    assert decrypted == original
    assert encrypted != original

def test_encrypt_different_each_time():
    """Test that encryption produces different output each time"""
    original = "my-secret-token"
    
    encrypted1 = encrypt_secret(original)
    encrypted2 = encrypt_secret(original)
    
    assert encrypted1 != encrypted2
    assert decrypt_secret(encrypted1) == original
    assert decrypt_secret(encrypted2) == original

def test_decrypt_invalid_data():
    """Test that decrypting invalid data raises error"""
    with pytest.raises(Exception):
        decrypt_secret("invalid-encrypted-data")
```

### Покрытие кода

```bash
# Генерировать HTML отчёт
pytest --cov=app --cov-report=html

# Открыть в браузере
# htmlcov/index.html

# Только процент покрытия
pytest --cov=app --cov-report=term-missing

# Фейлить если покрытие ниже N%
pytest --cov=app --cov-fail-under=80
```

## Backend E2E Testing (реальный HTTP, без моков)

Отдельный набор e2e-тестов в [`backend/tests/e2e/`](../../backend/tests/e2e/) прогоняется
против **живого** dev-стека (не `ASGITransport`, не SQLite, не `dependency_overrides`).

### Ключевые принципы

- Реальный HTTP на `http://localhost:8000` (переопределяется через `BIGBUG_E2E_BASE_URL`).
- Аутентификация через настоящий `POST /api/auth/login` (admin из env `E2E_ADMIN_USERNAME`/`E2E_ADMIN_PASSWORD`).
- Изоляция данных: уникальные имена + teardown через API (никаких прямых записей в БД).
- Валидация ответов по замороженному [`backend/openapi.json`](../../backend/openapi.json) через
  [`openapi_utils.assert_matches_openapi`](../../backend/tests/e2e/openapi_utils.py).
- Внешние интеграции (GitHub/GitLab/Harbor/Helm/Docker) **не дёргают реальные внешние API** —
  тестируются только endpoints без внешних вызовов либо ожидаемые 4xx/401/403.

### Запуск

```bash
# dev-стек должен быть поднят
docker compose up -d

# Сам e2e-прогон
cd backend && ./scripts/test-e2e.sh -v

# Фильтр по имени
./scripts/test-e2e.sh -k "test_login"

# Против другого URL
BIGBUG_E2E_BASE_URL=http://localhost:8011 ./scripts/test-e2e.sh
```

### Rate limiting на dev-стенде

Лимитер нужен только на продакшене. На dev/test стендах он отключается переменной
`RATE_LIMIT_ENABLED=false` (см. [`docker-compose.yml`](../../docker-compose.yml) и
[`.env.example`](../../.env.example)); иначе e2e-прогон упирается в лимит логина
(`5/minute`) и логины начинают таймаутиться.

### Endpoint-coverage отчёт

В teardown сессии автоматически генерируется отчёт, какие операции из
`openapi.json` были покрыты:

- [`backend/reports/endpoint-coverage.json`](../../backend/reports/endpoint-coverage.json)
- [`backend/reports/endpoint-coverage.md`](../../backend/reports/endpoint-coverage.md)

Тест [`test_endpoint_coverage.py`](../../backend/tests/e2e/test_endpoint_coverage.py)
мягко предупреждает (не падает), если покрытие ниже `MIN_COVERAGE_PERCENT` (30%).

### Code coverage (code coverage e2e)

Отдельный скрипт поднимает backend под `coverage run` на отдельном порту, прогоняет
e2e-тесты и снимает покрытие кода:

```bash
cd backend && ./scripts/test-e2e-coverage.sh
# порт можно переопределить: COVERAGE_PORT=8011
```

Отчёты: текстовый (`coverage report`), HTML (`backend/htmlcov/index.html`) и
endpoint-coverage (см. выше).

## Frontend Testing (Vitest + React Testing Library)

### Технологии

- **Vitest 2.0+** - фреймворк для тестирования (Vite-native)
- **@testing-library/react** - утилиты для тестирования React
- **@testing-library/user-event** - симуляция пользовательских действий
- **jsdom** - DOM окружение для Node.js

### Структура тестов

```
frontend/src/tests/
├── unit/               # Изолированные тесты (функции, хуки, редьюсеры)
├── integrations/       # Тесты страниц/компонентов с Redux store и RTK Query моками
└── e2e/                # E2E тесты (Cypress — planned)
```

**Где размещать новые тесты:**
- **Unit**: изолированная логика (редьюсеры, сервисы, хуки через `renderHook`). Файл: `src/tests/unit/Имя.test.ts`
- **Integrations**: тесты страниц/компонентов с Redux store и RTK Query моками. Файл: `src/tests/integrations/Имя.test.tsx`
- **E2E**: пока не реализованы, будут в `src/tests/e2e/`

**Отсутствующие тесты (нужно написать для RBAC Phase 1)**:
- `unit/usePermissions.test.ts` — тесты хука `usePermissions`
- `integrations/PermissionGate.test.tsx` — тесты компонента `PermissionGate`

### Запуск тестов

```bash
cd frontend

# Все тесты (unit + integrations)
./scripts/test.sh

# Только unit
./scripts/test.sh --unit

# Только integrations
./scripts/test.sh --integrations

# С покрытием
./scripts/test.sh --coverage

# Отладка конкретного теста
./scripts/test.sh -f DockerImages -t "should render"

# Watch mode (для разработки)
yarn test

# UI mode (интерактивный)
yarn test --ui
```

### Конфигурация

В [`vitest.config.ts`](../../frontend/vitest.config.ts):

```typescript
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/tests/integrations/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html', 'lcov'],
      reportsDirectory: './coverage',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['node_modules/', 'src/tests/**', 'src/main.tsx'],
    },
  },
});
```

В [`src/tests/integrations/setup.ts`](../../frontend/src/tests/integrations/setup.ts):

```typescript
import '@testing-library/jest-dom';
```

### Примеры тестов

#### Unit: тестирование хука

```typescript
// src/tests/unit/useKeycloakAuth.test.ts
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { useKeycloakAuth } from '../../hooks/useKeycloakAuth';

describe('useKeycloakAuth', () => {
  it('initializes with loading state', () => {
    const { result } = renderHook(() => useKeycloakAuth());
    expect(result.current.ready).toBe(false);
    expect(result.current.authenticated).toBe(false);
  });
});
```

#### Integration: тестирование страницы с API

```typescript
// src/tests/integrations/DockerImages.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import DockerImages from '../../pages/DockerImages';

// Mock RTK Query
vi.mock('../../store/api', () => ({
  useListDockerImagesQuery: () => ({
    data: [
      { id: 1, name: 'nginx', registry_url: 'https://registry.hub.docker.com',
        status_flag: 0, status_text: 'OK', created_at: '2024-01-01T00:00:00Z' },
    ],
    isLoading: false,
    isError: false,
    error: null,
  }),
}));

describe('DockerImages', () => {
  it('renders docker image list', async () => {
    render(<DockerImages />);
    await waitFor(() => {
      expect(screen.getByText('nginx')).toBeInTheDocument();
    });
  });
});

describe('DockerImages', () => {
  const renderComponent = () => {
    return render(
      <Provider store={store}>
        <BrowserRouter>
          <DockerImages />
        </BrowserRouter>
      </Provider>
    );
  };
  
  it('renders docker sources list', async () => {
    renderComponent();
    
    await waitFor(() => {
      expect(screen.getByText('nginx')).toBeInTheDocument();
      expect(screen.getByText('OK')).toBeInTheDocument();
    });
  });
  
  it('shows loading state', () => {
    vi.mocked(useGetDockerSourcesQuery).mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    });
    
    const { container } = renderComponent();
    expect(container.querySelector('.ant-spin')).toBeInTheDocument();
  });
  
  it('shows error message', () => {
    vi.mocked(useGetDockerSourcesQuery).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: { message: 'Network error' },
    });
    
    renderComponent();
    expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
  });
});
```

#### Тестирование Redux slice

```typescript
// src/tests/authSlice.test.ts
import { describe, it, expect } from 'vitest';
import authReducer, { login, logout } from '../store/authSlice';

describe('authSlice', () => {
  it('should handle initial state', () => {
    expect(authReducer(undefined, { type: 'unknown' })).toEqual({
      user: null,
      token: null,
      isAuthenticated: false,
    });
  });
  
  it('should handle login', () => {
    const user = { id: 1, email: 'test@example.com', role: 'operator' };
    const token = 'fake-jwt-token';
    
    const actual = authReducer(undefined, login({ user, token }));
    
    expect(actual.user).toEqual(user);
    expect(actual.token).toEqual(token);
    expect(actual.isAuthenticated).toBe(true);
  });
  
  it('should handle logout', () => {
    const previousState = {
      user: { id: 1, email: 'test@example.com', role: 'operator' },
      token: 'fake-jwt-token',
      isAuthenticated: true,
    };
    
    const actual = authReducer(previousState, logout());
    
    expect(actual.user).toBeNull();
    expect(actual.token).toBeNull();
    expect(actual.isAuthenticated).toBe(false);
  });
});
```

#### Тестирование с user-event

```typescript
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

it('handles button click', async () => {
  const user = userEvent.setup();
  const handleClick = vi.fn();
  
  render(<button onClick={handleClick}>Click me</button>);
  
  await user.click(screen.getByText('Click me'));
  
  expect(handleClick).toHaveBeenCalledTimes(1);
});
```

## E2E Testing (Cypress) - планируется

### Установка

```bash
cd frontend
yarn add -D cypress @testing-library/cypress
```

### Запуск

```bash
# Открыть Cypress UI
yarn cypress open

# Headless mode
yarn cypress run
```

## CI/CD Integration

### GitHub Actions пример

```yaml
name: Tests

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:17
        env:
          POSTGRES_USER: bigbug
          POSTGRES_PASSWORD: bigbug
          POSTGRES_DB: bigbug_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.14'
      - run: cd backend && pip install -e .
      - run: cd backend && pytest --cov=app --cov-report=xml
      - uses: codecov/codecov-action@v3
  
  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '26'
      - run: cd frontend && yarn install
      - run: cd frontend && ./scripts/test.sh
      - run: cd frontend && ./scripts/test.sh --coverage
```

## Best Practices

### Backend
- **Изолировать тесты**: каждый тест должен быть независимым
- **Использовать fixtures**: переиспользовать setup код
- **Мокировать внешние API**: не делать реальные запросы в GitHub/GitLab
- **Тестировать edge cases**: не только happy path
- **Покрытие > 80%**: стремиться к высокому покрытию

### Frontend
- **Тестировать поведение, а не implementation**: проверять что видит пользователь
- **Использовать `screen`**: избегать прямых запросов к container
- **Мокировать API**: использовать `vi.mock()` для RTK Query
- **Async operations**: всегда использовать `waitFor()` или `findBy*()`
- **Accessibility**: использовать семантические запросы (`getByRole`, `getByLabelText`)

## Полезные ссылки

- [pytest Documentation](https://docs.pytest.org/)
- [Vitest Documentation](https://vitest.dev/)
- [React Testing Library](https://testing-library.com/react)
- [Testing Library User Events](https://testing-library.com/docs/user-event/intro)
- [Cypress Documentation](https://docs.cypress.io/)
