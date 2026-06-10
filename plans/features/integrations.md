# Integrations Guide

Руководство по управлению интеграциями в BigBug (GitLab, Harbor, GitHub, Docker Registry, Helm Repository).

## Текущее состояние

✅ **Реализовано** — управляемые интеграции через Admin UI с поддержкой множественных инстансов для всех 5 типов.

### Реализованные типы интеграций

| Тип | Модель | API |
|-----|--------|-----|
| GitLab Instances | [`gitlab_instance.py`](../../backend/app/models/gitlab_instance.py) | [`gitlab.py`](../../backend/app/api/integrations/gitlab.py) |
| Harbor Instances | [`harbor_instance.py`](../../backend/app/models/harbor_instance.py) | [`harbor.py`](../../backend/app/api/integrations/harbor.py) |
| GitHub Instances | [`github_instance.py`](../../backend/app/models/github_instance.py) | [`github.py`](../../backend/app/api/integrations/github.py) |
| Docker Registries | [`docker_registry_instance.py`](../../backend/app/models/docker_registry_instance.py) | [`docker_registry.py`](../../backend/app/api/integrations/docker_registry.py) |
| Helm Repositories | [`helm_repository_instance.py`](../../backend/app/models/helm_repository_instance.py) | [`helm_repository.py`](../../backend/app/api/integrations/helm_repository.py) |

**Сервисный слой:** [`backend/app/services/integrations.py`](../../backend/app/services/integrations.py)

**Frontend UI:** `/settings/integrations` — управление всеми 5 типами интеграций (добавление, редактирование, проверка подключения)

## .env Fallback (обратная совместимость)

Основной способ конфигурации — **Admin UI** (`/settings/integrations`) с хранением инстансов в БД и шифрованием credentials через Fernet. Переменные окружения `.env` используются только как **fallback** в методах `_get_client()` и `get_default_*_instance()`, когда в БД нет активных инстансов:

```python
# backend/app/services/gitlab.py:67-86 — приоритет:
# 1. instance (из БД) → url + decrypted token
# 2. settings.gitlab_url + settings.gitlab_token (fallback из .env)
# 3. settings.gitlab_url без аутентификации
```

См. [`backend/app/services/integrations.py`](../../backend/app/services/integrations.py) — `get_default_gitlab_instance()`, `get_default_github_instance()`, `get_default_harbor_instance()`.

## Архитектура

Каждая интеграция — отдельная таблица с поддержкой множественных инстансов:

```
gitlab_instances     — множественные GitLab серверы
harbor_instances     — множественные Harbor реестры
github_instances     — GitHub конфигурации (токены)
docker_registry_instances — Docker Registry инстансы
helm_repository_instances — Helm Repository инстансы
```

## API Endpoints

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

## Docker Registry Integration

Docker Registry используется для синхронизации образов.

См. [`backend/app/services/docker.py`](../../backend/app/services/docker.py) — `DockerService` с методами `get_tags()` и `sync_image()`.

### Docker Image Sources

См. [`backend/app/models/docker_image_source.py`](../../backend/app/models/docker_image_source.py) — `DockerImageSource` модель с полями: `name`, `registry_url`, `image_name`, `target_registry_url`, `target_project`, `status_flag`, `status_text`, `last_synced_at`.

## Helm Repository Integration

См. [`backend/app/services/helm.py`](../../backend/app/services/helm.py) — `HelmService` с методами `get_chart_versions()` и `sync_chart()`.

### Helm Chart Sources

См. [`backend/app/models/helm_chart_source.py`](../../backend/app/models/helm_chart_source.py) — `HelmChartSource` модель с полями: `name`, `repo_url`, `chart_name`, `target_repo_url`, `status_flag`, `status_text`, `last_synced_at`.

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

## Admin UI ✅ Реализовано

Страница `/settings/integrations` — управление всеми 5 типами интеграций через [`frontend/src/pages/Settings/Integrations/index.tsx`](../../frontend/src/pages/Settings/Integrations/index.tsx):

- **GitLab Instances** — добавление, редактирование, проверка подключения
- **Harbor Instances** — добавление, редактирование, проверка подключения
- **GitHub** — настройка токенов
- **Docker Registries** — добавление, редактирование
- **Helm Repositories** — добавление, редактирование

Каждый тип поддерживает множественные инстансы, проверку подключения (test connection) и шифрование credentials через Fernet.

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
