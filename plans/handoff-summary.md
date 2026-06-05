# BigBug — Handoff Summary

> **Дата:** 2026-06-05
> **Состояние:** Блоки 1-5 завершены (Docker-инфраструктура + SSO + Helm Charts + Docker Images + Frontend UI). Остался блок 6 (тесты, Harbor, документация).
> **Целевая аудитория:** AI-агент, продолжающий реализацию.

---

## 1. Что сделано (26 из 31 задач)

### Блок 1 — Docker-инфраструктура (задачи 1–6)

| Файл | Что сделано |
|------|-------------|
| [`backend/entrypoint.sh`](../backend/entrypoint.sh) | Точка входа: `app:start` (migrate + uvicorn), `app:init` (только migrate). Ждёт PostgreSQL через `pg_isready`. |
| [`backend/Dockerfile`](../backend/Dockerfile) | Multi-stage: slim-bookworm → venv → копирование зависимостей. Запуск от `nonroot` пользователя. |
| [`backend/.dockerignore`](../backend/.dockerignore) | Исключены `__pycache__`, `.venv`, `tests/`, `alembic/versions/.gitkeep`. |
| [`docker-compose.yml`](../docker-compose.yml) | **Два** PostgreSQL (backend + keycloak), Keycloak 24.0, GitLab CE, GitLab Runner, Redis 7, backend, frontend. |
| [`docker-compose.yml`](../docker-compose.yml) | Сервис `keycloak-init` с `profiles: ["init"]` — запускается одноразово: `docker compose --profile init up keycloak-init`. |
| [`keycloak/init-keycloak.sh`](../keycloak/init-keycloak.sh) | Идемпотентный bootstrap: создаёт realm `bigbug`, роли (admin/operator/viewer), confidential client `bigbug-backend`, public client `bigbug-frontend` (PKCE S256 enforced), тестового пользователя. |
| [`.env.example`](../.env.example) | Все переменные окружения с комментариями: БД, Redis, Keycloak, GitLab, GitHub, Harbor, секреты. |

### Блок 2 — SSO (задачи 7–13)

**Backend — модель пользователя (Pt 7):**
- [`backend/app/models/user.py`](../backend/app/models/user.py:14) — `hashed_password` стал `nullable=True` (SSO-пользователи без пароля).
- [`backend/app/models/user.py`](../backend/app/models/user.py:15) — добавлено поле `keycloak_sub` (`String(255), unique=True, nullable=True`) — ключ связывания локального пользователя с Keycloak-identity.
- Миграция [`20260605_0449_39774f94ac35_initial_schema.py`](../backend/alembic/versions/20260605_0449_39774f94ac35_initial_schema.py) включает эти изменения.

**Backend — шифрование секретов (Pt 8):**
- [`backend/app/core/secrets.py`](../backend/app/core/secrets.py) — `SecretCipher` на базе Fernet (AES-128-CBC + HMAC-SHA256).
- [`SecretEncryptionError`](../backend/app/core/secrets.py:24) — доменное исключение для ошибок расшифровки.
- [`get_cipher()`](../backend/app/core/secrets.py:59) — `@lru_cache(maxsize=1)`, падает громко если `ENCRYPTION_KEY` не задан.
- [`encrypt_secret()`](../backend/app/core/secrets.py:78) / [`decrypt_secret()`](../backend/app/core/secrets.py:85) — хелперы, возвращают `None` для пустых входов.
- [`backend/app/config.py`](../backend/app/config.py:43) — `encryption_key: str = ""`.

