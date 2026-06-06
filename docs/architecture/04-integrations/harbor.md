# Harbor Integration

## Обзор

Harbor интеграция обеспечивает:
- Docker registry с дополнительными возможностями
- Управление проектами и репозиториями
- Репликация образов
- Vulnerability scanning
- Webhook интеграция
- RBAC на уровне Harbor

## API Research

### Аутентификация

Harbor API v2.0 поддерживает:

| Метод | Заголовок | Применение |
|-------|-----------|------------|
| Basic Auth | `Authorization: Basic <base64>` | username:password |
| Bearer Token | `Authorization: Bearer <token>` | Robot account token |
| Cookie | `Cookie: sid=...` | Session ID |

**Рекомендуемый метод**: Robot Account Token с ограниченными правами.

**Robot Account Permissions**:
- `push` - загрузка образов
- `pull` - скачивание образов
- `delete` - удаление образов
- `read` - чтение метаданных

### Base URL

```
https://harbor.example.com/api/v2.0
```

### Ключевые Endpoints

#### Projects

```http
# Список проектов
GET /api/v2.0/projects
Query params: name, public, page, page_size

# Создание проекта
POST /api/v2.0/projects
{
  "project_name": "my-project",
  "public": false,
  "storage_limit": -1,
  "metadata": {
    "auto_scan": "true",
    "severity": "critical"
  }
}

# Детали проекта
GET /api/v2.0/projects/:project_name_or_id

# Удаление проекта
DELETE /api/v2.0/projects/:project_name_or_id
```

#### Repositories & Artifacts

```http
# Список репозиториев в проекте
GET /api/v2.0/projects/:project_name/repositories
Response: [
  {
    "name": "my-project/my-app",
    "artifact_count": 10,
    "pull_count": 150,
    "creation_time": "2024-01-01T00:00:00Z",
    "update_time": "2024-01-10T00:00:00Z"
  }
]

# Список artifacts (tags)
GET /api/v2.0/projects/:project_name/repositories/:repository_name/artifacts
Query params: page, page_size, with_tag, with_scan_overview

Response: [
  {
    "digest": "sha256:abc123...",
    "tags": [{"name": "v1.0.0", "push_time": "..."}],
    "size": 123456789,
    "scan_overview": {
      "severity": "High",
      "summary": {"total": 5, "critical": 1, "high": 2}
    }
  }
]

# Детали artifact
GET /api/v2.0/projects/:project_name/repositories/:repository_name/artifacts/:reference

# Удаление artifact
DELETE /api/v2.0/projects/:project_name/repositories/:repository_name/artifacts/:reference
```

#### Replication

```http
# Создание replication policy
POST /api/v2.0/replication/policies
{
  "name": "replicate-to-prod",
  "description": "Sync to production Harbor",
  "src_registry": {
    "id": 1
  },
  "dest_registry": {
    "id": 2
  },
  "dest_namespace": "prod-project",
  "trigger": {
    "type": "manual"  # or "scheduled", "event_based"
  },
  "filters": [
    {
      "type": "name",
      "value": "my-app"
    },
    {
      "type": "tag",
      "value": "v*"
    }
  ]
}

# Запуск репликации
POST /api/v2.0/replication/executions
{
  "policy_id": 1
}

# Статус репликации
GET /api/v2.0/replication/executions/:id
```

#### Vulnerability Scanning

```http
# Запуск сканирования
POST /api/v2.0/projects/:project_name/repositories/:repository_name/artifacts/:reference/scan

# Результаты сканирования
GET /api/v2.0/projects/:project_name/repositories/:repository_name/artifacts/:reference/additions/vulnerabilities

Response: {
  "vulnerabilities": [
    {
      "id": "CVE-2024-1234",
      "severity": "Critical",
      "package": "openssl",
      "version": "1.0.2",
      "fix_version": "1.1.1",
      "description": "Buffer overflow vulnerability"
    }
  ]
}
```

#### Webhooks

