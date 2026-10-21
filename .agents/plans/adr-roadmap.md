# BigBug — план разработки ADR

> Дата: 2026-10-21. Статус: план согласован, issues в GitHub НЕ созданы (ждём команды).

## Принципы

- **Один домен — один ADR.**
- **Правило трёх корзин при удалении plans-файла** (проверяется в каждой задаче): *решение* → в ADR; *операционный рецепт* (runbook, команды, troubleshooting) → в остающийся документ (AGENTS.md, permissions.md или ещё живой plans-файл, который его поглотит); *устаревшее* → просто удалить (остаётся в git-истории). Файл удаляется только когда все три корзины разобраны.
- **Право владения файлом**: у каждого plans-файла ровно один ADR-владелец; удаляет файл последний ADR, покрытый контент которого включает весь файл. Если контент кросс-доменный (например, SSO-секция в auth-rbac.md принадлежит 0003, а RBAC — 0004), он переносится в plans-файл будущего владельца или удаляется вместе с последним владельцем.
- **Код — источник истины, не plans-док**: перед записью факта в ADR сверять с кодом (пример: таблица таблиц в database.md всё ещё показывает legacy `*_instances`, в коде уже `resource_providers`/`gitlab_projects`).
- Формат MADR по `docs/adr/_template.md`; язык — русский; создание через skill `/adr`.
- Все ADR создаются со статусом `Proposed`; `Accepted` ставит только человек.
- Нумерация сквозная `0001+`, каталоги `docs/adr/<component>/` (common | backend | frontend | infrastructure).
- Каждый ADR в Consequences указывает, какой контент из `plans/` он покрывает; файл из `plans/` **удаляется в той же задаче**, только если его контент уехал в ADR **полностью**.
- **Под каждый тип тестов — отдельный ADR**; для frontend и backend — отдельно; e2e — в common.

## Исходное состояние

- `docs/adr/` содержит только `README.md`, `ARCHIVE.md`, `_template.md` — реестры пусты.
- Фактический стек (из кода): Python 3.14 + FastAPI + SQLAlchemy 2 + PostgreSQL 17 + Redis 7 + APScheduler + authlib/python-jose/bcrypt; React 19 + TS + AntD 6.4.3 + RTK 2 + RTK Query + keycloak-js 26 + Vite; Yarn 4.3.1; OpenTofu, Keycloak 26, GitLab CE, Harbor.
- Документация разъехалась: `plans/tech-stack.md` заявляет MUI v9 / Node 26 (факт — AntD 6), `plans/architecture/decisions.md` описывает legacy (source_providers и пр.).

## Волна 1 — фундамент (0001–0004)

| # | Slug | Компонент | Удаляемые файлы plans/ |
|---|---|---|---|
| 0001 | `backend-stack-fastapi-sqlalchemy` | backend | — (tech-stack.md общий) |
| 0002 | `frontend-stack-react-antd-rtk` | frontend | — (tech-stack.md общий) |
| 0003 | `keycloak-oidc-dual-auth` | common | владеет SSO-секциями `auth-rbac.md` (flow, role mapping, JWT payload) |
| 0004 | `permission-based-rbac-scope-providers` | common | владеет `plans/features/auth-rbac.md` целиком — удаляет **последним** (после 0003), забирая RBAC-секции |

Примечание: `plans/architecture/permissions.md` НЕ удаляется — операционный индекс прав, на него ссылается AGENTS.md.

## Волна 2 — архитектура приложения (0005–0009)

| # | Slug | Компонент | Удаляемые файлы plans/ |
|---|---|---|---|
| 0005 | `service-layer-no-repository` | backend | — (decisions.md общий) |
| 0006 | `database-postgresql-alembic` | backend | владеет `plans/development/database.md` целиком — удаляет (сначала сверить схему с кодом: в доке legacy `*_instances`, факт — `resource_providers`/`gitlab_projects`) |
| 0007 | `providers-v3-registry` | common | `plans/features/providers-unified.md`, `plans/features/integrations.md` (troubleshooting-секция → AGENTS.md; FERNET-секция → 0010; удаляет оба файла) |
| 0008 | `git-mirroring-github-gitlab` | backend | `plans/features/git-mirroring-v2.md` |
| 0009 | `pull-sync-apscheduler-webhooks` | backend | — (контент в git-mirroring-v2 и decisions.md) |

## Волна 3 — платформа, инфраструктура, тестирование, тулинг (0010–0019)

