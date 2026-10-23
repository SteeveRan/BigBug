---
status: proposed
date: 2026-10-23
decision-makers: SteeveRan
consulted: SteeveRan
informed: SteeveRan
---

# Harbor в dev-стенде: chart в kind за TLS-ingress, конфигурация через apps root

> Сервисный ADR, фиксирующий **фактическое** состояние (проверено по коду, 2026-10-23). Новых решений не принимает — выносит Harbor-зону из разросшегося [ADR-0013](0013-opentofu-iac-keycloak-gitlab-harbor.md) (разборка — issue #80, архивация — #62).

## Context and Problem Statement

Harbor пережил две топологии: отдельный kind-кластер `harbor` (NodePort 30080/30443, insecure-registry — эпоха [ADR-0013](0013-opentofu-iac-keycloak-gitlab-harbor.md)) → chart внутри `bigbug-dev` за TLS-ingress (issue #58, [ADR-0022](0022-dev-stand-on-kind.md), [ADR-0030](0030-dev-stand-https-self-signed-certs.md)). Его конфигурация переехала из config root в apps-слой ([ADR-0029](0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md), update #58). Единого документа «Harbor в dev-стенде» нет.

Вопрос: **как Harbor устроен в dev-стенде** — установка, TLS, OIDC, конфигурация проектов/роботов.

## Decision Outcome

Chosen option: **Harbor chart в kind-кластере `bigbug-dev` (ns `harbor`) за TLS-ingress; API-конфигурация — OpenTofu apps root, модуль `harbor_conf`** (исторический кластер `harbor` снесён — #58, остатки убирает #62).

### Зафиксированные правила (фактическое состояние кода)

**1. Инсталляция — `apps/modules/harbor_init/`:**

| Сущность | Реализация |
|---|---|
| Namespace `harbor` | `kubernetes_namespace` |
| TLS-секрет `tls-harbor-local` | `kubernetes_secret` (type `kubernetes.io/tls`) из `~/.local/state/bigbug/certs/harbor.local/` (ADR-0030 §5) |
| CA-бандл `harbor-ca-bundle` | Secret с ключом `ca.crt` = серт `keycloak.local` — чарт принимает только Secret (`caBundleSecretName`), монтируется в core/jobservice/registry trust stores |
| Chart | `goharbor/harbor` 1.19.4 (Harbor 2.15.4, pinned, Renovate bumps), values `values/harbor.yaml`, Trivy и notary выключены, `wait = true`, timeout 600 |

Endpoint: `https://harbor.local` — TLS терминируется на haproxy-ingress; registry-endpoint для docker — `harbor.local` (443 по умолчанию), доверие — через system trust store после `trust-host.sh` + restart docker; **insecure-registries не используются** (ADR-0030 §4).

**2. Конфигурация — `apps/modules/harbor_conf/` (провайдер `goharbor/harbor ~> 3.12`, `https://harbor.local`):**

| Ресурс | Содержимое |
|---|---|
| `harbor_config_auth.oidc` | auth_mode `oidc_auth`; endpoint `https://keycloak.local/realms/bigbug`; client secret — из `keycloak_conf` (write-only `oidc_client_secret_wo`); `oidc_verify_cert = true` (никогда не отключать — ADR-0028 §2); auto-onboard, groups claim |
| `harbor_project.{gold_images,app_images,mirrors}` | 3 проекта с quotas; gold — private, app/mirrors — public |
| `harbor_robot_account.*_ci` | по robot'у на проект (project-level: repository push/pull, artifact read) |
| `harbor_registry.{docker_hub,quay}` | внешние registry для replication |
| `harbor_replication.{gold_images_mirror,mirrors_sync}` | pull-политики по cron-расписанию |
| `harbor_project_webhook.backend_notifications` | PUSH_ARTIFACT / DELETE_ARTIFACT / SCANNING_COMPLETED → backend webhook |

Связь с Keycloak неразрывна: OIDC client secret рождается в `keycloak_conf` — поэтому harbor-конфиг живёт в том же apps root (ADR-0029 update #58).

**3. Эксплуатация.** Health: `curl -fsS https://harbor.local/api/v2.0/systeminfo` → 200 (без `-k`, после trust). Push/pull-проверка: `infrastructure/kind/test-push.sh`. Webhook address указывает на host-адрес backend'а (`skip_cert_verify = true` — известный хвост, см. Consequences).

### Consequences

* Good, because Harbor репетирует prod: chart + ingress TLS + OIDC, никакого insecure-registry
* Good, because OIDC-цепочка Keycloak → Harbor собирается одним apply'ем apps (secret пробрасывается между модулями)
* Bad, because docker-dind CI-джобы не наследуют host trust store — до решения (маунт серта в джобу) работают с `--insecure`-паттернами (ADR-0030 known limitation)
* Bad, because harbor webhook к backend идёт на host-адрес с `skip_cert_verify = true` — отступление от ADR-0028 §2, чинится вместе с e2e-https-потоком (#60)
* Neutral, because старый кластер `harbor` и `infrastructure/harbor/` подлежат сносу — зона #62

### Confirmation

```bash
kubectl get pods -n harbor --context kind-bigbug-dev     # harbor-* Ready
curl -fsS https://harbor.local/api/v2.0/systeminfo       # → 200 без -k
kubectl get secret -n harbor --context kind-bigbug-dev tls-harbor-local harbor-ca-bundle
```

`tofu plan` в `infrastructure/terraform/infra-apps` после apply — no changes; OIDC auth-mode в Harbor UI — Keycloak.

## More Information

* [ADR-0022](0022-dev-stand-on-kind.md) — переезд Harbor внутрь `bigbug-dev`
* [ADR-0029](0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md) — apps root, harbor_init/conf split (update #58)
* [ADR-0030](0030-dev-stand-https-self-signed-certs.md) — TLS-секреты, caBundle-исключение, docker-доверие
* [ADR-0020](../backend/0020-image-builds-gold-app.md) — потребитель проектов (Gold/App Images, cosign, сканирование)
* Код: [`infrastructure/terraform/infra-apps/modules/harbor_init/`](../../../infrastructure/terraform/infra-apps/modules/harbor_init/), [`harbor_conf/`](../../../infrastructure/terraform/infra-apps/modules/harbor_conf/)
* Issues: #58 (переезд в bigbug-dev), #80 (этот ADR), #60 (webhook/https хвост), #62 (снос harbor-кластера, архивация ADR-0013)
