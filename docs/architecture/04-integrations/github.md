# GitHub Integration

## Обзор

GitHub интеграция обеспечивает:
- API для организаций и репозиториев
- Releases и artifacts
- Webhook обработка
- Импорт репозиториев для зеркалирования

## API Research

### Аутентификация

| Метод | Заголовок | Применение |
|-------|-----------|------------|
| Personal Access Token | `Authorization: token <token>` | Основной метод |
| GitHub App | `Authorization: Bearer <jwt>` | App authentication |
| OAuth Token | `Authorization: Bearer <token>` | OAuth flow |

**Рекомендуемый**: Personal Access Token (classic) или Fine-grained PAT.

**Необходимые scopes** (classic):
- `repo` - доступ к репозиториям
- `read:org` - чтение организаций
- `read:user` - информация о пользователе

### Base URL

```
https://api.github.com
Accept: application/vnd.github+json
X-GitHub-Api-Version: 2022-11-28
```

### Ключевые Endpoints

#### Organizations & Repositories

```http
# Организации
GET /user/orgs
GET /orgs/:org

# Репозитории организации
GET /orgs/:org/repos?per_page=100&page=1

# Детали репозитория
GET /repos/:owner/:repo
Response: {
  "id": 123,
  "name": "my-repo",
  "full_name": "owner/my-repo",
  "description": "Description",
  "html_url": "https://github.com/owner/my-repo",
  "clone_url": "https://github.com/owner/my-repo.git",
  "default_branch": "main",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-10T00:00:00Z",
  "pushed_at": "2024-01-10T12:00:00Z",
  "archived": false,
  "fork": false
}

# README
GET /repos/:owner/:repo/readme
```

#### Releases

```http
# Список releases
GET /repos/:owner/:repo/releases?per_page=100

Response: [
  {
    "id": 456,
    "tag_name": "v1.0.0",
    "name": "Release 1.0.0",
    "body": "Release notes...",
    "draft": false,
    "prerelease": false,
    "created_at": "2024-01-01T00:00:00Z",
    "published_at": "2024-01-01T01:00:00Z",
    "assets": [
      {
        "name": "binary-linux-amd64",
        "browser_download_url": "https://github.com/.../releases/download/..."
      }
    ]
  }
]

# Детали release
GET /repos/:owner/:repo/releases/:release_id
GET /repos/:owner/:repo/releases/tags/:tag
```

#### Webhooks

```http
# Создание webhook
POST /repos/:owner/:repo/hooks
{
  "name": "web",
  "active": true,
  "events": ["push", "release"],
  "config": {
    "url": "https://bigbug.example.com/api/v1/webhooks/github",
    "content_type": "json",
    "secret": "webhook-secret",
    "insecure_ssl": "0"
  }
}

# Список webhooks
GET /repos/:owner/:repo/hooks
DELETE /repos/:owner/:repo/hooks/:hook_id
```

### Webhook Payloads

#### Push Event

```json
{
  "ref": "refs/heads/main",
  "repository": {
    "id": 123,
    "name": "my-repo",
    "full_name": "owner/my-repo",
    "html_url": "https://github.com/owner/my-repo"
  },
  "commits": [
    {
      "id": "abc123...",
      "message": "Update README",
      "timestamp": "2024-01-01T00:00:00Z",
      "author": {"name": "John Doe", "email": "john@example.com"}
    }
  ],
  "sender": {"login": "johndoe"}
}
```

#### Release Event

```json
{
  "action": "published",
  "release": {
    "id": 456,
    "tag_name": "v1.0.0",
    "name": "Release 1.0.0",
    "body": "Release notes",
    "published_at": "2024-01-01T00:00:00Z"
  },
  "repository": {
    "full_name": "owner/my-repo"
  }
}
```

### Rate Limits

- **Authenticated**: 5000 requests/hour
- **Unauthenticated**: 60 requests/hour
- **Headers**: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

### Pagination

```http
Link: <https://api.github.com/repos?page=2>; rel="next",
      <https://api.github.com/repos?page=5>; rel="last"
```

## Database Schema

```sql
-- Существующие таблицы используются
-- github_orgs, github_projects, github_releases
-- Добавить поле для связи с интеграцией

ALTER TABLE github_orgs ADD COLUMN integration_id INTEGER;
ALTER TABLE github_projects ADD COLUMN integration_id INTEGER;
```

### Новая таблица `github_integrations`

```sql
CREATE TABLE github_integrations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    token_encrypted TEXT NOT NULL,
    
    -- Метаданные
    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,
    
    -- Webhook
    webhook_secret_encrypted TEXT,
    
    -- Статус
    last_health_check TIMESTAMPTZ,
    health_status VARCHAR(50),
    rate_limit_remaining INTEGER,
    rate_limit_reset TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

## API Endpoints (BigBug)

```
GET    /api/v1/admin/integrations/github
POST   /api/v1/admin/integrations/github
GET    /api/v1/admin/integrations/github/:id
PUT    /api/v1/admin/integrations/github/:id
DELETE /api/v1/admin/integrations/github/:id
POST   /api/v1/admin/integrations/github/:id/test

GET    /api/v1/admin/integrations/github/:id/organizations
GET    /api/v1/admin/integrations/github/:id/repositories
```

## Best Practices

1. **Rate Limit Handling**: Отслеживать и соблюдать лимиты
2. **Webhook Signature**: Проверять HMAC подпись (X-Hub-Signature-256)
3. **Conditional Requests**: Использовать ETag для кеширования
4. **Minimal Scopes**: Давать минимальные необходимые права