**Backend — OIDC сервис (Pt 9):**
- [`backend/app/core/exceptions.py`](../backend/app/core/exceptions.py) — 4 доменных исключения: `OIDCError` (базовый), `OIDCExchangeError`, `OIDCInvalidTokenError`, `OIDCProvisioningError`. Все наследуют `RuntimeError`, **не** `HTTPException`.
- [`backend/app/services/oidc.py`](../backend/app/services/oidc.py) (~333 строки):
  - [`OIDCClaims`](../backend/app/services/oidc.py:52) — frozen dataclass (subject, username, email, roles).
  - [`_JWKSCache`](../backend/app/services/oidc.py:62) — TTL-кэш с `time.monotonic()`, сбрасывается при ошибках.
  - [`KeycloakOIDCService`](../backend/app/services/oidc.py:92):
    - `exchange_code()` — POST на Keycloak token endpoint (Authorization Code → tokens).
    - `validate_id_token()` — проверка подписи через JWKS, issuer, audience, expiry.
    - `provision_or_update_user()` — создаёт или обновляет локального пользователя по `keycloak_sub`.
    - `_sync_roles()` — синхронизирует `realm_access.roles` → локальные роли (admin/operator/viewer), удаляет не назначенные.
  - [`_NonClosingClient`](../backend/app/services/oidc.py:313) — адаптер для инъекции тестовых httpx-клиентов.
  - `_client()` возвращает `AbstractAsyncContextManager[httpx.AsyncClient]` — для совместимости с реальным клиентом и тестовым.
- Зависимости: `httpx`, `python-jose[cryptography]` (уже были в pyproject.toml).

**Backend — SSO API (Pt 10):**
- [`backend/app/schemas/auth.py`](../backend/app/schemas/auth.py:19):
  - `OIDCExchangeRequest` — code, redirect_uri, code_verifier.
  - `SSOConfig` — enabled, url, realm, client_id.
- [`backend/app/api/auth.py`](../backend/app/api/auth.py):
  - [`GET /auth/sso/config`](../backend/app/api/auth.py:83) — возвращает SSOConfig. `enabled` = `bool(settings.keycloak_client_secret)`.
  - [`POST /auth/oidc/exchange`](../backend/app/api/auth.py:99) — принимает OIDCExchangeRequest, возвращает TokenResponse.
  - Обработка ошибок: `OIDCExchangeError` → 502, `OIDCInvalidTokenError` → 401, `OIDCProvisioningError` → 500.
- [`backend/app/config.py`](../backend/app/config.py:53) — [`keycloak_frontend_client_id`](../backend/app/config.py:53) (по умолчанию `bigbug-frontend`).
- [`backend/app/config.py`](../backend/app/config.py:56) — `keycloak_http_timeout_seconds` (10.0).
- [`backend/app/config.py`](../backend/app/config.py:59) — `keycloak_jwks_cache_ttl_seconds` (600).

**Frontend — сервис Keycloak (Pt 11):**
- [`frontend/src/services/keycloak.ts`](../frontend/src/services/keycloak.ts):
  - `getKeycloakInstance(url, realm, clientId)` — singleton.
  - `resetKeycloakInstance()` — для тестов.
  - `redirectToKeycloakLogin()` — строит URL вручную (keycloak-js 24.x не типизирует `codeChallenge` в `KeycloakLoginOptions`).
  - `generateCodeVerifier()` — 64 случайных байта → base64url.
  - `computeCodeChallenge(verifier)` — SHA-256 → base64url.
  - `SSO_VERIFIER_KEY = 'sso_code_verifier'` — ключ в sessionStorage.
- [`frontend/src/hooks/useKeycloakAuth.ts`](../frontend/src/hooks/useKeycloakAuth.ts):
  - Использует `useGetSsoConfigQuery()` для получения конфигурации.
  - `ready` — конфиг загружен, `enabled` — SSO включён на бэкенде, `error` — ошибка загрузки.
  - `login()` → `redirectToKeycloakLogin()`, редирект на `${window.location.origin}/sso/callback`.
  - `handleCallback()` — читает `code` из URL, `code_verifier` из sessionStorage, возвращает `ExchangePayload | { error: string }`.

**Frontend — store (Pt 13):**
- [`frontend/src/store/api.ts`](../frontend/src/store/api.ts:37):
  - `getSsoConfig` query → `GET /auth/sso/config`.
  - `ssoExchange` mutation → `POST /auth/oidc/exchange`.
  - Экспортированы `useGetSsoConfigQuery`, `useSsoExchangeMutation`.

**Frontend — UI (Pt 12):**
- [`frontend/src/pages/Login/index.tsx`](../frontend/src/pages/Login/index.tsx):
  - Импорт `useKeycloakAuth`.
  - Обработка `?error=` query-параметра (из SSO callback при ошибках).
  - После формы логина: `<Divider>or</Divider>` + кнопка "Sign in with SSO" (показывается только при `ready && enabled`).
