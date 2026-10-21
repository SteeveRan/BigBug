---
status: proposed
date: 2026-10-22
decision-makers: SteeveRan
---

# Dev-стенд на kind: единый кластер, haproxy-ingress, CNPG + Valkey, keycloakx

## Context and Problem Statement

Dev-стенд BigBug поднимается в Docker Compose (см. архивный [ADR-0012](../archive/infrastructure/0012-docker-compose-split-dev-env.md) — два compose-файла: infrastructure и application). Но целевая среда запуска приложения — Kubernetes: helm chart всё равно придётся разрабатывать для prod. Единственный компонент, уже живущий в k8s, — Harbor в отдельном kind-кластере `harbor` ([ADR-0013](0013-opentofu-iac-keycloak-gitlab-harbor.md)).

Вопрос: **где размещать dev-окружение приложения** — остаться в compose и отложить k8s на prod-этап, или переехать в единый kind-кластер сейчас, сделав dev-стенд репетицией prod-топологии?

Фактическое состояние (проверено по коду, 2026-10-22):

**Compose-инфраструктура** ([`infrastructure/docker-compose.yml`](../../../infrastructure/docker-compose.yml)): `postgres-keycloak` (:5433), `keycloak` 24.0 (:8180), `gitlab` CE omnibus (:8080/:8443/:2222, вольюмы `gitlab_*`), `gitlab-runner` (docker.sock executor). Сеть `bigbug-network`.

**Compose-приложение** (корневой `docker-compose.yml`): `postgres-backend` (:5432), `redis` (:6379), `backend` (:8000, bind-mount, uvicorn `--reload`), `frontend` (:5173, bind-mount, `yarn dev`).

**Harbor**: отдельный kind-кластер `harbor` ([`infrastructure/harbor/deploy.sh`](../../../harbor/deploy.sh)): Helm chart `harbor/harbor`, NodePort 30080/30443 → host :80/:443 через `extraPortMappings`, `/etc/hosts` → `harbor.local`, insecure-registry в docker daemon.

Связанные: [ADR-0006](../backend/0006-database-postgresql-alembic.md) (политика миграций), [ADR-0018](../common/0018-e2e-testing-strategy.md) (e2e против живого dev-стенда), [ADR-0019](../common/0019-makefile-tooling-single-entrypoint.md) (Makefile — единая точка входа).

## Decision Drivers

- **Целевая среда — Kubernetes**: приложение будет деплоиться в k8s; чем раньше dev-цикл совпадает с prod-топологией, тем раньше ловятся k8s-специфичные баги (probes, env, secrets, service discovery)
- Helm chart приложения нужен в любом случае — dev в kind позволяет использовать его ежедневно, а не писать «в стол»
- Единый механизм для всех сервисов (Harbor уже в kind — второй кластер и вторая схема адресации — лишний оверхед)
- Скорость dev-цикла должна сохраниться: hot-reload backend/frontend, быстрый рестарт без пересоздания инфраструктуры
- Драйвер минимализма (ADR-0001): без HA в dev — все single-instance
- RAM-бюджет рабочей станции: dev-стенд должен подниматься на 16–32 GB машине

## Considered Options

* Единый kind-кластер `bigbug-dev`: ingress-контроллер + операторы БД + helm chart приложения; GitLab omnibus остаётся в compose (исключение)
* Всё в kind, включая GitLab CE omnibus (самописный StatefulSet)
* Всё в kind через официальный chart `gitlab/gitlab`
* Остаться в compose (текущее состояние, ADR-0012)

## Decision Outcome

Chosen option: **единый kind-кластер `bigbug-dev`** для всего, кроме GitLab — GitLab CE omnibus и gitlab-runner остаются в Docker Compose как документированное исключение.

### Зафиксированные правила

**1. Топология кластера `bigbug-dev`** (одна нода control-plane):

| Компонент | Способ установки | Замечания |
|---|---|---|
| haproxy-ingress | Helm chart `haproxytech/kubernetes-ingress` | публикуется через kind `extraPortMappings` host :80 → node :80 |
| PostgreSQL | CloudNativePG (CNPG) operator, `Cluster` CR `instances: 1` | две database: `bigbug` (приложение) и `keycloak`; credentials — в Secret, создаваемом оператором |
| Redis/Valkey | Valkey standalone (single-node) | без Redis-operator в dev; single-instance |
| Keycloak | chart `codecentric/keycloakx` | БД — CNPG (не встроенная H2); hostname `keycloak.local` |
| Harbor | chart `harbor/harbor` | переезжает из кластера `harbor` внутрь `bigbug-dev`, за ingress, hostname `harbor.local` |
| BigBug app | собственный helm chart (см. [ADR-0023](0023-bigbug-helm-chart.md)) | backend `api.local`, frontend `app.local` |

**2. Адресация**: все хосты — через ingress на :80 + записи в `/etc/hosts` (`keycloak.local`, `harbor.local`, `app.local`, `api.local`); скрипт bootstrap добавляет записи сам (паттерн `harbor/deploy.sh`). GitLab не меняется: `gitlab.local:8080` (compose). Wildcard-DNS (dnsmasq, nip.io) отклонены: либо новая системная зависимость, либо внешняя.

**3. Hot-reload**: kind `extraMounts` маппит `./backend` и `./frontend` хоста в kind-ноду; поды приложения монтируют их hostPath'ом; dev-образы остаются с `uvicorn --reload` / `yarn dev`. Изменения кода подхватываются без пересборки образов.

