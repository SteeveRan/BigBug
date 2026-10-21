---
status: proposed
date: 2026-10-21
decision-makers: SteeveRan
---

# Считать интеграционным уровнем backend существующий e2e-suite против живого dev-стенда — без отдельного каталога `tests/integration/` и без testcontainers

## Context and Problem Statement

Backend BigBug — асинхронное FastAPI-приложение (ADR-0001) с сервисным слоем без repository pattern (ADR-0005) и PostgreSQL 17 как production-БД (ADR-0006). ADR-0014 зафиксировал unit-уровень: in-process API-тесты на in-memory SQLite, без сети, без dev-стека. Там же зафиксированы известные ограничения SQLite-изоляции: часть PG-специфичного поведения и реальный `commit()` на PostgreSQL unit-уровнем не проверяются.

Вопрос: **существует ли в backend отдельный интеграционный уровень** (API + БД + сервисы вместе, против реального PostgreSQL), и если да — как он оформлен?

Фактическое состояние кода:

- каталога `backend/tests/integration/` **нет**; есть только `backend/tests/unit/` (ADR-0014) и `backend/tests/e2e/` — 25 файлов, ~156 тестов
- `backend/tests/e2e/` прогоняется против **живого dev-стенда** (`make dev-up`, backend на `localhost:8000`): реальный HTTP-транспорт (`AsyncHTTPTransport`, без `ASGITransport`), реальный PostgreSQL из docker compose, без sqlite, без `Base.metadata.create_all`, без dependency-override'ов и без патчей `app.core.secrets` (шапка `tests/e2e/conftest.py`)
- suite уже делает интеграционную работу: полный путь «HTTP → роутер → сервис → SQLAlchemy → PostgreSQL», RBAC на реальных пользователях через `/api/auth/login`, валидация ответов по замороженному OpenAPI-контракту (`openapi_utils.py`), отчёт покрытия эндпоинтов с порогом 90%
- запуск: `make test-e2e-backend` → `backend/scripts/test-e2e.sh` с fail-fast проверкой доступности `/api/health`; маркер `pytest.mark.e2e` отличает эти тесты от unit

Домен — **интеграционный уровень backend**. Unit — ADR-0014; frontend — ADR-0015/0017; сводный e2e-домен (оба стека, CI-политика, удаление `plans/development/testing.md`) — ADR-0018.

Фактический вопрос решения: **принять ли существующий e2e-suite против dev-стенда за интеграционный уровень backend** (не заводя отдельный средний тир), или ввести отдельный интеграционный слой (testcontainers / SQLite-in-process / моки)?

## Decision Drivers

- Интеграционное покрытие **уже существует и живёт в `tests/e2e/`**: реальный PostgreSQL ловит именно те расхождения, которые ADR-0014 записал как «Bad» для SQLite (CHECK-constraints, PG-типы, реальный `commit()`)
- Минимализм (драйвер ADR-0001): testcontainers или отдельный средний тир — новая инфраструктура и новый make-цель/каталог ради дублирования того, что dev-стенд уже даёт; dev-стенд — штатный артефакт разработки (ADR-0012)
- Существующая терминология кода (маркер `e2e`, каталог `tests/e2e/`, make-цель `test-e2e-backend`, скрипт `test-e2e.sh`) уже устоялась на 25 файлах; переименование в `integration` — массовый churn без поведенческой выгоды
- API-тесты e2e-уровня валидируются по OpenAPI-контракту с отчётом покрытия эндпоинтов — это уже контроль полноты интеграционного прогона, отдельная метрика не нужна

## Considered Options

* Принять существующий `tests/e2e/` (живой dev-стенд, реальный HTTP + PostgreSQL) за интеграционный уровень — фактический стандарт кода
* Отдельный средний тир: testcontainers-postgresql + in-process ASGI (`ASGITransport`) в новом `tests/integration/`
* Отдельный средний тир: in-process API-тесты против SQLite (тот же стек, что unit, но тестирующий сквозные сценарии)
* Интеграционное покрытие моками: unit-тесты с `unittest.mock` на границах сервисов, без реальной БД

## Decision Outcome

