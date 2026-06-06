# GitLab Integration

## Обзор

GitLab интеграция обеспечивает:
- Управление группами, проектами, репозиториями
- Создание и управление CI/CD пайплайнами
- Управление переменными и secrets
- Создание GitLab Components
- Webhook обработка
- Поддержка нескольких инстансов

## API Research

### Аутентификация

GitLab поддерживает несколько методов:

| Метод | Заголовок | Применение |
|-------|-----------|------------|
| Personal Access Token | `PRIVATE-TOKEN: <token>` | Основной метод |
| Project Access Token | `PRIVATE-TOKEN: <token>` | Ограниченный scope |
| OAuth2 Token | `Authorization: Bearer <token>` | OAuth flow |
| Deploy Token | `DEPLOY-TOKEN: <token>` | CI/CD |

**Рекомендуемый метод**: Personal Access Token или Group Access Token с минимальными правами.

**Необходимые scopes**:
- `api` - полный доступ к API
- `read_api` - только чтение (для Viewer)
- `read_repository` - чтение репозиториев
- `write_repository` - запись в репозитории

### Ключевые Endpoints

#### Groups & Projects

```http
# Список групп
GET /api/v4/groups
GET /api/v4/groups/:id
GET /api/v4/groups/:id/subgroups
GET /api/v4/groups/:id/projects

# Создание группы
POST /api/v4/groups
{
  "name": "my-group",
  "path": "my-group",
  "visibility": "private"
}

# Проекты
GET /api/v4/projects
GET /api/v4/projects/:id
POST /api/v4/projects
{
  "name": "my-project",
  "namespace_id": 123,
  "visibility": "private",
  "initialize_with_readme": false
}

# Импорт проекта
POST /api/v4/projects
{
  "name": "mirrored-repo",
  "import_url": "https://github.com/org/repo.git"
}
```

#### Репозитории и файлы

```http
# Файлы
GET /api/v4/projects/:id/repository/files/:file_path?ref=main
PUT /api/v4/projects/:id/repository/files/:file_path
{
  "branch": "main",
  "content": "file content",
  "commit_message": "Update CI config"
}

# Ветки
GET /api/v4/projects/:id/repository/branches
POST /api/v4/projects/:id/repository/branches
{
  "branch": "feature/new-pipeline",
  "ref": "main"
}
```

#### CI/CD Pipelines

```http
# Список пайплайнов
GET /api/v4/projects/:id/pipelines
GET /api/v4/projects/:id/pipelines/:pipeline_id

# Запуск пайплайна
POST /api/v4/projects/:id/pipelines
{
  "ref": "main",
  "variables": [
    {"key": "MY_VAR", "value": "my_value"}
  ]
}

# Trigger token
POST /api/v4/projects/:id/trigger/pipeline
{
  "token": "trigger-token",
  "ref": "main",
  "variables": {}
}

# Jobs
GET /api/v4/projects/:id/jobs
GET /api/v4/projects/:id/pipelines/:pipeline_id/jobs
```

#### CI/CD Variables

```http
# Переменные проекта
GET /api/v4/projects/:id/variables
POST /api/v4/projects/:id/variables
{
  "key": "MY_SECRET",
  "value": "secret-value",
  "protected": true,
  "masked": true,
  "variable_type": "env_var"  # or "file"
}
PUT /api/v4/projects/:id/variables/:key
DELETE /api/v4/projects/:id/variables/:key

# Переменные группы
GET /api/v4/groups/:id/variables
POST /api/v4/groups/:id/variables
```

#### Webhooks

```http
# Создание webhook
POST /api/v4/projects/:id/hooks
{
  "url": "https://bigbug.example.com/api/v1/webhooks/gitlab",
  "push_events": true,
  "pipeline_events": true,
  "token": "webhook-secret-token",
  "enable_ssl_verification": true
}

# Список webhooks
GET /api/v4/projects/:id/hooks
DELETE /api/v4/projects/:id/hooks/:hook_id
```

### Webhook Payload Структуры

#### Pipeline Event

```json
{
  "object_kind": "pipeline",
  "object_attributes": {
    "id": 31,
    "ref": "main",
    "sha": "bcbb5ec396a2c0f828686f14fac9b80b780504f2",
    "status": "success",
    "created_at": "2023-01-01T00:00:00.000Z",
    "finished_at": "2023-01-01T00:05:00.000Z",
    "duration": 300,
    "variables": [
      {"key": "PIPELINE_TYPE", "value": "mirror_sync"}
    ]
  },
  "project": {
    "id": 1,
    "name": "my-project",
    "web_url": "https://gitlab.example.com/group/project"
  },
  "builds": [
    {
      "id": 380,
      "stage": "sync",
      "name": "mirror-sync",
      "status": "success",
      "duration": 290
    }
  ]
}
```

