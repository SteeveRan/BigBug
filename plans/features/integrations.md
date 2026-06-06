# Integrations Guide

Руководство по управлению интеграциями в BigBug (GitLab, Harbor, GitHub, Docker Registry, Helm Repository).

## Текущее состояние

Сейчас интеграции настраиваются через переменные окружения (`.env`). В рамках рефакторинга (Phase 2) планируется переход на управляемые интеграции через Admin UI с поддержкой множественных инстансов.

## Текущие интеграции (через .env)

### GitLab

```bash
GITLAB_URL=http://localhost:8080
GITLAB_TOKEN=glpat-xyz123
GITLAB_GROUP_ID=1
```

Используется в:
- [`backend/app/services/gitlab.py`](../../backend/app/services/gitlab.py) — создание зеркал, триггер пайплайнов
- [`backend/app/api/mirrors.py`](../../backend/app/api/mirrors.py) — API для зеркал

### GitHub

```bash
GITHUB_TOKEN=ghp_xyz123
```

Используется в:
- [`backend/app/services/github.py`](../../backend/app/services/github.py) — получение организаций и репозиториев

### Harbor (опционально)

```bash
HARBOR_URL=https://harbor.local
HARBOR_USERNAME=admin
HARBOR_PASSWORD=Harbor12345
```

Используется для:
- Хранение Docker образов
- Security scanning

## Планируемые интеграции (Phase 2)

### Архитектура

Каждая интеграция — отдельная таблица с поддержкой множественных инстансов:

```
gitlab_instances     — множественные GitLab серверы
harbor_instances     — множественные Harbor реестры
github_configs       — GitHub конфигурации (токены)
docker_registries    — Docker Registry инстансы
helm_repositories    — Helm Repository инстансы
```

### Модели (планируемые)

#### GitLab Instance

```python
class GitLabInstance(Base):
    __tablename__ = "gitlab_instances"
    
    id: Mapped[int]
    name: Mapped[str]                    # "Production GitLab", "Dev GitLab"
    url: Mapped[str]                     # https://gitlab.example.com
    token_encrypted: Mapped[str]         # Зашифрованный API token
    
    # Конфигурация
    default_group_id: Mapped[int | None]
    verify_ssl: Mapped[bool]
    
    # Статус
    status_flag: Mapped[int]
    status_text: Mapped[str]
    last_checked_at: Mapped[datetime | None]
    
    is_default: Mapped[bool]             # Используется по умолчанию
    is_enabled: Mapped[bool]
```

#### Harbor Instance

```python
class HarborInstance(Base):
    __tablename__ = "harbor_instances"
    
    id: Mapped[int]
    name: Mapped[str]                    # "Production Harbor"
    url: Mapped[str]                     # https://harbor.example.com
    username: Mapped[str]
    password_encrypted: Mapped[str]
    
    # Конфигурация
    default_project: Mapped[str | None]  # Проект по умолчанию
    verify_ssl: Mapped[bool]
    
    # Статус
    status_flag: Mapped[int]
    last_checked_at: Mapped[datetime | None]
    
    is_default: Mapped[bool]
    is_enabled: Mapped[bool]
```

### API Endpoints (планируемые)

```
# GitLab Instances
GET    /api/settings/integrations/gitlab          # Список
POST   /api/settings/integrations/gitlab          # Добавить
GET    /api/settings/integrations/gitlab/{id}     # Детали
PATCH  /api/settings/integrations/gitlab/{id}     # Обновить
DELETE /api/settings/integrations/gitlab/{id}     # Удалить
POST   /api/settings/integrations/gitlab/{id}/test # Проверить подключение

# Harbor Instances
GET    /api/settings/integrations/harbor          # Список
POST   /api/settings/integrations/harbor          # Добавить
GET    /api/settings/integrations/harbor/{id}     # Детали
PATCH  /api/settings/integrations/harbor/{id}     # Обновить
DELETE /api/settings/integrations/harbor/{id}     # Удалить
POST   /api/settings/integrations/harbor/{id}/test # Проверить подключение
```

### Проверка подключения

```python
# app/services/integrations.py
class IntegrationService:
    async def test_gitlab_connection(self, instance: GitLabInstance) -> dict:
        """Test GitLab connection and return status"""
        token = decrypt_secret(instance.token_encrypted)
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{instance.url}/api/v4/user",
                    headers={"PRIVATE-TOKEN": token},
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    user = response.json()
                    return {
                        "status": "ok",
                        "message": f"Connected as {user['username']}",
                        "version": response.headers.get("X-Gitlab-Meta")
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"HTTP {response.status_code}: {response.text}"
                    }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
    
    async def test_harbor_connection(self, instance: HarborInstance) -> dict:
        """Test Harbor connection"""
        password = decrypt_secret(instance.password_encrypted)
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{instance.url}/api/v2.0/systeminfo",
                    auth=(instance.username, password),
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    info = response.json()
                    return {
                        "status": "ok",
                        "message": f"Harbor {info.get('harbor_version', 'unknown')}",
                        "version": info.get("harbor_version")
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"HTTP {response.status_code}"
                    }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
```