Chosen option: **существующий e2e-suite против живого dev-стенда — это и есть интеграционный уровень backend**, because он уже прогоняет полный путь API → сервис → PostgreSQL и ловит PG-специфичные расхождения, записанные как ограничения unit-уровня (ADR-0014); dev-стенд — штатный, воспроизводимый одной командой (`make dev-up`, ADR-0012); отдельный средний тир (testcontainers или SQLite-in-process) дублировал бы это покрытие новой инфраструктурой ради экономии секунд на прогоне, что противоречит драйверу минимализма.

### Граница уровней (зафиксировано)

| | Unit (ADR-0014) | Интеграционный (этот ADR) |
|---|---|---|
| Каталог | `backend/tests/unit/` | `backend/tests/e2e/` |
| Транспорт | `ASGITransport`, in-process, без сети | реальный HTTP против `localhost:8000` |
| БД | in-memory SQLite, savepoint-изоляция | реальный PostgreSQL dev-стенда |
| Внешние системы | `unittest.mock` | dev-стек (GitLab/Keycloak), иначе — пропуски по availability |
| Требуемое окружение | только Python venv | `make dev-up` (docker compose) |
| Make-цель | `test-unit-backend` | `test-e2e-backend` |
| OpenAPI | contract unit-тесты схемы | валидация живых ответов + отчёт покрытия эндпоинтов (порог 90%) |

**Терминологическое соглашение**: имя `e2e` (каталог, маркер, make-цель, скрипт) сохраняется как есть — в этом ADR «backend e2e» и «backend integration» суть один и тот же tier. Названия в документации: «интеграционный уровень backend (suite `tests/e2e/`)». Переименование каталога/маркера не проводится; если когда-нибудь появится полноценный кросс-браузерный/Cross-System e2e-домен — это повод для нового ADR, а не для переименования задним числом.

### Consequences

* Good, because интеграционные гарантии уже работают на ~156 тестах: реальный PostgreSQL, реальные миграции Alembic (entrypoint dev-стенда), реальный путь аутентификации и RBAC
* Good, because ноль новых зависимостей и ноль новой инфраструктуры: testcontainers, отдельный каталог и make-цель не вводятся
* Good, because OpenAPI contract validation на живых ответах — бесплатный контроль полноты и нерегрессии API на интеграционном уровне
* Bad, because прогон требует запущенного dev-стенда: в голом CI интеграционный уровень не выполняется (unit — выполняется); CI-политика — домен ADR-0018
* Bad, because имя `e2e` исторически неточно: suite не является e2e в смысле «через браузер / кросс-системный сценарий»; расхождение термина и содержания зафиксировано этим ADR, но не устранено
* Bad, because мягкая изоляция данных (уникальные префиксы `e2e-*`, teardown эфемерных пользователей) вместо транзакционного rollback допускает мусор в dev-БД при падении теста — чистится пересозданием dev-стенда
* Neutral, because сессия прогоняет 3 логина и создаёт/удаляет эфемерных пользователей через реальный API — медленнее unit, но это цена реального пути
* Non-goals: изменение unit-уровня (ADR-0014); frontend-интеграции (ADR-0017); CI-политика запуска и пороги покрытия кода (ADR-0018); введение testcontainers — не решение, а зафиксированная альтернатива с условием пересмотра (ниже)

### Confirmation

Контрольный прогон интеграционного уровня (реальный HTTP + PostgreSQL + RBAC) — suite авторизации и OIDC-конфигурации:

```bash
make dev-up
make test-e2e-backend TEST_ARGS="tests/e2e/test_auth.py tests/e2e/test_oidc_config.py -v"
```

Ожидаемый результат: backend доступен (fail-fast на `/api/health`), все тесты проходят; без запущенного dev-стенда прогон **обязан** завершиться ошибкой «E2E backend is not reachable» — это и есть подтверждение, что тесты не деградировали до unit.

Правила для ревью (fitness-критерии):

1. Интеграционные тесты кладутся в `backend/tests/e2e/` с маркером `pytest.mark.e2e`; создание `backend/tests/integration/` или промежуточного тира — повод переоткрыть этот ADR
2. В `tests/e2e/` запрещены: in-memory SQLite, `ASGITransport`, `app.dependency_overrides`, патчи `app.core.secrets` — всё это признаки unit-теста, misplaced в e2e (см. шапку `tests/e2e/conftest.py`)
3. Ответы API на интеграционном уровне валидируются `assert_matches_openapi`; новый эндпоинт без покрытия в отчёте (`backend/reports/endpoint-coverage.md`, порог 90%) — нарушение
4. Unit-тест, которому нужен реальный PostgreSQL (PG-специфичное поведение, реальный `commit()`), переносится в `tests/e2e/`, а не эмулируется хаками поверх SQLite

