# Спецификация: починка импорта Docker-образа (Docker Hub → Harbor)

Статус: спроектировано (architect), к реализации в code-режиме.
Контекст: debug-агент локализовал 5 дефектов; все точки правок проверены по коду на 2026-08-17.

---

## Дефект 1 — Source/Target разделение + Harbor system-провайдер

### 1.1 Backend: analyze-ответ с двумя списками

Файл: [`backend/app/api/docker_images.py`](backend/app/api/docker_images.py)

- Новая service-функция в [`backend/app/services/docker.py`](backend/app/services/docker.py) рядом с [`get_compatible_docker_providers()`](backend/app/services/docker.py:252):

```python
async def get_internal_docker_targets(db: AsyncSession) -> list[ResourceProvider]
```

Выборка: `domain == docker`, `is_active`, не удалён, `direction == ProviderDirection.internal`,
`subtype in (harbor, generic_registry)`. Сортировка `(-priority, name)`.
Существующий fallback «external» в `get_compatible_docker_providers` (строка 278) оставить — он корректен для source-семантики; обновить только docstring («can serve as the **source**»).

- [`AnalyzeImageResponse`](backend/app/api/docker_images.py:520) — расширить полями:

```python
available_targets: list[ProviderOut] = []
repository_path: str          # чистый repo path без host/тега (см. дефект 2)
```

- В [`analyze_image`](backend/app/api/docker_images.py:531): вызвать `get_internal_docker_targets(db)`, заполнить `available_targets` и `repository_path=repository_path_from_ref(image_name)`.
- Схемы [`CreateDockerImageSourceRequest`](backend/app/schemas/docker.py:82)/[`UpdateDockerImageSourceRequest`](backend/app/schemas/docker.py:93) и `import_source_from_url` уже принимают target-поля — **не менять**.

### 1.2 Нормализация image_name при создании source

В [`import_source_from_url`](backend/app/services/docker.py:290): если передан `image_name` —
прогнать через `repository_path_from_ref()` до записи в `DockerImageSource.image_name`.
API становится толерантным к canonical ref от старых клиентов.

### 1.3 Harbor system-провайдер: расширение seed_providers.py

**Решение: расширить [`backend/scripts/seed_providers.py`](backend/scripts/seed_providers.py), отдельная секция «system providers», НЕ миграция.**
Обоснование: credential нужно шифровать Fernet через app-контекст; миграции с секретами — анти-паттерн;
upsert-by-name уже идиома скрипта; [`entrypoint.sh`](backend/docker/entrypoint.sh:123) уже вызывает его идемпотентно на каждом старте (правок entrypoint ноль).

Новая секция в скрипте — `seed_system_providers(session)`:

- Гейт: если `HARBOR_URL` не задан → `log INFO "HARBOR_URL not set — skipping system Harbor provider"` и выход (существующие окружения не ломаются).
- Env-переменные (добавить в [`.env.example`](.env.example) и backend compose env):

| Переменная | Назначение | Default |
|---|---|---|
| `HARBOR_URL` | base_url провайдера, напр. `https://harbor.local:443` | — (гейт) |
| `HARBOR_USERNAME` | robot-аккаунт (`robot$bigbug+mirror`) или admin | — |
| `HARBOR_PASSWORD` | secret robot-аккаунта / пароль admin | — |
| `HARBOR_DEFAULT_PROJECT` | Harbor-проект для mirror по умолчанию | `library` |
| `HARBOR_VERIFY_SSL` | `false` для self-signed `harbor.local` | `true` |
| `HARBOR_PROJECTS_ALLOWLIST` | CSV доп. проектов | пусто |

- Создаёт/апдейтит `Credential` (upsert по `name = "harbor-system-credential"`):
  `credential_type=https_basic`, `provider="harbor"`, `username=HARBOR_USERNAME`,
  `encrypted_secret=encrypt_secret(HARBOR_PASSWORD)` ([`app.core.secrets`](backend/app/core/secrets.py)).
- Создаёт/апдейтит `ResourceProvider` (upsert по `name = "harbor-system"`):
  `domain=docker, subtype=harbor, category=system, direction=internal, visibility=public`,
  `base_url=HARBOR_URL`, `credential_id=<credential>`, `is_protected=True, is_default=True`,
  `verify_ssl=HARBOR_VERIFY_SSL`,
  `config={"default_project": ..., "robot_prefix": "robot$", "projects_allowlist": [...]}` —
  ровно под schema реестра [`registry.py:246-256`](backend/app/services/providers/registry.py:246).
