# Builds Guide

Руководство по системе сборки Docker образов (Gold Images и App Images).

## Типы образов

### Gold Images

**Базовые образы** — OS и runtime окружения (Python, Node.js, Java, etc).

Примеры:
- `ubuntu:22.04` → `bigbug/gold/ubuntu:22.04`
- `python:3.14-slim` → `bigbug/gold/python:3.14-slim`
- `node:26-alpine` → `bigbug/gold/node:26-alpine`

**Цель**: централизованное управление базовыми образами с security scanning.

### App Images

**Образы приложений** — конечные образы для deployment.

Примеры:
- `bigbug/app/backend:1.0.0` (FastAPI приложение)
- `bigbug/app/frontend:1.0.0` (React приложение)
- `bigbug/app/worker:latest` (Celery worker)

**Цель**: автоматическая сборка приложений из Git репозиториев.

## Модели и таблицы

### Gold Images

См. [`backend/app/models/gold_image.py`](../../backend/app/models/gold_image.py) — модель `GoldImage` с полями: `name`, `source_registry`, `target_registry`, `target_project`, связь `versions`.
См. [`backend/app/models/image_version.py`](../../backend/app/models/image_version.py) — модель `ImageVersion` с полями: `gold_image_id`, `version`, `source_digest`, `target_digest`, `status_flag`, `status_text`, `scanned_at`, `vulnerabilities`.
### App Images

См. [`backend/app/models/app_image.py`](../../backend/app/models/app_image.py) — модель `AppImage` с полями: `name`, `github_project_id`, `dockerfile_path`, `context_path`, `gold_image_id`, `target_registry`, `target_project`, `build_schedule_id`.
### Build Logs

См. [`backend/app/models/build_log.py`](../../backend/app/models/build_log.py) — модель `BuildLog` с полями: `app_image_id`, `git_ref`, `version`, `status_flag`, `status_text`, `gitlab_pipeline_id`, `gitlab_job_id`, `build_output`, `started_at`, `finished_at`.
## API Endpoints

### Gold Images

```
GET    /api/gold-images              # Список Gold Images
POST   /api/gold-images              # Добавить Gold Image
GET    /api/gold-images/{id}         # Детали
PATCH  /api/gold-images/{id}         # Обновить
DELETE /api/gold-images/{id}         # Удалить
POST   /api/gold-images/{id}/sync    # Синхронизировать версии из source registry
GET    /api/gold-images/{id}/versions # Список версий
```

### App Images

```
GET    /api/app-images               # Список App Images
POST   /api/app-images               # Добавить App Image
GET    /api/app-images/{id}          # Детали
PATCH  /api/app-images/{id}          # Обновить
DELETE /api/app-images/{id}          # Удалить
POST   /api/app-images/{id}/build    # Запустить сборку
GET    /api/app-images/{id}/logs     # История сборок
GET    /api/app-images/{id}/logs/{log_id} # Детали сборки
```

## Workflow

### Gold Image Sync Flow

```
1. Пользователь добавляет Gold Image:
   - name: python:3.14-slim
   - source_registry: docker.io
   - target_registry: harbor.local

2. BigBug синхронизирует версии:
   GET https://registry-1.docker.io/v2/library/python/tags/list
   
3. Для каждой версии:
   - Проверить наличие в target registry
   - Если нет → скопировать (docker pull + docker push)
   - Сохранить digest

4. Опционально: Harbor security scan
   - Запустить scan через Harbor API
   - Получить количество vulnerabilities
   - Обновить ImageVersion.vulnerabilities
```

### App Image Build Flow

```
1. Пользователь создаёт App Image:
   - name: backend
   - github_project_id: 123
   - dockerfile_path: ./Dockerfile
   - gold_image_id: 456 (базовый python:3.14-slim)

2. Запуск сборки (manual или по schedule):
   POST /api/app-images/{id}/build
   {
     "git_ref": "main",  // или commit sha, tag
     "version": "1.0.0"  // опционально
   }

3. BigBug создаёт GitLab CI pipeline:
   - Генерирует .gitlab-ci.yml из template
   - Подставляет переменные (Dockerfile path, registry, etc)
   - Триггерит pipeline через GitLab API

4. GitLab Runner выполняет:
   - git clone
   - docker build
   - docker push to target registry
   - Отправляет webhook в BigBug

5. BigBug получает webhook:
   - Обновляет BuildLog status
   - Сохраняет build_output
```

## GitLab CI Templates

### Gold Image Template

[`gitlab-ci/gold-image-template.yml`](../../gitlab-ci/gold-image-template.yml):

