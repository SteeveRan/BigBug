---
status: proposed
date: 2026-10-22
decision-makers: SteeveRan
consulted: SteeveRan
informed: SteeveRan
---

# Модель безопасности транспортного и периметрового уровня: TLS на reverse proxy, per-provider verify_ssl, CORS, TTL токенов

## Context and Problem Statement

Как зафиксировать транспортную безопасность, политику доверия к внешним интеграциям, CORS и политику времени жизни JWT в BigBug?

Эти решения разрозненно живут в коде, а legacy-документ `docs/architecture/10-security.md` (удалён в #49) описывал их частично неверно (в частности, обещал верификацию webhook'ов, которой нет — см. [ADR-0025](0025-verify-incoming-webhooks-shared-secret.md)). Факты, проверенные по коду:

- **TLS**: терминируется на reverse proxy (nginx/traefik перед backend; в k8s — ingress, ADR-0022/0023). Backend сам по себе HTTP; checklist деплоя (`docs/runbooks/deploy-security-checklist.md`) требует HTTPS на proxy и запрета наружного plain HTTP.
- **Исходящие соединения к внешним системам** (GitLab, Harbor, Docker Registry, Helm-репозитории): доверие управляется **per-provider флагом `verify_ssl`** (`resource_providers.verify_ssl`, модель `backend/app/models/resource_provider.py`, default `True`; поле в API-схемах, frontend-формах; используется всеми клиентами — `providers/clients/_http.py`, `gitlab.py`, `mirror.py`, `helm.py`, `docker.py`, `harbor_scan.py` и др. через `ssl_verify=provider.verify_ssl`).
- **CORS**: захардкожено в `backend/app/main.py` — `allow_origins=["http://localhost:5173", "http://localhost:3000"]`, `allow_credentials=True`, методы/заголовки `*`.
- **JWT TTL** (`backend/app/config.py`): access — 60 минут (`access_token_expire_minutes`), refresh — 7 дней (`refresh_token_expire_days`); подпись HS256 общим `SECRET_KEY`; refresh endpoint (`POST /api/auth/refresh`) выпускает новую пару, проверяя `type: "refresh"` в payload; logout/revoke/черных списков нет — токен живёт до истечения.

Нужно зафиксировать эти решения (включая осознанный выбор «hardcode vs env» для CORS) и честно записать пробелы (отсутствие отзыва токенов).

## Decision Drivers

* Self-hosted платформа за reverse proxy: HTTPS — задача периметра, дублировать в приложении не нужно
* Dev-стенды на self-signed сертификатах (Harbor в kind, корпоративные GitLab) — жёсткая глобальная проверка сертификатов ломает легитимные стенды
* SPA на отдельном origin (Vite dev 5173, prod-сборка за тем же proxy) — CORS должен пропускать только известные origin'ы
* Кража токена: без revoke скомпрометированный access-токен живёт до 60 минут, refresh — до 7 дней
* Минимализм конфигурации: не плодить env-переменные, которые никто не настраивает

## Considered Options

* CORS: захардкоженные dev-origin'ы (текущее состояние) vs env-переменная `CORS_ORIGINS`
* verify_ssl: per-provider флаг (текущее) vs глобальный флаг vs всегда on
* Отзыв токенов: только TTL (текущее) vs server-side blacklist

## Decision Outcome

Chosen option — четыре подпункта, каждый по фактическому состоянию кода с явной фиксацией пробелов:

### 1. TLS — терминирование на reverse proxy

Backend всегда HTTP; HTTPS обеспечивает reverse proxy (nginx/traefik в compose-деплоях, ingress в k8s — ADR-0022/0023). Приложение не выполняет TLS и не проверяет схему запроса. Требования к деплою — runbook `docs/runbooks/deploy-security-checklist.md` (HTTPS на proxy, наружу только 80/443, DB/Redis без публичных портов).

### 2. Исходящий TLS к внешним системам — per-provider `verify_ssl`

Флаг `verify_ssl` на каждом `resource_provider` (default `True`), управляется через UI/API провайдеров. Все HTTP-клиенты провайдеров обязаны передавать `verify=provider.verify_ssl`. Отключать проверку — только для self-signed dev-стендов (правило в runbook).

### 3. CORS — захардкоженные dev-origin'ы, env-настройка отложена

**Решение: оставить hardcode** `["http://localhost:5173", "http://localhost:3000"]` в `main.py` на текущем этапе; вынести в переменную `CORS_ORIGINS` при первом production-деплое с отдельным frontend-origin (триггер — см. Confirmation). Обоснование: во всех текущих схемах деплоя SPA отдаётся тем же reverse proxy, что и API (тот же origin — CORS не задействован), а dev-стенд всегда localhost. Env-переменная, нужная только одному гипотетическому деплою, — YAGNI.

### 4. JWT TTL / refresh — без server-side отзыва

Access 60 мин, refresh 7 дней (HS256, `SECRET_KEY`); `POST /api/auth/refresh` (rate limit — ADR-0027) ротирует пару; `type: "refresh"` отличает refresh от access. **Осознанный пробел**: отзыва (logout/revoke/blacklist) нет — скомпрометированный refresh-токен действует до истечения или до смены `SECRET_KEY` (которая разлогинивает всех). Acceptance: модель угроз платформы (внутренний DevOps-инструмент, короткий TTL access, права зашиты в токен) позволяет принять риск; требование мгновенного отзыва (увольнение сотрудника) закрывается деактивацией пользователя — `get_current_user` проверяет `is_active` на каждый запрос, и access-токен перестаёт работать немедленно, несмотря на подпись.

### Consequences

* Good, потому что периметровая TLS-политика не дублируется в коде — одна точка (proxy) настройки сертификатов
* Good, потому что per-provider `verify_ssl` не жертвует безопасностью по умолчанию (default True) и позволяет работать с self-signed стендами точечно
* Good, потому что деактивация учётки работает как мгновенный revoke без инфраструктуры чёрных списков
* Bad, потому что CORS hardcode: деплой с раздельными origin'ами потребует правки кода (осознанно; триггер выноса в env — в Confirmation)
* Bad, потому что кража refresh-токена даёт 7 дней доступа без возможности отзыва конкретного токена (mitigation: смена `SECRET_KEY` — разлогин всех; деактивация пользователя — блокировка по `is_active`)
* Bad, потому что `verify_ssl=False` на провайдере открывает MITM-вектор на креды этого провайдера; риск принят для dev-стендов, в production недопустим (runbook)
* Neutral, потому что HS256 (симметричный) вместо RS256: подписывает и проверяет один и тот же сервис — асимметрия не нужна; смена ключа разлогинивает всех (приемлемо)
* Non-goals: mTLS между сервисами внутри кластера; CSP/заголовки безопасности frontend (решение на уровне proxy); серверные сессии (отклонены в ADR-0003); автоматическая ротация `SECRET_KEY`

### Confirmation

* Транспорт: `docs/runbooks/deploy-security-checklist.md` — чеклист деплоя (HTTPS на proxy, уникальные ключи, изоляция DB/Redis). Исполнение проверяется при деплое человеком.
* verify_ssl: unit-тесты клиентов передают флаг (например, `backend/tests/unit/test_provider_clients_*.py` — клиенты строятся с `verify_ssl`); fitness: grep `verify=` в `backend/app/services/providers/clients/` — все клиенты принимают `verify_ssl` параметром.
* CORS: unit-тест `backend/tests/unit/test_cors.py` (новый, после принятия): preflight-запрос с origin `http://localhost:5173` → `access-control-allow-origin` присутствует; origin `http://evil.example` → отсутствует.
* is_active-revoke: e2e `backend/tests/e2e/` — запрос с валидным access-токеном после деактивации пользователя → 401 (покрывается существующими auth-тестами `get_current_user`).

## Pros and Cons of the Options

### CORS: hardcode — chosen (на текущем этапе)

* Good, потому что нулевая конфигурация; в типовых деплоях (SPA за тем же proxy) CORS не задействован вовсе
* Bad, потому что раздельные origin'ы требуют правки кода
* Bad, потому что забытый hardcode — частый источник «на проде не работает» (mitigation: триггер выноса в Confirmation)

### CORS: env-переменная `CORS_ORIGINS`

* Good, потому что конфигурация деплоя без правки кода
* Bad, потому что сегодня ни один деплой-схема не нуждается (SPA всегда same-origin или localhost) — переменная-мертвец, как `rate_limit_global`

### verify_ssl: per-provider флаг — chosen

* Good, потому что granular: один self-signed Harbor не ослабляет проверку для корпоративного GitLab
* Bad, потому что флаг в UI — соблазн нажать «отключить проверку» при любой проблеме с сертификатом (mitigation: правило в runbook + default True)

### verify_ssl: глобальный флаг / всегда on

* Good, потому что всегда on — максимальная безопасность
* Bad, потому что self-signed dev-стенды (Harbor в kind — штатная схема, ADR-0022) неработоспособны; глобальный off — MITM везде

### Отзыв токенов: только TTL + is_active — chosen (с зафиксированным пробелом)

* Good, потому что деактивация пользователя закрывает главный кейс мгновенного отзыва без инфраструктуры
* Bad, потому что отзыв конкретного токена (кража без компрометации учётки) невозможен до истечения

### Отзыв: server-side blacklist (Redis)

* Good, потому что точечный revoke по jti
* Bad, потому что DB round-trip на каждый запрос ломает безгосударственную проверку `get_current_user` и кэш permissions в JWT (отклонено ещё в ADR-0003 как «server-side sessions»)
* Bad, потому что новая обязательная зависимость пути каждого запроса от Redis

## More Information

* Код: `backend/app/main.py` (CORS), `backend/app/config.py` (TTL, ключи), `backend/app/core/security.py` (`create_access_token`/`create_refresh_token`/`decode_token`), `backend/app/core/rbac.py` (`get_current_user` — проверка `is_active`), `backend/app/models/resource_provider.py` (`verify_ssl`), `backend/app/services/providers/clients/_http.py` (передача `verify`).
* Связанные ADR: ADR-0003 (аутентификация, JWT, отклонение server-side сессий), ADR-0010 (шифрование секретов `ENCRYPTION_KEY`), ADR-0025 (верификация webhook'ов — отдельный механизм), ADR-0027 (rate limiting), ADR-0022/0023 (k8s-деплой: ingress, secrets), ADR-0024 (secrets в k8s).
* Runbook деплоя: `docs/runbooks/deploy-security-checklist.md`.
* Происхождение: threat-model таблица legacy `docs/architecture/10-security.md` (удалён в #49) использована как черновик, но переписана по фактам кода: claim «HMAC/token верификация webhook» был ложным (см. ADR-0025); разделы про CORS/rate limit/TTL выверены.
* Триггеры пересмотра: первый деплой с раздельными frontend/backend origin'ами (вынести CORS в `CORS_ORIGINS`); требование регуляторики к отзыву токенов (blacklist новым ADR); появление сервис-меша (пересмотреть TLS-терминирование).
