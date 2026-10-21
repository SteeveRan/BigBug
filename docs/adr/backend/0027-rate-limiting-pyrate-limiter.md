---
status: proposed
date: 2026-10-22
decision-makers: SteeveRan
consulted: SteeveRan
informed: SteeveRan
---

# Rate limiting: pyrate-limiter с собственной FastAPI-интеграцией, in-memory, kill-switch

## Context and Problem Statement

Как BigBug должен ограничивать частоту запросов к чувствительным endpoint'ам (логин, OIDC exchange) и API в целом?

Rate limiting **уже реализован**, но решение нигде не зафиксировано. Фактическая реализация проверена по коду (`backend/app/core/rate_limit.py`):

- **Библиотека**: `pyrate-limiter` (>= 4.4.0, зависимость в `pyproject.toml`) с **собственной обёрткой** `_RateLimiter` — FastAPI-dependency, а не готовая интеграционная библиотека.
- **Почему не fastapi-limiter** (документировано в докстринге модуля): upstream-библиотека падает с `AttributeError` на `_IncludedRouter.path` — она читает `route.path` из scope, что не работает на вложенных роутерах FastAPI >= 0.115. Собственная обёртка использует `request.url.path` напрямую.
- **Лимиты** (настройки в `app/config.py`): login — `5/minute` (`rate_limit_login`), OIDC exchange — `3/minute` (`rate_limit_oidc_exchange`), global — `1000/minute` (`rate_limit_global`; на endpoint'ах пока не применяется, зарезервирован).
- **Хранилище**: in-memory (`Limiter(rate)` без внешнего бэкенда) — счётчики per-process.
- **Ключ**: клиентская идентичность (`X-Forwarded-For` первый hop, иначе TCP `client.host`) + path запроса.
- **Ответ при превышении**: `429` c `Retry-After: 60`.
- **Kill-switch**: `RATE_LIMIT_ENABLED=false` — фабрика `rate_limit()` возвращает no-op dependency; также no-op при `ENVIRONMENT=test` (ленивая проверка настроек, чтобы тесты могли переключать после импорта). На dev-стенде лимитер выключен по умолчанию (`.env.example`: `RATE_LIMIT_ENABLED=false`) — чтобы e2e-прогоны не упирались в лимит логина.
- **Применение**: сейчас только `POST /api/auth/login` и `POST /api/auth/oidc/exchange` (`app/api/auth.py`).

Нужно зафиксировать выбор библиотеки/подхода, правила применения и политику включения по окружениям.

## Decision Drivers

* Brute-force по кредам — реальная угроза для self-hosted платформы, открытой в сеть; login-эндпоинт обязан дросселироваться
* Вложения: без обязательного Redis (standalone-деплой не должен требовать Redis ради лимитов — Redis в стеке есть, но не как зависимость лимитера)
* Совместимость с актуальным FastAPI (>= 0.115, вложенные роутеры) — готовые интеграции падают
* Тестируемость: unit/e2e-тесты не должны упираться в лимиты ни при каких настройках стенда
* Масштаб: платформа деплоится и горизонтально (k8s, ADR-0023) — in-memory счётчики per-pod приемлемы для дросселирования абуз, не для точного quota

## Considered Options

* pyrate-limiter + собственная FastAPI-обёртка (текущая реализация)
* fastapi-limiter (готовая интеграция)
* slowapi (порт flask-limiter)
* Не ограничивать вовсе (reverse proxy решает)

## Decision Outcome

Chosen option: **pyrate-limiter + собственная обёртка** (`_RateLimiter` как FastAPI-dependency), in-memory хранилище, лимиты из настроек, kill-switch `RATE_LIMIT_ENABLED`.

Правила, зафиксированные по фактической реализации:

1. **Фабрика**: `rate_limit("<N>/<unit>")` возвращает dependency; применение — `Depends(rate_limit(settings.rate_limit_login))` на чувствительных endpoint'ах.
2. **Применение по умолчанию**: аутентификационные endpoint'ы, принимающие креды/коды — login (`5/minute`), oidc/exchange (`3/minute`). Остальные endpoint'ы — по необходимости; `rate_limit_global` (`1000/minute`) зарезервирован для общего лимита, пока не подключён.
3. **Идентичность**: `X-Forwarded-For` (первый hop) или TCP peer; ключ = identity + path. Запрос без идентификации — пропускается (fail-open для неизвестных клиентов; за reverse proxy `X-Forwarded-For` всегда присутствует).
4. **Окружения**: `ENVIRONMENT=test` или `RATE_LIMIT_ENABLED=false` → no-op dependency. На dev-стенде выключен (`.env.example`), на production включён (по умолчанию `true` в настройках).
5. **429**: тело `{"detail": "Too many requests", "retry_after": 60}`, заголовок `Retry-After: 60`.

### Consequences

* Good, потому что brute-force по login/oidc дросселируется без внешней инфраструктуры
* Good, потому что kill-switch + тестовый no-op: тесты никогда не упираются в лимиты (ленивая проверка `settings` позволяет переключать окружение после импорта модуля)
* Good, потому что обход `_IncludedRouter.path`-бага задокументирован в месте решения — будущий контрибьютор не «починит» обратно на fastapi-limiter
* Bad, потому что in-memory = per-process: за N replica'ми эффективный лимит умножается на N (для цели «затруднить brute-force» приемлемо; для точного quota — нет)
* Bad, потому что доверие к `X-Forwarded-For`: прямой клиент может подделать заголовок и обойти лимит по идентичности; mitigations — reverse proxy перезаписывает заголовок, и лимит всё равно применяется per-connection
* Bad, потому что `rate_limit_global` объявлен в настройках и в `.env.example`, но ни к одному endpoint'у не подключён — настройка-заглушка до отдельного решения
* Neutral, потому что счётчики сбрасываются на рестарт процесса — краткое окно послерестартового burst
* Non-goals: распределённое хранилище счётчиков (Redis-бэкенд pyrate-limiter); адаптивные лимиты; per-user квоты на API; CAPTCHA после N неудач

### Confirmation

* No-op путь покрыт конвенцией: `backend/tests/conftest.py` импортирует app при `ENVIRONMENT=test` — все unit-тесты ходят через no-op-ветку (любой зелёный прогон подтверждает, что лимитер не мешает тестам).
* Fitness-проверка на ревью: новый endpoint, принимающий креды (логин-семейство), обязан применять `rate_limit()`; grep: `grep -rn "Depends(rate_limit" backend/app/api` — список дросселируемых endpoint'ов, рост списка по необходимости, исчезновение — ошибка.
* После включения на production-стендах: ручная проверка `for i in $(seq 1 7); do curl -X POST .../api/auth/login; done` — 7-й запрос возвращает 429.

## Pros and Cons of the Options

### pyrate-limiter + собственная обёртка — chosen

См. Decision Outcome.

* Good, потому что работает с современным FastAPI (обход бага задокументирован и заfixтирован тестами окружения)
* Good, потому что без обязательного Redis; in-memory достаточно для цели
* Bad, потому что свою интеграцию надо поддерживать самому (~120 строк)
* Bad, потому что in-memory не шарится между репликами

### fastapi-limiter

Готовая FastAPI-интеграция с Redis-бэкендом.

* Good, потому что out-of-box dependency + decorator API
* Bad, потому что баг `_IncludedRouter.path` на FastAPI >= 0.115 (документирован в докстринге модуля) — библиотека неработоспособна на актуальном стеке
* Bad, потому что Redis обязателен — лишнее требование для standalone-деплоя

### slowapi

Порт flask-limiter для FastAPI.

* Good, потому что зрелый API, декораторы и limits-строки совместимы с flask-экосистемой
* Bad, потому что ещё одна зависимость-обёртка вокруг той же pyrate-limiter/limits с тем же in-memory/redis выбором — выигрыш против собственной обёртки только в декораторах
* Bad, потому что собственная обёртка уже написана и протестирована — миграция ничего не даёт

### Не ограничивать (reverse proxy решает)

* Good, потому что ноль кода
* Bad, потому что standalone-деплой без reverse proxy (docker-compose с портом 8000 наружу — дефолт) остаётся без защиты
* Bad, потому что настройки лимитов в reverse proxy не версионируются с кодом и различаются между стендами

## More Information

* Реализация: `backend/app/core/rate_limit.py`; применение: `backend/app/api/auth.py` (login, oidc/exchange); настройки: `backend/app/config.py` (`rate_limit_*`), `.env.example` + `docker-compose.yml`.
* Связанные ADR: ADR-0003 (аутентификация — защищаемые endpoint'ы), ADR-0001 (backend-стек; pyrate-limiter в зависимостях), ADR-0022/0023 (dev-стенд и k8s-деплой — in-memory лимиты per-pod).
* Эксплуатация: на dev-стенде `RATE_LIMIT_ENABLED=false` (иначе e2e-прогон ломается о лимит логина 5/min) — см. AGENTS.md, раздел e2e runbook.
* Триггеры пересмотра: горизонтальное масштабирование с требованием точного глобального лимита (включить Redis-бэкенд pyrate-limiter новым ADR); потребность в per-user квотах; подключение `rate_limit_global` к API-wide middleware.
