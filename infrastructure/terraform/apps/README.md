# apps — инфраструктура приложения BigBug в kind-кластере bigbug-dev

Слой приложения [ADR-0029](../../../docs/adr/infrastructure/0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md):
ns `bigbug` — CNPG Postgres Cluster, Redis CR, секреты приложения (ADR-0024),
TLS-секреты + CA-bundle (ADR-0030) — module `bigbug_init` (issue #59).
Платформа (ingress, операторы) — в `../base`; инсталляции и конфиг внешних
сервисов (Keycloak/Harbor) — в `../infra-apps`. Само приложение — chart
`charts/bigbug` (helm, issue #61).

## Зачем отдельный root (split от infra-apps, 2026-10-23)

Изменения в приложении не должны требовать apply инфраструктурного рута
(`infra-apps` ставит keycloakx/Harbor, логинится во внешние API при plan) —
иначе апплаи приложения конкурируют за state/lock с апплаями других ворктриев.
Граница: **infra-apps = чужие сервисы (Keycloak/Harbor), apps = своё
приложение**.

## Состав (module `bigbug_init`)

- Postgres Cluster `bigbug-dev` (CNPG): БД/юзер `bigbug`, RW endpoint
  `bigbug-dev-rw.bigbug.svc:5432`; креды — секрет оператора `bigbug-dev-app`.
- Redis `bigbug-cache` (redis-operator из base) — `bigbug-cache.bigbug.svc:6379`.
- Секреты приложения (ADR-0024 §1): `bigbug-db-credentials` (проекция
  `bigbug-dev-app`, DATABASE_URL), `bigbug-fernet-key` (ENCRYPTION_KEY,
  стабилен в state), `bigbug-keycloak-oidc` (client_id/secret backend-клиента
  из `../infra-apps` keycloak_conf).
- TLS-секреты `tls-api-local` / `tls-app-local` + ConfigMap `bigbug-ca-bundle`
  (серты из `~/.local/state/bigbug/certs`, ADR-0030 §4/§5).

## Применение

```bash
cd infrastructure/terraform/apps
tofu init && tofu plan && tofu apply
```

Порядок: base → infra-apps (нужен backend-клиент Keycloak для
`bigbug-keycloak-oidc`) → apps. Зависит от `infra-apps` только значениями
(client_id/secret — shared vars, не state-ссылки).

## Live-проверка

```bash
kubectl get pods -n bigbug                    # bigbug-dev-1 (CNPG), bigbug-cache-0
kubectl exec -n bigbug bigbug-cache-0 -- redis-cli ping   # PONG
tofu plan                                     # no-op после apply
```