- [`frontend/src/pages/SsoCallback/index.tsx`](../frontend/src/pages/SsoCallback/index.tsx):
  - `useRef` guard против StrictMode double-mount.
  - `handleCallback()` → `exchange()` → `fetch /api/auth/me` → `dispatch(setCredentials(...))` → `navigate('/')`.
  - При ошибке: `navigate('/login?error=...')`.
  - Показывает `CircularProgress` + "Completing sign in…".
- [`frontend/src/router/index.tsx`](../frontend/src/router/index.tsx:25):
  - Добавлен маршрут `<Route path="/sso/callback" element={<SsoCallbackPage />} />`.

### Блок 3 — Helm Charts (задачи 14–16)

**Backend — модели (Pt 14):**
- [`backend/app/models/helm_chart_source.py`](../backend/app/models/helm_chart_source.py) — модель `HelmChartSource`: репозиторий Helm-чартов с полями `name` (unique), `repo_url`, `description`, `gitlab_project_id`, `gitlab_project_url`, `last_synced_at`, `status_flag`/`status_text`, `created_at`, `updated_at`. Relationships: `versions` → HelmChartVersion (cascade delete), `sync_logs` → HelmSyncLog (cascade delete).
- [`backend/app/models/helm_chart_version.py`](../backend/app/models/helm_chart_version.py) — модель `HelmChartVersion`: версия чарта с полями `source_id` (FK → helm_chart_sources, CASCADE), `chart_name` (indexed), `version`, `app_version`, `description`, `digest` (SHA-256), `urls` (JSON-массив), `chart_url`, `gitlab_project_id`, `status_flag`/`status_text`, `is_synced` (bool), `last_synced_at`. Relationship: `source` → HelmChartSource.
- [`backend/app/models/helm_sync_log.py`](../backend/app/models/helm_sync_log.py) — модель `HelmSyncLog`: лог синхронизации с полями `source_id` (FK → helm_chart_sources, CASCADE), `pipeline_id`, `pipeline_url`, `status_flag`/`status_text`, `log_output`, `triggered_by` (scheduler/manual/webhook), `started_at`, `finished_at`. Relationship: `source` → HelmChartSource.
- [`backend/alembic/versions/20260605_0747_add_helm_tables.py`](../backend/alembic/versions/20260605_0747_add_helm_tables.py) — миграция, создающая 3 таблицы: `helm_chart_sources`, `helm_chart_versions`, `helm_sync_logs` со всеми индексами (`down_revision = '39774f94ac35'`).

**Backend — схемы + сервис + API (Pt 15):**
- [`backend/app/schemas/helm.py`](../backend/app/schemas/helm.py) — Pydantic v2 схемы: `HelmChartSourceOut`, `HelmChartSourceDetailOut` (с вложенным списком versions), `HelmChartVersionOut`, `HelmSyncLogOut`, `CreateHelmChartSourceRequest`, `UpdateHelmChartSourceRequest`.
- [`backend/app/services/helm.py`](../backend/app/services/helm.py) — класс `HelmService` (синглтон `helm_service`). Методы: `import_source_from_url()` (создание + индексация), `index_source()` (скачивание index.yaml через httpx → парсинг PyYAML → синхронизация версий), `refresh_source()`, `_fetch_index()` (httpx AsyncClient), `_sync_chart_entries()` (upsert по source_id+chart_name+version), `trigger_index_pipeline()`. Хелперы: `_normalize_repo_url()`, `_validate_repo_url()`. Исключения: `BadRequestError`, `ExternalServiceError`. Зависимости: `httpx`, `PyYAML`.
- [`backend/app/api/helm_charts.py`](../backend/app/api/helm_charts.py) — APIRouter с эндпоинтами (RBAC: чтение — `require_viewer`, изменение — `require_operator`): `GET /helm-charts`, `GET /helm-charts/{id}`, `POST /helm-charts`, `PATCH /helm-charts/{id}`, `DELETE /helm-charts/{id}`, `POST /helm-charts/{id}/index`, `GET /helm-charts/{id}/versions`, `GET /helm-charts/{id}/logs`.

