# bigbug chart

Helm chart приложения BigBug ([ADR-0023](../../docs/adr/infrastructure/0023-bigbug-helm-chart.md)):
FastAPI backend + React frontend, **external-only** PostgreSQL/Redis (никаких
subchart'ов и STS). Один chart для dev и prod — различия только в values.

## Состав

| Шаблон | Назначение |
|---|---|
| `backend-deployment.yaml` | FastAPI backend, 1 реплика, probes `/api/health`, env из ConfigMap + Secrets |
| `frontend-deployment.yaml` | Prod: nginx со статикой. Dev: Node + Vite dev server (`frontend.dev.enabled`) |
| `backend-service.yaml` / `frontend-service.yaml` | ClusterIP Services |
| `ingress.yaml` | `api.local` (backend) и `app.local` (frontend), className из values |
| `migrate-job.yaml` | Helm hook `pre-install,pre-upgrade` Job: `app:init` (wait DB → `alembic upgrade head` → seeds) |
| `configmap.yaml` | Несекретный env backend (REDIS_URL, CORS_ORIGINS, keycloak URL) |

## Контракт секретов (создаёт tofu — [ADR-0024](../../docs/adr/common/0024-k8s-secrets.md), `infrastructure/terraform/apps/modules/bigbug_init/`)

| Secret | Ключи | Потребитель |
|---|---|---|
| `bigbug-db-credentials` | `DATABASE_URL`, … | backend, migrate Job |
| `bigbug-fernet-key` | `ENCRYPTION_KEY` | backend |
| `bigbug-keycloak-oidc` | `client_id`, `client_secret` | backend |

Подключение — `backend.secretEnv` в values (secretKeyRef). Plain env в
манифестах для секретов запрещён (fitness-критерий ADR-0024).

## Dev-стенд (values-dev.yaml)

- Образы `bigbug-{backend,frontend}:dev` (сборка — `make dev-build`, #61).
- Hot-reload **вырезан**: источник кода — образ, изменения через пересборку
  (hostPath-маунты kind-ноды привязаны к ворктрию бутстрапа и умирали вместе
  с ним; `extraMounts` в kind-config.yaml остались, но chart их не использует).
- HTTPS: TLS терминируется на ingress (`tls-api-local`/`tls-app-local` —
  tofu, [ADR-0030](../../docs/adr/infrastructure/0030-dev-stand-https-self-signed-certs.md)),
  backend получает `SSL_CERT_FILE` на смонтированный `bigbug-ca-bundle`,
  `--proxy-headers` + `FORWARDED_ALLOW_IPS`; Vite HMR — `wss`, `clientPort: 443`.
- `RATE_LIMIT_ENABLED=false` (паритет с compose-девом).

## Проверка

```bash
helm lint charts/bigbug -f charts/bigbug/values-dev.yaml
helm template bigbug charts/bigbug -f charts/bigbug/values-dev.yaml > /dev/null
```

Деплой на dev-стенд:

```bash
helm upgrade --install bigbug charts/bigbug -n bigbug \
  --kube-context kind-bigbug-dev -f charts/bigbug/values-dev.yaml
# миграции применит hook Job: kubectl logs -n bigbug job/bigbug-migrate
curl -fsSk https://api.local/api/health   # → 200
curl -fsSk https://app.local              # → 200 (frontend)
```
