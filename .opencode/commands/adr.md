---
description: Создать новый ADR (четырёхфазный workflow skill adr-skill)
agent: plan
---
Создай Architecture Decision Record по четырёхфазному workflow из skill `adr-skill`
(Phase 0: скан кода → Phase 1: сократический интервью, по одному вопросу → Intent
Summary Gate → Phase 2: драфт → Phase 3: проверка по agent-readiness чеклисту).
Не пропускай фазы и не пиши ADR до подтверждения Intent Summary человеком.

Строгое следование конвенциям проекта:

## Структура

- Каталог: `docs/adr/<component>/`, где component ∈ `common` | `backend` | `frontend` | `infrastructure`.
- Решение, затрагивающее несколько компонентов, — в `common/`.
- Нумерация **сквозная по всем компонентам**: следующий `NNNN` = максимальный номер
  среди всех ADR в `docs/adr/` (включая `docs/adr/archive/`) + 1. Номера не переиспользуются.
- Имя файла: `NNNN-slug.md` (kebab-case slug, англоязычный).
- Шаблон: `docs/adr/_template.md` — копируй его, не изобретай свой формат.
- Язык ADR: русский; технические термины не переводить (Providers, RBAC, pipeline, webhook).

## Phase 0 — обязательный скан

- `docs/adr/README.md` — реестр действующих ADR; `docs/adr/ARCHIVE.md` — архив отменённых
  (из отменённых решений не наследоваться, но учитывать их историю).
- `AGENTS.md` — конвенции и структура кода.
- `plans/features/<домен>.md` — профильный доменный документ по затронутой теме
  (auth-rbac, pipelines, providers-unified, security, integrations, ...).
- `plans/architecture/decisions.md` — если решение там уже описано, новый ADR его
  выносит, а в `plans/architecture/decisions.md` помечается «→ вынесено в ADR-NNNN».
- `docs/architecture/` — НЕ читать в контекст (по правилам AGENTS.md, для людей).

## Наполнение

- Implementation Plan — только реальные файлы из AGENTS.md (`backend/app/services/providers/registry.py`,
  `backend/app/core/rbac.py`, `frontend/src/store/api.ts`, ...), не абстракции.
- Verification — только существующие make-цели из корневого `Makefile`
  (`make lint`, `make typecheck`, `make test-unit-backend`, ...). Не выдумывать команды.
- Decision Drivers минимум 2; рассмотренные варианты минимум 2 с явным tradeoff.

## После написания

- Заполни front-matter полностью (adr, component, status: Proposed, date, deciders).
- Добавь строку в реестр компонента в `docs/adr/README.md` (колонки: ADR, Статус, Название, Дата).
- Если новый ADR заменяет существующий — предложи пользователю архивацию: переместить
  старый файл в `docs/adr/archive/<component>/`, выставить `status: Superseded` и
  `superseded_by: ADR-NNNN`, перенести строку в `docs/adr/ARCHIVE.md`.
- Статус `Accepted` выставляет только человек.