**GitLab CI (Pt 16):**
- [`gitlab-ci/helm-sync-template.yml`](../gitlab-ci/helm-sync-template.yml) — CI-шаблон синхронизации Helm-чартов. Stages: `sync`, `notify`. Job `helm-sync` (образ `alpine/helm`: `helm repo add`, `helm search`, `helm pull`). Job `notify-failure`. CI-переменные: `HELM_REPO_URL`, `HELM_REPO_NAME`, `SYNC_STRATEGY`, `CHART_FILTER`.

**Изменённые файлы:**
| Файл | Изменение |
|------|-----------|
| [`backend/app/models/__init__.py`](../backend/app/models/__init__.py) | Добавлены импорты и в `__all__`: `HelmChartSource`, `HelmChartVersion`, `HelmSyncLog`. |
| [`backend/app/main.py`](../backend/app/main.py) | Импорт и регистрация роутера `helm_charts` с `prefix="/api/helm-charts"`, `tags=["helm-charts"]`. |
| [`backend/app/api/webhooks.py`](../backend/app/api/webhooks.py) | Добавлена обработка `HelmSyncLog`: поиск по `pipeline_id`, обновление `status_flag`/`status_text`/`finished_at`, обновление родительского `HelmChartSource` (status + `last_synced_at` при success). Импорты `HelmSyncLog`, `HelmChartSource`. |

### Блок 4 — Docker Images (задачи 17–19, 22)

**Backend — модели (Pt 17):**
- [`backend/app/models/docker_image_source.py`](../backend/app/models/docker_image_source.py) — модель `DockerImageSource`: источник Docker-образов с полями `name` (unique), `registry_url`, `description`, `gitlab_project_id`, `gitlab_project_url`, `last_synced_at`, `status_flag` (default=4), `status_text`, `created_at`, `updated_at`. Relationships: `tags` → DockerImageTag (cascade delete), `sync_logs` → DockerSyncLog (cascade delete).
- [`backend/app/models/docker_image_tag.py`](../backend/app/models/docker_image_tag.py) — модель `DockerImageTag`: тег Docker-образа с полями `source_id` (FK → docker_image_sources, CASCADE), `image_name` (indexed), `tag`, `digest` (SHA-256), `size_bytes`, `architectures` (JSON Text), `status_flag`/`status_text`, `is_synced` (bool), `last_synced_at`, `created_at`. Relationship: `source` → DockerImageSource.
- [`backend/app/models/docker_sync_log.py`](../backend/app/models/docker_sync_log.py) — модель `DockerSyncLog`: лог синхронизации с полями `source_id` (FK → docker_image_sources, CASCADE), `pipeline_id`, `pipeline_url`, `status_flag`/`status_text`, `log_output`, `triggered_by` (scheduler/manual/webhook), `started_at`, `finished_at`, `created_at`. Relationship: `source` → DockerImageSource.
- [`backend/alembic/versions/20260605_1200_add_docker_tables.py`](../backend/alembic/versions/20260605_1200_add_docker_tables.py) — миграция, создающая 3 таблицы: `docker_image_sources`, `docker_image_tags`, `docker_sync_logs` со всеми индексами (`down_revision = '39774f94ac35'`, `revision = 'add_docker_tables'`).

**Backend — схемы + сервис + API (Pt 18):**
- [`backend/app/schemas/docker.py`](../backend/app/schemas/docker.py) — Pydantic v2 схемы: `DockerImageSourceOut`, `DockerImageSourceDetailOut` (с вложенным списком tags), `DockerImageTagOut`, `DockerSyncLogOut`, `CreateDockerImageSourceRequest` (name, registry_url, description, с опциональным image_name для немедленной индексации), `UpdateDockerImageSourceRequest`.
- [`backend/app/services/docker.py`](../backend/app/services/docker.py) — класс `DockerRegistryService` (синглтон `docker_service`). Методы: `import_source_from_url()` (создание + опциональная индексация), `index_source()` (GET /v2/<image>/tags/list → HEAD /v2/<image>/manifests/<tag> для digest), `refresh_source()`, `_fetch_tags()` (httpx AsyncClient), `_resolve_manifest_digest()` (HEAD-запрос, digest из `docker-content-digest`), `_sync_tags()` (upsert по source_id + image_name + tag). Хелперы: `_normalize_registry_url()` (добавляет /v2), `_validate_registry_url()`. Исключения: `BadRequestError`, `ExternalServiceError`. Зависимости: `httpx`.
- [`backend/app/api/docker_images.py`](../backend/app/api/docker_images.py) — APIRouter с эндпоинтами (RBAC: чтение — `require_viewer`, изменение — `require_operator`): `GET /api/docker-images`, `GET /api/docker-images/{id}`, `POST /api/docker-images`, `PATCH /api/docker-images/{id}`, `DELETE /api/docker-images/{id}`, `POST /api/docker-images/{id}/index?image_name=...`, `GET /api/docker-images/{id}/tags`, `GET /api/docker-images/{id}/logs`.

