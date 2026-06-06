# Docker Registry Integration

## Обзор

Docker Registry v2 API для работы с любыми совместимыми registry:
- Docker Hub
- Google Container Registry (GCR)
- Amazon ECR
- Azure Container Registry (ACR)
- Частные Docker Registry

## API Research

### Аутентификация

Docker Registry v2 поддерживает несколько методов:

| Метод | Применение |
|-------|------------|
| Basic Auth | Простая аутентификация username:password |
| Bearer Token | Token-based auth с отдельным auth server |
| Anonymous | Публичные registry (DockerHub public repos) |

### Token Authentication Flow

```
1. Client -> Registry: GET /v2/
2. Registry -> Client: 401 + WWW-Authenticate header
3. Client -> Auth Server: GET /token?service=registry&scope=...
4. Auth Server -> Client: {"token": "..."}
5. Client -> Registry: GET /v2/ + Authorization: Bearer <token>
```

### Base Endpoints

```http
# Проверка поддержки v2
GET /v2/
Response: 200 OK (if v2 supported)

# Список репозиториев
GET /v2/_catalog?n=100
Response: {
  "repositories": ["library/ubuntu", "my-org/my-app"]
}

# Список тегов
GET /v2/<name>/tags/list
Response: {
  "name": "my-org/my-app",
  "tags": ["latest", "v1.0.0", "v1.0.1"]
}

# Manifest (детали образа)
GET /v2/<name>/manifests/<reference>
Headers: Accept: application/vnd.docker.distribution.manifest.v2+json

Response: {
  "schemaVersion": 2,
  "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
  "config": {
    "digest": "sha256:abc123...",
    "size": 1234
  },
  "layers": [...]
}

# Digest из заголовка
Headers: Docker-Content-Digest: sha256:abc123...
```

### Blob/Layer Information

```http
# HEAD запрос для получения размера
HEAD /v2/<name>/blobs/<digest>
Headers: Content-Length: 123456789
```

## Database Schema

```sql
-- Таблица уже существует: docker_image_sources
-- Расширить для поддержки множественных инстансов

CREATE TABLE docker_registry_integrations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    registry_url VARCHAR(500) NOT NULL,    -- https://registry.example.com
    
    -- Аутентификация
    auth_type VARCHAR(50) DEFAULT 'basic', -- basic, bearer, anonymous
    username VARCHAR(255),
    password_encrypted TEXT,
    token_encrypted TEXT,                  -- для bearer auth
    
    -- Token auth server (если используется)
    auth_server_url VARCHAR(500),
    
    -- Метаданные
    registry_type VARCHAR(50),             -- dockerhub, gcr, ecr, acr, generic
    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,
    
    -- Статус
    last_health_check TIMESTAMPTZ,
    health_status VARCHAR(50),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Связать существующие docker_image_sources с интеграциями
ALTER TABLE docker_image_sources ADD COLUMN integration_id INTEGER 
    REFERENCES docker_registry_integrations(id) ON DELETE CASCADE;
```

## Service Architecture

```python
class DockerRegistryService:
    """Работа с Docker Registry API v2."""
    
    async def list_repositories(
        self,
        integration: DockerRegistryIntegration,
        page_size: int = 100
    ) -> List[str]:
        """Получить список репозиториев."""
        client = await self._get_authenticated_client(integration)
        
        response = await client.get(f"{integration.registry_url}/v2/_catalog", params={"n": page_size})
        data = response.json()
        return data.get("repositories", [])
    
    async def list_tags(
        self,
        integration: DockerRegistryIntegration,
        image_name: str
    ) -> List[str]:
        """Получить список тегов образа."""
        client = await self._get_authenticated_client(integration)
        
        response = await client.get(f"{integration.registry_url}/v2/{image_name}/tags/list")
        data = response.json()
        return data.get("tags", [])
    
    async def get_manifest(
        self,
        integration: DockerRegistryIntegration,
        image_name: str,
        tag: str
    ) -> dict:
        """Получить manifest образа."""
        client = await self._get_authenticated_client(integration)
        
        headers = {
            "Accept": "application/vnd.docker.distribution.manifest.v2+json"
        }
        
        response = await client.get(
            f"{integration.registry_url}/v2/{image_name}/manifests/{tag}",
            headers=headers
        )
        
        # Digest из заголовка
        digest = response.headers.get("Docker-Content-Digest")
        manifest = response.json()
        
        return {
            "digest": digest,
            "manifest": manifest
        }
    
    async def _get_authenticated_client(
        self,
        integration: DockerRegistryIntegration
    ) -> httpx.AsyncClient:
        """Создать аутентифицированный клиент."""
        
        if integration.auth_type == "anonymous":
            return httpx.AsyncClient()
        
        if integration.auth_type == "basic":
            password = decrypt(integration.password_encrypted)
            auth = (integration.username, password)
            return httpx.AsyncClient(auth=auth)
        
        if integration.auth_type == "bearer":
            # Token-based auth
            token = await self._get_bearer_token(integration)
            headers = {"Authorization": f"Bearer {token}"}
            return httpx.AsyncClient(headers=headers)
    
    async def _get_bearer_token(
        self,
        integration: DockerRegistryIntegration,
        scope: str = "registry:catalog:*"
    ) -> str:
        """Получить Bearer токен от auth server."""
        client = httpx.AsyncClient()
        
        params = {
            "service": "registry",
            "scope": scope
        }
        
        if integration.username:
            password = decrypt(integration.password_encrypted)
            auth = (integration.username, password)
            response = await client.get(
                integration.auth_server_url,
                params=params,
                auth=auth
            )
        else:
            response = await client.get(integration.auth_server_url, params=params)
        
        data = response.json()
        return data["token"]
```

## Популярные Registry настройки

### Docker Hub

```yaml
registry_url: https://registry-1.docker.io
auth_type: basic
auth_server_url: https://auth.docker.io/token
username: <dockerhub-username>
password: <dockerhub-password or token>
```

### Google Container Registry (GCR)

```yaml
registry_url: https://gcr.io
auth_type: basic
username: _json_key
password: <service-account-json>
```

### Amazon ECR

```yaml
registry_url: https://<account-id>.dkr.ecr.<region>.amazonaws.com
auth_type: basic
username: AWS
password: <ECR auth token from aws ecr get-login-password>
# Note: ECR tokens expire after 12 hours
```

### Azure Container Registry (ACR)

```yaml
registry_url: https://<registry-name>.azurecr.io
auth_type: basic
username: <username>
password: <password or service principal>
```

## API Endpoints (BigBug)

```
GET    /api/v1/admin/integrations/docker-registry
POST   /api/v1/admin/integrations/docker-registry
GET    /api/v1/admin/integrations/docker-registry/:id
PUT    /api/v1/admin/integrations/docker-registry/:id
DELETE /api/v1/admin/integrations/docker-registry/:id
POST   /api/v1/admin/integrations/docker-registry/:id/test

GET    /api/v1/admin/integrations/docker-registry/:id/repositories
GET    /api/v1/admin/integrations/docker-registry/:id/repositories/:image/tags
```

## Best Practices

1. **Token Caching**: Кешировать bearer tokens до истечения
2. **Connection Pooling**: Переиспользовать HTTP клиенты
3. **Retry Logic**: Обрабатывать 5xx ошибки с exponential backoff
4. **ECR Token Rotation**: Автоматическое обновление ECR токенов (12h TTL)
5. **Rate Limiting**: Соблюдать лимиты registry (если есть)
