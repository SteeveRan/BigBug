# Интеграции (Integrations)

> **Дата**: 2026-06-06

## Обзор

Модуль интеграций BigBug управляет подключениями к внешним сервисам, поддерживая множественные инстансы каждого типа. Ранее конфигурация задавалась через переменные окружения (`.env`) — теперь все интеграции управляются через UI и хранятся в базе данных с шифрованием чувствительных данных.

## Поддерживаемые типы интеграций

| Тип | Таблица | RBAC Permission | Аутентификация |
|-----|---------|-----------------|----------------|
| **GitLab** | `gitlab_instances` | `integrations:manage` | Personal Access Token |
| **Harbor** | `harbor_instances` | `integrations:manage` | Username + Password |
| **GitHub** | `github_instances` | `integrations:manage` | Personal Access Token |
| **Docker Registry** | `docker_registry_instances` | `docker_registry:manage` | Username + Password (опционально) |
| **Helm Repository** | `helm_repository_instances` | `helm_repository:manage` | Username + Password (опционально) |

## Архитектура

### Слои

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                       │
│  pages/Settings/Integrations/index.tsx                    │
│  ├── GitlabPanel / GitlabDialog                          │
│  ├── HarborPanel / HarborDialog                          │
│  ├── GithubPanel / GithubDialog                          │
│  ├── DockerRegistryPanel / DockerRegistryDialog          │
│  └── HelmRepositoryPanel / HelmRepositoryDialog          │
├─────────────────────────────────────────────────────────┤
│                    API Layer (FastAPI)                    │
│  api/integrations.py — REST endpoints                    │
│  ├── GET    /api/integrations/{type}          (list)     │
│  ├── POST   /api/integrations/{type}          (create)   │
│  ├── GET    /api/integrations/{type}/{id}     (get)      │
│  ├── PATCH  /api/integrations/{type}/{id}     (update)   │
│  ├── DELETE /api/integrations/{type}/{id}     (delete)   │
│  └── POST   /api/integrations/{type}/{id}/test (test)   │
├─────────────────────────────────────────────────────────┤
│                  Service Layer                            │
│  services/integrations.py                                 │
│  ├── GitlabInstanceService                                │
│  ├── HarborInstanceService                                │
│  ├── GithubInstanceService                                │
│  ├── DockerRegistryInstanceService                        │
│  └── HelmRepositoryInstanceService                        │
├─────────────────────────────────────────────────────────┤
│                   Data Layer                              │
│  models/{type}_instance.py — SQLAlchemy models            │
│  core/secrets.py — Fernet encryption                     │
└─────────────────────────────────────────────────────────┘
```

### Модели данных

Все модели следуют единому паттерну с общими полями:

| Поле | Тип | Назначение |
|------|-----|------------|
| `id` | `Integer` | Первичный ключ |
| `name` | `String(255)` | Уникальное человекочитаемое имя |
| `url` | `String(512)` | URL инстанса (кроме GitHub — API всегда `api.github.com`) |
| `token` / `password` | `Text` | Fernet-зашифрованные креденшелы |
| `username` | `String(255)` | Имя пользователя (Harbor, Docker Registry, Helm) |
| `is_active` | `Boolean` | Включена ли интеграция |
| `is_default` | `Boolean` | Использовать по умолчанию |
| `verify_ssl` | `Boolean` | Проверять SSL сертификат |
| `status_flag` | `Integer` | 0=OK, 1=Failed, 2=Warning, 3=In Progress, 4=Pending |
| `status_text` | `String(255)` | Человекочитаемый статус |
| `last_checked_at` | `DateTime` | Последняя проверка соединения |
| `created_at` / `updated_at` | `DateTime` | Временные метки |

#### GitLab Instance (`gitlab_instances`)

Дополнительные поля:
- `default_group_id` (`Integer`, nullable) — ID группы GitLab по умолчанию

**Проверка соединения**: `GET {url}/api/v4/version` с заголовком `PRIVATE-TOKEN`

#### Harbor Instance (`harbor_instances`)

Дополнительные поля:
- `default_project` (`String(255)`, nullable) — проект Harbor по умолчанию

**Проверка соединения**: `GET {url}/api/v2.0/ping` с HTTP Basic Auth

#### GitHub Instance (`github_instances`)

Без поля `url` — API эндпоинт всегда `https://api.github.com`.

