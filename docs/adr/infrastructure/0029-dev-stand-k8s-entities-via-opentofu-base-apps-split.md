---
status: proposed
date: 2026-10-22
decision-makers: SteeveRan
---

# Dev-stand k8s entities via OpenTofu: base/apps split

> **Обновление 2026-10-23 (#58):** конфигурация Keycloak/Harbor через их API переехала из config root в `apps` (модули `*_conf`); config root остался только для GitLab. State всех root'ов вынесен в общий local backend `~/.local/state/bigbug/<root>/terraform.tfstate` (через `pathexpand` в `backend "local"`) — один стейт на все git-worktree одной машины. apps разбит на 4 модуля: `harbor_init`/`harbor_conf`, `keycloak_init`/`keycloak_conf`. Apply apps — двухфазный (сначала `*_init`, затем полный), потому что keycloak-провайдер логинится при plan, а Keycloak ставится тем же apply. Подробности — в конце документа.

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

## Update 2026-10-23 (#58): общий state backend, конфиг в apps, init/conf модули

Три уточнения поверх исходного решения (решение не отменяют — сужают):

1. **State backend — общий для всех worktree машины.** Вместо «terraform.tfstate в каталоге модуля» (где стейт попадает в git-worktree и расходится между ворктриями) — local backend с фиксированным путём:
   ```hcl
   # base/backend.tf и apps/backend.tf
   terraform {
     backend "local" {
       path = pathexpand("~/.local/state/bigbug/<root>/terraform.tfstate")
     }
   }
   ```
   `pathexpand` обязателен: внутри `backend`-блока `~` не раскрывается (tofu создаёт literal-каталог `~/`). Файл стейта создаётся только при первой записи — «No state file was found» до первого apply это норма, а не ошибка. Config root пока остаётся на локальном стейте в каталоге (GitLab-зона не трогалась).

2. **API-конфиг Keycloak/Harbor — в `apps`**, модулями `keycloak_conf`/`harbor_conf` (исходная таблица «config root: Keycloak realm/clients, Harbor projects/robots» устарела). Config root остаётся только для GitLab. Причина: harbor-конфиг неразрывно связан с инсталляцией (OIDC client secret из keycloak_conf → harbor_conf), а Keycloak в кластере — делить его конфиг между root'ами бессмысленно.

3. **apps = 4 модуля**: `harbor_init` (ns, TLS-секреты, chart), `harbor_conf` (API-конфиг), `keycloak_init` (ns, TLS/admin-секреты, CNPG CR, chart), `keycloak_conf` (realm/clients/roles/users). Провайдеры пробрасываются из root (`providers = {}`), в модулях собственных `provider`-блоков нет.

Следствие: apply apps **двухфазный** — `tofu apply -target=module.keycloak_init -target=module.harbor_init`, затем полный apply. Причина: keycloak-провайдер выполняет логин при plan/apply, а Keycloak ставится тем же apply. После первой фазы повторный полный apply идемпотентен и проходит одной командой. init.sh (шаг 8) исполняет: base → apps(фаза 1) → wait Keycloak → apps(полный) → config.

## Update 2026-10-23 (#80): поглощение инструментального ядра ADR-0013

[ADR-0013](0013-opentofu-iac-keycloak-gitlab-harbor.md) разрастался: он одновременно про выбор IaC-инструмента, state и границу императивного, и про три сервиса (Keycloak, Harbor, GitLab). После ADR-0022/0029/0030 его сервисные решения разъехались с фактической топологией. Разборка (issue #80):

1. **Сервисные решения вынесены в отдельные ADR** (каждый — фактическое состояние своей зоны):
   - [ADR-0033](0033-gitlab-dev-stand-compose-omnibus.md) — GitLab: compose-исключение, https://gitlab.local:8443, config root, PAT-исключение;
   - [ADR-0034](0034-keycloak-dev-stand-keycloakx.md) — Keycloak: keycloakx + CNPG + keycloak_conf;
   - [ADR-0035](0035-harbor-dev-stand-chart.md) — Harbor: chart + harbor_conf.

2. **Инструментальное ядро ADR-0013 поглощается этим ADR** (отдельный IaC-ADR не создаётся):
   - *Выбор OpenTofu* — MPL 2.0 против BUSL 1.1 Terraform, drop-in совместимость с Terraform-провайдерами (keycloak/harbor/gitlab/helm/kubernetes) — см. Decision Drivers и Alternatives ADR-0013; rationale переносится сюда как есть.
   - *State backend* — политика «общий local state `~/.local/state/bigbug/<root>/terraform.tfstate` для всех worktree машины» — update #58 выше; здесь не дублируется.
   - *Граница «императивно vs декларативно»* — общий принцип: tofu управляет всем декларативным (k8s-сущности, API-конфигурация сервисов); императивно — только то, что tofu не может сделать сам или что должно жить вне жизненного цикла стенда (kind-кластер, /etc/hosts, self-signed серты). **Класс исключений**: bootstrap рабочих кредов через внутренние инструменты сервиса (GitLab PAT через `gitlab-rails runner`, ADR-0033 §4) — задокументированные постоянные исключения, а не грязь.

3. **init flow не дублируется** ни здесь, ни в сервисных ADR — он живёт в [`infrastructure/init.sh`](../../../infrastructure/init.sh) + roadmap #61 (переписывание под kind-поток).

4. После accept сервисных ADR человеком ADR-0013 архивируется (статус superseded, взаимные ссылки) — выполняет **#62**; этим issue он не архивируется.
