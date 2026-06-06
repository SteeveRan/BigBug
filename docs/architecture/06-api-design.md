# 6. API Design

## Обзор

REST API построен на **FastAPI** с автоматической генерацией OpenAPI спецификации. Все endpoints следуют RESTful конвенциям и версионируются через префикс `/api/v1`.

## Принципы проектирования API

### Версионирование
- Использование префикса версии: `/api/v1/*`
- При breaking changes создается новая версия: `/api/v2/*`
- Старые версии поддерживаются минимум 6 месяцев

### Стандарты ответов

#### Успешный ответ
```json
{
  "id": 123,
  "name": "example",
  "created_at": "2026-06-06T12:00:00Z"
}
```

#### Список с пагинацией
```json
{
  "items": [...],
  "total": 150,
  "page": 1,
  "page_size": 20,
  "pages": 8
}
```

#### Ошибка
```json
{
  "detail": "Resource not found",
  "error_code": "NOT_FOUND",
  "timestamp": "2026-06-06T12:00:00Z"
}
```

## Структура API endpoints

### 1. Authentication (`/api/v1/auth`)

#### POST `/api/v1/auth/login`
Локальная аутентификация по email/password.

**Request:**
```json
{
  "email": "admin@example.com",
  "password": "secure_password"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "roles": ["admin"],
    "permissions": ["users:read", "users:write", ...]
  }
}
```

#### POST `/api/v1/auth/logout`
Отзыв токена (если используется refresh token).

**Headers:** `Authorization: Bearer <token>`

**Response (204 No Content)**

#### GET `/api/v1/auth/me`
Получение информации о текущем пользователе.

**Headers:** `Authorization: Bearer <token>`

**Response (200 OK):**
```json
{
  "id": 1,
  "username": "admin",
  "email": "admin@example.com",
  "roles": ["admin"],
  "permissions": ["users:read", "users:write", ...]
}
```

#### GET `/api/v1/auth/oidc/config`
Получение OIDC конфигурации (если настроена).

**Response (200 OK):**
```json
{
  "enabled": true,
  "authorization_url": "https://keycloak.example.com/realms/bigbug/protocol/openid-connect/auth",
  "client_id": "bigbug-frontend"
}
```

#### POST `/api/v1/auth/oidc/callback`
Обработка callback от OIDC провайдера.

**Request:**
```json
{
  "code": "authorization_code_from_keycloak",
  "state": "random_state_string"
}
```

**Response (200 OK):**
```json
{
  "access_token": "jwt_token",
  "token_type": "bearer",
  "user": { ... }
}
```

---

### 2. User Management (`/api/v1/admin/users`)

**Required permission:** `users:read`, `users:write`

#### GET `/api/v1/admin/users`
Список всех пользователей.

**Query params:**
- `page` (int, default=1)
- `page_size` (int, default=20)
- `search` (string, optional) - поиск по username/email

**Response (200 OK):**
```json
{
  "items": [
    {
      "id": 1,
      "username": "admin",
      "email": "admin@example.com",
      "is_active": true,
      "roles": ["admin"],
      "created_at": "2026-01-01T00:00:00Z"
    }
  ],
  "total": 5,
  "page": 1,
  "page_size": 20,
  "pages": 1
}
```

#### POST `/api/v1/admin/users`
Создание нового пользователя.

**Request:**
```json
{
  "username": "newuser",
  "email": "newuser@example.com",
  "password": "secure_password",
  "roles": ["viewer"]
}
```

**Response (201 Created):**
```json
{
  "id": 10,
  "username": "newuser",
  "email": "newuser@example.com",
  "is_active": true,
  "roles": ["viewer"]
}
```

#### GET `/api/v1/admin/users/{user_id}`
Получение информации о пользователе.

**Response (200 OK):**
```json
{
  "id": 10,
  "username": "newuser",
  "email": "newuser@example.com",
  "is_active": true,
  "roles": ["viewer"],
  "created_at": "2026-06-01T10:00:00Z",
  "keycloak_sub": null
}
```

#### PATCH `/api/v1/admin/users/{user_id}`
Обновление пользователя.