- Сид-владение полями: у system-провайдера сид владеет `label/is_default/is_protected/base_url/config/verify_ssl/credential_id` (в отличие от public-секции) — секрет ротируется из env при каждом запуске.
- Robot-аккаунт: создаётся админом Harbor (UI/API) с push в `HARBOR_DEFAULT_PROJECT`; dev-альтернатива — admin из [`terraform.tfvars.example:46`](infrastructure/terraform/terraform.tfvars.example:46). Keycloak OIDC для людей к mirror-пути отношения не имеет.

### 1.4 Frontend: два селекта

Файл [`frontend/src/pages/DockerImages/index.tsx`](frontend/src/pages/DockerImages/index.tsx):

- Тип [`AnalyzeImageResponse`](frontend/src/types/index.ts:547): добавить `available_targets: ResourceProvider[]`, `repository_path: string`, `suggested_target: ResourceProvider | null`.
- Текущий селект (строки 365–373) переименовать в **«Source Registry»** (помощь: «Registry to pull tags from»), данные из `compatible_registries` как сейчас.
- Новый блок **«Mirror Target»**: `Select` из `analysis.available_targets` (`label` + тег subtype), состояние `selectedTargetId`, дефолт — единственный элемент или `suggested_target`. Под ним — `Input` «Target Project» с default из `selectedTarget?.config?.default_project`.
- [`handleCreate()`](frontend/src/pages/DockerImages/index.tsx:90) передавать:
  `provider_id: selectedRegistryId`, `target_provider_id: selectedTargetId`,
  `target_registry_url: selectedTarget?.base_url`, `target_project`,
  `image_name: analysis.repository_path` (НЕ `normalized_image` — это canonical ref с host и тегом),
  `registry_url: selectedRegistry?.base_url ?? 'https://' + analysis.detected_registry_host`.
- Если `available_targets` пуст → предупреждение (`Alert title=`, не `message`!) «No internal Harbor target configured — mirroring will be unavailable» и кнопка Create остаётся активной (mirror опционален).

---

## Дефект 2 — repository path vs canonical ref

### Helper в [`backend/app/services/docker.py`](backend/app/services/docker.py) (рядом с `parse_registry_from_image`):

```python
def repository_path_from_ref(image_name: str) -> str:
    """nginx -> library/nginx; registry-1.docker.io/library/nginx:latest -> library/nginx."""

def ref_tag(image_name: str) -> str:
    """Извлечь тег (default 'latest'); digest-ref -> 'latest' (тег неактуален)."""
```

Правила `repository_path_from_ref`:
1. `strip()`; отрезать digest: `split("@")[0]`; отрезать тег только после последнего `/` (`rsplit("/",1)`, затем `rsplit(":",1)` если в хвосте есть `:` и это не порт — порт отсекается вместе с host на шаге 2).
2. `parts = ref.split("/")`; если `parts[0]` содержит `.` или `:` или `== "localhost"` → это host, отбросить.
3. Если остался 1 сегмент и registry — Docker Hub → префикс `library/`.
4. Вернуть путь без host и тега.

Таблица вход → выход:

| Вход | Выход |
|---|---|
| `nginx` | `library/nginx` |
| `library/nginx` | `library/nginx` |
| `nginx:1.25` | `library/nginx` |
| `docker.io/library/nginx:1.25` | `library/nginx` |
| `registry-1.docker.io/library/nginx:latest` | `library/nginx` |
| `quay.io/prom/node-exporter:v1.0` | `prom/node-exporter` |
| `harbor.local:443/bigbug/nginx` | `bigbug/nginx` |
| `ghcr.io/org/img@sha256:abc` | `org/img` |

Точки применения (все в [`docker.py`](backend/app/services/docker.py)):
- [`_fetch_tags`](backend/app/services/docker.py:419): `repo = repository_path_from_ref(image_name)`; `tags_url = f"{base_url}/{repo}/tags/list"` (base_url уже с `/v2`).
- [`_resolve_manifest_digest`](backend/app/services/docker.py:449): то же для `manifests/{tag}`.
- [`mirror_image`](backend/app/services/docker.py:535): `repo = repository_path_from_ref(image_name)`; тег из параметра/`ref_tag()`.
- `import_source_from_url` (см. 1.2).

