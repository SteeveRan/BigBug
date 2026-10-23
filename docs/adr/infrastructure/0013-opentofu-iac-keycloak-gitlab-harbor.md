---
status: proposed
date: 2026-10-21
decision-makers: SteeveRan
---

# Infrastructure as Code — OpenTofu для provisioning Keycloak, GitLab и Harbor (Harbor — в kind)

## Context and Problem Statement

Dev-инфраструктура BigBug (исторический compose-слой — архивный [ADR-0012](../archive/infrastructure/0012-docker-compose-split-dev-env.md); актуальный k8s-слой — [ADR-0022](0022-dev-stand-on-kind.md)) требует поверх «поднять контейнеры» ещё и **настройки сервисов**: Keycloak realm + OIDC clients + роли, GitLab group + service-account + PAT, Harbor OIDC auth + projects + robot-accounts + registries + replication. Исторически это делалось императивными bash-скриптами и ручными кликами в консолях — невоспроизводимо, не версионируется, деградирует при пересоздании окружения.

Фактический вопрос: **каким инструментом декларативно управлять конфигурацией инфраструктурных сервисов** — и где проходит граница между «IaC» и императивной обвязкой?

Дополнительно зафиксировано в этом ADR: полный **init flow** — `infrastructure/init.sh` → compose → Harbor (kind) → tofu → `update-env.sh`; и разделение ответственности: что управляется OpenTofu, а что — императивно.

## Decision Drivers

- **Лицензия**: HashiCorp с 2023 перевёл Terraform на BUSL — не open source; нужен fork с открытой лицензией (MPL 2.0, Linux Foundation)
- Совместимость с существующей экосистемой Terraform-провайдеров: `mrparkers/keycloak`, `goharbor/harbor`, `gitlabhq/gitlab`
- Идемпотентность и воспроизводимость: пересоздание dev-окружения с нуля одной командой (`make infra-init`)
- Единый граф зависимостей: Harbor-конфигурация зависит от Keycloak client secret — один `tofu apply` должен разрешить всё
- Минимализм (драйвер ADR-0001): local state без remote backend в dev; no extra services

## Considered Options

* OpenTofu (Terraform-fork, MPL 2.0) с root-модулем и подмодулями keycloak/harbor/gitlab
* HashiCorp Terraform (BUSL 1.1)
* Bash-only provisioning (curl-скрипты к API сервисов)
* Ansible (playbooks против API сервисов)

## Decision Outcome

Chosen option: **OpenTofu** — декларативный IaC с открытой лицензией (MPL 2.0), drop-in совместимый с Terraform и его провайдерами. Конфигурация в [`infrastructure/terraform/`](../../../infrastructure/terraform/): root-модуль (`required_version >= 1.5.0`) оркестрирует три подмодуля; порядок Keycloak → Harbor → GitLab задаётся **графом зависимостей**, а не скриптом — Harbor получает `module.keycloak.harbor_client_secret`, поэтому один `tofu apply` покрывает всё.

Что управляется OpenTofu (проверено по коду, 2026-10-21):