```http
# Создание webhook
POST /api/v2.0/projects/:project_name/webhook/policies
{
  "name": "notify-on-push",
  "description": "Notify BigBug on image push",
  "project_id": 1,
  "targets": [
    {
      "type": "http",
      "address": "https://bigbug.example.com/api/v1/webhooks/harbor",
      "auth_header": "Bearer webhook-token"
    }
  ],
  "event_types": [
    "PUSH_ARTIFACT",
    "DELETE_ARTIFACT",
    "SCANNING_COMPLETED"
  ],
  "enabled": true
}
```

### Webhook Payload

#### Push Artifact

```json
{
  "type": "PUSH_ARTIFACT",
  "occur_at": 1640000000,
  "operator": "admin",
  "event_data": {
    "resources": [
      {
        "digest": "sha256:abc123...",
        "tag": "v1.0.0",
        "resource_url": "harbor.example.com/my-project/my-app:v1.0.0"
      }
    ],
    "repository": {
      "name": "my-app",
      "namespace": "my-project",
      "repo_full_name": "my-project/my-app",
      "repo_type": "public"
    }
  }
}
```

#### Scanning Completed

```json
{
  "type": "SCANNING_COMPLETED",
  "occur_at": 1640000000,
  "operator": "auto",
  "event_data": {
    "resources": [
      {
        "digest": "sha256:abc123...",
        "resource_url": "harbor.example.com/my-project/my-app@sha256:abc123...",
        "scan_overview": {
          "application/vnd.security.vulnerability.report; version=1.1": {
            "report_id": "report-123",
            "scan_status": "Success",
            "severity": "Critical",
            "duration": 30,
            "summary": {
              "total": 10,
              "fixable": 5,
              "summary": {
                "Critical": 2,
                "High": 3,
                "Medium": 5
              }
            }
          }
        }
      }
    ]
  }
}
```

### Rate Limits

Harbor не имеет жестких rate limits на уровне API, но:
- Docker Registry API: зависит от настройки
- Рекомендуется: не более 100 req/sec
- Connection pooling обязателен

### Pagination

```http
GET /api/v2.0/projects?page=1&page_size=100
# Response headers:
X-Total-Count: 500
Link: <...>; rel="next", <...>; rel="prev"
```

## Database Schema

### Таблица `harbor_instances`

