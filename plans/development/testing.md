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

```
backend/tests/
├── conftest.py              # Fixtures (test DB, client, auth)
├── test_auth.py             # Тесты аутентификации
├── test_projects.py         # Тесты GitHub проектов
├── test_images.py           # Тесты Gold/App Images
├── test_helm_api.py         # Тесты Helm Charts API
├── test_helm_service.py     # Тесты Helm service layer
├── test_docker_api.py       # Тесты Docker Images API
├── test_docker_service.py   # Тесты Docker service layer
├── test_oidc.py             # Тесты OIDC интеграции
└── test_secrets.py          # Тесты шифрования
```

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

## Frontend Testing (Vitest + React Testing Library)

### Технологии

- **Vitest 2.0+** - фреймворк для тестирования (Vite-native)
- **@testing-library/react** - утилиты для тестирования React
- **@testing-library/user-event** - симуляция пользовательских действий
- **jsdom** - DOM окружение для Node.js

### Структура тестов

```
frontend/src/tests/
├── setup.ts                      # Настройки Vitest
├── authSlice.test.ts             # Redux slice тесты
├── StatusChip.test.tsx           # Компонент StatusChip
├── DockerImages.test.tsx         # Страница Docker Images
├── DockerImageDetail.test.tsx    # Детали Docker образа
├── HelmCharts.test.tsx           # Страница Helm Charts
├── HelmChartDetail.test.tsx      # Детали Helm чарта
├── SsoCallback.test.tsx          # SSO callback обработка
├── keycloak.service.test.ts      # Keycloak сервис
└── useKeycloakAuth.test.tsx      # Keycloak auth hook
```

**Отсутствующие тесты (нужно написать для RBAC Phase 1)**:
- `usePermissions.test.ts` — тесты хука `usePermissions` (`hasPermission`, `hasAnyPermission`, `hasAllPermissions`)
- `PermissionGate.test.tsx` — тесты компонента `PermissionGate` (условный рендер, `permission`/`anyOf`/`allOf`, fallback)

### Запуск тестов

```bash
cd frontend

# Watch mode (автоматический перезапуск)
yarn test

# Один запуск
yarn test:run

# С покрытием
yarn test:coverage

# Конкретный файл
yarn test DockerImages.test.tsx

# UI mode (интерактивный)
yarn test --ui

# Только failed тесты
yarn test --run --reporter=verbose --changed
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
    setupFiles: './src/tests/setup.ts',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'lcov'],
      exclude: ['node_modules/', 'src/tests/'],
    },
  },
});
```

В [`src/tests/setup.ts`](../../frontend/src/tests/setup.ts):

```typescript
import { expect, afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';
import '@testing-library/jest-dom';

// Cleanup после каждого теста
afterEach(() => {
  cleanup();
});

// Mock environment variables
vi.mock('import.meta', () => ({
  env: {
    VITE_API_URL: 'http://localhost:8000',
    VITE_KEYCLOAK_URL: 'http://localhost:8180',
    VITE_KEYCLOAK_REALM: 'bigbug',
    VITE_KEYCLOAK_CLIENT_ID: 'bigbug-frontend',
  },
}));
```

### Примеры тестов

#### Тестирование компонента

```typescript
// src/tests/StatusChip.test.tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import StatusChip from '../components/StatusChip';

describe('StatusChip', () => {
  it('renders OK status with green color', () => {
    render(<StatusChip status={0} />);
    const chip = screen.getByText('OK');
    expect(chip).toBeInTheDocument();
    expect(chip).toHaveClass('MuiChip-colorSuccess');
  });
  
  it('renders Failed status with red color', () => {
    render(<StatusChip status={1} />);
    const chip = screen.getByText('Failed');
    expect(chip).toBeInTheDocument();
    expect(chip).toHaveClass('MuiChip-colorError');
  });
  
  it('renders custom label', () => {
    render(<StatusChip status={0} label="Synced" />);
    expect(screen.getByText('Synced')).toBeInTheDocument();
  });
});
```

#### Тестирование страницы с API

```typescript
// src/tests/DockerImages.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect, vi } from 'vitest';
import DockerImages from '../pages/DockerImages';
import { store } from '../store';

// Mock RTK Query
vi.mock('../store/api', () => ({
  useGetDockerSourcesQuery: () => ({
    data: [
      {
        id: 1,
        name: 'nginx',
        registry_url: 'https://registry.hub.docker.com',
        status_flag: 0,
        status_text: 'OK',
        created_at: '2024-01-01T00:00:00Z',
      },
    ],
    isLoading: false,
    error: null,
  }),
  useDeleteDockerSourceMutation: () => [vi.fn(), { isLoading: false }],
  useSyncDockerSourceMutation: () => [vi.fn(), { isLoading: false }],
}));

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
    
    renderComponent();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
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
      - run: cd frontend && yarn test:run
      - run: cd frontend && yarn test:coverage
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