**Проверка соединения**: `GET https://api.github.com/user` с заголовком `Authorization: Bearer {token}`

#### Docker Registry Instance (`docker_registry_instances`)

**Проверка соединения**: `GET {url}/v2/` с HTTP Basic Auth (опционально)

#### Helm Repository Instance (`helm_repository_instances`)

**Проверка соединения**: `GET {url}/index.yaml` с HTTP Basic Auth (опционально)

## Безопасность

### Шифрование креденшелов

Все токены и пароли шифруются с помощью **Fernet** (AES-128-CBC + HMAC-SHA256) перед сохранением в базу данных:

```python
from app.core.secrets import encrypt_secret, decrypt_secret

# При создании/обновлении — автоматически в сервисном слое
instance.token = encrypt_secret(plaintext_token) if plaintext_token else None

# При чтении — расшифровывается только в сервисном слое
token = decrypt_secret(instance.token)
```

**Ключевые правила**:
- Креденшелы **никогда не возвращаются** в API ответах (Pydantic `Out` схемы исключают поля `token`/`password`)
- Ключ шифрования хранится в `ENCRYPTION_KEY` (переменная окружения)
- Пустые/None значения не шифруются

### RBAC

Доступ к управлению интеграциями контролируется через permissions:

| Действие | Permission |
|----------|------------|
| Управление GitLab, Harbor, GitHub | `integrations:manage` |
| Управление Docker Registry | `docker_registry:manage` |
| Управление Helm Repository | `helm_repository:manage` |

Все эндпоинты защищены через `require_permission()` dependency.

## API Reference

### Общий паттерн эндпоинтов

Каждый тип интеграции предоставляет одинаковый набор эндпоинтов:

```
GET    /api/integrations/{type}              # Список всех инстансов
POST   /api/integrations/{type}              # Создать новый инстанс
GET    /api/integrations/{type}/{id}         # Получить инстанс по ID
PATCH  /api/integrations/{type}/{id}         # Частичное обновление
DELETE /api/integrations/{type}/{id}         # Удалить инстанс
POST   /api/integrations/{type}/{id}/test    # Проверить соединение
```

Где `{type}` — один из: `gitlab`, `harbor`, `github`, `docker-registry`, `helm-repository`.

### Примеры запросов

**Создание GitLab инстанса**:
```bash
curl -X POST http://localhost:8000/api/integrations/gitlab \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production GitLab",
    "url": "https://gitlab.example.com",
    "token": "glpat-abc123",
    "is_default": true,
    "group_id": 1
  }'
```

**Проверка соединения**:
```bash
curl -X POST http://localhost:8000/api/integrations/gitlab/1/test \
  -H "Authorization: Bearer $TOKEN"
```

Ответ:
```json
{
  "success": true,
  "message": "Connected successfully. GitLab version: 16.8.0-ee",
  "status_code": 200
}
```

## Инстансы по умолчанию

Сервисный слой предоставляет хелперы для получения инстанса по умолчанию каждого типа:

```python
from app.services.integrations import (
    get_default_gitlab_instance,
    get_default_github_instance,
    get_default_harbor_instance,
    get_default_docker_registry_instance,
    get_default_helm_repository_instance,
)

gitlab = await get_default_gitlab_instance(db)
```

Логика выбора: первый активный инстанс с `is_default=True`, иначе первый активный.

## Frontend

### Страница Settings > Integrations

Файл: [`frontend/src/pages/Settings/Integrations/index.tsx`](../../frontend/src/pages/Settings/Integrations/index.tsx)

**Структура**:
- 5 вкладок (Tabs): GitLab, Harbor, GitHub, Docker Registry, Helm Repository
- Каждая вкладка содержит:
  - Таблицу со списком инстансов (имя, URL, статус, действия)
  - Кнопку "Add" для открытия диалога создания/редактирования
  - Кнопки действий: Edit, Delete, Test Connection
- `PermissionGate` проверяет наличие соответствующих прав