| # | Slug | Компонент | Удаляемые файлы plans/ |
|---|---|---|---|
| 0010 | `fernet-secrets-encryption` | backend | владеет секцией FERNET key rotation из `integrations.md` (файл удаляет 0007 — к этому моменту секция перенесена) |
| 0011 | `gitlab-ci-pipelines-components` (включая эволюцию по 3 спекам: provisioning → project-management → docker-import-fix) | backend | `plans/features/pipelines.md`, `plans/gitlab-components-provisioning-spec.md`, `plans/gitlab-project-management-spec.md`, `plans/docker-import-fix-spec.md` |
| 0012 | `docker-compose-split-dev-env` | infrastructure | `plans/development/infrastructure.md` частично (compose-структура) |
| 0013 | `opentofu-iac-keycloak-gitlab-harbor` | infrastructure | `plans/development/infrastructure.md` (оставшиеся tofu-секции + troubleshooting → AGENTS.md), удаляет файл; `plans/tech-stack.md` (стек к этому моменту покрыт 0001+0002+0012+0013) |
| 0014 | `backend-unit-testing-pytest` | backend | — (testing.md общий) |
| 0015 | `frontend-unit-testing-vitest` | frontend | — (testing.md общий) |
| 0016 | `backend-integration-testing` | backend | — (testing.md общий) |
| 0017 | `frontend-integration-testing` | frontend | — (testing.md общий) |
| 0018 | `e2e-testing-strategy` (pytest e2e + Cypress planned) | common | владеет `plans/development/testing.md` целиком — удаляет **последним** (после 0014–0017); pytest-шпаргалка и TEST_ARGS → остаются в AGENTS.md / соответствующих тестовых ADR |
| 0019 | `makefile-tooling-single-entrypoint` (Makefile как единая точка входа; mypy, knip, vulture, скрипты lint/format/typecheck/dead-code) | common | `plans/makefile-tooling.md` |

## Волна 4 — продуктовые домены (0020–0021)

| # | Slug | Компонент | Удаляемые файлы plans/ |
|---|---|---|---|
| 0020 | `image-builds-gold-app` (Gold/App Images: модели, версии, build schedules, scan/sign, cosign) | backend | `plans/features/builds.md` |
| 0021 | `user-profile-cabinet` (личный кабинет: профиль, мои команды, мои провайдеры) | frontend | `plans/features/user-profile.md` |

## 0022 — финальная зачистка (задача, не ADR)

Покрытие всех оставшихся файлов `plans/`:

- `plans/architecture/decisions.md` — удалить (контент распределён по 0001–0021; перед удалением проверить, что ни одно решение не осталось без ADR).
- `plans/architecture.md` — legacy, удалить.
- `plans/current-state.md` — удалить (снапшот от 2026-06, устарел; источники истины после миграции — реестр ADR + код).
- `plans/project-overview.md` — ревизия: актуализировать как intro-док или удалить (не решение, ADR не нужен).
- `plans/README.md` — переписать навигацию под новый состав plans/ (сейчас ссылается на несуществующие `features/mirroring.md`, `handoff-summary.md`, `infrastructure-init-redesign.md`); добавить ссылку на `.agents/plans/adr-roadmap.md`.
- `AGENTS.md` — пройтись по всем ссылкам на plans-файлы: битые (удалённые) заменить ссылками на соответствующие ADR; секции, дублирующие ADR, сократить до ссылок на реестр.
- Операционные гайды — **остаются** (это не решения, ADR не нужен), но ревизия: убрать секции, дублирующие ADR, и исправить устаревшие версии:
  - `plans/development/backend.md` — стек-секция сокращается до ссылки на ADR 0001;
  - `plans/development/frontend.md` — стек-секция → ссылка на ADR 0002; проверить версию Node (указано 26 LTS, факт в коде не подтверждён);
  - `plans/development/setup.md` — обновить версии prerequisites, сверить make-команды с фактическим Makefile.
- Ревизия остатка `plans/`: `docker-import-fix-spec.md` удалён в 0011, `features/builds.md` — в 0020, `features/user-profile.md` — в 0021 (после написания соответствующих ADR).
- `plans/architecture/permissions.md` — остаётся (операционный индекс прав), сверить с фактическим `backend/app/core/rbac.py`.
- `docs/architecture/README.md` — добавить блок ссылок на реестр ADR.
- Обновить таблицы реестра `docs/adr/README.md` после Accept (человек принимает волной).

## Организация работ

- Issues: по одному на ADR + issue на зачистку = **22 issues** (создание — только по команде пользователя).
- Каждая волна = отдельная сессия Code; внутри волны ADR создаются через `/adr`.
- Зависимости: 0004 опирается на 0003; 0007 писать после 0005/0006; 0018 (и удаление testing.md) — после 0014–0017; 0019 — после 0001/0002 (ссылается на стековые ADR); 0020 — после 0011 (builds использует CI-домен); 0021 — после 0003/0004 (профиль завязан на auth/RBAC); 0022 — строго последним.

## Вне scope

- ADR по мониторингу/observability и message queue — решения ещё не приняты, планировать нечего; вернуться при появлении.
