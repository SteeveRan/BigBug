# Mirroring Guide

Руководство по системе зеркалирования репозиториев GitHub → GitLab.

## Назначение

BigBug автоматически создаёт зеркала (mirrors) GitHub репозиториев в GitLab для:
- Резервного копирования кода
- Запуска CI/CD пайплайнов в GitLab
- Контроля доступа через единую систему

## Модели и таблицы

### GitHub Organizations

```python
# app/models/github_org.py
class GitHubOrg(Base):
    __tablename__ = "github_orgs"
    
    id: Mapped[int]
    name: Mapped[str]                    # organization name
    github_org_id: Mapped[int]           # GitHub org ID
    
    projects: Mapped[list["GitHubProject"]] = relationship(...)
```

### GitHub Projects

```python
# app/models/github_project.py
class GitHubProject(Base):
    __tablename__ = "github_projects"
    
    id: Mapped[int]
    name: Mapped[str]                    # repository name
    github_id: Mapped[int]               # GitHub repo ID
    clone_url: Mapped[str]               # https://github.com/org/repo.git
    
    github_org_id: Mapped[int] = mapped_column(ForeignKey("github_orgs.id"))
    
    # Status
    status_flag: Mapped[int]
    status_text: Mapped[str]
    last_synced_at: Mapped[datetime | None]
    
    mirrors: Mapped[list["GitLabMirror"]] = relationship(...)
    releases: Mapped[list["GitHubRelease"]] = relationship(...)
```

### GitLab Mirrors

```python
# app/models/gitlab_mirror.py
class GitLabMirror(Base):
    __tablename__ = "gitlab_mirrors"
    
    id: Mapped[int]
    name: Mapped[str]                    # mirror name (обычно = project name)
    
    # Source (GitHub)
    github_project_id: Mapped[int] = mapped_column(ForeignKey("github_projects.id"))
    source_url: Mapped[str]              # https://github.com/org/repo.git
    
    # Target (GitLab)
    gitlab_project_id: Mapped[int | None]    # GitLab project ID (после создания)
    gitlab_token_encrypted: Mapped[str | None]  # Зашифрованный токен
    
    # Configuration
    mirror_enabled: Mapped[bool]         # Автоматическая синхронизация
    
    # Status
    status_flag: Mapped[int]             # 0=OK, 1=Failed, 2=Stale, 3=In Progress, 4=Pending
    status_text: Mapped[str]
    
    # Timestamps
    created_at: Mapped[datetime]
    last_synced_at: Mapped[datetime | None]
    
    # Relationships
    github_project: Mapped["GitHubProject"] = relationship(...)
    sync_logs: Mapped[list["SyncLog"]] = relationship(...)
```

### Sync Logs

```python
# app/models/sync_log.py
class SyncLog(Base):
    __tablename__ = "sync_logs"
    
    id: Mapped[int]
    gitlab_mirror_id: Mapped[int]
    
    # Sync details
    commits_synced: Mapped[int]
    branches_synced: Mapped[int]
    
    status_flag: Mapped[int]
    status_text: Mapped[str]
    error_message: Mapped[str | None]
    
    started_at: Mapped[datetime]
    finished_at: Mapped[datetime | None]
```

## API Endpoints

```
# GitHub Organizations
GET    /api/projects                  # Список GitHub organizations
POST   /api/projects/sync             # Синхронизировать organizations из GitHub
GET    /api/projects/{org_id}         # Детали организации
GET    /api/projects/{org_id}/repos   # Репозитории в организации

# GitLab Mirrors
GET    /api/mirrors                   # Список зеркал
POST   /api/mirrors                   # Создать зеркало
GET    /api/mirrors/{id}              # Детали зеркала
PATCH  /api/mirrors/{id}              # Обновить зеркало
DELETE /api/mirrors/{id}              # Удалить зеркало
POST   /api/mirrors/{id}/sync         # Запустить синхронизацию
GET    /api/mirrors/{id}/logs         # История синхронизации
POST   /api/mirrors/import            # Импортировать существующее зеркало
```

## Workflow

### 1. Добавление GitHub Organization

```
1. Пользователь добавляет GitHub token в настройки
   
2. Нажимает "Sync Organizations"
   POST /api/projects/sync

3. Backend:
   - Получает список organizations через GitHub API
   - Создаёт/обновляет GitHubOrg записи
   - Для каждой org получает список repositories
   - Создаёт/обновляет GitHubProject записи
```

### 2. Создание зеркала

