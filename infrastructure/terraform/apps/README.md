# apps — app-инстансы в kind-кластере bigbug-dev

App-слой [ADR-0029](../../../docs/adr/infrastructure/0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md):
инстансы приложений в собственных namespace: стек Keycloak (issue #57),
Harbor (issue #58) и инфраструктура приложения BigBug в ns `bigbug`
(issue #59 — module `bigbug_init`). Платформа (ingress, операторы) — в
`../base`; конфигурация сервисов через их API (realm, clients, Harbor
projects/robots) — в `../..` (config root, ADR-0013). Запуск приложения —
chart `charts/bigbug` (helm, issue #61).

## Состав

### Postgres Cluster `keycloak` (CNPG, ns `keycloak`)

Отдельный Cluster CR для Keycloak: БД `keycloak`, юзер `keycloak`. Креды —
секрет оператора `keycloak-app` (ns `keycloak`), RW endpoint
`keycloak-rw.keycloak.svc:5432`.

### BigBug app infra (ns `bigbug`, module `bigbug_init`, issue #59)

- Postgres Cluster `bigbug-dev` (CNPG): БД `bigbug`, юзер `bigbug`, RW
  endpoint `bigbug-dev-rw.bigbug.svc:5432`. Креды — секрет оператора
  `bigbug-dev-app`.
- Redis `bigbug-cache` (redis-operator из base) — `bigbug-cache.bigbug.svc:6379`.
- Секреты приложения (ADR-0024 §1): `bigbug-db-credentials` (проекция
  `bigbug-dev-app`, DATABASE_URL для backend и hook Job), `bigbug-fernet-key`
  (ENCRYPTION_KEY, стабилен в state), `bigbug-keycloak-oidc`
  (client_id/client_secret backend-клиента).
- TLS-секреты `tls-api-local` / `tls-app-local` + ConfigMap `bigbug-ca-bundle`
  (серты keycloak.local/harbor.local для backend-пода, SSL_CERT_FILE —
  ADR-0030 §4/§5).

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
на haproxy-ingress, серт — секрет `tls-harbor-local` из `../../kind/certs/`,
ADR-0030). Trivy и notary выключены, chartmuseum в chart 1.19.x отсутствует
(удалён upstream). Registry-endpoint для docker — `harbor.local` (порт не
нужен, дефолт 443); доверие хоста — `../../kind/trust-host.sh` +
restart docker (insecure-registries не используются, ADR-0030 §4). Health:

```bash
curl -fsS https://harbor.local/api/v2.0/systeminfo   # → 200 (без -k)
```

Push/pull-проверка: `../../kind/test-push.sh`. После apps — config root
(`cd .. && tofu apply`): projects/robots/webhooks против `https://harbor.local`.

## Применение (порядок обязателен)

```bash
# 0. серты для *.local (до bootstrap; переживают infra-clean)
../../kind/certs.sh && ../../kind/trust-host.sh   # trust-host требует sudo
# 1. кластер + /etc/hosts
../../kind/bootstrap.sh
# 2. платформа (CNPG operator + CRD, haproxy-ingress, CoreDNS *.local hosts)
cd ../base && tofu init && tofu apply && cd ../apps
# 3. app-инстансы (этот root; требует секретов из шага 0 — harbor-tls.tf)
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

## Apply order (после пересоздания кластера)

```bash
./kind/certs.sh                      # 1. серты (переживают teardown)
./kind/bootstrap.sh                  # 2. kind кластер + hosts
cd terraform/base && tofu apply      # 3. платформа (ingress, операторы, coredns)
cd terraform/apps && tofu apply -target=module.keycloak_init -target=module.harbor_init   # 4. инсталляции (chart'ы)
cd terraform/apps && tofu apply      # 5. конфиг (realm, клиенты, harbor projects) — keycloak-провайдер требует живой Keycloak
```

State: общий local backend `~/.local/state/bigbug/{base,apps}/` (все ворктрии видят один стейт).

Примечание: шаг 4 отдельной фазой нужен потому, что keycloak-провайдер логинится при plan/apply — конфиг-модули применяются только когда Keycloak отвечает (шаги 4→5 можно объединить повторным apply: `tofu apply -target=module.keycloak_init` уже создан → полный apply проходит).
