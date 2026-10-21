---
status: proposed
date: 2026-10-21
decision-makers: SteeveRan
---

# Тестировать backend unit-уровень стеком pytest + pytest-asyncio + httpx AsyncClient (без запущенного сервера)

## Context and Problem Statement

Backend BigBug — асинхронное FastAPI-приложение (ADR-0001), сервисный слой без repository pattern (ADR-0005). Тесты уже написаны (924 unit-теста в `backend/tests/unit/`), но решение о **тестовом стеке unit-уровня** нигде не зафиксировано — оно существует только в коде (`backend/pyproject.toml`, `backend/tests/conftest.py`) и в `plans/development/testing.md` (файл удаляется после принятия ADR-0018).

Фактический вопрос: **принимать ли существующий стек как стандарт** — pytest + pytest-asyncio (asyncio_mode=auto) + httpx `AsyncClient` поверх `ASGITransport` (API-тесты без запущенного uvicorn) + in-memory SQLite, с общими fixture в `conftest.py` и пробросом флагов через `TEST_ARGS`?

Домен — **только unit-уровень backend** (`backend/tests/unit/`). E2E-уровень backend — ADR-0018; frontend — ADR-0015/0017.

## Decision Drivers

- Асинхронный код везде: async-роутеры, async-сервисы, SQLAlchemy 2 async (ADR-0001, ADR-0005) — тестовый стек обязан нативно запускать async-тесты и async-фикстуры
- API-тесты должны вызывать приложение в процессе (in-process), без оркестрации uvicorn/портов: unit-прогон обязан работать в голом CI без dev-стека
- Изоляция тестов друг от друга по БД без отдельного PostgreSQL в CI — dev-зависимость `aiosqlite` уже есть
- Минимализм (драйвер ADR-0001): без новых инфраструктурных зависимостей; мокирование — stdlib `unittest.mock` (pytest-mock сознательно не добавлен)
- Единая точка входа запуска — корневой Makefile с пробросом аргументов (`TEST_ARGS`), соглашение общее для backend и frontend

## Considered Options

* pytest + pytest-asyncio + httpx AsyncClient (in-process, ASGITransport) — фактический стандарт кода
* unittest (stdlib) + unittest.IsolatedAsyncioTestCase
* plain httpx против запущенного сервера (real transport)
* Jest-style snapshot testing (jest-snapshots / syrupy)

## Decision Outcome

Chosen option: **pytest + pytest-asyncio + httpx AsyncClient (in-process)**, because это уже работающий стандарт с 924 тестами: pytest-asyncio в `asyncio_mode = "auto"` убирает ручные декораторы на каждом async-тесте, `ASGITransport` прогоняет API-тесты через реальный ASGI-стек FastAPI без сети и без запущенного uvicorn, а in-memory SQLite с rollback-изоляцией даёт быстрый детерминированный прогон в голом CI.

### Инструментарий и конфигурация (зафиксировано)

**Зависимости** — `backend/pyproject.toml`, группа `dev` (источник истины по версиям):

| Пакет | Роль |
|---|---|
| `pytest >= 8.2` | фреймворк |
| `pytest-asyncio >= 0.23` | async-тесты и async-фикстуры |
| `pytest-cov >= 5.0` | покрытие (`make coverage-*`) |
| `httpx >= 0.27` | `AsyncClient` для API-тестов (уже в runtime-зависимостях) |
| `aiosqlite >= 0.20` | in-memory SQLite для тестовой БД |
| `jsonschema`, `factory-boy`, `faker` | contract-проверки OpenAPI, генерация тестовых данных |

**pytest-конфиг** — `[tool.pytest.ini_options]` в `pyproject.toml` (отдельного `setup.cfg`/`pytest.ini` нет):

- `asyncio_mode = "auto"` — async-тесты и `pytest_asyncio.fixture` без `@pytest.mark.asyncio` на каждом тесте
- `testpaths = ["tests"]`; имена `test_*.py` / `Test*` / `test_*`
- маркер `e2e` — отличает e2e-тесты (требуют dev-стек) от unit; unit-тесты маркеров не требуют, живут в `tests/unit/`

**API-тесты без сервера**: `AsyncClient(transport=ASGITransport(app=app), base_url="http://test")` — запрос идёт напрямую в FastAPI-приложение в процессе теста. Подмена БД — через `app.dependency_overrides[get_db]` (см. fixture `client` в `conftest.py`).