```sql
CREATE TABLE harbor_instances (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    url VARCHAR(500) NOT NULL,              -- https://harbor.example.com
    
    -- Аутентификация
    auth_type VARCHAR(50) DEFAULT 'robot',  -- robot, basic
    username VARCHAR(255),                  -- для basic auth
    password_encrypted TEXT,                -- зашифрованный
    robot_token_encrypted TEXT,             -- для robot account
    
    -- Метаданные
    version VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,
    
    -- Webhook
    webhook_secret_encrypted TEXT,
    
    -- Статус
    last_health_check TIMESTAMPTZ,
    health_status VARCHAR(50),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Таблица `harbor_projects`

```sql
CREATE TABLE harbor_projects (
    id SERIAL PRIMARY KEY,
    instance_id INTEGER NOT NULL REFERENCES harbor_instances(id) ON DELETE CASCADE,
    harbor_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    is_public BOOLEAN DEFAULT FALSE,
    
    -- Метаданные
    repo_count INTEGER DEFAULT 0,
    chart_count INTEGER DEFAULT 0,
    storage_limit BIGINT DEFAULT -1,
    
    -- Настройки безопасности
    auto_scan BOOLEAN DEFAULT TRUE,
    severity_threshold VARCHAR(50) DEFAULT 'critical',
    
    last_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(instance_id, harbor_id),
    UNIQUE(instance_id, name)
);
```

### Таблица `harbor_repositories`

```sql
CREATE TABLE harbor_repositories (
    id SERIAL PRIMARY KEY,
    instance_id INTEGER NOT NULL REFERENCES harbor_instances(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES harbor_projects(id) ON DELETE CASCADE,
    name VARCHAR(500) NOT NULL,         -- my-project/my-app
    artifact_count INTEGER DEFAULT 0,
    pull_count INTEGER DEFAULT 0,
    
    last_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(instance_id, name)
);
```

### Таблица `harbor_artifacts`

```sql
CREATE TABLE harbor_artifacts (
    id SERIAL PRIMARY KEY,
    repository_id INTEGER NOT NULL REFERENCES harbor_repositories(id) ON DELETE CASCADE,
    digest VARCHAR(255) NOT NULL,
    size_bytes BIGINT,
    push_time TIMESTAMPTZ,
    
    -- Tags (JSON array)
    tags JSONB DEFAULT '[]',            -- [{"name": "v1.0.0", "push_time": "..."}]
    
    -- Scan результаты
    scan_status VARCHAR(50),            -- Success, Failed, Pending
    scan_severity VARCHAR(50),          -- Critical, High, Medium, Low, None
    vulnerabilities_summary JSONB,      -- {"total": 10, "critical": 2, ...}
    last_scan_time TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(repository_id, digest)
);
```

## Service Architecture

```python
class HarborInstanceService:
    """Управление инстансами Harbor."""
    
    async def create_instance(
        self,
        data: HarborInstanceCreate,
        db: AsyncSession
    ) -> HarborInstance:
        """Создать новый Harbor инстанс."""
        # Проверить подключение
        await self._test_connection(data.url, data.robot_token or data.username, data.password)
        
        # Зашифровать credentials
        if data.robot_token:
            encrypted_token = encrypt(data.robot_token)
            instance = HarborInstance(
                name=data.name,
                url=data.url,
                auth_type='robot',
                robot_token_encrypted=encrypted_token
            )
        else:
            encrypted_password = encrypt(data.password)
            instance = HarborInstance(
                name=data.name,
                url=data.url,
                auth_type='basic',
                username=data.username,
                password_encrypted=encrypted_password
            )
        
        db.add(instance)
        await db.commit()
        return instance
    
    def _get_client(self, instance: HarborInstance) -> httpx.AsyncClient:
        """Создать HTTP клиент для Harbor API."""
        if instance.auth_type == 'robot':
            token = decrypt(instance.robot_token_encrypted)
            headers = {"Authorization": f"Bearer {token}"}
        else:
            password = decrypt(instance.password_encrypted)
            auth = (instance.username, password)
            return httpx.AsyncClient(base_url=f"{instance.url}/api/v2.0", auth=auth)
        
        return httpx.AsyncClient(
            base_url=f"{instance.url}/api/v2.0",
            headers=headers
        )


class HarborSyncService:
    """Синхронизация данных из Harbor."""
    
    async def sync_projects(
        self,
        instance: HarborInstance,
        db: AsyncSession
    ):
        """Синхронизировать проекты."""
        client = self._get_client(instance)
        
        response = await client.get("/projects", params={"page_size": 100})
        projects_data = response.json()
        
        for proj_data in projects_data:
            # Upsert project
            result = await db.execute(
                select(HarborProject).where(
                    HarborProject.instance_id == instance.id,
                    HarborProject.harbor_id == proj_data["project_id"]
                )
            )
            project = result.scalar_one_or_none()
            
            if not project:
                project = HarborProject(
                    instance_id=instance.id,
                    harbor_id=proj_data["project_id"]
                )
                db.add(project)
            
            project.name = proj_data["name"]
            project.is_public = proj_data["metadata"].get("public") == "true"
            project.repo_count = proj_data.get("repo_count", 0)
            project.last_synced_at = datetime.now(timezone.utc)
        
        await db.commit()
    
    async def sync_repository_artifacts(
        self,
        instance: HarborInstance,
        project_name: str,
        repository_name: str,
        db: AsyncSession
    ):
        """Синхронизировать artifacts репозитория."""
        client = self._get_client(instance)
        
        # Get artifacts
        url = f"/projects/{project_name}/repositories/{repository_name}/artifacts"
        response = await client.get(url, params={
            "page_size": 100,
            "with_tag": True,
            "with_scan_overview": True
        })
        
        artifacts_data = response.json()
        
        for art_data in artifacts_data:
            # Upsert artifact
            artifact = await self._upsert_artifact(
                repository_id,
                art_data,
                db
            )
        
        await db.commit()
```

## Webhook Processing

```python
@router.post("/webhooks/harbor/{instance_id}")
async def handle_harbor_webhook(
    instance_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    # Верификация токена из заголовка
    auth_header = request.headers.get("Authorization")
    instance = await get_instance(instance_id, db)
    
    if not verify_harbor_webhook(auth_header, instance.webhook_secret_encrypted):
        raise HTTPException(status_code=401)
    
    payload = await request.json()
    event_type = payload.get("type")
    
    match event_type:
        case "PUSH_ARTIFACT":
            await handle_push_artifact(payload, instance_id, db)
        case "SCANNING_COMPLETED":
            await handle_scan_completed(payload, instance_id, db)
        case "DELETE_ARTIFACT":
            await handle_delete_artifact(payload, instance_id, db)
    
    return {"status": "ok"}
```

## Replication Management

```python
class HarborReplicationService:
    """Управление репликацией."""
    
    async def create_replication_policy(
        self,
        instance: HarborInstance,
        data: ReplicationPolicyCreate,
        db: AsyncSession
    ):
        """Создать политику репликации."""
        client = self._get_client(instance)
        
        policy_data = {
            "name": data.name,
            "description": data.description,
            "src_registry": {"id": data.source_registry_id} if data.source_registry_id else None,
            "dest_registry": {"id": data.dest_registry_id},
            "dest_namespace": data.dest_namespace,
            "trigger": {"type": data.trigger_type},
            "filters": data.filters
        }
        
        response = await client.post("/replication/policies", json=policy_data)
        policy_id = response.headers.get("Location").split("/")[-1]
        
        return {"id": int(policy_id), "name": data.name}
    
    async def trigger_replication(
        self,
        instance: HarborInstance,
        policy_id: int
    ):
        """Запустить репликацию."""
        client = self._get_client(instance)
        
        response = await client.post(
            "/replication/executions",
            json={"policy_id": policy_id}
        )
        
        execution_id = response.headers.get("Location").split("/")[-1]
        return {"execution_id": int(execution_id)}
```

## API Endpoints (BigBug)

```
# Инстансы
GET    /api/v1/admin/integrations/harbor
POST   /api/v1/admin/integrations/harbor
GET    /api/v1/admin/integrations/harbor/:id
PUT    /api/v1/admin/integrations/harbor/:id
DELETE /api/v1/admin/integrations/harbor/:id
POST   /api/v1/admin/integrations/harbor/:id/test

# Проекты
GET    /api/v1/admin/integrations/harbor/:id/projects
POST   /api/v1/admin/integrations/harbor/:id/projects/sync

# Репозитории
GET    /api/v1/admin/integrations/harbor/:id/projects/:project/repositories
GET    /api/v1/admin/integrations/harbor/:id/projects/:project/repositories/:repo/artifacts

# Репликация
GET    /api/v1/admin/integrations/harbor/:id/replication/policies
POST   /api/v1/admin/integrations/harbor/:id/replication/policies
POST   /api/v1/admin/integrations/harbor/:id/replication/policies/:policy_id/execute
```

## Best Practices

1. **Robot Accounts**: Использовать robot accounts вместо user credentials
2. **Minimal Permissions**: Давать минимально необходимые права
3. **Auto Scanning**: Включать автоматическое сканирование уязвимостей
4. **Webhook Verification**: Всегда проверять webhook токены
5. **Connection Pooling**: Переиспользовать HTTP клиенты
6. **Retry Logic**: Обрабатывать временные ошибки с retry