**GitLab CI (Pt 19, покрывает также задачи 20–21):**
- [`gitlab-ci/docker-sync-template.yml`](../gitlab-ci/docker-sync-template.yml) — CI-шаблон синхронизации Docker-образов. Stages: `sync`, `notify`. Job `docker-sync` (образ `docker:27-dind`: тянет теги из registry). Job `notify-failure`. CI-переменные: `DOCKER_REGISTRY_URL`, `DOCKER_IMAGE_NAME`, `DOCKER_REGISTRY_USER`/`DOCKER_REGISTRY_PASS`, `BIGBUG_WEBHOOK_URL`/`BIGBUG_WEBHOOK_TOKEN`, `SYNC_STRATEGY`, `TAG_FILTER`, `TAG_LIMIT`.

**Расширение webhook (Pt 22):**
- [`backend/app/api/webhooks.py`](../backend/app/api/webhooks.py) — добавлен 4-й обработчик типа лога (`DockerSyncLog`) после helm-блока: поиск по `pipeline_id`, обновление `status_flag`/`status_text`/`pipeline_url`, `finished_at` и `last_synced_at` родительского `DockerImageSource` при success.

**Изменённые файлы:**
| Файл | Изменение |
|------|-----------|
| [`backend/app/models/__init__.py`](../backend/app/models/__init__.py) | Добавлены импорты и в `__all__`: `DockerImageSource`, `DockerImageTag`, `DockerSyncLog`. |
| [`backend/app/main.py`](../backend/app/main.py) | Импорт и регистрация роутера `docker_images` с `prefix="/api/docker-images"`, `tags=["docker-images"]`. |
| [`backend/app/api/webhooks.py`](../backend/app/api/webhooks.py) | Добавлен 4-й обработчик типа лога (`DockerSyncLog`): поиск по `pipeline_id`, обновление полей, `DockerImageSource.last_synced_at` при success. |

### Блок 5 — Frontend UI (задачи 23–26)

**TypeScript-типы (Pt 23):**
- [`frontend/src/types/index.ts`](../frontend/src/types/index.ts) — добавлены интерфейсы: `HelmChartSource`, `HelmChartSourceDetail`, `HelmChartVersion`, `HelmSyncLog`, `DockerImageSource`, `DockerImageSourceDetail`, `DockerImageTag`, `DockerSyncLog`. Поля точно соответствуют Pydantic-схемам бэкенда.

**Store — RTK Query (Pt 23):**
- [`frontend/src/store/api.ts`](../frontend/src/store/api.ts) — добавлены `tagTypes`: `HelmChart`, `DockerImage`. Добавлено 16 эндпоинтов (CRUD + index + versions/tags + logs для обоих ресурсов). Экспортированы хуки: `useListHelmChartsQuery`, `useGetHelmChartQuery`, `useCreateHelmChartMutation`, `useUpdateHelmChartMutation`, `useDeleteHelmChartMutation`, `useIndexHelmChartMutation`, `useGetHelmChartVersionsQuery`, `useGetHelmChartLogsQuery` и аналогичные для Docker (`...DockerImage...`). Эндпоинт индексации Docker передаёт `image_name` как query-параметр.