**Изоляция БД** (шаблон transaction-rollback из документации SQLAlchemy):

- одна in-memory SQLite (`sqlite+aiosqlite:///:memory:`, `StaticPool`) на сессию pytest, схема создаётся один раз
- каждый тест — вложенная транзакция (`begin_nested()`); сессии теста и endpoint'ов открываются поверх неё с `join_transaction_mode="create_savepoint"` — `commit()` внутри handler'а превращается в savepoint release, откат внешней транзакции даёт пустую БД на следующий тест
- следствие: unit-тесты не требуют PostgreSQL и работают параллельно с любым запущенным dev-стеком

**Ускорение и детерминизм**:

- fixture `_fast_bcrypt` (autouse, session) снижает bcrypt-раунды до 4 (~60x быстрее), сохраняя реальный алгоритм
- `settings.environment = "test"` отключает rate limiting на весь прогон
- `tests/unit/conftest.py` — autouse-патч `settings.encryption_key` на валидный Fernet-ключ + сброс LRU-кэша `get_cipher` (см. ADR-0010)

**Мокирование**: stdlib `unittest.mock` (`patch`, `AsyncMock`, `MagicMock`). Зависимость pytest-mock **не добавляется** — `mocker`-фикстура не нужна, `unittest.mock.patch` покрывает всё (52 файла unit-тестов используют только его).

**Запуск** — единая точка входа Makefile, проброс флагов через `TEST_ARGS`:

```bash
make test-unit-backend TEST_ARGS="-k test_login"        # фильтр по имени
make test-unit-backend TEST_ARGS="tests/unit/test_secrets.py -v"  # конкретный файл
make test-e2e-backend TEST_ARGS="tests/e2e/test_auth.py -v"       # e2e (ADR-0018)
```

`TEST_ARGS` пробрасывается в `backend/scripts/test-unit.sh` (переменная окружения `ENVIRONMENT=test` ставится скриптом) и аналогично в frontend-скрипты — соглашение общее для обоих стеков. Ручной запуск (`cd backend && pytest -k ...`) возможен, но make — канонический способ для агентов и CI.

### Consequences

* Good, because unit-прогон не требует ни запущенного сервера, ни PostgreSQL, ни dev-стека — работает в голом CI и локально за секунды
* Good, because `asyncio_mode = "auto"` — минимальный boilerplate: async-тесты пишутся как обычные функции
* Good, because API-тесты идут через реальный ASGI-стек (middleware, dependency injection, роутинг) — покрытие близко к интеграционному без цены оркестрации
* Good, because rollback-изоляция даёт чистую БД на каждый тест без `drop_all`/пересоздания схемы
* Bad, because in-memory SQLite отличается от production PostgreSQL 17: нет части CHECK-constraint'ов и специфичных для PG типов поведения; расхождения ловит только e2e-уровень (ADR-0018, там dev-стек с реальным PostgreSQL)
* Bad, because transaction-rollback-хитрость (`begin_nested` + create_savepoint) непрозрачна: тест, проверяющий именно поведение реального `commit()`, может дать ложный результат — такие проверки уходят в e2e
* Bad, because `event_loop`-fixture с session scope привязывает тесты к текущему API pytest-asyncio (0.23); при апгрейде на pytest-asyncio 1.x потребуется миграция (см. «Условие пересмотра»)
* Neutral, because фикстуры аутентификации (`admin_token`, `login_headers`, `operator_token`, `viewer_*`) проходят реальный `/api/auth/login` — медленнее прямого crafting'а JWT, но тестируют настоящий путь авторизации
* Non-goals: e2e-тестирование backend (ADR-0018); frontend-тестирование (ADR-0015/0017); coverage-политика (пороги и отчёты — отдельно, `pytest-cov` лишь инструмент); contract-тестирование OpenAPI как отдельный домен (пока — обычные unit-тесты `test_openapi_contract.py`)

### Confirmation

Контрольный прогон стека (фикстуры БД + API-клиент + аутентификация) — suite авторизации:

```bash
make test-unit-backend TEST_ARGS="tests/unit/test_auth_me.py -v"
```

Ожидаемый результат: все тесты проходят (запускается без dev-стека, только Python venv).

Правила для ревью (fitness-критерии):

