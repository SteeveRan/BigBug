---
status: accepted
date: 2026-10-23
decision-makers: SteeveRan
consulted: SteeveRan
informed: SteeveRan
---

# Keycloak в dev-стенде: keycloakx в kind, CNPG-БД, конфигурация через apps root

> Сервисный ADR, фиксирующий **фактическое** состояние (проверено по коду, 2026-10-23). Новых решений не принимает — выносит Keycloak-зону из разросшегося [ADR-0013](../archive/infrastructure/0013-opentofu-iac-keycloak-gitlab-harbor.md) (разборка — issue #80, архивация — #62).

## Context and Problem Statement

[ADR-0013](../archive/infrastructure/0013-opentofu-iac-keycloak-gitlab-harbor.md) описывал Keycloak в эпоху compose + единого tofu root: с тех пор Keycloak переехал в kind-кластер ([ADR-0022](0022-dev-stand-on-kind.md), issue #57), его API-конфиг — в apps-слой ([ADR-0029](0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md), update #58), схема — на HTTPS ([ADR-0030](0030-dev-stand-https-self-signed-certs.md)). Единого документа «Keycloak в dev-стенде» нет.

Вопрос: **как Keycloak устроен в dev-стенде** — установка, БД, конфигурация, секреты, HTTPS.

## Decision Outcome

Chosen option: **keycloakx chart в kind-кластере `bigbug-dev`, БД — CNPG, вся конфигурация — OpenTofu infra-apps root `infrastructure/terraform/infra-apps/` (до split #59 — apps root)**. Разделение: инсталляция — `keycloak_init`, API-конфигурация — `keycloak_conf` (двухфазный apply).

### Зафиксированные правила (фактическое состояние кода)

**1. Инсталляция — `apps/modules/keycloak_init/`:**

| Сущность | Реализация |
|---|---|
| Namespace `keycloak` | `kubernetes_namespace` |
| TLS-секрет `tls-keycloak-local` | `kubernetes_secret` (type `kubernetes.io/tls`) из `~/.local/state/bigbug/certs/keycloak.local/` (ADR-0030 §5) |
| Admin-секрет `keycloak-admin-credentials` | `kubernetes_secret` с `KC_BOOTSTRAP_ADMIN_*` (admin/admin; действует только при первой инициализации пустой БД) |
| БД | CNPG `Cluster` CR: БД/owner `keycloak`, endpoint `keycloak-rw.keycloak.svc:5432`, креды — секрет оператора `keycloak-app` |
| Chart | `codecentric/keycloakx` 7.4.0 (Keycloak 26.8.1, pinned, Renovate bumps), `wait = true` |

Hostname: `keycloak.local`, TLS терминируется на haproxy-ingress, секрет из tofu. `proxy: forwarded` (ADR-0030 §6).

**2. Конфигурация — `apps/modules/keycloak_conf/` (провайдер `keycloak/keycloak ~> 5.0`, логин `https://keycloak.local`):**

| Ресурс | Содержимое |
|---|---|
| `keycloak_realm.bigbug` | realm `bigbug`: `ssl_required=external`, access token 15m, SSO idle 30m / max 10h, без self-registration |
| `keycloak_openid_client.backend` | confidential `bigbug-backend` (secret из переменной), redirect `["*"]` |
| `keycloak_openid_client.frontend` | public `bigbug-frontend`, PKCE S256, redirect `http://localhost:5173/*`, `http://localhost:3000/*` |
| `keycloak_openid_client.harbor` | confidential `harbor`: root `https://harbor.local`, redirect `["https://harbor.local/c/oidc/callback", "https://harbor.local/*"]` (ADR-0030 §8) |
| `keycloak_role.{admin,operator,viewer}` | роли RBAC; держать в синхроне с `app/core/rbac.py` (`RoleName`) |
| `keycloak_user.test_admin` + роли | тестовый пользователь `bigbug`/`bigbug`, роль `admin` |

**3. Двухфазный apply.** keycloak-провайдер логинится при plan/apply, а Keycloak ставится тем же apply (apps). Поэтому init.sh применяет apps в две фазы: `-target=module.keycloak_init -target=module.harbor_init` → wait `https://keycloak.local/realms/master` → полный apply (конфиг). После первой инсталляции полный apply идемпотентен.

**4. Секреты.** Admin-bootstrap и client-secrets — tofu ([ADR-0024](../common/0024-k8s-secrets.md)); креды приложения (OIDC client secret backend) попадают в приложение через k8s Secret app-chart'а, не через `.env`.

**5. Эксплуатация.** Health: `curl -fsS https://keycloak.local/realms/master` → 200 (доверие хоста — `trust-host.sh`). Под → Keycloak: трафик выходит из кластера через external IP (known nuance ADR-0030 More Information). Teardown кластера удаляет БД Keycloak — для dev допустимо; state остаётся, повторный apply пересоздаёт.

### Consequences

* Good, because Keycloak репетирует prod-топологию: chart + операторная БД + TLS-терминирование
* Good, because вся конфигурация realm'а декларативна и воспроизводится apply'ем
* Bad, because двухфазный apply — порядок важен, ошибка видна только на запуске (ADR-0029)
* Bad, because admin-секрет действует только при первой инициализации БД — смена пароля admin'а после этого только через UI/console
* Neutral, because credentials Keycloak-операторного секрета не управляются tofu явно (генерирует CNPG) — accepted

### Confirmation

```bash
kubectl get pods -n keycloak --context kind-bigbug-dev   # keycloakx + cnpg поды Ready
curl -fsS https://keycloak.local/realms/bigbug           # → 200, issuer JSON
kubectl get secret -n keycloak --context kind-bigbug-dev tls-keycloak-local keycloak-admin-credentials
```

`tofu plan` в `infrastructure/terraform/infra-apps` после apply — no changes.

## More Information

* [ADR-0022](0022-dev-stand-on-kind.md) — топология (keycloakx в kind, БД CNPG)
* [ADR-0029](0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md) — base/apps split, общий state backend; update #58 — keycloak_init/conf split
* [ADR-0030](0030-dev-stand-https-self-signed-certs.md) — HTTPS, серты, §8 redirect URIs
* [ADR-0024](../common/0024-k8s-secrets.md) — секреты через tofu
* [ADR-0003](../common/0003-keycloak-oidc-dual-auth.md) — зачем clients (dual-mode auth приложения)
* Код: [`infrastructure/terraform/infra-apps/modules/keycloak_init/`](../../../infrastructure/terraform/infra-apps/modules/keycloak_init/), [`keycloak_conf/`](../../../infrastructure/terraform/infra-apps/modules/keycloak_conf/)
* Issues: #57 (переезд в kind), #58 (conf-split), #80 (этот ADR); архивация ADR-0013 — #62