---

## Дефект 3 — OCI/Docker Hub token handshake

### Новый файл `backend/app/services/providers/clients/docker_auth.py`

Скучное явное решение вместо хитрого `httpx.Auth` (retry руками, максимум 1 повтор):

```python
def parse_bearer_challenge(header: str) -> dict[str, str]   # realm, service, scope
def scope_for_url(path: str, actions: str = "pull") -> str  # /v2/<repo>/… -> "repository:<repo>:pull"

class TokenCache:  # ponytail: простой dict c TTL 300s без LRU; апгрейд — настоящий кэш при росте
    def get(self, service: str, scope: str) -> str | None
    def put(self, service: str, scope: str, token: str) -> None

async def fetch_token(client, realm: str, service: str, scope: str,
                      basic: tuple[str, str] | None = None) -> str

async def oci_request(client: httpx.AsyncClient, method: str, url: str, *,
                      basic: tuple[str, str] | None = None,
                      headers: dict | None = None,
                      scope_actions: str = "pull",
                      cache: TokenCache | None = None) -> httpx.Response
```

Поведение `oci_request`:
1. Отправить запрос; если есть `basic` — Basic-заголовок сразу (Harbor отвечает 200, flow завершён).
2. Если 401 и есть `WWW-Authenticate: Bearer realm=…,service=…[,scope=…]`:
   - scope из challenge, иначе вычислить `scope_for_url` из пути;
   - токен из кэша, иначе `fetch_token` (realm GET `?service=&scope=`, при наличии creds — Basic на realm тоже);
   - повторить исходный запрос с `Authorization: Bearer …` ровно один раз.
3. Вернуть финальный `Response` (статус проверяет вызывающий). Не-401 ошибки — как есть.
4. Если 401 без Bearer-challenge и creds нет → вернуть 401 (вызывающий мапнит в понятную ошибку по паттерну [`service.py:515`](backend/app/services/providers/service.py:515)).

Docker Hub specifics: realm `https://auth.docker.io/token`, service `registry.docker.io` — ничего хардкодить не нужно, всё из challenge.

### Интеграция

- [`DockerRegistryClient`](backend/app/services/providers/clients/docker_registry.py:28): `list_tags`/`list_repositories`/`test_connection` — вместо голого `client.get` вызывать `oci_request(self._client().__enter__…)`; `basic=(username, secret)` если оба есть. `test_connection` при этом честно проверяет handshake (401+challenge → ok/anonymous).
- [`_fetch_tags`](backend/app/services/docker.py:419): credentials из source-провайдера: `source.provider_id → ResourceProvider.credential_id → Credential` (расшифровка по паттерну [`_decrypt_credential_secret`](backend/app/services/providers/service.py:539)); нет провайдера/credential → анонимно. `verify_ssl` брать из провайдера.
- `_resolve_manifest_digest` — тот же `oci_request` + `scope_actions="pull"`.
- Реюз для Harbor: robot-creds → `basic` → шаг 1 сразу 200; если Harbor за Bearer — тот же flow. Один helper на оба.

---

## Дефект 4 — зеркалирование: рекомендация **crane**

### Обоснование (ленивый senior)

Нативный OCI copy = manifest list/index traversal, HEAD blob existence, chunked/monolithic POST uploads, docker schema v2 + OCI manifest + attestations, retry на каждый blob. Это ~250+ строк тонкого кода и рассадник багов. `crane copy` — один вызов существующего subprocess-кода ([строки 585–592 уже написаны](backend/app/services/docker.py:585)), статический бинарник ~15MB, обрабатывает auth/manifest-типы/ретраи сам. Дифф: ~15 строк Dockerfile + ~20 строк Python. Ущерб от «ещё одной зависимости» — один статический бинарник без transitive-deps.

### 4.1 Dockerfile ([`backend/docker/Dockerfile`](backend/docker/Dockerfile))

В runtime-стадию (после строки 85):

