---
status: accepted
date: 2026-10-22
decision-makers: SteeveRan
---

# Helm chart приложения BigBug: backend + frontend, external postgres/redis

## Context and Problem Statement

Приложение BigBug (backend FastAPI + frontend React) сейчас запускается в dev через корневой `docker-compose.yml` (bind-mount + uvicorn `--reload` / `yarn dev`). Целевая среда — Kubernetes ([ADR-0022](0022-dev-stand-on-kind.md)): dev-стенд переезжает в kind-кластер `bigbug-dev`, и для запуска приложения в нём нужен helm chart. Тот же chart станет основой prod-деплоя.

Вопрос: **каким должен быть собственный chart приложения BigBug**, чтобы покрыть dev (kind) и будущий prod, не создавая две несовместимые схемы?

## Decision Drivers

- Единый chart для dev и prod: различия — только в values, не в шаблонах
- PostgreSQL и Redis в dev живут через операторы CNPG/redis-operator ([ADR-0022](0022-dev-stand-on-kind.md)) — chart приложения не должен тащить собственные БД
- Hot-reload в dev: правка кода должна попадать в под без пересборки образа
- Порядок старта: БД должны быть готовы до старта backend; миграции Alembic применяются автоматически ([ADR-0006](../backend/0006-database-postgresql-alembic.md))
- Драйвер минимализма (ADR-0001): без HA, без service mesh, без операторов внутри chart'а

## Considered Options

* Собственный chart: backend + frontend Deployments, external-only postgres/redis; dev-режим — Vite dev-сервер, https- ingress (hot-reload hostPath вырезан — §3)
* Chart со встроенными subchart'ами БД (bitnami postgresql/redis)
* Chart с собственными STS postgres/redis (dual-mode: internal STS в dev, external в prod)
* Kustomize-манифесты вместо helm

## Decision Outcome

Chosen option: **собственный chart `charts/bigbug` — external-only postgres/redis**. Chart содержит только само приложение: backend Deployment, frontend Deployment (nginx), Services, Ingress. PostgreSQL и Redis — всегда external: host/credentials приходят из values и k8s Secret'ов (в dev их создаёт CNPG-оператор и tofu — [ADR-0024](../common/0024-k8s-secrets.md); в prod — те же операторы или managed-сервисы).

### Зафиксированные правила

**1. Состав chart** (`charts/bigbug/`):

| Шаблон | Назначение |
|---|---|
| `backend-deployment.yaml` | FastAPI backend, 1 реплика, probes (`/api/health` — health-route смонтирована под `/api` префиксом), env из Secret/ConfigMap |
| `frontend-deployment.yaml` | nginx со статикой React-сборки, 1 реплика |
| `backend-service.yaml`, `frontend-service.yaml` | ClusterIP Services |
| `ingress.yaml` | хосты `api.local` (backend) и `app.local` (frontend), класс ingress-контроллера из values |
| `migrate-job.yaml` | Helm `pre-install,pre-upgrade` hook: Job с `alembic upgrade head` (наследует entrypoint-логику `app:init`) |
| `_helpers.tpl`, `values.yaml`, `values-dev.yaml` | стандартная структура |

**2. External-only БД** — никаких subchart'ов и встроенных STS. Connection-параметры:

- `DATABASE_URL` приходит в backend **целиком** из секрета `bigbug-db-credentials` (создаёт tofu — [ADR-0024](../common/0024-k8s-secrets.md): проекция CNPG-секрета `<cluster>-app`, там же username/password/host/port). URL не собирается в шаблонах.
- `REDIS_URL` собирается в `_helpers.tpl` из values (`redis.host/port/db`).
- Секретные env — только через `secretKeyRef` (fitness-критерий [ADR-0024](../common/0024-k8s-secrets.md)).

