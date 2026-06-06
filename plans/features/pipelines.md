# Pipelines Guide

Руководство по управлению GitLab CI/CD пайплайнами через BigBug UI.

## Назначение

BigBug предоставляет UI для:
- Просмотра и запуска GitLab пайплайнов
- Управления GitLab Components (переиспользуемые CI/CD блоки)
- Отслеживания истории запусков
- Получения webhook обратной связи от GitLab

## Статус

⏳ **Планируется** — функциональность в разработке.

Текущие CI/CD шаблоны в [`gitlab-ci/`](../../gitlab-ci/) используются напрямую GitLab Runner, без управления через BigBug UI.

## GitLab CI Templates

Существующие шаблоны в [`gitlab-ci/`](../../gitlab-ci/):

| Файл | Назначение |
|------|-----------|
| [`mirror-template.yml`](../../gitlab-ci/mirror-template.yml) | Синхронизация зеркал |
| [`gold-image-template.yml`](../../gitlab-ci/gold-image-template.yml) | Сборка Gold Images |
| [`app-image-template.yml`](../../gitlab-ci/app-image-template.yml) | Сборка App Images |
| [`helm-sync-template.yml`](../../gitlab-ci/helm-sync-template.yml) | Синхронизация Helm чартов |
| [`docker-sync-template.yml`](../../gitlab-ci/docker-sync-template.yml) | Синхронизация Docker образов |

## Планируемая архитектура

### Модели

#### Pipeline Run

```python
class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    
    id: Mapped[int]
    
    # GitLab info
    gitlab_instance_id: Mapped[int]      # Какой GitLab инстанс
    gitlab_project_id: Mapped[int]       # GitLab project ID
    gitlab_pipeline_id: Mapped[int]      # GitLab pipeline ID
    
    # Trigger info
    triggered_by_user_id: Mapped[int | None]
    trigger_type: Mapped[str]            # manual, scheduled, webhook
    
    # Pipeline params
    ref: Mapped[str]                     # branch, tag, commit
    variables: Mapped[dict | None]       # Pipeline variables (JSON)
    
    # Status
    status_flag: Mapped[int]             # 0=OK, 1=Failed, 3=Running, 4=Pending
    status_text: Mapped[str]             # success, failed, running, pending
    
    # Timestamps
    created_at: Mapped[datetime]
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    duration: Mapped[int | None]         # Секунды
    
    # Output
    web_url: Mapped[str | None]          # Ссылка на GitLab pipeline
```

#### GitLab Component

```python
class GitLabComponent(Base):
    __tablename__ = "gitlab_components"
    
    id: Mapped[int]
    name: Mapped[str]                    # "docker-build", "helm-deploy"
    description: Mapped[str | None]
    
    # Component location
    gitlab_instance_id: Mapped[int]
    project_path: Mapped[str]            # group/project
    component_path: Mapped[str]          # templates/docker-build
    
    # Version
    version: Mapped[str]                 # ~latest, 1.0.0
    
    # Input schema (JSON Schema)
    inputs_schema: Mapped[dict | None]
    
    is_enabled: Mapped[bool]
```

### API Endpoints (планируемые)

```
# Pipeline Runs
GET    /api/pipelines                   # История запусков
POST   /api/pipelines                   # Запустить пайплайн
GET    /api/pipelines/{id}              # Детали запуска
POST   /api/pipelines/{id}/cancel       # Отменить
POST   /api/pipelines/{id}/retry        # Повторить

# GitLab Components
GET    /api/components                  # Список компонентов
POST   /api/components                  # Добавить компонент
GET    /api/components/{id}             # Детали
PATCH  /api/components/{id}             # Обновить
DELETE /api/components/{id}             # Удалить
POST   /api/components/{id}/run         # Запустить компонент

# Webhooks
POST   /api/webhooks/gitlab             # GitLab webhook endpoint
```

### Запуск пайплайна

```python
# app/services/pipeline.py
class PipelineService:
    async def trigger_pipeline(
        self,
        gitlab_instance_id: int,
        project_id: int,
        ref: str,
        variables: dict | None = None,
        user_id: int | None = None
    ) -> PipelineRun:
        """Trigger GitLab pipeline and create PipelineRun record"""
        
        # Получить GitLab instance
        instance = await self.get_gitlab_instance(gitlab_instance_id)
        token = decrypt_secret(instance.token_encrypted)
        
        # Создать PipelineRun
        run = PipelineRun(
            gitlab_instance_id=gitlab_instance_id,
            gitlab_project_id=project_id,
            ref=ref,
            variables=variables,
            triggered_by_user_id=user_id,
            trigger_type="manual",
            status_flag=4,  # Pending
            status_text="pending",
            created_at=datetime.utcnow()
        )
        self.db.add(run)
        await self.db.commit()
        
        # Триггернуть в GitLab
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{instance.url}/api/v4/projects/{project_id}/pipeline",
                headers={"PRIVATE-TOKEN": token},
                json={
                    "ref": ref,
                    "variables": [
                        {"key": k, "value": v}
                        for k, v in (variables or {}).items()
                    ]
                }
            )
            
            pipeline = response.json()
            
            # Обновить с GitLab pipeline ID
            run.gitlab_pipeline_id = pipeline["id"]
            run.status_flag = 3  # In Progress
            run.status_text = "running"
            run.web_url = pipeline["web_url"]
            await self.db.commit()
        
        return run
```

