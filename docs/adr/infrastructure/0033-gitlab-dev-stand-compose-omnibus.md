---
status: proposed
date: 2026-10-23
decision-makers: SteeveRan
consulted: SteeveRan
informed: SteeveRan
---

# GitLab в dev-стенде: compose-исключение (CE omnibus + runner), https, config root

## Context and Problem Statement

После переезда dev-стенда на kind ([ADR-0022](0022-dev-stand-on-kind.md)) и base/apps-разрезки OpenTofu ([ADR-0029](0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md)) GitLab остался единственным сервисом вне kind — compose-исключением. Его решения были размазаны по трём ADR ([ADR-0013](0013-opentofu-iac-keycloak-gitlab-harbor.md), ADR-0022, [ADR-0030](0030-dev-stand-https-self-signed-certs.md)), а код отставал:

- `infrastructure/docker-compose.yml` всё ещё содержал `postgres-keycloak` + `keycloak` (чеклист ADR-0022 §7 требует только gitlab + gitlab-runner);
- config root OpenTofu (`infrastructure/terraform/main.tf`) содержал модули `keycloak`/`harbor`, хотя их конфиг переехал в `terraform/apps` (ADR-0029, update #58) — при полном прогоне два root'а управляли одним Keycloak realm;
- TLS не был реализован: `external_url 'http://gitlab.local:8080'` против зафиксированного ADR-0030 §9 `https://gitlab.local:8443`.

Вопрос: **как GitLab устроен в dev-стенде** — где живёт, как защищается, чем управляется, где проходит граница IaC.

## Decision Drivers

* Omnibus не поддерживается в k8s как есть; официальный chart — 6–8 GB RAM (см. ADR-0022 alternatives)
* GitLab нужен только dev-стенду как **внешняя интеграция** (CI/CD, mirroring) — в prod BigBug не деплоится вместе с GitLab
* TLS-схема стенда уже зафиксирована (ADR-0030): self-signed серты из `certs.sh`, доверие через trust-host.sh
* Рабочие креды приложения заводятся в UI ([ADR-0024](../common/0024-k8s-secrets.md)) — tofu не должен mint'ить PAT приложения
* Минимализм (ADR-0001): один способ управления одной зоной

## Considered Options

* GitLab CE omnibus + gitlab-runner в compose, TLS на omnibus-nginx, config root = GitLab-only tofu
* Переезд GitLab в kind (chart `gitlab/gitlab`)
* Переезд GitLab в kind (самописный StatefulSet)
* Managed GitLab (gitlab.com / self-managed внешне)

## Decision Outcome

Chosen option: **GitLab CE omnibus + gitlab-runner остаются в `infrastructure/docker-compose.yml`** (compose-исключение ADR-0022 §4), HTTPS на omnibus-nginx, config root OpenTofu — GitLab-only.

### Зафиксированные правила

**1. Compose-исключение.** `infrastructure/docker-compose.yml` содержит ровно два сервиса: `gitlab` (CE omnibus, PostgreSQL bundled внутрь образа) и `gitlab-runner` (docker.sock executor — known limitation: джобы бегут на хосте, не в кластере). Сеть `bigbug-network`, вольюмы `gitlab_*`. RAM-бюджет: `mem_limit: 4g`. Переезд в kind (chart `gitlab/gitlab` или managed) — отдельный ADR при необходимости (условие пересмотра ниже).

**2. TLS: `https://gitlab.local:8443`.** Omnibus `external_url 'https://gitlab.local:8443'`; серт — self-signed из `kind/certs.sh` (ADR-0030 §2/§3, файлы в `~/.local/state/bigbug/certs/gitlab.local/`), bind-mount `~/.local/state/bigbug/certs/gitlab.local/` → `/etc/gitlab/ssl/gitlab.local/` (read-only), порты `8443:8443` и `2222:22` (SSH). HTTP-слушателя нет. `letsencrypt` выключен явно. Доверие хоста — `trust-host.sh`; скрипты стенда (init.sh, healthcheck) используют `-k`/`--cacert`, но никогда не переходят на plain HTTP.

**3. Config root OpenTofu = GitLab-only.** Root `infrastructure/terraform/` управляет ровно базовой настройкой GitLab через API (провайдер `gitlabhq/gitlab ~> 17.0`):

| Ресурс | Файл | Содержимое |
|---|---|---|
| `gitlab_group.mirrors` | `modules/gitlab/groups.tf` | группа `bigbug-mirrors` (private, merge только через MR) |
| `gitlab_user.backend` | `modules/gitlab/users.tf` | service-account `bigbug-backend` (не root, `projects_limit=100`) |
| `gitlab_group_membership.backend_mirrors` | `modules/gitlab/memberships.tf` | membership `maintainer` в группе |

Модули `keycloak`/`harbor` из config root удалены (их конфиг — `terraform/apps/modules/{keycloak_conf,harbor_conf}`, ADR-0029 update #58). Провайдер ходит на `https://gitlab.local:8443` с `cacert_file` = серт из `~/.local/state/bigbug/certs/` — верификация self-signed не отключается (ADR-0028 §2). State-следы старых keycloak/harbor-ресурсов root'а не переносятся: существующие ресурсы заселены через apps, двойное управление хуже.

**4. PAT bootstrap — постоянное задокументированное исключение из IaC.** Начальный root-PAT программируется `gitlab-rails runner` внутри контейнера (init.sh, шаг 8), только если токен из `infrastructure/.env` отвечает 403. Почему императивно: gitlab-провайдер не умеет `set_token` (нельзя задать значение существующего PAT), а рабочие креды приложения (resource_providers) заводятся в UI — [ADR-0024](../common/0024-k8s-secrets.md). Это единственный императивный шаг в GitLab-зоне; PAT живёт 90 дней, re-bootstrap — повторный запуск init.sh.

**5. Интеграционная точка с приложением.** Приложение работает с GitLab через API: resource_providers ([ADR-0007](../common/0007-providers-v3-registry.md)), пресеты CI в [`backend/app/services/gitlab_projects/presets.py`](../../../backend/app/services/gitlab_projects/presets.py) ([ADR-0011](../backend/0011-gitlab-ci-pipelines-components.md)). Provisioning CI/CD components и пайплайнов — задача приложения, не IaC.

### Consequences

* Good, because compose — родная среда omnibus: нуль k8s-костылей, стабильные вольюмы, healthcheck
* Good, because config root снова честный: один root — одна зона, никакого двойного управления realm'ом
* Good, because весь GitLab-стек решения (размещение, TLS, IaC-граница, PAT-исключение) — в одном документе
* Bad, because docker.sock у runner'а: CI-джобы не изолированы кластером (known limitation, согласован в ADR-0022 §4)
* Bad, because PAT-исключение = один ручной артефакт в «декларативной» зоне; init.sh идемпотентен, но PAT не версионируется
* Neutral, because 8443 вместо 443 — хост-порт занят ingress'ом kind (extraPortMappings 443); GitLab слушает 8443 и внутри контейнера — URL един везде

### Confirmation

1. Конфигурация валидна и соответствует решению:

```bash
cd infrastructure/terraform && tofu validate        # → Success
grep -c "keycloak\|harbor" main.tf variables.tf outputs.tf   # → 0 (GitLab-only)
```

2. Compose-состав (ADR-0022 §7 чеклист):

```bash
docker compose -f infrastructure/docker-compose.yml config --services   # → gitlab, gitlab-runner
docker compose -f infrastructure/docker-compose.yml ps                   # → 2 контейнера
```

3. TLS живой:

```bash
curl -kfsS https://gitlab.local:8443/users/sign_in | head -1   # → <!DOCTYPE html> (после boots)
curl -s --cacert ~/.local/state/bigbug/certs/gitlab.local/tls.crt \
  -H "PRIVATE-TOKEN: $GITLAB_TOKEN" https://gitlab.local:8443/api/v4/user  # → 200
```

4. Полный цикл с чистого места (владелец инфры): `make infra-init` — проходит; tofu config root apply — без keycloak/harbor-ресурсов.

## Pros and Cons of the Options

### Compose-исключение (chosen)

* Good, because omnibus официально поддерживается в Docker; поддерживать StatefulSet/чарт не надо
* Good, because RAM 4 GB против 6–8 GB официального chart'а
* Bad, because вторая система контейнерного управления (compose + kind) живёт в проекте
* Bad, because prod-топология GitLab (если появится) не репетируется

### Chart `gitlab/gitlab` в kind

* Good, because единая система управления
* Bad, because 6–8 GB только на GitLab — dev-стенд вылетает из 16 GB-машин (ADR-0022 driver)
* Bad, because переезд omnibus → chart = ручной экспорт/импорт данных; в dev не окупается

### Самописный StatefulSet omnibus

* Good, because «всё в kind»
* Bad, because неподдерживаемый зоопарк (healthchecks, PV, конфиг) — отклонён в ADR-0022

### Managed GitLab

* Good, because ноль эксплуатации
* Bad, because dev-стенд должен быть самодостаточным и offline-способным

## More Information

* [ADR-0022](0022-dev-stand-on-kind.md) §4 — само compose-исключение и его обоснование
* [ADR-0030](0030-dev-stand-https-self-signed-certs.md) §9 — GitLab HTTPS, серт из certs.sh
* [ADR-0029](0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md) — base/apps/config-разрезка; update #58 — переезд Keycloak/Harbor-конфига в apps (config root стал GitLab-only)
* [ADR-0013](0013-opentofu-iac-keycloak-gitlab-harbor.md) — исторический IaC-ADR; инструментальное ядро поглощено update-блоком ADR-0029 (#80), архивация — #62
* [ADR-0024](../common/0024-k8s-secrets.md) — почему PAT не генерирует tofu
* [ADR-0007](../common/0007-providers-v3-registry.md) / [ADR-0011](../backend/0011-gitlab-ci-pipelines-components.md) — интеграция приложения с GitLab API
* Issues: #80 (этот ADR + актуализация кода), #61 (Makefile/init.sh под kind-поток), #62 (снос compose-app, архивация ADR-0013)
* Условие пересмотра: появление prod-GitLab / командная разработка в GitLab-стенде → ADR о переезде (chart или managed)