**3. Dev-режим** (`values-dev.yaml`): образы dev-сборки; backend запускает uvicorn с `--proxy-headers` (за TLS-terminating ingress, [ADR-0030](0030-dev-stand-https-self-signed-certs.md)), frontend — dev-сервер Vite (в dev frontend-под — Node, не nginx) с HMR через `wss` (`server.hmr.protocol: wss`, `clientPort: 443` — ingress терминирует TLS, браузер ходит по `https://app.local`). Backend env включает `REQUESTS_CA_BUNDLE`/`SSL_CERT_FILE` (маунт self-signed сертов стенда — ADR-0030 §4) и `CORS_ORIGINS` (ConfigMap; ADR-0028 §3). В prod-values — обычные образы.
**Hot-reload через hostPath-маунты ворктрия вырезан** (обсуждение #59): bind-mountы kind-ноды (`extraMounts`) привязаны к ворктрию, из которого запускался bootstrap, и умирают вместе с ним (deleted-inode), ломая поды молча. Источник кода в dev — dev-образ; изменение кода = пересборка образа (`kind load docker-image` + `helm upgrade`). Chart сохраняет generic `extraVolumes`/`extraVolumeMounts` — если hot-reload понадобится, это values-изменение, не шаблонное.

**4. Миграции** — Helm hook Job `pre-upgrade` с `alembic upgrade head`: схема приводится к актуальной при каждом `helm upgrade`, что сохраняет гарантию entrypoint'а ([ADR-0012/0006](../backend/0006-database-postgresql-alembic.md)) в новой форме. Entrypoint `app:start` перестаёт сам гонять миграции при запуске в k8s (проверка готовности БД остаётся).

**5. Без HA**: реплики 1, requests/limits и probes заданы (задел под prod), но без PDB, HPA, anti-affinity — их добавит prod-values при необходимости.

### Consequences

* Good, because один chart обслуживает dev и prod — различия только в values-файлах
* Good, because external-only БД совпадает с операторной схемой dev (CNPG/redis-operator) и будущим prod — dual-mode STS-костыли не нужны
* Good, because helm hook Job заменяет auto-migration entrypoint'а декларативно и видно в `helm status`
* Bad, because dev-режим завязан на Linux-хост (extraMounts kind-ноды) — как и весь kind-стенд ([ADR-0022](0022-dev-stand-on-kind.md))
* Bad, because front-end dev-под с Vite потребляет больше памяти, чем nginx-под prod — цена dev-режима Vite
* Neutral, because chart живёт в `charts/bigbug` этого репозитория; отдельный chart-репозиторий (Harbor chartmuseum) — позже, при необходимости

### Confirmation

1. Валидация chart:

```bash
helm lint charts/bigbug -f charts/bigbug/values-dev.yaml
helm template bigbug charts/bigbug -f charts/bigbug/values-dev.yaml > /dev/null  # рендер без ошибок
```

2. Функциональная проверка (живой стенд): `make dev-up` поднимает backend/frontend в kind; `curl -fsS https://api.local/api/health` → 200 (ADR-0030); e2e-прогон зелёный; изменение `backend/app/*.py` попадает в стенд пересборкой образа + `helm upgrade` (hot-reload вырезан — см. §3).

3. Fitness-критерии ревью:
   - В `charts/bigbug/templates/` нет StatefulSet/Deployment для postgres/redis и нет зависимостей (`Chart.yaml` `dependencies` пуст) — БД только external
   - Любые новые параметры приложения появляются в `values.yaml` + env-шаблоне backend, а не хардкодом в манифестах

## Pros and Cons of the Options

### Собственный chart, external-only БД (chosen)

* Good, because совпадает с операторной схемой dev и целевым prod — один path, ноль dual-mode
* Good, because chart минимален: 5–6 шаблонов, легко ревьюить
* Bad, because вне k8s-окружения (CI без кластера) chart не поднять без подмены БД — unit/e2e-тесты это не затрагивает (ADR-0014/0016/0018)

### Subchart'ы bitnami postgresql/redis

* Good, because быстрый старт «из коробки»
* Bad, because запрещены владельцем: bitnami-чарты в dev и операторы в prod — две несовместимые схемы credentials и discovery
* Bad, потому что vendor-lock на структуру values bitnami

### Dual-mode: свои STS в dev, external в prod

* Good, потому что не требует операторов в dev
* Bad, потому что самописные STS для БД — те самые костыли, которые в prod всё равно заменяются операторами; двойная поддержка
* Bad, because credentials-схема различается между режимами — источник рассинхрона

### Kustomize вместо helm

* Good, because проще для чистых манифестов
* Bad, потому что prod-деплой и внешние интеграции (keycloakx, harbor) уже в helm; два механизма шаблонов в одном проекте
* Bad, because parametrization через overlays хуже читается при росте числа параметров

## More Information

- [ADR-0022](0022-dev-stand-on-kind.md) — dev-стенд на kind: кластер, ingress, CNPG/redis-operator, keycloakx, Harbor
- [ADR-0024](../common/0024-k8s-secrets.md) — откуда берутся Secret'ы (tofu kubernetes provider)
- [ADR-0006](../backend/0006-database-postgresql-alembic.md) — политика миграций (hook Job сохраняет идемпотентность `alembic upgrade head`)
- [ADR-0012](../archive/infrastructure/0012-docker-compose-split-dev-env.md) (архив) — entrypoint `app:start`/`app:init`, чья роль частично переходит в helm hook
- [ADR-0030](0030-dev-stand-https-self-signed-certs.md) — HTTPS стенда: values-dev содержит REQUESTS_CA_BUNDLE, CORS_ORIGINS, Vite HMR wss-настройки
- Условие пересмотра: prod-деплой с требованиями HA (PDB/HPA/replicas>1) — расширение prod-values, новый ADR не нужен
