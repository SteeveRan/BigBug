# Integrations / Providers Guide

Руководство по управлению внешними интеграциями в BigBug (GitLab, Harbor, GitHub, Docker Registry, Helm Repository).

> **Статус:** Unified Providers V3 — все интеграции управляются через единую сущность `resource_providers`.
> Полный план миграции: [`plans/features/providers-unified.md`](providers-unified.md).

## Текущее состояние

✅ **Реализовано** — единый реестр провайдеров (`resource_providers`) вместо 5 отдельных инстанс-таблиц и параллельной V2-системы `source_providers`.

### Единая модель провайдера

Все 5 бывших типов интеграций теперь представлены одной моделью:

| Модель | API |
|--------|-----|
| [`ResourceProvider`](../../backend/app/models/resource_provider.py) | [`backend/app/api/providers.py`](../../backend/app/api/providers.py) |

Каждый провайдер описывается четырьмя измерениями:

| Поле | Enum | Значения |
|------|------|----------|
| `domain` | `ProviderDomain` | `git`, `docker`, `helm` |
| `subtype` | `ProviderSubtype` | `github`, `gitlab`, `generic_git`, `docker_hub`, `quay`, `gcr`, `ecr`, `acr`, `ghcr`, `harbor`, `generic_registry`, `helm_repo` |
| `category` | `ProviderCategory` | `system`, `public`, `private` |
| `direction` | `ProviderDirection` | `external`, `internal` |

Маппинг бывших инстанс-таблиц:

| Бывшая таблица | Новый провайдер |
|----------------|-----------------|
| `gitlab_instances` | `git` / `gitlab` / `system` / `internal` (или `private`/`external`) |
| `github_instances` | `git` / `github` / `private` / `external` |
| `harbor_instances` | `docker` / `harbor` / `system` / `internal` |
| `docker_registry_instances` | `docker` / `generic_registry` (+ `direction` из `RegistryType`) |
| `helm_repository_instances` | `helm` / `helm_repo` / `private` / `external` |
| `source_providers` (V2 git) | `git` / `github`·`gitlab`·`generic_git` |

**Сервисный слой:** [`backend/app/services/providers/`](../../backend/app/services/providers/) — `registry.py` (реестр подтипов), `service.py` (CRUD/test/actions/матрица доступа), `clients/` (тонкие HTTP-клиенты per-domain).

**Frontend UI:** `/settings/providers` — единая страница управления всеми провайдерами (фильтры по domain/category/direction, добавление, редактирование, проверка подключения, шаринг).

## Реестр подтипов

Реестр подтипов живёт в коде, а не в БД ([`backend/app/services/providers/registry.py`](../../backend/app/services/providers/registry.py)) — декларативное описание полей, типов credentials, действий и правил категорий. Фронтенд получает метаданные через `GET /api/providers/types` для генерации форм.

## API Endpoints

Единый роутер с префиксом `/api/providers`:

```
GET    /api/providers                      # Список (фильтры: domain, subtype, category, direction, owner=me)
GET    /api/providers/types                # Метаданные реестра подтипов (генерация форм)
POST   /api/providers                      # Создать (system → providers_system:write, иначе providers:write)
GET    /api/providers/{id}                 # Детали
PATCH  /api/providers/{id}                 # Обновить
DELETE /api/providers/{id}                 # Удалить
POST   /api/providers/{id}/test            # Проверить подключение
POST   /api/providers/{id}/actions/{action} # Доменное действие (list_repositories и т.д.)
POST   /api/providers/{id}/share           # Поделиться с командой
POST   /api/providers/{id}/unshare         # Вернуть в owner-видимость
GET    /api/providers/{id}/usage           # Использование провайдера
```

## Docker Registry Integration

Docker Registry используется для синхронизации образов.

См. [`backend/app/services/docker.py`](../../backend/app/services/docker.py) — `DockerService` с методами `get_tags()` и `sync_image()`.

### Docker Image Sources

См. [`backend/app/models/docker_image_source.py`](../../backend/app/models/docker_image_source.py) — `DockerImageSource` модель с полями: `name`, `provider_id` (source registry), `target_provider_id` (target registry), `image_name`, `target_project`, `status_flag`, `status_text`, `last_synced_at`.

## Helm Repository Integration

См. [`backend/app/services/helm.py`](../../backend/app/services/helm.py) — `HelmService` с методами `get_chart_versions()` и `sync_chart()`.

### Helm Chart Sources

См. [`backend/app/models/helm_chart_source.py`](../../backend/app/models/helm_chart_source.py) — `HelmChartSource` модель с полями: `name`, `provider_id`, `chart_name`, `target_repo_url`, `status_flag`, `status_text`, `last_synced_at`.

## Шифрование credentials

Все секреты хранятся только в таблице `credentials` (Fernet):

```python
from app.core.secrets import encrypt_secret, decrypt_secret

# Провайдер ссылается на credential
provider.credential_id = credential.id

# Сохранить
credential.encrypted_secret = encrypt_secret(token)
await db.commit()

# Получить
token = decrypt_secret(credential.encrypted_secret)
```

**Важно**: FERNET_KEY должен быть стабильным. Смена ключа требует перешифрования всех данных.

## Admin UI

- **`/settings/providers`** — единая страница провайдеров (фильтры, CRUD, test, шаринг).
- **`/admin/credentials`** — менеджмент учётных данных.
- **`/settings/teams`** / **`/admin/teams`** — команды и шаринг провайдеров.

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
```

## Полезные ссылки

- [`backend/app/services/gitlab.py`](../../backend/app/services/gitlab.py)
- [`backend/app/services/github.py`](../../backend/app/services/github.py)
- [`backend/app/services/docker.py`](../../backend/app/services/docker.py)
- [`backend/app/services/helm.py`](../../backend/app/services/helm.py)
- [`backend/app/services/providers/`](../../backend/app/services/providers/) — реестр, сервис, клиенты
- [`backend/app/core/secrets.py`](../../backend/app/core/secrets.py)
- [`plans/features/providers-unified.md`](providers-unified.md) — полный план миграции V3
- [`plans/architecture/permissions.md`](../architecture/permissions.md) — permissions `providers:*`