**Request:**
```json
{
  "email": "updated@example.com",
  "is_active": false,
  "roles": ["operator"]
}
```

**Response (200 OK):** обновленный пользователь

#### DELETE `/api/v1/admin/users/{user_id}`
Удаление пользователя.

**Response (204 No Content)**

---

### 3. Role Management (`/api/v1/admin/roles`)

**Required permission:** `roles:read`, `roles:write`

#### GET `/api/v1/admin/roles`
Список всех ролей.

**Response (200 OK):**
```json
{
  "items": [
    {
      "id": 1,
      "name": "admin",
      "description": "Full system access",
      "is_system": true,
      "permissions": ["users:read", "users:write", ...]
    }
  ]
}
```

#### POST `/api/v1/admin/roles`
Создание кастомной роли.

**Request:**
```json
{
  "name": "custom_operator",
  "description": "Custom operator role",
  "permissions": ["images:read", "images:build"]
}
```

**Response (201 Created):**
```json
{
  "id": 10,
  "name": "custom_operator",
  "description": "Custom operator role",
  "is_system": false,
  "permissions": ["images:read", "images:build"]
}
```

#### PATCH `/api/v1/admin/roles/{role_id}`
Обновление роли (только для кастомных).

#### DELETE `/api/v1/admin/roles/{role_id}`
Удаление роли (только для кастомных).

---

### 4. GitLab Integration (`/api/v1/admin/integrations/gitlab`)

**Required permission:** `integrations:gitlab:read`, `integrations:gitlab:write`

#### GET `/api/v1/admin/integrations/gitlab/instances`
Список GitLab инстансов.

**Response (200 OK):**
```json
{
  "items": [
    {
      "id": 1,
      "name": "Main GitLab",
      "url": "https://gitlab.example.com",
      "is_active": true,
      "created_at": "2026-01-01T00:00:00Z"
    }
  ]
}
```

#### POST `/api/v1/admin/integrations/gitlab/instances`
Добавление GitLab инстанса.

**Request:**
```json
{
  "name": "Main GitLab",
  "url": "https://gitlab.example.com",
  "token": "glpat-xxx",
  "verify_ssl": true
}
```

**Response (201 Created):**
```json
{
  "id": 1,
  "name": "Main GitLab",
  "url": "https://gitlab.example.com",
  "is_active": true
}
```

#### GET `/api/v1/admin/integrations/gitlab/instances/{instance_id}/groups`
Список групп в GitLab инстансе.

#### POST `/api/v1/admin/integrations/gitlab/instances/{instance_id}/projects/import`
Импорт проекта из GitLab.

**Request:**
```json
{
  "project_id": 123,
  "group_path": "mygroup/subgroup"
}
```

---

### 5. Harbor Integration (`/api/v1/admin/integrations/harbor`)

**Required permission:** `integrations:harbor:read`, `integrations:harbor:write`

#### GET `/api/v1/admin/integrations/harbor/instances`
Список Harbor инстансов.

#### POST `/api/v1/admin/integrations/harbor/instances`
Добавление Harbor инстанса.

**Request:**
```json
{
  "name": "Main Harbor",
  "url": "https://harbor.example.com",
  "username": "admin",
  "password": "Harbor12345",
  "verify_ssl": true
}
```

#### GET `/api/v1/admin/integrations/harbor/instances/{instance_id}/projects`
Список проектов в Harbor.

#### POST `/api/v1/admin/integrations/harbor/instances/{instance_id}/sync`
Запуск синхронизации артефактов.

**Request:**
```json
{
  "project_name": "library"
}
```

---

### 6. GitHub Integration (`/api/v1/admin/integrations/github`)

**Required permission:** `integrations:github:read`, `integrations:github:write`

#### GET `/api/v1/admin/integrations/github/instances`
Список GitHub интеграций.

#### POST `/api/v1/admin/integrations/github/instances`
Добавление GitHub интеграции.

**Request:**
```json
{
  "name": "GitHub Enterprise",
  "base_url": "https://github.example.com/api/v3",
  "token": "ghp_xxx"
}
```

#### POST `/api/v1/admin/integrations/github/instances/{instance_id}/projects/import`
Импорт GitHub репозитория.

