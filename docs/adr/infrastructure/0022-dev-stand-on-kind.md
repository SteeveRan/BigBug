---
status: proposed
date: 2026-10-22
decision-makers: SteeveRan
---

# Dev-стенд на kind: единый кластер, haproxy-ingress, операторы CNPG/redis-operator, keycloakx

## Context and Problem Statement

Dev-стенд BigBug поднимался в Docker Compose (см. архивный [ADR-0012](../archive/infrastructure/0012-docker-compose-split-dev-env.md) — два compose-файла: infrastructure и application). Но целевая среда запуска приложения — Kubernetes: helm chart всё равно придётся разрабатывать для prod. Единственный компонент, уже живущий в k8s, — Harbor в отдельном kind-кластере `harbor` ([ADR-0013](0013-opentofu-iac-keycloak-gitlab-harbor.md)).

> **Историческая фиксация** (2026-10-22). Актуальное состояние — после сноса (#62, 2026-10-24): compose — только GitLab-зона ([ADR-0033](0033-gitlab-dev-stand-compose-omnibus.md)); compose-приложение, keycloak/postgres-keycloak из compose и legacy-кластер `harbor` снесены.

Вопрос: **где размещать dev-окружение приложения** — остаться в compose и отложить k8s на prod-этап, или переехать в единый kind-кластер сейчас, сделав dev-стенд репетицией prod-топологии?

Фактическое состояние (проверено по коду, 2026-10-22; compose-приложение и harbor-кластер снесены в #62):

**Compose-инфраструктура** ([`infrastructure/gitlab/docker-compose.yml`](../../../infrastructure/gitlab/docker-compose.yml), [ADR-0033](0033-gitlab-dev-stand-compose-omnibus.md)): ~~`postgres-keycloak` (:5433), `keycloak` 24.0 (:8180)~~ (снесены — БД в CNPG), `gitlab` CE omnibus (`https://gitlab.local:8443`/:2222, вольюмы `gitlab_*`), `gitlab-runner` (docker.sock executor). Сеть `bigbug-network`.

~~**Compose-приложение** (корневой `docker-compose.yml`): `postgres-backend` (:5432), `redis` (:6379), `backend` (:8000, bind-mount, uvicorn `--reload`), `frontend` (:5173, bind-mount, `yarn dev`).~~ — снесено (#62): postgres → CNPG, redis → redis-operator, приложение — helm chart ([ADR-0023](0023-bigbug-helm-chart.md)).

~~**Harbor**: отдельный kind-кластер `harbor` ... insecure-registry в docker daemon.~~ — кластер снесён (#62); Harbor — chart в `bigbug-dev` ([ADR-0035](0035-harbor-dev-stand-chart.md)).

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
| PostgreSQL | CloudNativePG (CNPG) operator | operator — в base-слое ([ADR-0029](0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md)); `Cluster` CR `instances: 1` — в apps-слое (кластер БД — инстанс приложения); БД `keycloak` создаётся apps-слоем вместе с keycloakx; credentials — в Secret, создаваемом оператором |
| Redis/Valkey | ot-container-kit [redis-operator](https://github.com/ot-container-kit/redis-operator) | operator — в base-слое; Redis CR (cache-инстанс) — в apps-слое; bare-Valkey Deployment отклонён |
| Keycloak | chart `codecentric/keycloakx` | БД — CNPG (не встроенная H2); hostname `keycloak.local` |
| Harbor | chart `harbor/harbor` | переезжает из кластера `harbor` внутрь `bigbug-dev`, за ingress, hostname `harbor.local` |
| BigBug app | собственный helm chart (см. [ADR-0023](0023-bigbug-helm-chart.md)) | backend `api.local`, frontend `app.local` |

**2. Адресация**: все хосты — через ingress с **TLS-терминированием** ([ADR-0030](0030-dev-stand-https-self-signed-certs.md): `https://` для `keycloak.local`, `harbor.local`, `app.local`, `api.local`; самоподписанные per-service сертификаты, генерируемые `certs.sh` до бутстрапа) + записи в `/etc/hosts`. GitLab тоже HTTPS на своём nginx: `https://gitlab.local:8443` (серт из certs.sh; compose-исключение остаётся). Wildcard-DNS (dnsmasq, nip.io) отклонены: либо новая системная зависимость, либо внешняя.

**3. Hot-reload**: (вырезан в #59 — см. [ADR-0023](0023-bigbug-helm-chart.md) §3) изначальная схема «kind `extraMounts` + hostPath в поды + `uvicorn --reload`» оказалась хрупкой: bind-mountы ноды привязаны к ворктрию, из которого запускался bootstrap, и умирают вместе с ним (deleted-inode), ломая поды молча. Источник кода в dev — dev-образ; изменение кода = пересборка образа + `helm upgrade`. `extraMounts` в kind-config остаются (нейтральны).

**4. GitLab-исключение**: GitLab CE omnibus + gitlab-runner остаются в `infrastructure/gitlab/docker-compose.yml`. Обоснование: официальный helm chart требует 6–8 GB RAM только на GitLab и тянет переезд omnibus-конфигурации; самописный StatefulSet для omnibus — неподдерживаемый путь. Runner остаётся с docker.sock executor'ом (known limitation: джобы бегут на хосте, а не в кластере). Путь будущего переезда: официальный chart `gitlab/gitlab` или managed GitLab — отдельный ADR, не эта задача.

**5. Запрет на bitnami-чарты для БД** — вместо них операторы CNPG и redis-operator (ot-container-kit): в dev и prod — одинаковые механизмы, никаких «dev-заглушек, которые в проде заменяют».

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

Чеклист ревью (агент проверяет по живому стенду, 2026-10-24 — пройдено, #62):

1. ✅ `kind get clusters` содержит `bigbug-dev` и **не содержит** `harbor` (кластер ликвидирован #62)
2. ✅ `kubectl get pods -A --context kind-bigbug-dev` показывает поды: haproxy-ingress, cnpg (postgres), redis-operator (+ Redis CR из apps), keycloakx, harbor, backend, frontend
3. ✅ `curl -fsS https://keycloak.local/realms/bigbug` → HTTP 200 (https — ADR-0030)
4. ✅ `curl -fsS https://harbor.local/api/v2.0/systeminfo` → HTTP 200
5. ~~Hot-reload: правка файла в `backend/app/` видна в uvicorn без пересборки образа~~ — вырезан в #59 ([ADR-0023](0023-bigbug-helm-chart.md) §3); источник кода — dev-образ
6. ✅ `make dev-clean` не трогает GitLab-вольюмы compose (`gitlab_data` и пр. остаются)
7. ✅ `infrastructure/gitlab/docker-compose.yml` содержит только gitlab + gitlab-runner (+ без postgres-keycloak — БД в CNPG)

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
- [ADR-0030](0030-dev-stand-https-self-signed-certs.md) — HTTPS на стенде: per-service self-signed сертификаты (certs.sh), терминирование на ingress, доверие хоста/подов
- [ADR-0024](../common/0024-k8s-secrets.md) — secrets в k8s: tofu через kubernetes provider
- [ADR-0013](0013-opentofu-iac-keycloak-gitlab-harbor.md) — OpenTofu-слой остаётся; init flow адаптируется (kind вместо compose для Keycloak/Harbor)
- Supersedes: [ADR-0012](../archive/infrastructure/0012-docker-compose-split-dev-env.md) — compose-разделение dev-стенда (compose остаётся только для GitLab)
- План миграции: [`/.agents/plans/dev-stand-on-kind.md`](../../../.agents/plans/dev-stand-on-kind.md)
- Условие пересмотра: переезд GitLab в kind (официальный chart), переход на prod-кластер
