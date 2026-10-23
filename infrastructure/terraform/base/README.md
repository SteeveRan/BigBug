# base — платформа kind-кластера bigbug-dev

In-cluster сущности **платформенного слоя** ([ADR-0029](../../../docs/adr/infrastructure/0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md)):
haproxy-ingress, операторы CNPG и redis-operator (CRD). App-инстансы (Postgres
Cluster, Redis CR, Harbor, keycloakx, chart приложения, k8s-секреты
приложения, ns `bigbug`) — в root-модуле `../apps`, их деплой — отдельные
issues (I4/I6/I8).

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
kubectl wait --context kind-bigbug-dev --for=condition=Ready deployment/redis-operator -n redis-operator --timeout=120s
```

## Состав

### haproxy-ingress (ns `haproxy-ingress`)

IngressClass default; host :80/:443 → nodePort 30080/30443 (kind
extraPortMappings в `../kind/kind-config.yaml`).

### redis-operator (ns `redis-operator`)

Оператор [ot-container-kit/redis-operator](https://github.com/ot-container-kit/redis-operator)
(CRD `redis.redis.redis.opstreelabs.in` и др.). Bare-Valkey Deployment из
ранних итераций (#55) удалён: инстанс кэша — это Redis CR в app-слое (I6),
base деплоит только оператора.

### CNPG operator (ns `cnpg-system`)

Только оператор + CRD `postgresql.cnpg.io`. Postgres **Cluster CR здесь не
создаётся** — это app-слой (I6): кластер БД — инстанс приложения, а не
платформа. После base оператор готов принимать Cluster CR из apps.

## App-сущности (вне base, для контекста)

- Postgres Cluster `bigbug-dev` (CNPG) — apps root (I6, готово #59); оператор
  генерирует секрет `<cluster>-app` с кредами.
- Redis CR (кэш вместо bare-Valkey) — apps root (I6, готово #59).
- k8s-секреты приложения (`bigbug-db-credentials`, `bigbug-fernet-key`,
  ADR-0024) — apps root (I6, готово #59), зависят от Postgres-кластера,
  не от base.

## Teardown

`../../kind/teardown.sh` удаляет кластер вместе со всеми данными —
для dev-стенда потеря данных допустима. State tofu (`terraform.tfstate`)
остаётся локально; после пересоздания кластера применяйте base заново.