**Страницы Helm Charts (Pt 24):**
- [`frontend/src/pages/HelmCharts/index.tsx`](../frontend/src/pages/HelmCharts/index.tsx) — список источников чартов (таблица: Name, Repo URL, Last Synced, Status, Actions). Диалог создания (name, repo_url, description). Кнопка Re-index в строке. Паттерн скопирован с `Mirrors/index.tsx`.
- [`frontend/src/pages/HelmCharts/HelmChartDetail.tsx`](../frontend/src/pages/HelmCharts/HelmChartDetail.tsx) — карточка Source Info (status, repo_url, description, last_synced, GitLab project), таблица версий чарта (Chart, Version, App Version, Status + индикатор Synced), таблица истории синхронизации. Кнопки Re-index и Open Repo.

**Страницы Docker Images (Pt 25):**
- [`frontend/src/pages/DockerImages/index.tsx`](../frontend/src/pages/DockerImages/index.tsx) — список источников образов (таблица). Диалог создания (name, registry_url, image_name опционально, description).
- [`frontend/src/pages/DockerImages/DockerImageDetail.tsx`](../frontend/src/pages/DockerImages/DockerImageDetail.tsx) — карточка Source Info, таблица тегов (Image, Tag, Architecture, Size с форматированием байт, Status), история синхронизации. Диалог "Index Image" с вводом имени образа (т.к. бэкенд требует `image_name` для индексации). Кнопки Index Image и Open Registry.

**Роутер + меню (Pt 26):**
- [`frontend/src/router/index.tsx`](../frontend/src/router/index.tsx) — добавлены маршруты `/helm-charts`, `/helm-charts/:id`, `/docker-images`, `/docker-images/:id`.
- [`frontend/src/components/Layout/index.tsx`](../frontend/src/components/Layout/index.tsx) — добавлены пункты меню "Helm Charts" (иконка `Sailing`) и "Docker Images" (иконка `Dock`).

---

## 2. Ключевые архитектурные решения

### Именование переменных окружения
- Все env-переменные Keycloak унифицированы с префиксом `KEYCLOAK_`.
- Pydantic Settings маппит `keycloak_frontend_client_id` → `KEYCLOAK_FRONTEND_CLIENT_ID`.
- В `.env.example` и `init-keycloak.sh` используется единое имя `KEYCLOAK_FRONTEND_CLIENT_ID`.

### Разделение БД
- `postgres-backend` (порт 5432) — для Alembic-схемы backend.
- `postgres-keycloak` (порт 5433) — для схемы Keycloak.
- Причина: разное владение схемами, независимые бэкапы, соответствие production-топологии.

### Гибридная аутентификация
- Локальные пользователи: `username` + `hashed_password` (не nullable, но может быть NULL для SSO).
- SSO пользователи: `keycloak_sub` связывает с Keycloak-identity, `hashed_password = NULL`.
- Обе группы в одной таблице `users`.
- Роли синхронизируются из `realm_access.roles` Keycloak-токена.

### Фреймворк-независимый сервисный слой
- OIDC-сервис выбрасывает доменные `RuntimeError` (не `HTTPException`).
- HTTP-слой (роутер) маппит их на статус-коды.
- `_NonClosingClient` позволяет инъектить тестовые httpx-клиенты.

### PKCE S256
- Фронтенд генерирует `code_verifier` (64 случайных байта) и `code_challenge` (SHA-256).
- `code_verifier` хранится в `sessionStorage` между редиректами.
- Бэкенд передаёт `code_verifier` в Keycloak token endpoint при обмене кода.
- Keycloak-клиент `bigbug-frontend` создан как public client с обязательным PKCE S256.

### Fernet для секретов
- `encrypt_secret()` / `decrypt_secret()` для Helm/Docker registry-паролей.
- `None`-safe: пустые строки и `None` проходят прозрачно.
- `SecretCipher` спроектирован для будущего перехода на `MultiFernet` (ротация ключей).

### Helm-чарты как источники (аналогия с GitHub)
- `HelmChartSource` / `HelmChartVersion` спроектированы по аналогии с GitHub-моделями (`GithubOrg` → `GithubProject` → `GithubRelease`), но для Helm-репозиториев.
- Сервис парсит `index.yaml` напрямую через httpx + PyYAML — не требует внешнего бинарника `helm` в backend.
- `_sync_chart_entries()` выполняет upsert по `(source_id, chart_name, version)` — повторные индексации идемпотентны.

