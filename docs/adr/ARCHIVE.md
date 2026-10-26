# Architecture Decision Records — архив отменённых решений

Реестр **неактуальных** ADR (статус `Superseded` или `Rejected`). Действующие решения: [README.md](README.md).

Правила:

- Файлы лежат в `docs/adr/archive/<component>/NNNN-slug.md` (номер и компонент сохраняются).
- Статус в front-matter — по скиллу: `rejected` либо `superseded by ADR-NNNN` (markdown-ссылка на заменивший ADR) со взаимной ссылкой в обе стороны.
- Причину отмены и ссылку на заменивший ADR — в колонке «Причина/Замена».
- Номер из архива **никогда не переиспользуется**: сквозная нумерация продолжается дальше.

## common

| ADR | Статус | Название | Причина / Замена | Дата архивации |
|---|---|---|---|---|
| — | — | — | — | — |

## backend

| ADR | Статус | Название | Причина / Замена | Дата архивации |
|---|---|---|---|---|
| [ADR-0009](archive/backend/0009-pull-sync-apscheduler-webhooks.md) | superseded by [ADR-0039](backend/0039-background-tasks-taskiq-redis-streams.md) | Фоновая синхронизация: pull-based через APScheduler с опциональными webhooks | Собственные revisit-триггеры сработали: retry с backoff, >1 реплики, рост масштаба; исполнение задач — taskiq + Redis Streams (APScheduler остаётся enqueue-only) | 2026-10-24 |

## frontend

| ADR | Статус | Название | Причина / Замена | Дата архивации |
|---|---|---|---|---|
| — | — | — | — | — |

## infrastructure

| ADR | Статус | Название | Причина / Замена | Дата архивации |
|---|---|---|---|---|
| [ADR-0012](archive/infrastructure/0012-docker-compose-split-dev-env.md) | superseded by [ADR-0022](infrastructure/0022-dev-stand-on-kind.md) | Dev environment: разделение Docker Compose на infrastructure и application, entrypoint с wait-for-DB и auto-migration | Dev-стенд переезжает в единый kind-кластер; compose остаётся только для GitLab | 2026-10-22 |
| [ADR-0013](archive/infrastructure/0013-opentofu-iac-keycloak-gitlab-harbor.md) | superseded by [ADR-0029](infrastructure/0029-dev-stand-k8s-entities-via-opentofu-base-apps-split.md) | Infrastructure as Code: OpenTofu для provisioning Keycloak, GitLab и Harbor | In-cluster non-goal superseded ADR-0029; инструментальное ядро (выбор OpenTofu, state, граница императивного) поглощено ADR-0029; сервисные решения разъехались в ADR-0033/0034/0035 | 2026-10-26 |