1. Новые unit-тесты кладутся в `backend/tests/unit/`, имя `test_*.py`, без маркера `e2e` (маркер — только для `tests/e2e/`)
2. Async-тесты **не** помечаются `@pytest.mark.asyncio` вручную — режим auto (появление маркера — сигнал, что тест ошибочно помещён не в auto-режим конфигурации)
3. Мокирование — только `unittest.mock`; добавление pytest-mock/respx/pytest-httpserver — повод переоткрыть этот ADR
4. API-тесты используют fixture `client` из `conftest.py`; запуск реального HTTP-сервера в unit-тестах — нарушение
5. Новый общий fixture — в `conftest.py` (`tests/` или `tests/unit/`), а не дублируется по файлам тестов

## Pros and Cons of the Options

### pytest + pytest-asyncio + httpx AsyncClient (in-process) — chosen

Фактический стандарт кода, 924 unit-теста.

* Good, because нативный async: pytest-asyncio auto-режим покрывает и тесты, и fixture
* Good, because in-process API-тесты: полный ASGI-стек без сети, портов и ожидания старта uvicorn
* Good, because fixture-система pytest + `conftest.py` — переиспользование (БД, пользователи, токены) без базовых классов
* Good, because экосистема: pytest-cov, маркеры, `-k`-фильтрация, `--lf` — из коробки
* Bad, because два слоя изоляции (fixture-транзакция поверх реального кода endpoint'ов) требуют понимания savepoint-механики при отладке

### unittest (stdlib) + IsolatedAsyncioTestCase

* Good, because ноль зависимостей — test runner и async-поддержка уже в stdlib
* Bad, because нет fixture-инъекции и экосистемы: общие фикстуры БД/пользователей превратились бы в иерархии базовых классов
* Bad, because `IsolatedAsyncioTestCase` создаёт event loop на тест — медленнее и шумнее, чем session-scoped loop pytest-asyncio
* Bad, because переписать 924 существующих теста — цена без выгоды

### plain httpx против запущенного сервера (real transport)

* Good, because тестирует настоящий сетевой путь (uvicorn, TCP) — максимум реализма
* Bad, because unit-прогон требует оркестрации: старт/стоп сервера, ожидание готовности, выбор порта, очистка — это определение e2e-уровня (ADR-0018), не unit
* Bad, because медленно и хрупко в CI; отладка упавших тестов через сетевой слой мучительна
* Условие пересмотра: нет — реализм сетевого слоя покрывается e2e-ADR

### Jest-style snapshot testing (syrupy)

* Good, because дёшево фиксирует сложные структуры ответов (одна строка на тест)
* Bad, because snapshot-дифф не объясняет причину падения: рефакторинг серийных полей API ломает сотни снапшотов разом
* Bad, because не заменяет поведенческих assert'ов — для CRUD-логики и RBAC нужны точные проверки статусов и тел ответов, а не «совпало/не совпало»
* Bad, because добавляет зависимость и новый формат артефактов ради того, что обычные assert'ы уже покрывают

## More Information

- Конфигурация: `backend/pyproject.toml` (`[tool.pytest.ini_options]`, dev-зависимости)
- Фикстуры: `backend/tests/conftest.py` (БД, клиент, пользователи/токены), `backend/tests/unit/conftest.py` (патч `ENCRYPTION_KEY`)
- Запуск: `backend/scripts/test-unit.sh`, Makefile-цели `test-unit-backend` / `test-e2e-backend`, проброс `TEST_ARGS`
- Сиблинги по домену testing: ADR-0015 (frontend unit), ADR-0016 (backend integrations), ADR-0017 (frontend integrations), ADR-0018 (e2e — удаляет `plans/development/testing.md`, из которого этот ADR поглощает backend-раздел)
- Связанные ADR: [ADR-0001](0001-choose-backend-stack.md) (стек, async-драйвер), [ADR-0005](0005-service-layer-no-repository.md) (что тестируем — сервисный слой), [ADR-0006](0006-database-postgresql-alembic.md) (production-БД, отличия SQLite), [ADR-0010](0010-fernet-secrets-encryption.md) (патч ключа в unit-фикстуре)
- Реестр ADR и конвенции: [docs/adr/README.md](../README.md)
- Условие пересмотра: апгрейд pytest-asyncio до 1.x (удаление/изменение `event_loop`-fixture API); переход тестовой БД на PostgreSQL (testcontainers) при росте числа SQLite-расхождений; появление потребности в мокировании HTTP-границ (respx) в provider-клиентах
