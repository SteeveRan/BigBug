# base — платформа kind-кластера bigbug-dev

In-cluster сущности платформенного слоя ([ADR-0029](../../../docs/adr/infrastructure/0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md)):
haproxy-ingress, CNPG operator + Postgres-кластер, Valkey. App-инстансы
(Harbor, keycloakx, chart приложения) — в root-модуле `../apps`.

## Применение

Требуется кластер из `../../kind/bootstrap.sh` (контекст `kind-bigbug-dev`).

**Первый apply на свежем кластере — двухшаговый**: CRD `postgresql.cnpg.io`
создаются helm-релизом оператора, а `kubernetes_manifest` проверяет их наличие
на этапе plan:

```bash
tofu init
tofu apply -target=helm_release.cloudnative_pg   # оператор + CRD
tofu apply                                       # Cluster CR, Valkey, ...
```

Все последующие apply — обычный `tofu apply`, идемпотентны.

Wait-for-ready (входит в init-цепочку I8): применяется только после того, как
под Postgres готов:

```bash
kubectl wait --context kind-bigbug-dev --for=condition=Ready cluster/bigbug-dev -n bigbug --timeout=300s
```

## Подключение потребителей (I3 / I4 / I6)

### PostgreSQL (CNPG Cluster `bigbug-dev`, ns `bigbug`)

Две базы: `bigbug` (приложение) и `keycloak` (Keycloak, I4). Обе принадлежат
юзеру `app` — один набор кредов.

Секреты оператора в ns `bigbug`:

| Секрет | Назначение |
|---|---|
| `bigbug-dev-app` | креды юзера `app`. Ключи: `user`, `password`, `host`, `port`, `dbname`, `uri`, `jdbc-uri`, `fqdn-uri`, `fqdn-jdbc-uri`, `pgpass` |
| `bigbug-dev-superuser` | юзер `postgres` (создаётся при `enableSuperuserAccess`, dev: по требованию) |
| `bigbug-dev-ca`, `bigbug-dev-server`, `bigbug-dev-replication` | TLS/репликация (только для отладки) |

Read-write endpoint: `bigbug-dev-rw.bigbug.svc:5432` (также `bigbug-dev-ro`,
`bigbug-dev-r`). Пример из секрета:

```
postgresql://app:<password>@bigbug-dev-rw.bigbug:5432/bigbug
```

Для БД `keycloak` тот же user/password, `dbname=keycloak`.

### Valkey (ns `bigbug`, single-node, без operator — [ADR-0022](../../../docs/adr/infrastructure/0022-dev-stand-on-kind.md))

Endpoint: `valkey.bigbug.svc:6379`, без аутентификации, без PV (кэш,
потеря данных при пересоздании пода допустима).

## Teardown

`../../kind/teardown.sh` удаляет кластер вместе со всеми данными Postgres и
Valkey — для dev-стенда потеря данных допустима. State tofu (`terraform.tfstate`)
остаётся локально; после пересоздания кластера применяйте base заново
(см. двухшаговый первый apply выше).