#### Push Event

```json
{
  "object_kind": "push",
  "ref": "refs/heads/main",
  "checkout_sha": "5937ac0a7beb003549fc5fd26055a0...",
  "project": {
    "id": 15,
    "name": "Diaspora",
    "web_url": "https://gitlab.example.com/mike/diaspora"
  },
  "commits": [
    {
      "id": "b6568db1bc1dcd7f8b4d5a946b0b91f9dacd7327",
      "message": "Update Catalan translation",
      "timestamp": "2011-12-12T14:27:31+02:00",
      "author": {"name": "Jordi Mallach", "email": "jordi@softcatala.org"}
    }
  ]
}
```

### Rate Limits

- **Default**: 2000 requests/min per user
- **Unauthenticated**: 500 requests/min per IP
- **Headers**: `RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-Reset`

### Pagination

```http
GET /api/v4/projects?page=1&per_page=100
# Response headers:
X-Total: 1000
X-Total-Pages: 10
X-Page: 1
X-Per-Page: 100
X-Next-Page: 2
X-Prev-Page: 
```

## Database Schema

### Таблица `gitlab_instances`

```sql
CREATE TABLE gitlab_instances (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,           -- "Production GitLab"
    url VARCHAR(500) NOT NULL,            -- https://gitlab.example.com
    token_encrypted TEXT NOT NULL,        -- зашифрованный PAT
    token_type VARCHAR(50) DEFAULT 'personal_access_token',
    
    -- Метаданные
    version VARCHAR(50),                  -- GitLab version
    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,     -- один default инстанс
    
    -- Webhook
    webhook_secret_encrypted TEXT,        -- для верификации webhooks
    
    -- Статус
    last_health_check TIMESTAMPTZ,
    health_status VARCHAR(50),            -- ok, error, unknown
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_gitlab_instances_default 
    ON gitlab_instances(is_default) WHERE is_default = TRUE;
```

### Таблица `gitlab_groups`

```sql
CREATE TABLE gitlab_groups (
    id SERIAL PRIMARY KEY,
    instance_id INTEGER NOT NULL REFERENCES gitlab_instances(id) ON DELETE CASCADE,
    gitlab_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    full_path VARCHAR(500) NOT NULL,
    description TEXT,
    visibility VARCHAR(50),
    parent_id INTEGER,                    -- для subgroups
    
    last_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(instance_id, gitlab_id)
);
```

### Таблица `gitlab_projects`

```sql
CREATE TABLE gitlab_projects (
    id SERIAL PRIMARY KEY,
    instance_id INTEGER NOT NULL REFERENCES gitlab_instances(id) ON DELETE CASCADE,
    group_id INTEGER REFERENCES gitlab_groups(id) ON DELETE SET NULL,
    gitlab_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    full_path VARCHAR(500) NOT NULL,
    description TEXT,
    web_url VARCHAR(500),
    default_branch VARCHAR(255) DEFAULT 'main',
    visibility VARCHAR(50),
    
    -- Тип использования
    project_type VARCHAR(50),             -- mirror, pipeline, component, build
    
    last_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(instance_id, gitlab_id)
);
```

## Service Architecture

```python
class GitLabInstanceService:
    """Управление инстансами GitLab."""
    
    async def create_instance(self, data: GitLabInstanceCreate, db: AsyncSession) -> GitLabInstance:
        """Создать новый инстанс GitLab."""
        # Проверить подключение
        await self._test_connection(data.url, data.token)
        
        # Зашифровать токен
        encrypted_token = encrypt(data.token)
        
        instance = GitLabInstance(
            name=data.name,
            url=data.url,
            token_encrypted=encrypted_token,
            is_default=data.is_default
        )
        db.add(instance)
        await db.commit()
        return instance
    
    async def test_connection(self, instance_id: int, db: AsyncSession) -> dict:
        """Проверить подключение к GitLab."""
        instance = await get_instance(instance_id, db)
        token = decrypt(instance.token_encrypted)
        
        gl = gitlab.Gitlab(instance.url, private_token=token)
        try:
            gl.auth()
            version = gl.version()
            return {"status": "ok", "version": version[0]}
        except gitlab.exceptions.GitlabAuthenticationError:
            return {"status": "error", "message": "Authentication failed"}
    
    def _get_client(self, instance: GitLabInstance) -> gitlab.Gitlab:
        token = decrypt(instance.token_encrypted)
        return gitlab.Gitlab(instance.url, private_token=token)


class GitLabPipelineService:
    """Управление CI/CD пайплайнами."""
    
    async def create_pipeline_project(
        self,
        instance: GitLabInstance,
        group_path: str,
        name: str,
        ci_config: str,
        db: AsyncSession
    ) -> GitLabProject:
        """Создать новый проект с CI/CD конфигурацией."""
        gl = self._get_client(instance)
        
        # Найти группу
        group = gl.groups.get(group_path)
        
        # Создать проект
        gl_project = gl.projects.create({
            "name": name,
            "namespace_id": group.id,
            "visibility": "private",
            "initialize_with_readme": False
        })
        
        # Загрузить .gitlab-ci.yml
        gl_project.files.create({
            "file_path": ".gitlab-ci.yml",
            "branch": "main",
            "content": ci_config,
            "commit_message": "Initial CI/CD configuration"
        })
        
        # Сохранить в БД
        project = GitLabProject(
            instance_id=instance.id,
            gitlab_id=gl_project.id,
            name=name,
            full_path=gl_project.path_with_namespace,
            web_url=gl_project.web_url,
            project_type="pipeline"
        )
        db.add(project)
        await db.commit()
        return project
    
    async def set_variable(
        self,
        instance: GitLabInstance,
        project_id: int,
        key: str,
        value: str,
        masked: bool = False,
        protected: bool = False
    ):
        """Установить переменную CI/CD."""
        gl = self._get_client(instance)
        gl_project = gl.projects.get(project_id)
        
        try:
            var = gl_project.variables.get(key)
            var.value = value
            var.masked = masked
            var.protected = protected
            var.save()
        except gitlab.exceptions.GitlabGetError:
            gl_project.variables.create({
                "key": key,
                "value": value,
                "masked": masked,
                "protected": protected
            })
```

