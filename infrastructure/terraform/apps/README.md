# apps — app-инстансы в kind-кластере bigbug-dev

App-слой [ADR-0029](../../../docs/adr/infrastructure/0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md):
инстансы приложений в собственных namespace. Сейчас — только стек Keycloak
(issue #57). Платформа (ingress, операторы) — в `../base`; конфигурация
сервисов через их API (realm, clients) — в `../..` (config root, ADR-0013).
Ns `bigbug` приложения (backend/frontend/секреты) — не здесь, это app chart (I6).

## Состав

### Postgres Cluster `keycloak` (CNPG, ns `keycloak`)

Отдельный Cluster CR для Keycloak: БД `keycloak`, юзер `keycloak`. Креды —
секрет оператора `keycloak-app` (ns `keycloak`), RW endpoint
`keycloak-rw.keycloak.svc:5432`. Postgres-кластер приложения (`bigbug`) —
отдельный CR, I6.

### keycloakx (ns `keycloak`, issue #57)

Chart `codecentric/keycloakx` 7.4.0 (Keycloak 26.8.1, pinned). БД — CNPG
`keycloak`, креды из секрета оператора. Admin bootstrap — `admin`/`admin`
(KC_BOOTSTRAP_ADMIN_*, секр. `keycloak-admin-credentials`, действует только
при первой инициализации пустой БД). Endpoint: `http://keycloak.local`
(Ingress из chart, haproxy, :80, без TLS). Health:

```bash
curl -fsS http://keycloak.local/realms/master   # → 200
```

## Применение (порядок обязателен)

```bash
# 1. кластер + /etc/hosts
../../kind/bootstrap.sh
# 2. платформа (CNPG operator + CRD, haproxy-ingress)
cd ../base && tofu init && tofu apply && cd ../apps
# 3. app-инстансы (этот root)
tofu init && tofu apply
```

Wait-for-ready keycloakx (первый старт ~1–2 мин, dbchecker ждёт Postgres):

```bash
kubectl wait --context kind-bigbug-dev --for=condition=Ready \
  pod -l app.kubernetes.io/instance=keycloakx -n keycloak --timeout=300s
```

После apps — config root (`cd .. && tofu apply`): realm/clients против
`http://keycloak.local`.

## Teardown

`../../kind/teardown.sh` удаляет кластер вместе со всеми данными (Postgres,
Keycloak) — для dev-стенда потеря данных допустима. State остаётся локально;
после пересоздания кластера применяйте base заново, затем apps.
