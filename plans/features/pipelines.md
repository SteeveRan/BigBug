# Pipelines Guide

Руководство по управлению GitLab CI/CD пайплайнами через BigBug UI.

## Назначение

BigBug предоставляет UI для:
- Просмотра и запуска GitLab пайплайнов
- Управления GitLab Components (переиспользуемые CI/CD блоки)
- Отслеживания истории запусков
- Получения webhook обратной связи от GitLab

## Статус

✅ **Реализовано** — полный цикл управления пайплайнами через BigBug UI.

### Реализованные компоненты

**Backend API:**
- `GET /api/pipelines` — история запусков
- `POST /api/pipelines` — запустить пайплайн
- `GET /api/pipelines/{id}` — детали запуска
- `POST /api/pipelines/{id}/cancel` — отменить
- `POST /api/pipelines/{id}/retry` — повторить
- `GET/POST/PATCH/DELETE /api/components` — CRUD GitLab Components
- `POST /api/webhooks/gitlab` — приём webhook-событий от GitLab

**Сервисный слой:** [`backend/app/services/pipeline.py`](../../backend/app/services/pipeline.py)

**Модель:** [`backend/app/models/pipeline_run.py`](../../backend/app/models/pipeline_run.py)

**Frontend UI:**
- `/pipelines` — Pipeline Runs (запуск, cancel, retry, фильтрация)
- `/settings/pipelines` — GitLab CI/CD Components (CRUD)

## GitLab CI Templates

CI/CD шаблоны в [`infrastructure/gitlab-components/`](../../infrastructure/gitlab-components/):

| Файл | Назначение |
|------|-----------|
| [`mirror-template.yml`](../../infrastructure/gitlab-components/mirror-template.yml) | Синхронизация зеркал |
| [`gold-image-template.yml`](../../infrastructure/gitlab-components/gold-image-template.yml) | Сборка Gold Images |
| [`app-image-template.yml`](../../infrastructure/gitlab-components/app-image-template.yml) | Сборка App Images |
| [`helm-sync-template.yml`](../../infrastructure/gitlab-components/helm-sync-template.yml) | Синхронизация Helm чартов |
| [`docker-sync-template.yml`](../../infrastructure/gitlab-components/docker-sync-template.yml) | Синхронизация Docker образов |

## Модели

### Pipeline Run

См. [`backend/app/models/pipeline_run.py`](../../backend/app/models/pipeline_run.py) — модель `PipelineRun` с полями: `gitlab_instance_id`, `gitlab_project_id`, `gitlab_pipeline_id`, `triggered_by_user_id`, `trigger_type`, `ref`, `variables`, `status_flag`, `status_text`, `created_at`, `started_at`, `finished_at`, `duration`, `web_url`.
### GitLab Component

См. [`backend/app/models/gitlab_component.py`](../../backend/app/models/gitlab_component.py) — модель `GitLabComponent` с полями: `name`, `description`, `gitlab_instance_id`, `project_path`, `component_path`, `version`, `inputs_schema`, `is_enabled`.
## API Endpoints

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

## Запуск пайплайна

См. [`backend/app/services/pipeline.py`](../../backend/app/services/pipeline.py) — реализация `PipelineService` и метода `trigger_pipeline()` для запуска GitLab пайплайнов.
## Webhook обработка

См. [`backend/app/api/webhooks.py`](../../backend/app/api/webhooks.py) — реализация `gitlab_webhook()` и `handle_pipeline_event()` для обработки GitLab webhook событий.
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

## Frontend

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

- [`backend/app/services/pipeline.py`](../../backend/app/services/pipeline.py)
- [`backend/app/api/pipelines.py`](../../backend/app/api/pipelines.py)
- [`backend/app/api/components.py`](../../backend/app/api/components.py)
- [`backend/app/api/webhooks.py`](../../backend/app/api/webhooks.py)
- [`infrastructure/gitlab-components/`](../../infrastructure/gitlab-components/) — CI/CD шаблоны
- [GitLab Pipeline API](https://docs.gitlab.com/ee/api/pipelines.html)
- [GitLab Components](https://docs.gitlab.com/ee/ci/components/)
- [GitLab Webhooks](https://docs.gitlab.com/ee/user/project/integrations/webhooks.html)
