---
description: Создать новый ADR (четырёхфазный workflow skill adr-skill)
agent: plan
---
Создай Architecture Decision Record строго по четырёхфазному workflow из skill `adr-skill`.
Фазы скилла обязательны и не подлежат «пропуску с обоснованием»:

- **Phase 0 — Scan the Codebase** (см. SKILL.md скилла): скан существующих ADR, стека, паттернов.
- **Phase 1 — Capture Intent** (сократическое интервью по одному вопросу + **Intent Summary Gate**).
- **Phase 2 — Draft the ADR** по каноническому шаблону.
- **Phase 3 — Review** по чеклисту agent-readiness.

## Жёсткие требования фаз (не отменяются источником задачи)

- **Наличие issue/плана с ответами НЕ отменяет Phase 1.** Если ответы на вопросы Phase 1
  уже есть в issue, плане или документах — сократическое интервью сокращается, но
  **Intent Summary Gate обязателен всегда**: собери summary (Title, Trigger, Constraints,
  Options, Lean, Non-goals, Related ADRs/code, Affected files, Verification) и дождись
  явного подтверждения человека («да, фиксируй»), прежде чем создавать файл. Без Gate
  ADR не пишется вообще.
- Допускается самостоятельно определять только механические поля: номер `NNNN`, дата,
  slug. Всё содержательное — только через подтверждённый Intent Summary.
- **Phase 3 прогоняется формально**: прочитай `references/review-checklist.md` скилла
  и пройдись по каждому пункту, приведя в ответе результат проверки (пункт → ok/нет → почему).
  «Прошёлся в уме» — не выполненная Phase 3.

## Формат — только канонический шаблон скилла

- Копируй шаблон `.opencode/skills/adr-skill/assets/templates/adr-madr.md` (MADR 4.0):
  секции, порядок и формулировки — как в шаблоне.
- Front-matter строго по скиллу: `status`, `date`, `decision-makers` (обязательные),
  `consulted`, `informed` (опциональные). Дополнительных полей не добавляй.
- Статусы строго по скиллу: `proposed | accepted | rejected | deprecated |
  superseded by [ADR-NNNN](NNNN-slug.md)`. Новый ADR создаётся со статусом `proposed`.
- Язык ADR: русский; технические термины не переводить (Providers, RBAC, pipeline, webhook).

## Размещение — конвенции проекта (docs/adr/README.md)

- Каталог: `docs/adr/<component>/`, где component ∈ `common` | `backend` | `frontend` | `infrastructure`.
  Решение, затрагивающее несколько компонентов, — в `common/`.
- Нумерация **сквозная по всем компонентам и архиву**: следующий `NNNN` = максимальный номер
  среди всех ADR в `docs/adr/` (включая `docs/adr/archive/`) + 1. Номера не переиспользуются.
- Имя файла: `NNNN-slug.md` (kebab-case, present-tense imperative slug, англоязычный).
- **Скрипт `scripts/new_adr.js` сознательно не используется**: его нумерация локальна
  внутри одного каталога и не может выразить сквозную нумерацию проекта и схему архива.
  Скилл сам предписывает следовать конвенциям репозитория, если они уже есть. Файл
  создаётся вручную из канонического шаблона — это санкционированное отклонение,
  зафиксированное в `docs/adr/README.md`. Скрипт `set_adr_status.js` использовать можно.

## Phase 0 — обязательный скан

- `docs/adr/README.md` — реестр действующих ADR; `docs/adr/ARCHIVE.md` — архив отменённых
  (из отменённых решений не наследоваться, но учитывать их историю).
- `AGENTS.md` — конвенции и структура кода.
- `plans/features/<домен>.md` — профильный доменный документ по затронутой теме
  (auth-rbac, pipelines, providers-unified, security, integrations, ...).
- `plans/architecture/decisions.md` — если решение там уже описано, новый ADR его
  выносит, а в `plans/architecture/decisions.md` помечается «→ вынесено в ADR-NNNN».
- `docs/architecture/` — НЕ читать в контекст (по правилам AGENTS.md, для людей).

## Наполнение секций по правилам проекта

- Секция `### Confirmation` (verification по скиллу): только реально существующие make-цели
  из корневого `Makefile` (`make lint`, `make typecheck`, `make test-unit-backend`, ...),
  конкретные и проверяемые. Команды не выдумывать.
- Constraints и affected files — только реальные файлы из AGENTS.md
  (`backend/app/services/providers/registry.py`, `backend/app/core/rbac.py`,
  `frontend/src/store/api.ts`, ...), не абстракции. Non-goals — явно, по требованиям скилла.
- Минимум 2 рассмотренных варианта с явным tradeoff (по шаблону: Considered Options +
  Pros and Cons of the Options).
- `## Context and Problem Statement` и `## More Information` — ссылки на доменные
  документы `plans/features/<домен>.md`, релевантные ADR, issues.

## После написания

- Добавь строку в реестр компонента в `docs/adr/README.md` (колонки: ADR, Статус, Название, Дата).
- Если новый ADR заменяет существующий — предложи пользователю архивацию: переместить
  старый файл в `docs/adr/archive/<component>/`, выставить в front-matter
  `status: superseded by [ADR-NNNN](NNNN-slug.md)` со взаимной ссылкой в обе стороны,
  перенести строку в `docs/adr/ARCHIVE.md`.
- Статус `accepted` выставляет только человек.