### Расширение webhook четырьмя типами логов
- Webhook-обработчик теперь поддерживает четыре типа логов: `sync_log` (gitlab mirror), `build_log` (docker build), `helm_sync_log` (helm chart sync), `docker_sync_log` (docker image sync).
- Для каждого типа — свой поиск и своя логика обновления родительской сущности.

### PyYAML в зависимостях
- `PyYAML` добавлен для парсинга `index.yaml` в [`HelmService`](../backend/app/services/helm.py). Используется `yaml.safe_load()` — безопасный парсер (только базовые типы Python, без произвольных объектов).

---

## 3. Что осталось (задачи 27–31)

### Блок 6 — Тесты, инфраструктура, документация (Pt 27–31)
- Backend тесты: OIDC, Helm sources, Docker client, Secrets, API.
- Frontend тесты: keycloak service, useKeycloakAuth hook, компоненты.
- Папка `harbor/` — скрипты для развёртывания Harbor в kind.
- CHANGELOG.md и README.md.

---

## 4. Рабочее окружение

### Python
```bash
cd /home/vnosov/Projects/BigBug/backend
source .venv/bin/activate
```
Зависимости: FastAPI, SQLAlchemy 2.x (async), Alembic, httpx, python-jose[cryptography], cryptography, passlib[bcrypt], psycopg2-binary, asyncpg, pydantic-settings.

### Node.js
```bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
cd /home/vnosov/Projects/BigBug/frontend
```
Node.js v24.16.0 (LTS), Yarn 4.3.1, зависимости установлены.
Команды: `yarn dev`, `npx tsc --noEmit`, `yarn build`, `yarn test`.

### TypeScript-проверка
```bash
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && cd /home/vnosov/Projects/BigBug/frontend && npx tsc --noEmit
```
Текущий статус: 0 ошибок.

---

## 5. Паттерны кода, которые нужно соблюдать

1. **Модели:** SQLAlchemy 2.0 Column-стиль. Каждая модель — отдельный файл в `backend/app/models/`. Регистрировать в `__init__.py`. Миграция — отдельный файл в `alembic/versions/`.

2. **Схемы:** Pydantic v2, отдельные файлы в `backend/app/schemas/`.

3. **Сервисы:** Класс в `backend/app/services/`. Доменные исключения — plain `RuntimeError` подклассы (не HTTPException). HTTPException — только в API-слое.

4. **API:** Роутер через `APIRouter()`. Регистрация в [`backend/app/main.py`](../backend/app/main.py) через `app.include_router()`.

5. **Фронтенд — страницы:** Компонент в `frontend/src/pages/Имя/`. Экспорт через `index.tsx`.

6. **Фронтенд — store:** Эндпоинты в [`frontend/src/store/api.ts`](../frontend/src/store/api.ts). Хуки экспортируются внизу файла.

7. **Фронтенд — роутинг:** Маршруты в [`frontend/src/router/index.tsx`](../frontend/src/router/index.tsx). Меню — в [`Layout`](../frontend/src/components/Layout/index.tsx).

8. **Шифрование:** Для registry-паролей использовать `encrypt_secret()` / `decrypt_secret()` из [`backend/app/core/secrets.py`](../backend/app/core/secrets.py).

9. **RBAC:** `require_roles()` декоратор из [`backend/app/core/rbac.py`](../backend/app/core/rbac.py:44). Роли: `admin`, `operator`, `viewer`.

---

## 6. Известные нестандартные решения

- `keycloak-js` 24.x не типизирует `codeChallenge` в `KeycloakLoginOptions` → URL для PKCE строится вручную в [`frontend/src/services/keycloak.ts`](../frontend/src/services/keycloak.ts).
- `_NonClosingClient` в [`oidc.py`](../backend/app/services/oidc.py:313) — костыль для тестирования. `_client()` возвращает `AbstractAsyncContextManager`, а не `AsyncClient`.
- `Column` типы в SQLAlchemy иногда дают false-positive в Pylance → используется `# type: ignore[assignment]` или `# type: ignore[comparison-overlap]`.
- `select(Role).where(False)` не работает в SQLAlchemy → используется условное ветвление.

---

## 7. Порядок продолжения

Рекомендуемый порядок: **27 → 28 → 29 → 30 → 31**.

Оставшиеся задачи: тесты (backend + frontend), инфраструктура Harbor, документация.
