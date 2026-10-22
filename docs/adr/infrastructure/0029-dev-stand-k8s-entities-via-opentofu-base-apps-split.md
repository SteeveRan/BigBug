---
status: proposed
date: 2026-10-22
decision-makers: SteeveRan
---

# Dev-stand k8s entities via OpenTofu: base/apps split

## Context and Problem Statement

[ADR-0022](0022-dev-stand-on-kind.md) вводит единый kind-кластер `bigbug-dev`, и внутрь него предстоит установить цепочку сущностей: haproxy-ingress → операторы (CNPG, redis-operator/keycloakx-зависимости) → Harbor, keycloakx, приложение. Первый шаг (issue #54) был сделан bash-скриптом (`bootstrap.sh` c `helm upgrade --install`) — и это воспроизводит ровно проблему, из-за которой ушёл bash-only provisioning в [ADR-0013](0013-opentofu-iac-keycloak-gitlab-harbor.md): нет state, нет plan/diff, «проверь-а-нет-ли-уже»-ветки на каждый ресурс.

При этом ADR-0013 зафиксировал non-goal «управление ресурсами внутри kind-кластера через tofu». Этот non-goal теперь мешает: in-cluster сущностей становится много (ingress, операторы, сервисы, app), и императивные скрипты для них не масштабируются. Требуется пересмотреть границу.

Дополнительные требования:

- **Запуск по кнопке**: весь dev-стенд поднимается одной командой (`make infra-init`), несмотря на цепочку зависимостей bash → in-cluster tofu → config-tofu.
- **Переиспользуемость на preprod**: preprod получает уже готовый кластер с операторами — на нём должны накатываться только app-сущности (Harbor, GitLab-конфиг, keycloak-конфиг), без base-слоя.

## Decision

OpenTofu управляет **всем содержимым kind-кластера**; сам кластер и `/etc/hosts` остаются императивными (bash). Разрез на два корневых модуля:

| Root | State | Содержимое | Куда переезжает |
|---|---|---|---|
| `infrastructure/terraform/base/` | свой (`terraform.tfstate` в каталоге модуля) | платформа in-cluster: haproxy-ingress (helm release, ingressClass default), **только операторы** и их CRD (CNPG, redis-operator). Инстансов и секретов приложений в base нет: base применяется одной командой при бутстрапе и не принимает внешних значений | на preprod **как есть** |
| `infrastructure/terraform/apps/` | свой | app-сущности: Harbor chart, keycloakx, helm chart приложения (следующие issues) | на preprod с переменными под окружение |
| `infrastructure/terraform/` (существующий) | свой (не трогаем) | конфигурация **сервисов** через API: Keycloak realm/clients, Harbor projects/robots, GitLab group/PAT | на preprod с переменными под окружение |

Граница трёх состояний: **base** = платформа кластера; **apps** = инстансы сервисов в кластере; **config** = настройка этих сервисов через их API (ADR-0013 как был, так и остаётся — меняется только non-goal про in-cluster).

Императивным остаётся только то, что tofu сделать не может: `kind create cluster`, `/etc/hosts`, дождаться готовности API. Это `infrastructure/kind/bootstrap.sh`/`teardown.sh` — они сужаются до кластера + hosts, установка ingress переходит в `base`.

«Кнопка» — оркестрация в `infrastructure/init.sh` (последовательность, не единый state): кластер → `tofu apply` (base) → `tofu apply` (apps) → `tofu apply` (config). Каждый шаг идемпотентен, пересоздание кластера перекатывает только base/apps-state, не трогая state внешних API (Keycloak/GitLab живы и без кластера).

### Scope этого решения

- haproxy-ingress переезжает из `bootstrap.sh` в `base` немедленно (issue #54 дорабатывается).
- CNPG/redis-operator, Postgres Cluster CR, Redis CR, keycloakx, Harbor-chart, app-chart, k8s-секреты приложения добавляются в соответствующие root'ы отдельными issues — структура под них готова. Уточнение границы из #56: **base = операторы + платформенные сервисы; инстансы (Cluster CR, Redis CR, keycloakx, Harbor, app-chart) и k8s-секреты приложения ([ADR-0024](../common/0024-k8s-secrets.md)) — apps**.
- Провайдеры: `helm` (hashicorp/helm) и `kubernetes` (hashicorp/kubernetes) в `base`/`apps`; аутентификация — через kubeconfig контекста `kind-bigbug-dev` (для preprod — kubeconfig кластера в переменной).

### Non-goals

- Управление самим kind-кластером через tofu (провайдер `kyma-project/kind` отклонён — комьюнити-зрелость, слабое управление `extraPortMappings`/`extraMounts`).
- Remote state в dev (остаётся local; для preprod — отдельное решение).
- Перенос конфигурации Keycloak/GitLab/Harbor-API в `apps` — они остаются в root-модуле ADR-0013.

## Consequences

* Good, because in-cluster сущности получают state, plan/diff и идемпотентность — тот же выигрыш, что ADR-0013 дал для API-конфигурации
* Good, because base/apps split прямо готовит preprod: base накатывается без изменений, apps — с env-специфичными переменными
* Good, because пересоздание dev-кластера не затрагивает state внешних API (Keycloak/GitLab) — изолированные state'ы ограничивают blast radius
* Good, because «кнопка» сохраняется: init.sh оркестрирует 3 apply последовательностью — явная и отлаживаемая, в отличие от единого графа, падающего целиком
* Bad, because три state'а вместо одного: агент/человек должен знать, какой apply за что отвечает
* Bad, because зависимости между root'ами (apps ждёт base, config ждёт apps) разрешаются порядком в init.sh, а не графом tofu — ошибка порядка видна только на запуске
* Bad, because провайдеры helm/kubernetes внутри kind требуют kubeconfig — ещё одна точка хрупкости при пересоздании кластера (state помнит кластер, которого нет; лечится полным циклом teardown → bootstrap)

## Alternatives Considered

* **Единый root-модуль** (base + apps + config в одном state): один `tofu apply`, граф разрешает всё сам; отклонено — падение/пересоздание кластера трогает state внешних API, и теряется переиспользуемость base на preprod (там нет GitLab-config и других dev-специфичных настроек).
* **Bash + helm для in-cluster** (статус-кво issue #54): отклонено — нет state/plan/diff, не масштабируется на ~5 helm-релизов + CRD, именно от этого ушли в ADR-0013.
* **Провайдер kind для всего** (кластер тоже в tofu): отклонён — комьюнити-провайдер, `extraPortMappings`/`extraMounts` управляются хуже, чем в kind-config.yaml; выгода (минус один bash-скрипт) не стоит риска.

## More Information

- [ADR-0022](0022-dev-stand-on-kind.md) — топология dev-стенда на kind (этот ADR уточняет его раздел императивного)
- [ADR-0013](0013-opentofu-iac-keycloak-gitlab-harbor.md) — IaC-слой для API-конфигурации; его non-goal «in-cluster через tofu» этим ADR superseded-по-смыслу (документально оформить supersede при accept)
- Issue #54 — первая реализация bootstrap (haproxy-ingress переносится в base)
- Условие пересмотра: появление production-кластера (remote state, secrets management) — новый ADR