| Модуль | Ресурсы | Провайдер |
|---|---|---|
| `modules/keycloak` | realm `bigbug` (token lifespans, `ssl_required=external`), 3 OIDC clients (`bigbug-backend`, `bigbug-frontend`, `harbor`), роли `admin`/`operator`/`viewer`, тестовый пользователь с привязкой ролей | `mrparkers/keycloak ~> 4.0` |
| `modules/harbor` | OIDC auth-mode (client secret из Keycloak), 3 projects (`gold_images`, `app_images`, `mirrors`) с quotas, robot accounts, registries (Docker Hub, Quay), pull-replication policies, webhooks на backend | `goharbor/harbor ~> 3.12` |
| `modules/gitlab` | group `mirrors`, service-account user `backend`, group membership ~~+ PAT~~ (PAT-генерация убрана #56 — рабочие креды приложения заводятся при деплое приложения, [ADR-0024](../common/0024-k8s-secrets.md)) | `gitlabhq/gitlab ~> 17.0` |

Важная граница: **Harbor как runtime не управляется OpenTofu** — он разворачивается в kind-кластере (Helm, [`infrastructure/harbor/deploy.sh`](../../../infrastructure/harbor/deploy.sh), optional, пропускается если `kind` не установлен). OpenTofu управляет только **конфигурацией** Harbor через API (auth, projects, robots, replication). Аналогично provisioning GitLab CI/CD components и пайплайнов — задача самого приложения через GitLab API (пресеты в [`backend/app/services/gitlab_projects/presets.py`](../../../backend/app/services/gitlab_projects/presets.py)), не IaC: tofu отвечает только за **базовую настройку**.

### Init flow и граница императивного

[`infrastructure/init.sh`](../../../infrastructure/init.sh) — единственная точка входа (`make infra-init`); императивные шаги — ровно те, которые tofu не может сделать сам:

1. Проверка зависимостей (`docker`, `curl`, `jq`, `tofu` **или** `terraform` — fallback осознанный, но OpenTofu рекомендуется)
2. `infrastructure/gitlab/.env` из `.env.example` (если нет)
3. `docker compose up` инфраструктурных сервисов (compose-слой; после [ADR-0022](0022-dev-stand-on-kind.md) — только GitLab, остальное в kind), если ещё не запущены
4. Ожидание готовности: Keycloak `/realms/master` (180s), GitLab `/users/sign_in` (600s)
5. Harbor в kind: `deploy.sh`, только если кластера нет (idempotent)
6. **GitLab PAT bootstrap** — документированное исключение из IaC: начальный root PAT программируется через `gitlab-rails runner` внутри контейнера, только если токен из `infrastructure/gitlab/.env` отвечает 403; затем пишется в `terraform.tfvars`
7. `tofu init` + `tofu apply -auto-approve` из единого root-модуля
8. [`infrastructure/update-env.sh`](../../../infrastructure/update-env.sh): `tofu output` → корневой `.env` (`OIDC_*`, `GITLAB_*` и др.) — приложение получает сконфигурированные секреты без ручных шагов

State: **local** (`terraform.tfstate` в `infrastructure/terraform/`, в `.gitignore`); для production — remote backend (S3 / GitLab managed terraform state), в dev не нужен.

### Consequences

* Good, because вся базовая настройка инфраструктуры версионируется в git и воспроизводится `make infra-init` с нуля
* Good, because граф зависимостей Keycloak → Harbor разрешается самим tofu: OIDC secret передаётся между модулями без склейки скриптами
* Good, because MPL 2.0 — никаких лицензионных рисков BUSL; провайдеры Terraform работают без изменений
* Good, because `tofu plan` даёт dry-run и diff для любых изменений инфраструктуры
* Bad, because local state без locking: параллельные запуски `apply` могут конфликтовать; потеря state = drift (лечится `infra-clean-tofu` + повторный apply — окружение dev и так пересоздаётся)
* ~~Bad, because GitLab PAT живёт 90 дней (`ignore_changes` маскирует проблему от tofu) — по истечении нужен re-bootstrap через `init.sh` (шаг 6); осознанная цена dev-окружения~~ (снято #56/[ADR-0024](../common/0024-k8s-secrets.md): tofu больше не генерирует backend PAT; root-PAT bootstrap в init.sh остаётся только для аутентификации самого tofu)
* Bad, because история инфраструктуры размазана на три инструмента: compose (контейнеры, ADR-0012), kind+Helm (Harbor runtime), tofu (конфигурация) — новый агент должен понимать, что где живёт
* Neutral, because `terraform.tfvars` (с токенами) gitignored, в репозитории только `.example`
* Non-goals: production deployment (K8s и т.п.); remote state backend в dev; provisioning CI/CD компонентов и пайплайнов через IaC; управление ресурсами внутри kind-кластера через tofu

### Confirmation

1. Валидация конфигурации и соответствие фактам:

```bash
cd infrastructure/terraform && tofu validate
make infra-clean && make infra-init   # с нуля, до шага 8 включительно
grep -E '^OIDC_|^GITLAB_URL' .env    # outputs записаны update-env.sh
```

2. Fitness-критерии для ревью:
   - Новый ресурс базовой настройки Keycloak/GitLab/Harbor добавляется как resource в соответствующий подмодуль `infrastructure/terraform/modules/`, а не curl-скриптом в `init.sh` (исключение — PAT bootstrap, шаг 6, он задокументирован)
   - `*.tfstate`, `*.tfvars` не попадают в git (`.gitignore` — уже покрыто)
   - Root-модуль не содержит inline-ресурсов: только `module`-блоки + provider-конфигурация

## Pros and Cons of the Options

### OpenTofu — chosen

Fork Terraform 1.5/1.6 под эгидой Linux Foundation, MPL 2.0.

* Good, because открытая лицензия — fork создавался именно как ответ на смену лицензии Terraform
* Good, because полная совместимость с Terraform-провайдерами (keycloak/harbor/gitlab — официальные registry-провайдеры)
* Good, because CLI-совместимость: `init.sh` работает и с `terraform` как fallback (драйвер ADR-0001 — не заставлять всех переустанавливать инструменты)
* Neutral, because версия lag за Terraform существует, но используемые фичи (providers, modules, `write-only` аргументы в harbor provider) стабильны давно

### HashiCorp Terraform (BUSL)

* Good, because эталонная реализация, максимум документации
* Bad, because BUSL 1.1 — запрещает предоставлять конкурирующий сервис; для open-source проекта BigBug лицензионная неопределённость недопустима
* Neutral, because конфигурация переносима обратно 1:1, если политика изменится

### Bash-only provisioning

Исторический вариант: так и было до редизайна — curl-скрипты к API Keycloak/GitLab/Harbor (legacy-план миграции не сохранился; см. [`infrastructure/README.md`](../../../infrastructure/README.md)).

* Good, because ноль новых инструментов
* Bad, because нет state: скрипты либо не идемпотентны, либо обрастают «проверь-а-нет-ли-уже»-ветками на каждый ресурс
* Bad, because нет графа зависимостей и plan/diff — ошибки настройки обнаруживаются в рантайме приложения
* Bad, because именно от этой схемы ушли (эволюция через issue #12 → #13): ручной путь не масштабируется на 3 сервиса × N ресурсов

### Ansible

* Good, because зрелые модули для API-систем, процедурная модель знакома
* Bad, because провайдеры Keycloak/Harbor в Ansible — community-коллекции заметно беднее terraform-провайдеров (robot accounts, replication policies в harbor-коллекции отсутствуют или неполны)
* Bad, because Ansible силён в конфигурации хостов, а не в декларативном управлении ресурсами API — это другой класс задач
* Neutral, because ещё один язык (YAML + Jinja) в стеке без выигрыша против tofu

## More Information

- [ADR-0012](../archive/infrastructure/0012-docker-compose-split-dev-env.md) (архив) — исторический compose-слой; этот ADR — слой поверх (после ADR-0022 compose остаётся только для GitLab)
- [ADR-0003](../common/0003-keycloak-oidc-dual-auth.md) — зачем Keycloak clients (dual-mode auth); [ADR-0007](../common/0007-providers-v3-registry.md) — приложение хранит эти credentials через Providers V3 (шифрование — [ADR-0010](../backend/0010-fernet-secrets-encryption.md))
- Эксплуатация и troubleshooting (curl-проверки, ручной путь, сброс state) — [`AGENTS.md`](../../../AGENTS.md), make-цели `infra-*` — корневой [`Makefile`](../../../Makefile)
- Обзор: [`infrastructure/README.md`](../../../infrastructure/README.md)
- Условие пересмотра: переход на production-окружение (remote state, секреты из vault, k8s-провижининг) — новый ADR