```yaml
stages:
  - sync

sync_gold_image:
  stage: sync
  image: docker:latest
  services:
    - docker:dind
  variables:
    SOURCE_IMAGE: ${SOURCE_REGISTRY}/${SOURCE_IMAGE_NAME}:${VERSION}
    TARGET_IMAGE: ${TARGET_REGISTRY}/${TARGET_PROJECT}/${TARGET_IMAGE_NAME}:${VERSION}
  script:
    - docker login -u ${SOURCE_REGISTRY_USER} -p ${SOURCE_REGISTRY_PASSWORD} ${SOURCE_REGISTRY}
    - docker login -u ${TARGET_REGISTRY_USER} -p ${TARGET_REGISTRY_PASSWORD} ${TARGET_REGISTRY}
    - docker pull ${SOURCE_IMAGE}
    - docker tag ${SOURCE_IMAGE} ${TARGET_IMAGE}
    - docker push ${TARGET_IMAGE}
    - docker inspect ${TARGET_IMAGE} --format='{{.RepoDigests}}'
```

### App Image Template

[`gitlab-ci/app-image-template.yml`](../../gitlab-ci/app-image-template.yml):

```yaml
stages:
  - build
  - push

build_app_image:
  stage: build
  image: docker:latest
  services:
    - docker:dind
  variables:
    DOCKERFILE_PATH: ${DOCKERFILE_PATH}
    CONTEXT_PATH: ${CONTEXT_PATH}
    IMAGE_NAME: ${TARGET_REGISTRY}/${TARGET_PROJECT}/${APP_NAME}:${VERSION}
    BASE_IMAGE: ${BASE_IMAGE_REGISTRY}/${BASE_IMAGE_NAME}:${BASE_IMAGE_TAG}
  script:
    - cd ${CONTEXT_PATH}
    - docker build -f ${DOCKERFILE_PATH} -t ${IMAGE_NAME} --build-arg BASE_IMAGE=${BASE_IMAGE} .
    - docker login -u ${REGISTRY_USER} -p ${REGISTRY_PASSWORD} ${TARGET_REGISTRY}
    - docker push ${IMAGE_NAME}
    - docker inspect ${IMAGE_NAME} --format='{{.RepoDigests}}'
```

## Service Layer

### BuildService

См. [`backend/app/services/build.py`](../../backend/app/services/build.py) — реализация `BuildService` и его методов.
## Build Schedules

### Модель

См. [`backend/app/models/build_schedule.py`](../../backend/app/models/build_schedule.py) — модель `BuildSchedule` с полями: `app_image_id`, `cron_expression`, `git_ref`, `auto_version`, `is_enabled`, `last_run_at`, `next_run_at`.
### APScheduler Integration

См. [`backend/app/services/scheduler.py`](../../backend/app/services/scheduler.py) — реализация `schedule_app_build()` и `build_app_image_task()` для планирования и выполнения сборки образов.
## Webhooks

GitLab отправляет webhook при завершении pipeline:

См. [`backend/app/api/webhooks.py`](../../backend/app/api/webhooks.py) — реализация `gitlab_webhook()` для обработки завершения GitLab пайплайнов и обновления статусов сборок.
## Frontend

### Gold Images страница

```typescript
// src/pages/GoldImages/index.tsx
const { data: goldImages, isLoading } = useGetGoldImagesQuery();

return (
  <Table>
    {goldImages?.map((image) => (
      <TableRow key={image.id}>
        <TableCell>{image.name}</TableCell>
        <TableCell>{image.source_registry}</TableCell>
        <TableCell>
          <StatusChip status={image.status_flag} label={image.status_text} />
        </TableCell>
        <TableCell>
          <Button onClick={() => syncImage(image.id)}>Sync</Button>
        </TableCell>
      </TableRow>
    ))}
  </Table>
);
```

### App Images страница

```typescript
// src/pages/AppImages/index.tsx
const { data: appImages } = useGetAppImagesQuery();
const [buildImage] = useBuildAppImageMutation();

const handleBuild = async (imageId: number) => {
  await buildImage({
    id: imageId,
    git_ref: 'main',
    version: '1.0.0'
  });
};

return (
  <Table>
    {appImages?.map((image) => (
      <TableRow key={image.id}>
        <TableCell>{image.name}</TableCell>
        <TableCell>{image.github_project?.name}</TableCell>
        <TableCell>
          <Button onClick={() => handleBuild(image.id)}>Build</Button>
        </TableCell>
      </TableRow>
    ))}
  </Table>
);
```

## Troubleshooting

### Сборка не запускается

```bash
# Проверить GitLab API
curl -H "PRIVATE-TOKEN: glpat-xyz" http://localhost:8080/api/v4/projects

# Проверить GitLab Runner
docker compose -f infrastructure/docker-compose.yml logs gitlab-runner
```

### Docker build fails

```
Error: Cannot connect to Docker daemon
```

GitLab Runner должен использовать Docker-in-Docker (dind):

```yaml
# infrastructure/docker-compose.yml
gitlab-runner:
  environment:
    - DOCKER_HOST=tcp://docker:2375
```

## Полезные ссылки

- [`backend/app/services/build.py`](../../backend/app/services/build.py)
- [`gitlab-ci/gold-image-template.yml`](../../gitlab-ci/gold-image-template.yml)
- [`gitlab-ci/app-image-template.yml`](../../gitlab-ci/app-image-template.yml)
- [`docs/architecture/06-api-design.md`](../../docs/architecture/06-api-design.md)