## Docker Registry Integration

### Текущая реализация

Docker Registry используется для синхронизации образов:

```python
# app/services/docker.py
class DockerService:
    async def get_tags(self, registry_url: str, image_name: str) -> list[str]:
        """Get available tags from Docker Registry"""
        ...
    
    async def sync_image(
        self,
        source_registry: str,
        source_image: str,
        target_registry: str,
        target_image: str,
        tag: str
    ) -> dict:
        """Sync image from source to target registry"""
        ...
```

### Docker Image Sources

```python
# app/models/docker_image_source.py
class DockerImageSource(Base):
    __tablename__ = "docker_image_sources"
    
    id: Mapped[int]
    name: Mapped[str]                    # nginx, python, etc.
    registry_url: Mapped[str]            # https://registry.hub.docker.com
    image_name: Mapped[str]              # library/nginx
    
    # Target
    target_registry_url: Mapped[str]     # harbor.local
    target_project: Mapped[str]          # docker-images
    
    # Status
    status_flag: Mapped[int]
    status_text: Mapped[str]
    last_synced_at: Mapped[datetime | None]
    
    tags: Mapped[list["DockerImageTag"]] = relationship(...)
```

## Helm Repository Integration

### Текущая реализация

```python
# app/services/helm.py
class HelmService:
    async def get_chart_versions(
        self,
        repo_url: str,
        chart_name: str
    ) -> list[dict]:
        """Get available versions from Helm repository"""
        # Скачать index.yaml
        # Парсить через ruamel.yaml
        ...
    
    async def sync_chart(
        self,
        source_repo: str,
        chart_name: str,
        version: str,
        target_repo: str
    ) -> dict:
        """Sync chart from source to target repository"""
        ...
```

### Helm Chart Sources

```python
# app/models/helm_chart_source.py
class HelmChartSource(Base):
    __tablename__ = "helm_chart_sources"
    
    id: Mapped[int]
    name: Mapped[str]                    # stable, bitnami, etc.
    repo_url: Mapped[str]                # https://charts.helm.sh/stable
    chart_name: Mapped[str]              # nginx, postgresql, etc.
    
    # Target
    target_repo_url: Mapped[str]         # https://harbor.local/chartrepo/charts
    
    # Status
    status_flag: Mapped[int]
    status_text: Mapped[str]
    last_synced_at: Mapped[datetime | None]
    
    versions: Mapped[list["HelmChartVersion"]] = relationship(...)
```

## Шифрование credentials

Все чувствительные данные шифруются через Fernet:

```python
from app.core.secrets import encrypt_secret, decrypt_secret

# Сохранить
instance.token_encrypted = encrypt_secret(gitlab_token)
await db.commit()

# Получить
token = decrypt_secret(instance.token_encrypted)
```

**Важно**: FERNET_KEY должен быть стабильным. Смена ключа требует перешифрования всех данных.

## Admin UI (планируется)

### Страница Integrations

```
Settings → Integrations
├── GitLab Instances
│   ├── [+ Add GitLab]
│   ├── Production GitLab (gitlab.example.com) ✓
│   └── Dev GitLab (localhost:8080) ✓
├── Harbor Instances
│   ├── [+ Add Harbor]
│   └── Production Harbor (harbor.example.com) ✓
├── GitHub
│   └── GitHub Token (configured) ✓
└── Docker Registries
    └── Docker Hub (registry.hub.docker.com) ✓
```

### Форма добавления GitLab

```typescript
interface GitLabInstanceForm {
  name: string;
  url: string;
  token: string;
  default_group_id?: number;
  verify_ssl: boolean;
  is_default: boolean;
}
```

## Troubleshooting

### GitLab API недоступен

```bash
# Проверить подключение
curl -H "PRIVATE-TOKEN: glpat-xyz" http://localhost:8080/api/v4/user

# Проверить токен
curl -H "PRIVATE-TOKEN: glpat-xyz" http://localhost:8080/api/v4/personal_access_tokens/self
```

### Harbor недоступен

```bash
# Проверить Harbor
curl -u admin:Harbor12345 https://harbor.local/api/v2.0/systeminfo

# Проверить SSL
curl -k -u admin:Harbor12345 https://harbor.local/api/v2.0/systeminfo
```

### Helm index.yaml не парсится

```bash
# Скачать и проверить
curl https://charts.helm.sh/stable/index.yaml | head -50

# Проверить ruamel.yaml
python -c "from ruamel.yaml import YAML; yaml = YAML(); print('OK')"
```

## Полезные ссылки

- [`backend/app/services/gitlab.py`](../../backend/app/services/gitlab.py)
- [`backend/app/services/github.py`](../../backend/app/services/github.py)
- [`backend/app/services/docker.py`](../../backend/app/services/docker.py)
- [`backend/app/services/helm.py`](../../backend/app/services/helm.py)
- [`backend/app/core/secrets.py`](../../backend/app/core/secrets.py)
- [`docs/architecture/04-integrations/`](../../docs/architecture/04-integrations/) — детальный дизайн интеграций
