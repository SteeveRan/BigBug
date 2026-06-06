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

```python
# app/models/gold_image.py
class GoldImage(Base):
    __tablename__ = "gold_images"
    
    id: Mapped[int]
    name: Mapped[str]                    # python:3.14-slim
    source_registry: Mapped[str]         # docker.io
    target_registry: Mapped[str]         # harbor.local
    target_project: Mapped[str]          # gold-images
    
    # Версии
    versions: Mapped[list["ImageVersion"]] = relationship(...)
```

```python
# app/models/image_version.py
class ImageVersion(Base):
    __tablename__ = "image_versions"
    
    id: Mapped[int]
    gold_image_id: Mapped[int] = mapped_column(ForeignKey("gold_images.id"))
    version: Mapped[str]                 # 3.14.1, 22.04, latest
    source_digest: Mapped[str | None]    # sha256:abc...
    target_digest: Mapped[str | None]
    status_flag: Mapped[int]             # 0=OK, 1=Failed, 3=In Progress, 4=Pending
    status_text: Mapped[str]
    scanned_at: Mapped[datetime | None]
    vulnerabilities: Mapped[int | None]  # Количество CVE
```

### App Images

```python
# app/models/app_image.py
class AppImage(Base):
    __tablename__ = "app_images"
    
    id: Mapped[int]
    name: Mapped[str]                    # backend, frontend, worker
    github_project_id: Mapped[int]       # Связь с Git репозиторием
    
    # Dockerfile
    dockerfile_path: Mapped[str]         # ./Dockerfile, ./backend/Dockerfile
    context_path: Mapped[str]            # ., ./backend
    
    # Gold Image base
    gold_image_id: Mapped[int | None]    # Базовый образ (опционально)
    
    # Target registry
    target_registry: Mapped[str]         # harbor.local
    target_project: Mapped[str]          # apps
    
    # Build schedule
    build_schedule_id: Mapped[int | None]
```

### Build Logs

```python
# app/models/build_log.py
class BuildLog(Base):
    __tablename__ = "build_logs"
    
    id: Mapped[int]
    app_image_id: Mapped[int]
    
    # Build info
    git_ref: Mapped[str]                 # commit sha, tag, branch
    version: Mapped[str]                 # tag name или auto-generated
    
    # Status
    status_flag: Mapped[int]
    status_text: Mapped[str]
    
    # GitLab CI
    gitlab_pipeline_id: Mapped[int | None]
    gitlab_job_id: Mapped[int | None]
    
    # Output
    build_output: Mapped[str | None]     # Логи сборки
    
    # Timestamps
    started_at: Mapped[datetime]
    finished_at: Mapped[datetime | None]
```

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

```python
# app/services/build.py
class BuildService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def sync_gold_image_versions(self, gold_image_id: int) -> list[ImageVersion]:
        """Sync versions from source registry"""
        gold_image = await self.get_gold_image(gold_image_id)
        
        # Получить теги из source registry
        tags = await self._get_registry_tags(
            gold_image.source_registry,
            gold_image.name
        )
        
        # Обновить или создать ImageVersion записи
        versions = []
        for tag in tags:
            version = await self._get_or_create_version(gold_image_id, tag)
            versions.append(version)
        
        return versions
    
    async def build_app_image(
        self,
        app_image_id: int,
        git_ref: str,
        version: str | None = None
    ) -> BuildLog:
        """Trigger app image build"""
        app_image = await self.get_app_image(app_image_id)
        
        # Создать BuildLog
        build_log = BuildLog(
            app_image_id=app_image_id,
            git_ref=git_ref,
            version=version or git_ref,
            status_flag=3,  # In Progress
            status_text="Starting build",
            started_at=datetime.utcnow()
        )
        self.db.add(build_log)
        await self.db.commit()
        
        # Триггернуть GitLab pipeline
        gitlab_service = GitLabService(...)
        pipeline = await gitlab_service.trigger_pipeline(
            project_id=app_image.gitlab_project_id,
            ref=git_ref,
            variables={
                "DOCKERFILE_PATH": app_image.dockerfile_path,
                "CONTEXT_PATH": app_image.context_path,
                "APP_NAME": app_image.name,
                "VERSION": version or git_ref,
                # ...
            }
        )
        
        # Обновить BuildLog с pipeline info
        build_log.gitlab_pipeline_id = pipeline["id"]
        await self.db.commit()
        
        return build_log
```

## Build Schedules

### Модель

```python
# app/models/build_schedule.py
class BuildSchedule(Base):
    __tablename__ = "build_schedules"
    
    id: Mapped[int]
    app_image_id: Mapped[int]
    
    # Cron expression
    cron_expression: Mapped[str]         # "0 2 * * *" = daily at 2am
    
    # Build params
    git_ref: Mapped[str]                 # main, develop, v*
    auto_version: Mapped[bool]           # Auto-generate version from commit
    
    is_enabled: Mapped[bool]
    last_run_at: Mapped[datetime | None]
    next_run_at: Mapped[datetime | None]
```

### APScheduler Integration

```python
# app/services/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

def schedule_app_build(schedule: BuildSchedule):
    """Schedule app image build"""
    scheduler.add_job(
        func=build_app_image_task,
        trigger='cron',
        **parse_cron(schedule.cron_expression),
        id=f"build_{schedule.id}",
        args=[schedule.app_image_id, schedule.git_ref],
        replace_existing=True
    )

async def build_app_image_task(app_image_id: int, git_ref: str):
    """Background task to build app image"""
    async with AsyncSessionLocal() as db:
        service = BuildService(db)
        await service.build_app_image(app_image_id, git_ref)
```

## Webhooks

GitLab отправляет webhook при завершении pipeline:

```python
# app/api/webhooks.py
@router.post("/gitlab")
async def gitlab_webhook(
    payload: dict,
    db: AsyncSession = Depends(get_db)
):
    """Handle GitLab pipeline webhook"""
    if payload["object_kind"] != "pipeline":
        return {"status": "ignored"}
    
    pipeline_id = payload["object_attributes"]["id"]
    status = payload["object_attributes"]["status"]  # success, failed
    
    # Найти BuildLog
    build_log = await get_build_log_by_pipeline_id(db, pipeline_id)
    if not build_log:
        return {"status": "not_found"}
    
    # Обновить статус
    if status == "success":
        build_log.status_flag = 0
        build_log.status_text = "Build completed"
    elif status == "failed":
        build_log.status_flag = 1
        build_log.status_text = "Build failed"
    
    build_log.finished_at = datetime.utcnow()
    await db.commit()
    
    return {"status": "processed"}
```

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
docker compose -f docker-compose.infra.yml logs gitlab-runner
```

### Docker build fails

```
Error: Cannot connect to Docker daemon
```

GitLab Runner должен использовать Docker-in-Docker (dind):

```yaml
# docker-compose.infra.yml
gitlab-runner:
  environment:
    - DOCKER_HOST=tcp://docker:2375
```

## Полезные ссылки

- [`backend/app/services/build.py`](../../backend/app/services/build.py)
- [`gitlab-ci/gold-image-template.yml`](../../gitlab-ci/gold-image-template.yml)
- [`gitlab-ci/app-image-template.yml`](../../gitlab-ci/app-image-template.yml)
- [`docs/architecture/06-api-design.md`](../../docs/architecture/06-api-design.md)