## Webhook Processing

```python
@router.post("/webhooks/gitlab/{instance_id}")
async def handle_gitlab_webhook(
    instance_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    # Верификация подписи
    token = request.headers.get("X-Gitlab-Token")
    instance = await get_instance(instance_id, db)
    
    if not verify_webhook_token(token, instance.webhook_secret_encrypted):
        raise HTTPException(status_code=401, detail="Invalid webhook token")
    
    payload = await request.json()
    event_type = request.headers.get("X-Gitlab-Event")
    
    match event_type:
        case "Pipeline Hook":
            await handle_pipeline_event(payload, instance_id, db)
        case "Push Hook":
            await handle_push_event(payload, instance_id, db)
        case _:
            logger.debug(f"Unhandled GitLab event: {event_type}")
    
    return {"status": "ok"}
```

## GitLab Components

### Структура компонента

```yaml
# /infrastructure/gitlab-components/docker-build/template.yml
spec:
  inputs:
    image_name:
      description: "Docker image name"
    dockerfile_path:
      default: "Dockerfile"
    registry_url:
      description: "Target registry URL"

---
build-image:
  stage: build
  image: docker:24
  services:
    - docker:24-dind
  script:
    - docker build -t $[[ inputs.registry_url ]]/$[[ inputs.image_name ]] -f $[[ inputs.dockerfile_path ]] .
    - docker push $[[ inputs.registry_url ]]/$[[ inputs.image_name ]]
```

### Использование компонента

```yaml
# В .gitlab-ci.yml проекта
include:
  - component: gitlab.example.com/infrastructure/gitlab-components/docker-build@main
    inputs:
      image_name: my-app
      registry_url: harbor.example.com/my-project
```

## API Endpoints (BigBug)

```
# Инстансы
GET    /api/v1/admin/integrations/gitlab
POST   /api/v1/admin/integrations/gitlab
GET    /api/v1/admin/integrations/gitlab/:id
PUT    /api/v1/admin/integrations/gitlab/:id
DELETE /api/v1/admin/integrations/gitlab/:id
POST   /api/v1/admin/integrations/gitlab/:id/test

# Группы
GET    /api/v1/admin/integrations/gitlab/:id/groups
POST   /api/v1/admin/integrations/gitlab/:id/groups/sync

# Проекты
GET    /api/v1/admin/integrations/gitlab/:id/projects
POST   /api/v1/admin/integrations/gitlab/:id/projects

# Переменные
GET    /api/v1/admin/integrations/gitlab/:id/projects/:project_id/variables
POST   /api/v1/admin/integrations/gitlab/:id/projects/:project_id/variables
PUT    /api/v1/admin/integrations/gitlab/:id/projects/:project_id/variables/:key
DELETE /api/v1/admin/integrations/gitlab/:id/projects/:project_id/variables/:key
```

## Best Practices

1. **Token Rotation**: Регулярная ротация токенов
2. **Minimal Scopes**: Использовать минимально необходимые scopes
3. **Webhook Verification**: Всегда верифицировать webhook токены
4. **Rate Limit Handling**: Обрабатывать 429 с exponential backoff
5. **Connection Pooling**: Переиспользовать HTTP клиенты
6. **Error Handling**: Обрабатывать GitLab API ошибки gracefully
