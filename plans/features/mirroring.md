# Mirroring Guide

Руководство по системе зеркалирования репозиториев GitHub → GitLab.

## Назначение

BigBug автоматически создаёт зеркала (mirrors) GitHub репозиториев в GitLab для:
- Резервного копирования кода
- Запуска CI/CD пайплайнов в GitLab
- Контроля доступа через единую систему

## Модели и таблицы

### GitHub Organizations

См. [`backend/app/models/github_org.py`](../../backend/app/models/github_org.py) — модель `GitHubOrg` с полями: `name`, `github_org_id`, связь `projects`.
### GitHub Projects

См. [`backend/app/models/github_project.py`](../../backend/app/models/github_project.py) — модель `GitHubProject` с полями: `name`, `github_id`, `clone_url`, `github_org_id`, `status_flag`, `status_text`, `last_synced_at`, связи `mirrors` и `releases`.
### GitLab Mirrors

См. [`backend/app/models/gitlab_mirror.py`](../../backend/app/models/gitlab_mirror.py) — модель `GitLabMirror` с полями: `name`, `github_project_id`, `source_url`, `gitlab_project_id`, `gitlab_token_encrypted`, `mirror_enabled`, `status_flag`, `status_text`, `created_at`, `last_synced_at`, связи `github_project` и `sync_logs`.
### Sync Logs

См. [`backend/app/models/sync_log.py`](../../backend/app/models/sync_log.py) — модель `SyncLog` с полями: `gitlab_mirror_id`, `commits_synced`, `branches_synced`, `status_flag`, `status_text`, `error_message`, `started_at`, `finished_at`.
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

См. [`backend/app/services/github.py`](../../backend/app/services/github.py) — реализация `GitHubService` и его методов.
### GitLabService

См. [`backend/app/services/gitlab.py`](../../backend/app/services/gitlab.py) — реализация `GitLabService` и его методов.
## Sync Schedules

### Модель

См. [`backend/app/models/sync_schedule.py`](../../backend/app/models/sync_schedule.py) — модель `SyncSchedule` с полями: `gitlab_mirror_id`, `cron_expression`, `is_enabled`, `last_run_at`, `next_run_at`.
### APScheduler

См. [`backend/app/services/scheduler.py`](../../backend/app/services/scheduler.py) — реализация `schedule_mirror_sync()` и `sync_mirror_task()` для планирования и выполнения синхронизации зеркал.
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