## Pros and Cons of the Options

### Существующий `tests/e2e/` против dev-стенда — chosen

Фактический стандарт кода: 25 файлов, реальный HTTP, реальный PostgreSQL, OpenAPI contract validation.

* Good, потому что уже написан, прогоняется и ловит реальные расхождения PostgreSQL (главное «Bad» unit-уровня ADR-0014)
* Good, потому что ноль новых зависимостей и инфраструктуры; dev-стенд — штатный артефакт (ADR-0012)
* Good, потому что fail-fast проверка `/api/health` даёт понятную диагностику вместо зависаний на таймаутах
* Bad, потому что требует docker compose — не выполняется в голом CI и на машинах без Docker
* Bad, потому что имя `e2e` семантически неточно (см. Consequences)

### Отдельный тир: testcontainers-postgresql + in-process ASGI

Новый каталог `tests/integration/`, контейнер PostgreSQL на прогон, `ASGITransport` без сети.

* Good, потому что реальный PostgreSQL без docker compose, пригоден для голого CI
* Good, потому что транзакционная изоляция чище мягкой e2e-изоляции
* Bad, потому что новая зависимость (testcontainers), новый каталог, make-цель и скрипт ради покрытия, которое уже есть в dev-стенде
* Bad, потому что duplicate-поддержка: схемы фикстур, пользователями и окружением пришлось бы обеспечивать в двух местах (контейнер и dev-стенд)
* Условие пересмотра: если dev-стенд станет невозможен в основном CI-контуре (нет Docker / стоимость) и unit-расхождения SQLite начнут массово уходить незамеченными — переоткрыть ADR и рассмотреть testcontainers

### Отдельный тир: in-process тесты против SQLite

Тот же стек, что unit (ADR-0014), но сквозные сценарии вместо точечных.

* Good, потому что быстрый прогон без любого Docker
* Bad, потому что наследует все SQLite-ограничения ADR-0014 — не решает ни одной проблемы, ради которых вводится интеграционный уровень; это просто «больше unit-тестов»
* Bad, потому что третий уровень поверх двух существующих усложняет навигацию без добавления гарантий

### Интеграционное покрытие моками без реальной БД

Только unit с `unittest.mock` на границах; сквозные проверки — код-ревью.

* Good, потому что мгновенный прогон
* Bad, потому что mock повторяет предположения автора о внешней системе, а не её поведение: интеграционные дефекты (миграции, SQL, RBAC-путь, сериализация PG) не ловятся вообще
* Bad, потому что противоречит уже существующей практике — 156 реальных интеграционных тестов пришлось бы удалить или игнорировать

## More Information

- Фактура: `backend/tests/e2e/conftest.py` (транспорт, аутентификация, изоляция данных), `backend/tests/e2e/openapi_utils.py` (OpenAPI contract + отчёт покрытия), `backend/scripts/test-e2e.sh`, Makefile-цель `test-e2e-backend`
- Dev-стенд: ADR-0012 (docker compose split, entrypoint с миграциями), запуск `make dev-up`
- Сиблинги по домену testing: ADR-0014 (backend unit — граница уровней задана там), ADR-0015 (frontend unit), ADR-0017 (frontend integrations), ADR-0018 (e2e — удаляет `plans/development/testing.md`, из которого этот ADR поглощает backend-раздел)
- Связанные ADR: [ADR-0001](0001-choose-backend-stack.md) (стек), [ADR-0005](0005-service-layer-no-repository.md) (что тестируем), [ADR-0006](0006-database-postgresql-alembic.md) (PostgreSQL 17, миграции), [ADR-0011](0011-gitlab-ci-pipelines-components.md) (GitLab-интеграции, проверяемые этим уровнем)
- Реестр ADR и конвенции: [docs/adr/README.md](../README.md)
- Условие пересмотра: недоступность Docker в основном CI при росте SQLite-расхождений (см. testcontainers-альтернативу); появление настоящего кросс-системного e2e-домена (браузерные сценарии frontend+backend) — тогда термин «e2e» разводится на два уровня новым ADR