**4. GitLab-исключение**: GitLab CE omnibus + gitlab-runner остаются в `infrastructure/docker-compose.yml`. Обоснование: официальный helm chart требует 6–8 GB RAM только на GitLab и тянет переезд omnibus-конфигурации; самописный StatefulSet для omnibus — неподдерживаемый путь. Runner остаётся с docker.sock executor'ом (known limitation: джобы бегут на хосте, а не в кластере). Путь будущего переезда: официальный chart `gitlab/gitlab` или managed GitLab — отдельный ADR, не эта задача.

**5. Запрет на bitnami-чарты для БД** — вместо них операторы CNPG и Valkey: в dev и prod — одинаковые механизмы, никаких «dev-заглушек, которые в проде заменяют».

### Consequences

* Good, because dev-стенд = репетиция prod: одинаковая топология (ingress, operators, helm chart) ловит k8s-специфичные проблемы до прода
* Good, because один кластер вместо «compose + kind» упрощает mental model: всё видно через `kubectl get pods -A`
* Good, because CNPG-оператор даёт прод-подобное управление БД (Secret'ы с credentials, bootstrap, backup-задел) без ручных паролей
* Bad, because RAM-бюджет растёт: kind ~8–10 GB (Harbor ~2 GB, CNPG ~0.5 GB, keycloakx ~1 GB, app ~1.5 GB, ingress ~0.2 GB) + GitLab в compose до 4 GB — итого до 14 GB
* Bad, because две системы контейнеров (compose для GitLab, kind для остального) остаются — init-скрипт должен управлять обеими
* Bad, because hot-reload через extraMounts+hostPath работает только на Linux-хостах (на macOS file-watcher через kind деградирует) — осознанное ограничение dev-стенда
* Neutral, because ingress вместо прямых NodePort'ов — +1 компонент, но единая точка входа для всех хостов
* Neutral, because путь будущего переезда GitLab в k8s (официальный chart `gitlab/gitlab` или managed) — отдельный ADR при необходимости

### Confirmation

Чеклист ревью (агент проверяет по живому стенду):

1. `kind get clusters` содержит `bigbug-dev` и **не содержит** `harbor` (кластер ликвидирован)
2. `kubectl get pods -A --context kind-bigbug-dev` показывает поды: haproxy-ingress, cnpg (postgres), valkey, keycloakx, harbor, backend, frontend
3. `curl -fsS http://keycloak.local/realms/master` → HTTP 200
4. `curl -fsS http://harbor.local/api/v2.0/systeminfo` → HTTP 200
5. Hot-reload: правка файла в `backend/app/` видна в uvicorn без пересборки образа (лог пода показывает reload)
6. `make dev-clean` не трогает GitLab-вольюмы compose (`gitlab_data` и пр. остаются)
7. `infrastructure/docker-compose.yml` содержит только gitlab + gitlab-runner (+ без postgres-keycloak — БД в CNPG)

## Pros and Cons of the Options

### Единый kind-кластер (chosen)

* Good, because максимальное совпадение dev и prod топологий — главный драйвер
* Good, потому что chart приложения проверяется каждый день, а не разово перед prod
* Bad, потому что GitLab всё равно остаётся в compose — две системы, два механизма очистки
* Bad, because поднятие кластера с операторами медленнее compose (5–10 мин против 2–3)

### GitLab omnibus в kind (StatefulSet)

* Good, потому что «всё в одном месте» было бы идеологически чище
* Bad, потому что omnibus в k8s не поддерживается: свой StatefulSet с самописными healthchecks, PV-миграцией, конфигом — неподдерживаемый зоопарк
* Bad, потому что RAM та же, сложность выше — ноль выгоды

### Официальный chart `gitlab/gitlab`

* Good, because поддерживаемый путь GitLab в k8s
* Bad, because 6–8 GB RAM только на GitLab (против 4 GB omnibus) — dev-стенд перестаёт помещаться на 16 GB машину
* Bad, because переезд omnibus → chart требует ручного экспорта/импорта данных (проекты, зеркала) — отдельная большая задача, не окупается в dev

### Остаться в compose (ADR-0012)

* Good, потому что ноль работы — всё работает
* Bad, потому что prod-перенос всё равно потребует helm chart, и он будет написан «в стол» без ежедневной проверки
* Bad, because k8s-специфичные баги (env, secrets, probes, service names) всплывут только при первом prod-деплое

## More Information

- [ADR-0023](0023-bigbug-helm-chart.md) — собственный helm chart приложения (backend+frontend), external postgres/redis
- [ADR-0024](../common/0024-k8s-secrets.md) — secrets в k8s: tofu через kubernetes provider
- [ADR-0013](0013-opentofu-iac-keycloak-gitlab-harbor.md) — OpenTofu-слой остаётся; init flow адаптируется (kind вместо compose для Keycloak/Harbor)
- Supersedes: [ADR-0012](../archive/infrastructure/0012-docker-compose-split-dev-env.md) — compose-разделение dev-стенда (compose остаётся только для GitLab)
- План миграции: [`/.agents/plans/dev-stand-on-kind.md`](../../../.agents/plans/dev-stand-on-kind.md)
- Условие пересмотра: переезд GitLab в kind (официальный chart), переход на prod-кластер