**Request:**
```json
{
  "url": "https://github.com/org/repo"
}
```

---

### 7. Docker Registry Integration (`/api/v1/admin/integrations/docker-registry`)

**Required permission:** `integrations:docker:read`, `integrations:docker:write`

#### GET `/api/v1/admin/integrations/docker-registry/instances`
Список Docker Registry интеграций.

#### POST `/api/v1/admin/integrations/docker-registry/instances`
Добавление Docker Registry.

**Request:**
```json
{
  "name": "DockerHub",
  "url": "https://registry-1.docker.io",
  "username": "myuser",
  "password": "mypassword"
}
```

#### POST `/api/v1/admin/integrations/docker-registry/instances/{instance_id}/sources/import`
Импорт Docker образа.

**Request:**
```json
{
  "url": "docker.io/library/nginx"
}
```

---

### 8. Helm Repository Integration (`/api/v1/admin/integrations/helm-repository`)

**Required permission:** `integrations:helm:read`, `integrations:helm:write`

#### GET `/api/v1/admin/integrations/helm-repository/instances`
Список Helm Repository интеграций.

#### POST `/api/v1/admin/integrations/helm-repository/instances`
Добавление Helm Repository.

**Request:**
```json
{
  "name": "Bitnami",
  "url": "https://charts.bitnami.com/bitnami",
  "auth_type": "none"
}
```

#### POST `/api/v1/admin/integrations/helm-repository/instances/{instance_id}/sources/import`
Импорт Helm чарта.

**Request:**
```json
{
  "url": "https://charts.bitnami.com/bitnami",
  "chart_name": "nginx"
}
```

---

### 9. OIDC Configuration (`/api/v1/admin/auth/oidc`)

**Required permission:** `auth:oidc:read`, `auth:oidc:write`

#### GET `/api/v1/admin/auth/oidc/config`
Получение OIDC конфигурации.

**Response (200 OK):**
```json
{
  "enabled": true,
  "provider_url": "https://keycloak.example.com/realms/bigbug",
  "client_id": "bigbug",
  "role_mapping": {
    "bigbug-admin": "admin",
    "bigbug-operator": "operator"
  }
}
```

#### PUT `/api/v1/admin/auth/oidc/config`
Настройка OIDC.

**Request:**
```json
{
  "enabled": true,
  "provider_url": "https://keycloak.example.com/realms/bigbug",
  "client_id": "bigbug",
  "client_secret": "secret123",
  "role_claim_path": "realm_access.roles",
  "role_mapping": {
    "bigbug-admin": "admin"
  }
}
```

---

### 10. Pipelines (`/api/v1/pipelines`)

**Required permission:** `pipelines:read`, `pipelines:write`

#### GET `/api/v1/pipelines`
Список пайплайнов.

**Query params:**
- `type` (mirror|gold_image|app_image|helm_sync|docker_sync)
- `status` (pending|running|success|failed)
- `page`, `page_size`

**Response (200 OK):**
```json
{
  "items": [
    {
      "id": 1,
      "type": "mirror",
      "status": "success",
      "gitlab_instance_id": 1,
      "gitlab_pipeline_id": "12345",
      "started_at": "2026-06-06T10:00:00Z",
      "finished_at": "2026-06-06T10:05:00Z"
    }
  ],
  "total": 50,
  "page": 1,
  "page_size": 20
}
```

#### POST `/api/v1/pipelines/trigger`
Запуск пайплайна.

**Request:**
```json
{
  "type": "mirror",
  "mirror_id": 5
}
```

**Response (202 Accepted):**
```json
{
  "pipeline_id": 123,
  "status": "pending",
  "gitlab_pipeline_id": null
}
```

#### GET `/api/v1/pipelines/{pipeline_id}`
Статус пайплайна.

#### GET `/api/v1/pipelines/{pipeline_id}/logs`
Логи пайплайна.

**Response (200 OK):**
```json
{
  "logs": "Step 1: Cloning repository...\nStep 2: Building image...\n"
}
```

---

### 11. Gold Images (`/api/v1/builds/gold-images`)