```dockerfile
ARG CRANE_VERSION=v0.20.2   # go-containerregistry release; зафиксировать актуальный тег при реализации
RUN curl -fsSL "https://github.com/google/go-containerregistry/releases/download/${CRANE_VERSION}/go-containerregistry_Linux_x86_64.tar.gz" \
    | tar -xz -C /usr/local/bin crane \
    && /usr/local/bin/crane version >/dev/null 2>&1 || true
```

(архи x86_64; tar содержит `crane`; проверить имя тарбола по релизу; checksum-верификация опциональна, отметить в PR.)

### 4.2 mirror_image — правки в [`docker.py:535`](backend/app/services/docker.py:535)

1. **Refs без `/v2`**: `source.registry_url` нормализован с `/v2` ([строка 311](backend/app/services/docker.py:311)) → добавить helper `_registry_root(url) -> url без хвостового /v2`; `source_ref = f"{_registry_root(source.registry_url)}/{repo}:{tag}"`.
2. **repo path**: `repo = repository_path_from_ref(image_name)`; для target отрезать `library/`-префикс (неймспейс Docker Hub — шум в Harbor): `target_repo = repo.removeprefix("library/")`; `target_ref = f"{_registry_root(target_url)}/{source.target_project or 'library'}/{target_repo}:{tag}"`.
3. **Creds target**: `source.target_provider_id → ResourceProvider → credential_id → Credential` → `username + decrypt_secret`; НЕ через argv (`--dest-creds` виден в `ps`) → временный `docker config.json` (`{"auths": {host: {"auth": base64(user:pass)}}}`) в `tempfile` 0600, env `DOCKER_CONFIG=<dir>` для subprocess, удалить в `finally`. Источник (Docker Hub) — анонимно; при наличии source-credential — второй auths-ключ в том же файле (crane сам выберет по host).
4. **Self-signed target**: если у target-провайдера `verify_ssl=False` → флаг `--insecure`.
5. **Graceful degradation**: `FileNotFoundError` при exec crane → `ExternalServiceError("crane", "crane binary is not installed in the backend image; rebuild backend/docker/Dockerfile")` вместо 500.
6. `log.log_output` — уже пишется в БД, не трогать; таймаут `asyncio.wait_for(process.communicate(), timeout=1800)` c пометкой `ponytail:` (одиночный образ; апгрейд — очередь задач).

---

## Дефект 5 — Frontend mirror

### 5.1 Mutation ([`frontend/src/store/api/docker-images.ts`](frontend/src/store/api/docker-images.ts))

Рядом с [`indexDockerImage`](frontend/src/store/api/docker-images.ts:57):

```typescript
mirrorDockerImage: builder.mutation<DockerSyncLog, { id: number; image_name: string; tag: string }>({
  query: ({ id, image_name, tag }) => ({
    url: `/docker-images/${id}/mirror?image_name=${encodeURIComponent(image_name)}&tag=${encodeURIComponent(tag)}`,
    method: 'POST',
  }),
  invalidatesTags: (_r, _e, { id }) => [{ type: 'DockerImage', id }, 'DockerImage'],
}),
```

Экспорт хука `useMirrorDockerImageMutation`. `DockerSyncLog`-тип уже есть.

### 5.2 Кнопка + диалог ([`DockerImageDetail.tsx`](frontend/src/pages/DockerImages/DockerImageDetail.tsx:439))

- Кнопка «Mirror» рядом с Index (иконка `CloudUploadOutlined`), обёрнута в `<PermissionGate permission="docker:sync">`.
- `disabled={!s.target_registry_url}` + Tooltip «No mirror target configured on this source».
- Модал: `Select` тега (options из `s.tags`, `defaultValue='latest'` если теги не загружены), текст «Mirror `{repo}:{tag}` → `{s.target_registry_url}/{s.target_project}`».
- Сабмит: `mirrorDockerImage({ id: s.id, image_name: <repository path>, tag })`; `message.success('Mirror started')` по статусу лога; ошибки — `Alert title=` (правило antd: только `title`, не `message`).
- invalidatesTags перечитает detail → теги покажут `is_synced`, логи обновятся.

---

## Тесты (состав для code-режима)

### Backend unit (`make test-unit-backend`)

