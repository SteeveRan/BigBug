# infra-apps — инсталляции и конфиг внешних сервисов в kind-кластере bigbug-dev

Инфраструктурный app-слой [ADR-0029](../../../docs/adr/infrastructure/0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md):
стек Keycloak (issue #57) и Harbor (issue #58). Платформа (ingress,
операторы) — в `../base`; конфигурация сервисов через их API (realm,
clients, Harbor projects/robots) — здесь же (модули `*_conf`); инфраструктура
самого приложения BigBug (ns `bigbug`) — в отдельном `../apps` (split
2026-10-23: апплаи приложения не должны требовать apply этого root'а).
Запуск приложения — chart `charts/bigbug` (helm, issue #61).

## Состав

### Postgres Cluster `keycloak` (CNPG, ns `keycloak`)

Отдельный Cluster CR для Keycloak: БД `keycloak`, юзер `keycloak`. Креды —
секрет оператора `keycloak-app` (ns `keycloak`), RW endpoint
`keycloak-rw.keycloak.svc:5432`.

### BigBug app infra — переехал в `../apps` (split 2026-10-23, issue #59)

ns `bigbug` (CNPG Cluster `bigbug-dev`, Redis `bigbug-cache`, секреты
`bigbug-db-credentials`/`bigbug-fernet-key`/`bigbug-keycloak-oidc`, TLS +
CA-bundle) управляется отдельным root'ом `../apps` (module `bigbug_init`) —
см. его README. Связь с этим root'ом: значения `backend_client_id/secret`
(клиент создаёт `keycloak_conf` здесь) передаются переменными, не
state-ссылками.

Само приложение — chart `charts/bigbug` (деплой helm, см. README chart'а;
инсталляция — `make dev-up`/`dev-build`, issue #61).

### keycloakx (ns `keycloak`, issue #57)

Chart `codecentric/keycloakx` 7.4.0 (Keycloak 26.8.1, pinned). БД — CNPG
`keycloak`, креды из секрета оператора. Admin bootstrap — `admin`/`admin`
(KC_BOOTSTRAP_ADMIN_*, секр. `keycloak-admin-credentials`, действует только
при первой инициализации пустой БД). Endpoint: `http://keycloak.local`
(Ingress из chart, haproxy, :80, без TLS). Health:

```bash
curl -fsS http://keycloak.local/realms/master   # → 200
```

### Harbor (ns `harbor`, issue #58)

Chart `goharbor/harbor` 1.19.4 (Harbor 2.15.4, pinned), values в
`values/harbor.yaml`. Endpoint: `https://harbor.local` (TLS терминируется
на haproxy-ingress, серт — секрет `tls-harbor-local` из
`~/.local/state/bigbug/certs/`,
ADR-0030). Trivy и notary выключены, chartmuseum в chart 1.19.x отсутствует
(удалён upstream). Registry-endpoint для docker — `harbor.local` (порт не
нужен, дефолт 443); доверие хоста — `../../kind/trust-host.sh` +
restart docker (insecure-registries не используются, ADR-0030 §4). Health:

```bash
curl -fsS https://harbor.local/api/v2.0/systeminfo   # → 200 (без -k)
```

Push/pull-проверка: `../../kind/test-push.sh`. После этого root'а — app-infra
(`cd ../apps && tofu apply`): projects/robots/webhooks против
`https://harbor.local`.

## Применение (порядок обязателен)

```bash
# 0. серты для *.local (до bootstrap; живут в ~/.local/state/bigbug/certs —
#    общие для всех ворктриев, переживают infra-clean)
../../kind/certs.sh && ../../kind/trust-host.sh   # trust-host требует sudo
# 1. кластер + /etc/hosts
../../kind/bootstrap.sh
# 2. платформа (CNPG operator + CRD, haproxy-ingress, CoreDNS *.local hosts)
cd ../base && tofu init && tofu apply && cd ../infra-apps
# 3. app-инстансы (этот root; требует секретов из шага 0 — harbor-tls.tf)
tofu init && tofu apply
```

Wait-for-ready keycloakx (первый старт ~1–2 мин, dbchecker ждёт Postgres):

```bash
kubectl wait --context kind-bigbug-dev --for=condition=Ready \
  pod -l app.kubernetes.io/instance=keycloakx -n keycloak --timeout=300s
```

После infra-apps — app-infra (`cd ../apps && tofu apply`): realm/clients
против `http://keycloak.local`. GitLab base setup (group, service-account) —
часть этого root'а (module `gitlab`, ADR-0033 §3).

## Teardown

`../../kind/teardown.sh` удаляет кластер вместе со всеми данными (Postgres,
Keycloak) — для dev-стенда потеря данных допустима. State остаётся локально;
после пересоздания кластера применяйте base заново, затем infra-apps и apps.

## Apply order (после пересоздания кластера)

```bash
./kind/certs.sh                      # 1. серты (→ ~/.local/state/bigbug/certs, переживают teardown)
./kind/bootstrap.sh                  # 2. kind кластер + hosts
cd terraform/base && tofu apply      # 3. платформа (ingress, операторы, coredns)
cd terraform/infra-apps && tofu apply -target=module.keycloak_init -target=module.harbor_init   # 4. инсталляции (chart'ы)
cd terraform/infra-apps && tofu apply      # 5. конфиг (realm, клиенты, harbor projects) — keycloak-провайдер требует живой Keycloak
cd terraform/apps && tofu apply      # 6. app-infra ns bigbug (нужен backend-клиент из шага 5)
```

State: общий local backend `~/.local/state/bigbug/{base,infra-apps,apps}/` (все ворктрии видят один стейт).

Примечание: шаг 4 отдельной фазой нужен потому, что keycloak-провайдер логинится при plan/apply — конфиг-модули применяются только когда Keycloak отвечает (шаги 4→5 можно объединить повторным apply: `tofu apply -target=module.keycloak_init` уже создан → полный apply проходит).