**Required permission:** `images:gold:read`, `images:gold:write`

#### GET `/api/v1/builds/gold-images`
Список Gold образов.

#### POST `/api/v1/builds/gold-images`
Создание Gold образа.

**Request:**
```json
{
  "name": "ubuntu-22.04-base",
  "base_image": "ubuntu:22.04",
  "dockerfile": "FROM ubuntu:22.04\nRUN apt-get update..."
}
```

#### POST `/api/v1/builds/gold-images/{id}/build`
Запуск сборки.

---

### 12. App Images (`/api/v1/builds/app-images`)

**Required permission:** `images:app:read`, `images:app:write`

Аналогично Gold Images.

---

### 13. Git Mirroring (`/api/v1/mirroring`)

**Required permission:** `mirrors:read`, `mirrors:write`

#### GET `/api/v1/mirroring/mirrors`
Список зеркал.

#### POST `/api/v1/mirroring/mirrors/import`
Импорт существующего зеркала из GitLab.

**Request:**
```json
{
  "gitlab_instance_id": 1,
  "gitlab_url": "https://gitlab.example.com/mirrors/repo"
}
```

#### POST `/api/v1/mirroring/mirrors/{id}/sync`
Запуск синхронизации зеркала.

---

## Security

### Authentication
Все endpoints (кроме `/api/v1/auth/login` и `/api/v1/auth/oidc/*`) требуют JWT токен в заголовке:

```
Authorization: Bearer <jwt_token>
```

### Rate Limiting
- 100 requests/minute для аутентифицированных пользователей
- 10 requests/minute для анонимных запросов

### CORS
Настраивается в `main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## OpenAPI / Swagger

FastAPI автоматически генерирует OpenAPI спецификацию:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## Webhooks

### Incoming Webhooks

#### POST `/api/v1/webhooks/gitlab`
Webhook от GitLab для pipeline events.

**Headers:**
- `X-Gitlab-Token: <webhook_secret>`

**Body:** GitLab Pipeline Hook payload

#### POST `/api/v1/webhooks/harbor`
Webhook от Harbor для artifact events.

**Headers:**
- `Authorization: <webhook_secret>`

**Body:** Harbor Webhook payload

#### POST `/api/v1/webhooks/github`
Webhook от GitHub для push/release events.

**Headers:**
- `X-Hub-Signature-256: <hmac_signature>`

**Body:** GitHub Webhook payload

## Error Codes

| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| 400 | `INVALID_REQUEST` | Невалидный запрос |
| 401 | `UNAUTHORIZED` | Требуется аутентификация |
| 403 | `FORBIDDEN` | Недостаточно прав |
| 404 | `NOT_FOUND` | Ресурс не найден |
| 409 | `CONFLICT` | Конфликт (например, дубликат) |
| 422 | `VALIDATION_ERROR` | Ошибка валидации данных |
| 500 | `INTERNAL_ERROR` | Внутренняя ошибка сервера |
| 502 | `EXTERNAL_SERVICE_ERROR` | Ошибка внешнего сервиса |

## Примеры использования

### Python (httpx)
```python
import httpx

async with httpx.AsyncClient() as client:
    # Login
    response = await client.post(
        "http://localhost:8000/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin"}
    )
    token = response.json()["access_token"]
    
    # Get users
    response = await client.get(
        "http://localhost:8000/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token}"}
    )
    users = response.json()
```

### JavaScript (fetch)
```javascript
// Login
const loginResponse = await fetch('http://localhost:8000/api/v1/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: 'admin@example.com', password: 'admin' })
});
const { access_token } = await loginResponse.json();

// Get users
const usersResponse = await fetch('http://localhost:8000/api/v1/admin/users', {
  headers: { 'Authorization': `Bearer ${access_token}` }
});
const users = await usersResponse.json();
```

## Миграция API

При добавлении новых endpoints:
1. Добавить endpoint в соответствующий router (`app/api/*.py`)
2. Добавить Pydantic схемы в `app/schemas/*.py`
3. Обновить OpenAPI описание через docstrings
4. Добавить unit тесты в `tests/test_*.py`
5. Обновить эту документацию
