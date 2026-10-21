# Architecture Decision Records — архив отменённых решений

Реестр **неактуальных** ADR (статус `Superseded` или `Rejected`). Действующие решения: [README.md](README.md).

Правила:

- Файлы лежат в `docs/adr/archive/<component>/NNNN-slug.md` (номер и компонент сохраняются).
- Статус в front-matter — по скиллу: `rejected` либо `superseded by [ADR-NNNN](NNNN-slug.md)` со взаимной ссылкой в обе стороны.
- Причину отмены и ссылку на заменивший ADR — в колонке «Причина/Замена».
- Номер из архива **никогда не переиспользуется**: сквозная нумерация продолжается дальше.

## common

| ADR | Статус | Название | Причина / Замена | Дата архивации |
|---|---|---|---|---|
| — | — | — | — | — |

## backend

| ADR | Статус | Название | Причина / Замена | Дата архивации |
|---|---|---|---|---|
| — | — | — | — | — |

## frontend

| ADR | Статус | Название | Причина / Замена | Дата архивации |
|---|---|---|---|---|
| — | — | — | — | — |

## infrastructure

| ADR | Статус | Название | Причина / Замена | Дата архивации |
|---|---|---|---|---|
| [ADR-0012](archive/infrastructure/0012-docker-compose-split-dev-env.md) | superseded by [ADR-0022](infrastructure/0022-dev-stand-on-kind.md) | Dev environment: разделение Docker Compose на infrastructure и application, entrypoint с wait-for-DB и auto-migration | Dev-стенд переезжает в единый kind-кластер; compose остаётся только для GitLab | 2026-10-22 |