```
1. Пользователь выбирает GitHub проект и создаёт mirror:
   POST /api/mirrors
   {
     "github_project_id": 123,
     "name": "my-app",
     "mirror_enabled": true
   }

2. Backend:
   - Создаёт GitLabMirror с status=Pending
   - Триггерит async задачу создания проекта в GitLab

3. Async задача (GitLabService):
   - Создаёт GitLab project через API
   - Настраивает mirror (push mirror или pull mirror)
   - Сохраняет gitlab_project_id
   - Обновляет status=OK
```

### 3. Синхронизация

```
Manual sync:
1. POST /api/mirrors/{id}/sync

2. Backend триггерит GitLab mirror sync:
   POST /api/v4/projects/{id}/mirror/pull

3. GitLab синхронизирует изменения из GitHub

Automatic sync:
1. APScheduler периодически проверяет mirrors с mirror_enabled=true
2. Для каждого зеркала триггерит sync
3. Логирует результат в sync_logs

Webhook-based (optional):
1. GitHub webhook → BigBug
2. BigBug триггерит GitLab mirror sync
3. Актуальность в real-time
```

### 4. Stale Detection

```
1. APScheduler задача проверяет mirrors:
   - Если last_synced_at > 24 часа → status=Stale
   
2. На странице mirrors показывается предупреждение

3. Пользователь может запустить sync вручную
```

### 5. Import существующего зеркала

```
1. Пользователь уже создал mirror вручную в GitLab
   
2. Импортирует в BigBug:
   POST /api/mirrors/import
   {
     "gitlab_project_id": 456,
     "github_project_id": 123
   }

3. Backend:
   - Проверяет что GitLab project существует
   - Создаёт GitLabMirror с существующим gitlab_project_id
   - Получает mirror status из GitLab API
```

## Service Layer

### GitHubService

```python
# app/services/github.py
class GitHubService:
    def __init__(self, token: str):
        self.token = token
        self.client = httpx.AsyncClient()
    
    async def list_orgs(self) -> list[dict]:
        """Get organizations for authenticated user"""
        response = await self.client.get(
            "https://api.github.com/user/orgs",
            headers={"Authorization": f"token {self.token}"}
        )
        return response.json()
    
    async def list_repos(self, org_name: str) -> list[dict]:
        """Get repositories in organization"""
        response = await self.client.get(
            f"https://api.github.com/orgs/{org_name}/repos",
            headers={"Authorization": f"token {self.token}"}
        )
        return response.json()
    
    async def get_releases(self, owner: str, repo: str) -> list[dict]:
        """Get releases for repository"""
        response = await self.client.get(
            f"https://api.github.com/repos/{owner}/{repo}/releases",
            headers={"Authorization": f"token {self.token}"}
        )
        return response.json()
```

### GitLabService

```python
# app/services/gitlab.py
class GitLabService:
    def __init__(self, url: str, token: str):
        self.url = url
        self.token = token
        self.client = httpx.AsyncClient()
    
    async def create_mirror(
        self,
        name: str,
        source_url: str,
        group_id: int
    ) -> dict:
        """Create GitLab project with mirror configuration"""
        # 1. Создать проект
        project = await self.client.post(
            f"{self.url}/api/v4/projects",
            headers={"PRIVATE-TOKEN": self.token},
            json={
                "name": name,
                "namespace_id": group_id,
                "mirror": True,
                "import_url": source_url,
                "mirror_trigger_builds": True
            }
        )
        
        # 2. Настроить pull mirror
        mirror_config = await self.client.put(
            f"{self.url}/api/v4/projects/{project.id}/mirror/pull",
            headers={"PRIVATE-TOKEN": self.token}
        )
        
        return project.json()
    
    async def trigger_mirror_sync(self, project_id: int) -> dict:
        """Trigger mirror synchronization"""
        response = await self.client.post(
            f"{self.url}/api/v4/projects/{project_id}/mirror/pull",
            headers={"PRIVATE-TOKEN": self.token}
        )
        return response.json()
    
    async def get_mirror_status(self, project_id: int) -> dict:
        """Get mirror status"""
        response = await self.client.get(
            f"{self.url}/api/v4/projects/{project_id}",
            headers={"PRIVATE-TOKEN": self.token}
        )
        return response.json()
```

## Sync Schedules

### Модель

```python
# app/models/sync_schedule.py
class SyncSchedule(Base):
    __tablename__ = "sync_schedules"
    
    id: Mapped[int]
    gitlab_mirror_id: Mapped[int]
    
    cron_expression: Mapped[str]         # "0 */6 * * *" = every 6 hours
    is_enabled: Mapped[bool]
    
    last_run_at: Mapped[datetime | None]
    next_run_at: Mapped[datetime | None]
```

