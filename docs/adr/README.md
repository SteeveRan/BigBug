# Architecture Decision Records — актуальные решения

Реестр **действующих** ADR проекта BigBug. Архив отменённых решений: [ARCHIVE.md](ARCHIVE.md).

## Конвенции

- **Формат ADR**: канонический шаблон MADR 4.0 из skill `adr-skill` —
  [`.opencode/skills/adr-skill/assets/templates/adr-madr.md`](../../.opencode/skills/adr-skill/assets/templates/adr-madr.md).
  Свой шаблон не изобретать; секции, front-matter поля и статусы — только как в скилле
  (см. [`adr-conventions.md`](../../.opencode/skills/adr-skill/references/adr-conventions.md)).
- **Front-matter** (по скиллу): `status`, `date`, `decision-makers` (обязательные), `consulted`, `informed` (опциональные, RACI).
- **Статусы** (по скиллу): `proposed | accepted | rejected | deprecated | superseded by [ADR-NNNN](NNNN-slug.md)`.
- **Язык ADR**: русский; технические термины не переводить (Providers, RBAC, pipeline, webhook).
- **Каталоги компонентов**: `docs/adr/<component>/`, где component ∈ `common` | `backend` | `frontend` | `infrastructure`.
- **Сквозная нумерация** (осознанное отклонение от дефолта скилла «номера локальны в категории», принято владельцем проекта): `NNNN` едина для всех компонентов. Следующий номер = максимальный среди **всех** ADR (активные + `archive/`) + 1. Номера не переиспользуются.
- **Имя файла**: `NNNN-slug.md` (по скиллу: kebab-case, present-tense imperative), например `0007-unify-providers-registry.md`.
- **Архивация** (вместо in-place `deprecated`, по требованию проекта): при `superseded` или `rejected` файл перемещается в `docs/adr/archive/<component>/`, статус в front-matter обновляется (для superseded — со взаимной ссылкой на новый ADR в обе стороны), строка удаляется из этого реестра и добавляется в [ARCHIVE.md](ARCHIVE.md).
- **Verification** (секция `### Confirmation` по скиллу): указывать только реально существующие make-цели из корневого `Makefile` (`make lint`, `make typecheck`, `make test-unit-backend`, ...); команды не выдумывать.
- **Скрипт `scripts/new_adr.js` скилла не используется**: его нумерация локальна внутри каталога и несовместима со сквозной нумерацией и схемой архива этого репозитория. Файл создаётся вручную из канонического шаблона скилла; `set_adr_status.js` использовать можно.
- **Связь с доменами**: в `## Context and Problem Statement` и `## More Information` ссылаться на `plans/features/<домен>.md` и `plans/architecture/decisions.md`.

## Реестр актуальных ADR

### common

| ADR | Статус | Название | Дата |
|---|---|---|---|
| — | — | — | — |

### backend

| ADR | Статус | Название | Дата |
|---|---|---|---|
| — | — | — | — |

### frontend

| ADR | Статус | Название | Дата |
|---|---|---|---|
| — | — | — | — |

### infrastructure

| ADR | Статус | Название | Дата |
|---|---|---|---|
| — | — | — | — |

## Правила для агентов

1. Перед любым архитектурным изменением / новой зависимостью / новым паттерном — прочитать этот реестр и релевантные ADR со статусом `accepted` (по скиллу: accepted обязателен к исполнению, proposed — учитывать, rejected/deprecated — не наследоваться).
2. Новое решение, затрагивающее несколько компонентов, размещается в `common/`.
3. Создание ADR — через команду `/adr` (workflow skill `adr-skill`), а не вручную с нуля.
