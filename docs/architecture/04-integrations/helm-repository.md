# Helm Repository Integration

## Обзор

Helm Chart Repository интеграция для работы с:
- HTTP-based Helm repositories
- ChartMuseum
- Harbor (как Helm registry)
- Artifact Hub

## API Research

### Аутентификация

Helm repositories поддерживают:

| Метод | Применение |
|-------|-----------|------------|
| Anonymous | Публичные репозитории |
| Basic Auth | `Authorization: Basic <base64>` |
| Bearer Token | Некоторые ChartMuseum инсталляции |

### Repository Structure

Helm repository - это HTTP сервер со специальной структурой:

```
https://charts.example.com/
├── index.yaml           # Основной индекс
├── chart-name-1.0.0.tgz
├── chart-name-1.0.1.tgz
└── chart-name-2.0.0.tgz
```

### index.yaml Structure

```yaml
apiVersion: v1
entries:
  chart-name:
    - name: chart-name
      version: 1.0.0
      appVersion: "1.0"
      description: "Chart description"
      created: 2024-01-01T00:00:00Z
      digest: sha256:abc123...
      urls:
        - https://charts.example.com/chart-name-1.0.0.tgz
      maintainers:
        - name: "Maintainer Name"
          email: "maintainer@example.com"
    - name: chart-name
      version: 1.0.1
      # ...
```

### Key Endpoints

```http
# Получить index.yaml
GET /index.yaml
Response: YAML файл со всеми charts

# Скачать chart
GET /<chart-name>-<version>.tgz
Response: Binary .tgz файл
```

### ChartMuseum API (опционально)

ChartMuseum предоставляет дополнительное API:

```http
# Список charts
GET /api/charts
Response: {
  "chart-name": [
    {
      "name": "chart-name",
      "version": "1.0.0",
      "description": "...",
      "apiVersion": "v2",
      "appVersion": "1.0",
      "created": "2024-01-01T00:00:00Z",
      "digest": "sha256:...",
      "urls": ["charts/chart-name-1.0.0.tgz"]
    }
  ]
}

# Детали конкретного chart
GET /api/charts/<name>/<version>

# Загрузка chart (если есть права)
POST /api/charts
Content-Type: multipart/form-data
Body: chart .tgz file
```

## Database Schema

```sql
-- Таблица уже существует: helm_chart_sources
-- Расширить для поддержки множественных инстансов

CREATE TABLE helm_repository_integrations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    repo_url VARCHAR(500) NOT NULL,       -- https://charts.example.com
    
    -- Аутентификация
    auth_type VARCHAR(50) DEFAULT 'anonymous', -- anonymous, basic, bearer
    username VARCHAR(255),
    password_encrypted TEXT,
    token_encrypted TEXT,
    
    -- Тип репозитория
    repo_type VARCHAR(50) DEFAULT 'helm',  -- helm, chartmuseum, harbor
    
    -- ChartMuseum API (если доступно)
    has_api BOOLEAN DEFAULT FALSE,
    api_url VARCHAR(500),                  -- https://charts.example.com/api
    
    -- Метаданные
    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,
    
    -- Статус
    last_health_check TIMESTAMPTZ,
    health_status VARCHAR(50),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Связать существующие helm_chart_sources с интеграциями
ALTER TABLE helm_chart_sources ADD COLUMN integration_id INTEGER 
    REFERENCES helm_repository_integrations(id) ON DELETE CASCADE;
```

## Service Architecture