### APScheduler

```python
# app/services/scheduler.py
def schedule_mirror_sync(schedule: SyncSchedule):
    """Schedule mirror synchronization"""
    scheduler.add_job(
        func=sync_mirror_task,
        trigger='cron',
        **parse_cron(schedule.cron_expression),
        id=f"mirror_sync_{schedule.id}",
        args=[schedule.gitlab_mirror_id],
        replace_existing=True
    )

async def sync_mirror_task(mirror_id: int):
    """Background task to sync mirror"""
    async with AsyncSessionLocal() as db:
        gitlab_service = GitLabService(...)
        mirror = await get_mirror(db, mirror_id)
        
        # Создать SyncLog
        log = SyncLog(
            gitlab_mirror_id=mirror_id,
            status_flag=3,  # In Progress
            started_at=datetime.utcnow()
        )
        db.add(log)
        await db.commit()
        
        try:
            # Триггернуть sync
            result = await gitlab_service.trigger_mirror_sync(mirror.gitlab_project_id)
            
            # Обновить статус
            log.status_flag = 0
            log.status_text = "Sync completed"
            log.finished_at = datetime.utcnow()
            
            mirror.last_synced_at = datetime.utcnow()
            mirror.status_flag = 0
            
        except Exception as e:
            log.status_flag = 1
            log.status_text = "Sync failed"
            log.error_message = str(e)
            log.finished_at = datetime.utcnow()
            
            mirror.status_flag = 1
            mirror.status_text = f"Sync failed: {str(e)}"
        
        await db.commit()
```

## Frontend

### Projects (Organizations) страница

```typescript
// src/pages/Projects/index.tsx
const { data: orgs, isLoading } = useGetProjectsQuery();
const [syncProjects] = useSyncProjectsMutation();

return (
  <Box>
    <Button onClick={() => syncProjects()}>Sync from GitHub</Button>
    
    <List>
      {orgs?.map((org) => (
        <ListItem key={org.id}>
          <ListItemText primary={org.name} />
          <Button component={Link} to={`/projects/${org.id}`}>
            View Repos
          </Button>
        </ListItem>
      ))}
    </List>
  </Box>
);
```

### Mirrors страница

```typescript
// src/pages/Mirrors/index.tsx
const { data: mirrors } = useGetMirrorsQuery();
const [syncMirror] = useSyncMirrorMutation();
const [deleteMirror] = useDeleteMirrorMutation();

return (
  <Table>
    {mirrors?.map((mirror) => (
      <TableRow key={mirror.id}>
        <TableCell>{mirror.name}</TableCell>
        <TableCell>{mirror.github_project?.name}</TableCell>
        <TableCell>
          <StatusChip status={mirror.status_flag} label={mirror.status_text} />
        </TableCell>
        <TableCell>
          {mirror.last_synced_at 
            ? new Date(mirror.last_synced_at).toLocaleString()
            : 'Never'}
        </TableCell>
        <TableCell>
          <Button onClick={() => syncMirror(mirror.id)}>Sync Now</Button>
          <Button color="error" onClick={() => deleteMirror(mirror.id)}>
            Delete
          </Button>
        </TableCell>
      </TableRow>
    ))}
  </Table>
);
```

## Troubleshooting

### Mirror не создаётся

```bash
# Проверить GitLab API token
curl -H "PRIVATE-TOKEN: glpat-xyz" http://localhost:8080/api/v4/projects

# Проверить GitLab группу
curl -H "PRIVATE-TOKEN: glpat-xyz" http://localhost:8080/api/v4/groups
```

### Синхронизация не работает

```
Error: Repository not found
```

Проверить:
1. GitHub token имеет доступ к репозиторию
2. Source URL корректный
3. GitLab может достучаться до GitHub (firewall, proxy)

### Stale mirrors

```sql
-- Найти mirrors которые давно не синхронизировались
SELECT name, last_synced_at
FROM gitlab_mirrors
WHERE last_synced_at < NOW() - INTERVAL '24 hours'
  AND mirror_enabled = true;
```

## Полезные ссылки

- [`backend/app/services/github.py`](../../backend/app/services/github.py)
- [`backend/app/services/gitlab.py`](../../backend/app/services/gitlab.py)
- [`backend/app/api/mirrors.py`](../../backend/app/api/mirrors.py)
- [`backend/app/api/projects.py`](../../backend/app/api/projects.py)
- [GitHub API Documentation](https://docs.github.com/en/rest)
- [GitLab Mirror API](https://docs.gitlab.com/ee/api/projects.html#configure-pull-mirroring-for-a-project)