Расширить [`tests/unit/test_docker_service.py`](backend/tests/unit/test_docker_service.py):
- `repository_path_from_ref` — параметризованная таблица из дефекта 2 (+кейсы: пустой хвост после host → `""` → BadRequest; uppercase host).
- `ref_tag` — тег, digest-ref, default latest.
- `_fetch_tags` через `httpx.MockTransport`: assert URL `/v2/library/nginx/tags/list` при входе canonical ref; 401→token→200 flow; 404 → ExternalServiceError.
- `_resolve_manifest_digest` — нормализация + Bearer retry.
- `get_internal_docker_targets` — фильтр internal/harbor/generic_registry, сортировка (in-memory DB, существующий конвент conftest).
- `mirror_image` — monkeypatch `asyncio.create_subprocess_exec`: assert argv (refs без `/v2`, `--insecure` при verify_ssl=False), env DOCKER_CONFIG создан/удалён, rc=0 → tag synced, rc≠0 → failed; FileNotFoundError → ExternalServiceError.

Новый `tests/unit/test_docker_auth.py`:
- `parse_bearer_challenge` (realm/service/scope, quoted values);
- `scope_for_url`;
- `oci_request` на MockTransport: Basic-200 без handshake; анонимный 401→token→200; кэш второго вызова (1 запрос токена); 401 без challenge → прокинут.
- `fetch_token` с Basic на realm.

Расширить [`tests/unit/test_provider_clients_docker.py`](backend/tests/unit/test_provider_clients_docker.py):
- `list_tags`/`test_connection` через анонимный handshake; Harbor Basic.

Расширить [`tests/unit/test_seed_providers.py`](backend/tests/unit/test_seed_providers.py):
- без HARBOR_URL → skip; с env → upsert провайдера+credential, `encrypt→decrypt` roundtrip, повторный запуск идемпотентен, config schema совпадает с реестром.

### Backend e2e (`make test-e2e-backend`)

Новый `tests/e2e/test_docker_import_flow.py` (dev-стек): analyze (возвращает `available_targets` после сида harbor) → create source (target_provider_id) → index (теги nginx реального Docker Hub; при отсутствии сети — skip) → mirror (crane; при отсутствии бинарника — skip с явной причиной). Проверки статусов DockerSyncLog.

### Frontend integrations (`make test-integrations-frontend`)

Новый `src/tests/integrations/DockerImagesCreate.test.tsx`:
- analyze-мок возвращает compatible_registries + available_targets → рендерятся оба селекта;
- выбор source+target → payload create содержит `provider_id`, `target_provider_id`, `target_registry_url`, `target_project`, `image_name === repository_path`;
- пустой available_targets → предупреждение.

Новый `src/tests/integrations/DockerImageDetailMirror.test.tsx`:
- кнопка Mirror за PermissionGate с `docker:sync`;
- источник без target → disabled;
- диалог: выбор тега → вызов mutation с правильным query → успех/refetch.

---

## Порядок реализации (code-режим)

1. `repository_path_from_ref`/`ref_tag` + применение в `_fetch_tags`/`_resolve_manifest_digest` (закрывает 404).
2. `docker_auth.py` (handshake) + интеграция в `DockerRegistryClient` и `_fetch_tags` (закрывает 401).
3. `get_internal_docker_targets` + analyze-поля + нормализация в `import_source_from_url` (дефект 1 backend).
4. `seed_providers.py` system-секция + `.env.example` (дефект 1 infra).
5. `mirror_image`: refs/creds/`--insecure`/graceful-crane + `Dockerfile` crane (дефект 4).
6. Frontend: types + mutation + два селекта + кнопка Mirror (дефекты 1/5).
7. Backend тесты (unit → e2e), frontend тесты.
8. `CHANGELOG.md` (Added/Fixed); [`plans/architecture/permissions.md`](plans/architecture/permissions.md) — без изменений (новых permissions нет: docker:read/write/sync существуют); прогон `make lint typecheck dead-code`.

## Edge-cases, зафиксированные в дизайне

- registry_url с `/v2` → crane refs через `_registry_root`.
- `library/`-префикс отрезается в target repo, сохраняется в source path.
- Тег в `image_name` от frontend игнорируется для tags/list; digest-ref → тег неактуален (`ref_tag` → latest, mirror по digest не поддерживается — отметить `ponytail:`).
- Токен-кэш per-(service, scope) TTL 300s.
- Harbor self-signed: `verify_ssl=False` из провайдера и `--insecure` для crane.
- Секреты: не в argv, не в логах; временный DOCKER_CONFIG 0600 + finally-delete.
