# План: Dev-стенд на kind (все ADR)

Дата: 2026-10-22. Статус: согласовано с владельцем (grilling complete).

## Цель

Заменить docker compose dev-стенд единым kind-кластером. Приложение разрабатывается
и запускается в Kubernetes — тем самым попутно создаётся helm chart, который станет
основой prod-деплоя. GitLab omnibus — осознанное исключение (остаётся в compose).

## Зафиксированные решения (результат grilling)

| # | Решение |
|---|---|
| D1 | Один kind-кластер `bigbug-dev` на всё; кластер `harbor` ликвидируется, Harbor переезжает внутрь |
| D2 | Backend и frontend — в кластере, с hot-reload через kind `extraMounts` (bind-mount `./backend`, `./frontend` в ноду) + hostPath в поды |
| D3 | GitLab CE omnibus + gitlab-runner остаются в docker compose (дорого тащить в kind); возможен переезд потом. Runner — docker.sock executor, known limitation |
| D4 | Адресация: haproxy-ingress (haproxytech) на :80 через kind extraPortMappings + записи в /etc/hosts (скрипт добавляет сам). Хосты: `keycloak.local`, `harbor.local`, `app.local`, `api.local`. `gitlab.local:8080` не меняется |
| D5 | БД/кэш: операторы **CNPG** (single-instance, `instances: 1`, без HA) и **Valkey** (single-node) в dev-кластере. Bitnami запрещён. Keycloak использует CNPG (отдельная database в том же Cluster), не H2 |
| D6 | Helm chart приложения BigBug — только **external** postgres/redis (host/credentials из values/Secret). Никаких subchart'ов БД, никаких самописных STS-костылей: в dev и проде одни и те же операторы |
| D7 | Keycloak — chart `codecentric/keycloakx`, БД — CNPG |
| D8 | tofu управляет k8s-объектами через **kubernetes provider** — закидывает креды (DB, Fernet ENCRYPTION_KEY, GitLab PAT) прямо в k8s Secrets. update-env.sh сокращается: только то, что нужно хостовым инструментам (e2e base URL, PAT для CLI) |
| D9 | E2E-учётки: отдельный скрипт (make-цель, вызывается из `test-e2e.sh` до прогона), создаёт тестовых пользователей в BigBug БД + realm-юзеров в Keycloak (SSO-сценарии — приоритет, они самые хрупкие). Никаких реальных кредов в e2e |
| D10 | Dev-образы: `make dev-build` = docker build + `kind load docker-image`. CI-сборка — потом, отдельной задачей |
| D11 | Make-интерфейс: имена сохраняются (`infra-init`, `dev-up/down/clean`, `dev-build`), реализация меняется на kind/helm/kubectl |

## Серия ADR (следующий номер = 0022, сквозная нумерация)

### ADR-0022 — `docs/adr/infrastructure/0022-dev-stand-on-kind.md` — «Dev-стенд на kind»

- Front-matter MADR 4.0, статус `proposed`, дата 2026-10-22.
- **Context**: текущее состояние (2 compose-файла, Harbor уже в отдельном kind, ADR-0012/0013), боль — приложение будет в кубере, чарт всё равно нужен.
- **Decision** (D1–D5, D7, D11): один кластер `bigbug-dev`; haproxy-ingress + /etc/hosts; CNPG (1 instance, databases: bigbug, keycloak) + Valkey; keycloakx; GitLab omnibus-исключение в compose с обоснованием (RAM/сложность omnibus в k8s) и путём будущего переезда; hot-reload через extraMounts.
- **Supersedes**: ADR-0012 (compose split dev env) — перенести в `docs/adr/archive/infrastructure/`, статус `superseded by ADR-0022`, взаимные ссылки, обновить оба реестра (README.md, ARCHIVE.md). ADR-0013 (OpenTofu) остаётся действующим — обновить упоминания compose в нём при необходимости.
- **Consequences**: RAM-бюджет (kind ~8–10 GB + GitLab compose 4 GB); входные зависимости разработчика: kind, kubectl, helm, tofu.
- **Confirmation**: чеклист ревью — `kind get clusters` содержит bigbug-dev; `kubectl get pods -A` показывает cnpg/valkey/keycloakx/harbor; `curl http://keycloak.local/realms/master` отвечает 200; `make dev-clean` не затрагивает GitLab-вольюмы.

### ADR-0023 — `docs/adr/infrastructure/0023-bigbug-helm-chart.md` — «Helm chart приложения BigBug»

- Собственный chart (backend Deployment + frontend Deployment, Services, Ingress на api.local/app.local).
- **External-only** postgres/redis (D6): connection-строки из k8s Secret'ов, которые создаёт CNPG-оператор / values. Dual-mode не нужен: prod получит те же операторы.
- Dev-сборка образов: docker build + kind load (D10); hot-reload через extraMounts + hostPath (D2).
- Реплики 1, resources requests/limits, probes — задел под prod, но без HA.
- **Confirmation**: `helm template` проходит lint; `make dev-up` поднимает backend/frontend; e2e-прогон зелёный на `http://api.local`.

### ADR-0024 — `docs/adr/common/0024-k8s-secrets.md` — «Secrets в k8s»

- tofu + kubernetes provider пишет k8s Secrets (D8): DB credentials, `ENCRYPTION_KEY` (Fernet, naming по ADR-0010), GitLab PAT.
- Границы: `app/core/secrets.py` (шифрование stored credentials в БД) не меняется — ENCRYPTION_KEY просто доставляется из k8s Secret вместо .env.
- E2E-политика (D9): отдельный seed-скрипт тестовых учёток (BigBug БД + Keycloak realm), вызывается из `test-e2e.sh`; реальные креды в e2e запрещены.
- update-env.sh сокращается (только хостовые инструменты).
- **Confirmation**: `kubectl get secret` содержит созданные tofu-секреты; e2e-прогон использует только seeded-учётки.

## Порядок работ

1. ADR-0022 → 2. ADR-0023 → 3. ADR-0024 (ADR-0024 можно параллельно с 0023).
4. После accept — задачи на реализацию (отдельные issues, не в этом плане):
   - kind-кластер + haproxy-ingress + /etc/hosts (переработка harbor/deploy.sh → единый bootstrap-скрипт)
   - CNPG + Valkey операторы в кластере
   - keycloakx + OpenTofu-модуль keycloak на новый endpoint
   - Harbor внутри кластера за ingress
   - helm chart приложения + dev-values
   - Makefile: переезд dev-*/infra-* целей
   - tofu kubernetes provider: Secrets
   - e2e seed-скрипт + адаптация test-e2e*.sh (api.local)
   - снос compose-приложения и кластера `harbor`, обновление AGENTS.md/README

## Затронутые при реализации файлы (карта)

- `infrastructure/harbor/deploy.sh`, `teardown.sh`, `test-push.sh`, `kind-config.yaml` — переработка/снос
- `infrastructure/init.sh`, `update-env.sh` — переписать под kind-поток
- `infrastructure/docker-compose.yml` — остаётся только GitLab + runner (+ его postgres внутри образа)
- `docker-compose.yml` (корневой) — удалить после переезда
- `Makefile` — dev-*/infra-* цели, COMPOSE_APP убрать
- `backend/scripts/test-e2e.sh`, `test-e2e-coverage.sh` — base URL api.local + вызов seed-скрипта
- `backend/docker/entrypoint.sh` — пересмотреть: wait-for-db/migrations уходят в helm-hook/initContainer
- `docs/adr/README.md`, `ARCHIVE.md`, `AGENTS.md` — реестры и quick-start