**RTK Query хуки** (в [`frontend/src/store/api.ts`](../../frontend/src/store/api.ts)):
- `useGet{Type}InstancesQuery` — получение списка
- `useCreate{Type}InstanceMutation` — создание
- `useUpdate{Type}InstanceMutation` — обновление
- `useDelete{Type}InstanceMutation` — удаление
- `useTest{Type}ConnectionMutation` — проверка соединения

Все мутации инвалидируют тег `'Integration'` для автоматического обновления списка.

**Диалоги**:
- Валидация полей: имя (обязательно, 2-100 символов), URL (валидный формат)
- Поля токена/пароля опциональны при редактировании (пустое = не менять)
- Чекбоксы: Default, Active, Verify SSL

## Тестирование

### Backend unit-тесты

Файл: [`backend/tests/test_integrations.py`](../../backend/tests/test_integrations.py)

50 тестов (по 10 на каждый тип интеграции):
- CRUD операции с проверкой шифрования
- Обработка дубликатов (ConflictError)
- Обработка несуществующих инстансов (NotFoundError)
- Проверка соединения (успех / ошибка) с моком `httpx.AsyncClient`

### Backend e2e тесты

Файл: [`backend/tests/test_integrations_e2e.py`](../../backend/tests/test_integrations_e2e.py)

35 тестов (по 7 на каждый тип интеграции):
- Полный HTTP цикл (create → get → update → delete)
- Проверка соединения через API с моком httpx
- Проверка аутентификации (401) и авторизации (403)

### Frontend тесты

Файл: [`frontend/src/tests/Integrations.test.tsx`](../../frontend/src/tests/Integrations.test.tsx)

8 тестов:
- Рендеринг вкладок
- Отображение списка инстансов
- Диалог создания
- Диалог редактирования
- Подтверждение удаления
- Успешная проверка соединения
- Ошибка проверки соединения
- Permission Gate (отказ в доступе)

## Миграции

| Миграция | Описание |
|----------|----------|
| `20260606_2145_a66daaecc2fa` | Создание таблиц `gitlab_instances`, `harbor_instances`, `github_instances` |
| `20260607_0105_a1b2c3d4e5f6` | Добавление полей `is_default`, `is_active`, `verify_ssl` и др. |
| `20260606_2220_b0714dde902c` | Создание таблиц `docker_registry_instances`, `helm_repository_instances` |

## Связанные файлы

| Файл | Назначение |
|------|------------|
| [`backend/app/models/gitlab_instance.py`](../../backend/app/models/gitlab_instance.py) | Модель GitLab Instance |
| [`backend/app/models/harbor_instance.py`](../../backend/app/models/harbor_instance.py) | Модель Harbor Instance |
| [`backend/app/models/github_instance.py`](../../backend/app/models/github_instance.py) | Модель GitHub Instance |
| [`backend/app/models/docker_registry_instance.py`](../../backend/app/models/docker_registry_instance.py) | Модель Docker Registry Instance |
| [`backend/app/models/helm_repository_instance.py`](../../backend/app/models/helm_repository_instance.py) | Модель Helm Repository Instance |
| [`backend/app/services/integrations.py`](../../backend/app/services/integrations.py) | Сервисный слой (CRUD + connection testing) |
| [`backend/app/api/integrations.py`](../../backend/app/api/integrations.py) | REST API эндпоинты |
| [`backend/app/schemas/integrations.py`](../../backend/app/schemas/integrations.py) | Pydantic схемы |
| [`backend/app/core/secrets.py`](../../backend/app/core/secrets.py) | Fernet шифрование |
| [`backend/app/core/rbac.py`](../../backend/app/core/rbac.py) | RBAC permissions |
| [`frontend/src/pages/Settings/Integrations/index.tsx`](../../frontend/src/pages/Settings/Integrations/index.tsx) | Страница управления интеграциями |
| [`frontend/src/store/api.ts`](../../frontend/src/store/api.ts) | RTK Query хуки |
| [`backend/tests/test_integrations.py`](../../backend/tests/test_integrations.py) | Unit-тесты сервисов |
| [`backend/tests/test_integrations_e2e.py`](../../backend/tests/test_integrations_e2e.py) | E2E API тесты |
| [`frontend/src/tests/Integrations.test.tsx`](../../frontend/src/tests/Integrations.test.tsx) | Frontend тесты |
