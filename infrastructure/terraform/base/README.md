# base — платформа kind-кластера bigbug-dev

In-cluster сущности **платформенного слоя** ([ADR-0029](../../../docs/adr/infrastructure/0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md)):
haproxy-ingress, оператор CNPG (CRD), Valkey. App-инстансы (Postgres Cluster,
Harbor, keycloakx, chart приложения, k8s-секреты приложения) — в root-модуле
`../apps`, их деплой — отдельные issues (I4/I6/I8).

**Граница**: base деплоит только операторов и платформенные сервисы — никаких
инстансов приложений и их секретов. Применяется одной командой при бутстрапе
кластера и не принимает внешних значений.

## Применение

Требуется кластер из `../../kind/bootstrap.sh` (контекст `kind-bigbug-dev`).

```bash
tofu init
tofu apply
```

Идемпотентно; CRD оператора ставятся helm-релизом, поэтому двухшаговый
первый apply (как раньше с `kubernetes_manifest`) больше не нужен.

Wait-for-ready (входит в init-цепочку I8):

```bash
kubectl wait --context kind-bigbug-dev --for=condition=Ready deployment/valkey -n bigbug --timeout=120s
```

## Состав

### haproxy-ingress (ns `haproxy-ingress`)

IngressClass default; host :80/:443 → nodePort 30080/30443 (kind
extraPortMappings в `../kind/kind-config.yaml`).

### CNPG operator (ns `cnpg-system`)

Только оператор + CRD `postgresql.cnpg.io`. Postgres **Cluster CR здесь не
создаётся** — это app-слой (I6): кластер БД — инстанс приложения, а не
платформа. После base оператор готов принимать Cluster CR из apps.

### Valkey (ns `bigbug`, single-node, без operator — [ADR-0022](../../../docs/adr/infrastructure/0022-dev-stand-on-kind.md))

Endpoint: `valkey.bigbug.svc:6379`, без аутентификации, без PV (кэш,
потеря данных при пересоздании пода допустима).

## App-сущности (вне base, для контекста)

- Postgres Cluster `bigbug-dev` (CNPG) — apps root, I6; оператор генерирует
  секрет `<cluster>-app` с кредами.
- k8s-секреты приложения (`bigbug-db-credentials`, `bigbug-fernet-key`,
  ADR-0024) — apps root (модуль `../base/modules/k8s-secrets` переедет туда
  wiring'ом I6), зависят от Postgres-кластера, не от base.

## Teardown

`../../kind/teardown.sh` удаляет кластер вместе со всеми данными —
для dev-стенда потеря данных допустима. State tofu (`terraform.tfstate`)
остаётся локально; после пересоздания кластера применяйте base заново.