### Webhook обработка

```python
# app/api/webhooks.py
@router.post("/gitlab")
async def gitlab_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Handle GitLab webhook events"""
    
    # Проверить X-Gitlab-Token
    token = request.headers.get("X-Gitlab-Token")
    if not verify_webhook_token(token):
        raise HTTPException(status_code=401, detail="Invalid webhook token")
    
    payload = await request.json()
    event_type = payload.get("object_kind")
    
    if event_type == "pipeline":
        await handle_pipeline_event(db, payload)
    elif event_type == "push":
        await handle_push_event(db, payload)
    elif event_type == "build":
        await handle_build_event(db, payload)
    
    return {"status": "ok"}

async def handle_pipeline_event(db: AsyncSession, payload: dict):
    """Update PipelineRun status from webhook"""
    pipeline_id = payload["object_attributes"]["id"]
    status = payload["object_attributes"]["status"]
    duration = payload["object_attributes"].get("duration")
    
    # Найти PipelineRun
    run = await get_pipeline_run_by_gitlab_id(db, pipeline_id)
    if not run:
        return
    
    # Маппинг статусов GitLab → BigBug
    status_map = {
        "success": (0, "success"),
        "failed": (1, "failed"),
        "running": (3, "running"),
        "pending": (4, "pending"),
        "canceled": (1, "canceled"),
        "skipped": (2, "skipped"),
    }
    
    flag, text = status_map.get(status, (1, status))
    run.status_flag = flag
    run.status_text = text
    
    if duration:
        run.duration = duration
    
    if status in ("success", "failed", "canceled"):
        run.finished_at = datetime.utcnow()
    
    await db.commit()
```

## GitLab Components

GitLab Components — переиспользуемые CI/CD блоки (GitLab 16+):

```yaml
# Пример использования компонента в .gitlab-ci.yml
include:
  - component: gitlab.example.com/bigbug/components/docker-build@1.0.0
    inputs:
      image_name: my-app
      dockerfile: ./Dockerfile
      registry: harbor.local
```

### Создание компонента

```yaml
# В репозитории bigbug/components
# templates/docker-build.yml

spec:
  inputs:
    image_name:
      description: "Docker image name"
    dockerfile:
      description: "Path to Dockerfile"
      default: "./Dockerfile"
    registry:
      description: "Target registry URL"

---
docker-build:
  stage: build
  image: docker:latest
  services:
    - docker:dind
  script:
    - docker build -f $[[ inputs.dockerfile ]] -t $[[ inputs.registry ]]/$[[ inputs.image_name ]]:$CI_COMMIT_SHORT_SHA .
    - docker push $[[ inputs.registry ]]/$[[ inputs.image_name ]]:$CI_COMMIT_SHORT_SHA
```

## Frontend (планируется)

### Pipelines страница

```
Pipelines
├── [+ Run Pipeline]
├── Filter: [All] [Running] [Success] [Failed]
│
├── #1234 | backend | main | ✓ success | 2m 30s | 5 min ago
├── #1233 | frontend | v1.0.0 | ✗ failed | 1m 15s | 1 hour ago
└── #1232 | worker | develop | ⟳ running | ... | just now
```

### Components страница

```
Settings → Pipelines → Components
├── [+ Add Component]
│
├── docker-build (gitlab.example.com/bigbug/components/docker-build@1.0.0)
│   └── [Run] [Edit] [Delete]
├── helm-deploy (gitlab.example.com/bigbug/components/helm-deploy@latest)
│   └── [Run] [Edit] [Delete]
└── security-scan (gitlab.example.com/bigbug/components/security-scan@2.0.0)
    └── [Run] [Edit] [Delete]
```

## Webhook Configuration

### Настройка в GitLab

```bash
# Добавить webhook в GitLab project
curl -X POST \
  -H "PRIVATE-TOKEN: glpat-xyz" \
  "http://localhost:8080/api/v4/projects/1/hooks" \
  -d "url=http://bigbug-backend:8000/api/webhooks/gitlab" \
  -d "pipeline_events=true" \
  -d "push_events=true" \
  -d "token=your-webhook-secret"
```

### Переменная окружения

```bash
GITLAB_WEBHOOK_SECRET=your-webhook-secret
```

## Полезные ссылки

- [`backend/app/api/webhooks.py`](../../backend/app/api/webhooks.py)
- [`gitlab-ci/`](../../gitlab-ci/) — CI/CD шаблоны
- [`docs/architecture/08-pipelines.md`](../../docs/architecture/08-pipelines.md) — детальный дизайн
- [GitLab Pipeline API](https://docs.gitlab.com/ee/api/pipelines.html)
- [GitLab Components](https://docs.gitlab.com/ee/ci/components/)
- [GitLab Webhooks](https://docs.gitlab.com/ee/user/project/integrations/webhooks.html)