```python
class HelmRepositoryService:
    """Работа с Helm repository."""
    
    async def fetch_index(
        self,
        integration: HelmRepositoryIntegration
    ) -> dict:
        """Получить index.yaml."""
        client = self._get_client(integration)
        
        index_url = f"{integration.repo_url.rstrip('/')}/index.yaml"
        response = await client.get(index_url)
        
        # Parse YAML
        import yaml
        index_data = yaml.safe_load(response.text)
        
        return index_data
    
    async def sync_charts(
        self,
        integration: HelmRepositoryIntegration,
        db: AsyncSession
    ):
        """Синхронизировать charts из репозитория."""
        index = await self.fetch_index(integration)
        
        entries = index.get("entries", {})
        
        for chart_name, versions in entries.items():
            for version_data in versions:
                # Upsert chart version
                await self._upsert_chart_version(
                    integration.id,
                    chart_name,
                    version_data,
                    db
                )
        
        await db.commit()
    
    async def download_chart(
        self,
        integration: HelmRepositoryIntegration,
        chart_name: str,
        version: str,
        dest_path: str
    ):
        """Скачать chart .tgz файл."""
        client = self._get_client(integration)
        
        # Get chart URL from index
        index = await self.fetch_index(integration)
        chart_data = self._find_chart_in_index(index, chart_name, version)
        
        chart_url = chart_data["urls"][0]
        if not chart_url.startswith("http"):
            # Relative URL
            chart_url = f"{integration.repo_url.rstrip('/')}/{chart_url}"
        
        # Download
        response = await client.get(chart_url)
        
        with open(dest_path, "wb") as f:
            f.write(response.content)
    
    def _get_client(
        self,
        integration: HelmRepositoryIntegration
    ) -> httpx.AsyncClient:
        """Создать HTTP клиент с аутентификацией."""
        
        if integration.auth_type == "anonymous":
            return httpx.AsyncClient()
        
        if integration.auth_type == "basic":
            password = decrypt(integration.password_encrypted)
            auth = (integration.username, password)
            return httpx.AsyncClient(auth=auth)
        
        if integration.auth_type == "bearer":
            token = decrypt(integration.token_encrypted)
            headers = {"Authorization": f"Bearer {token}"}
            return httpx.AsyncClient(headers=headers)


class ChartMuseumService(HelmRepositoryService):
    """Расширенная работа с ChartMuseum API."""
    
    async def list_charts_via_api(
        self,
        integration: HelmRepositoryIntegration
    ) -> dict:
        """Получить список charts через API (быстрее чем index.yaml)."""
        if not integration.has_api:
            raise ValueError("Integration does not have ChartMuseum API")
        
        client = self._get_client(integration)
        response = await client.get(f"{integration.api_url}/charts")
        
        return response.json()
    
    async def upload_chart(
        self,
        integration: HelmRepositoryIntegration,
        chart_path: str
    ):
        """Загрузить chart в ChartMuseum."""
        if not integration.has_api:
            raise ValueError("Integration does not have ChartMuseum API")
        
        client = self._get_client(integration)
        
        with open(chart_path, "rb") as f:
            files = {"chart": (os.path.basename(chart_path), f, "application/gzip")}
            response = await client.post(
                f"{integration.api_url}/charts",
                files=files
            )
        
        return response.json()
```

## Популярные Helm Repositories

### Bitnami

```yaml
repo_url: https://charts.bitnami.com/bitnami
auth_type: anonymous
repo_type: helm
```

### Artifact Hub

```yaml
repo_url: https://artifacthub.io/packages/helm/<repo-name>
auth_type: anonymous
repo_type: helm
```

### Harbor as Helm Repository

```yaml
repo_url: https://harbor.example.com/chartrepo/<project-name>
auth_type: basic
username: <harbor-username>
password: <harbor-password>
repo_type: harbor
```

### Private ChartMuseum

```yaml
repo_url: https://charts.private.com
auth_type: basic
username: <username>
password: <password>
repo_type: chartmuseum
has_api: true
api_url: https://charts.private.com/api
```

## Chart Version Schema

```sql
-- Расширить существующую таблицу helm_chart_versions
ALTER TABLE helm_chart_versions ADD COLUMN integration_id INTEGER 
    REFERENCES helm_repository_integrations(id) ON DELETE CASCADE;

-- Добавить индексы
CREATE INDEX idx_helm_chart_versions_integration 
    ON helm_chart_versions(integration_id);
```

## API Endpoints (BigBug)

```
GET    /api/v1/admin/integrations/helm-repository
POST   /api/v1/admin/integrations/helm-repository
GET    /api/v1/admin/integrations/helm-repository/:id
PUT    /api/v1/admin/integrations/helm-repository/:id
DELETE /api/v1/admin/integrations/helm-repository/:id
POST   /api/v1/admin/integrations/helm-repository/:id/test

GET    /api/v1/admin/integrations/helm-repository/:id/charts
POST   /api/v1/admin/integrations/helm-repository/:id/sync
GET    /api/v1/admin/integrations/helm-repository/:id/charts/:name/versions
```

## Best Practices

1. **Index Caching**: Кешировать index.yaml (обновлять по расписанию)
2. **Partial Updates**: Проверять изменения index.yaml перед полной синхронизацией
3. **Chart Verification**: Проверять digest/checksum при скачивании
4. **Connection Timeout**: Устанавливать таймауты для HTTP запросов
5. **Large Repositories**: Использовать ChartMuseum API для больших репозиториев
