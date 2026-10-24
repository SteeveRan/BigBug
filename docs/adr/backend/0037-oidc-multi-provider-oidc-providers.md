---
status: proposed
date: 2026-10-24
decision-makers: "@SteeveRan"
consulted: ""
informed: ""
---

# OIDC multi-provider: таблица `oidc_providers` вместо singleton `oidc_config`, list-контракт `/sso/config`, `provider_id` в exchange

## Context and Problem Statement

SSO-конфигурация сейчас — singleton: таблица `oidc_config` (одна строка),
`GET /api/auth/sso/config` возвращает единственный объект SSO-bootstrap, login-flow
провайдер-агностичен. Продукту требуется **несколько OIDC-провайдеров**: админ
регистрирует несколько Keycloak (или иных OIDC) настроек, фронтенд рендерит по одной
SSO-кнопке на каждый включённый провайдер.

Текущая архитектура этого не позволяет: сервис `OIDCConfigService` читает
`select(OIDCConfig).limit(1)`, JWKS-кэш в `KeycloakOIDCService` — глобальный на процесс
(один набор ключей), а контракт `/sso/config` — плоский объект без списка провайдеров.

Вопрос: как заменить singleton на коллекцию провайдеров с сохранением
master-switch, security-семантики (CSRF-привязка flow к провайдеру, изоляция
JWKS-валидации между realm'ами) и минимумом кода?

Связано: [ADR-0036](0036-oidc-issuer-semantics-rfc-8414.md) (семантика `issuer_url`,
RFC 8414 — зависит от него), [ADR-0003](../common/0003-keycloak-oidc-dual-auth.md)
(dual-auth), [ADR-0010](0010-fernet-secrets-encryption.md) (шифрование credentials),
issue [SteeveRan/BigBug#98](https://github.com/SteeveRan/BigBug/issues/98).

## Decision Drivers

* Несколько провайдеров: админ CRUD, per-provider `enabled`, сортировка кнопок.
* Master-switch «SSO вкл/выкл глобально» остаётся сверху per-provider флагов — incident
  сценарий «убить весь SSO» не должен требовать правки каждого провайдера.
* Security: токен realm A не должен валидироваться конфигом провайдера B — JWKS-кэш и
  ожидаемый iss обязаны быть per-provider/per-realm.
* CSRF-привязка: `provider_id` передаётся в exchange и в OIDC `state`-параметр —
  exchange отвергает mismatch.
* Обратная совместимость не стоит кода: legacy-эндпоинт `/admin/oidc-config` удаляется
  без deprecation shim (внутренний admin API, единственный фронтенд);
  legacy-значение `issuer_url` без `/realms/` мигрирует как есть (per ADR-0036 —
  «не сконфигурирован до пересохранения»).
* Frontend-изменения — отдельный issue, ломающий контракт; оба должны попасть в один
  релиз.

## Considered Options

* **Одна таблица `oidc_providers` + list-контракт + `provider_id` в exchange** (выбрано)
* Singleton как «default» + отдельная таблица для дополнительных провайдеров
* Убрать master-switch, управлять только per-provider `enabled`
* OIDC discovery fetch для разрешения провайдера по issuer

## Decision Outcome

Chosen option: "Одна таблица `oidc_providers` + list-контракт + `provider_id` в
exchange", потому что это один код-путь (никаких «default + extras» ветвлений), вся
коллекция живёт в одном CRUD с существующей permission-моделью, а security-требования
(per-provider JWKS/iss, state-привязка) ложатся на таблицу естественно.

Семантика:

* Таблица `oidc_providers`, одна строка на провайдер: `name` (display name для кнопки),
  `issuer_url`, `client_id`, `client_secret` (Fernet at rest, ADR-0010),
  `frontend_client_id`, `public_url`, `role_mapping`, `enabled` (per-provider),
  `sort_order`. Семантика `issuer_url`/`public_url` — по [ADR-0036]
  (0036-oidc-issuer-semantics-rfc-8414.md), без изменений.
* Master-switch `enabled` — глобальный boolean поверх per-provider флагов (место
  хранения — implementation choice: settings-строка vs отдельная конфиг-строка;
  требование — один boolean + одна проверка). Master-switch off → `/sso/config`
  возвращает `enabled=false` и пустой список.
* `GET /api/auth/sso/config` — **list-контракт** (breaking change для фронтенда):
  `{enabled, providers: [{id, name, url, realm, client_id}]}`. `url`/`realm`
  вычисляются бэкендом per ADR-0036. Провайдер без парсируемого realm → исключается из
  списка, warning `oidc_issuer_missing_realm_segment`.
* Admin CRUD — коллекция `GET/POST/PATCH/DELETE /api/auth/admin/oidc-providers`
  (permission model без изменений: `oidc:read` / `oidc:write`). Легаси-эндпоинты
  `/admin/oidc-config` (включая `/public`) **удаляются**.
* `POST /api/auth/oidc/exchange` принимает `provider_id` в теле; фронтенд также кладёт
  его в Keycloak `state`. Бэкенд: резолвит провайдера по `provider_id`; `state` обязан
  нести тот же `provider_id` — mismatch → 401. Неизвестный/выключенный `provider_id`
  → 4xx, без fallback на «какой-нибудь» провайдер.
* `KeycloakOIDCService`: per-provider конфиг; **JWKS-кэш ключуется per-provider**
  (сегодняшний глобальный single-key кэш при двух realm'ах коллизирует).
* Миграция Alembic поверх текущей головы: создать `oidc_providers`, перенести значения
  singleton-строки `oidc_config` в один провайдер **как есть** (без enrichment
  `issuer_url` — per ADR-0036), сохранить/представить master-switch (implementation
  choice), дропнуть `oidc_config`.

### Consequences

* Good, потому что N провайдеров = N строк одной таблицы; один CRUD, один код-путь
  exchange, один сервис.
* Good, потому что master-switch даёт incident-кнопку «выключить весь SSO» одним
  флагом.
* Good, потому что per-provider JWKS-кэш и state-привязка закрывают cross-realm
  подмену: токен realm A не пройдёт валидацию под конфигом провайдера B.
* Bad, потому что `/sso/config` и admin API меняют контракт — breaking change для
  фронтенда; релиз синхронный (фронтенд-issue в том же релизе).
* Bad, потому что legacy-строка с `issuer_url` без `/realms/` после миграции останется
  «не сконфигурированной» (не попадёт в `/sso/config`) до пересохранения админом —
  унаследовано от ADR-0036 осознанно.

### Confirmation

* Unit-тесты `backend/tests/unit/test_oidc.py` (расширение): per-provider построение
  `url`/`realm` для разных realm'ов; изоляция JWKS-кэша между провайдерами; поведение
  master-switch; mismatch `state`/`provider_id`; legacy-строка → disabled.
  Прогон: `make test-unit-backend TEST_ARGS="-k TestIssuerSemantics or TestMultiProvider"`.
* Integration-тесты: admin CRUD (create → `/sso/config` показывает провайдера →
  disable → скрыт); exchange с неизвестным/выключенным `provider_id` → 4xx.
* Контракт: `grep -rn "oidc_config" backend/app --include="*.py"` не даёт
  prod-совпадений после удаления singleton (только тесты/архив миграций).
* Миграция: `make dev-migrate-check` — `alembic upgrade head` на чистой копии БД
  создаёт одного провайдера из legacy-строки.

## Pros and Cons of the Options

### Одна таблица `oidc_providers` (chosen)

* Good, because один источник истины и один код-путь — нет ветвления «default vs
  extra».
* Good, because CRUD и permission-модель переиспользуются как есть.
* Bad, because breaking change контрактов `/sso/config` и admin API (фронтенд в том же
  релизе).
* Bad, because master-switch надо куда-то положить (одна boolean-строка/колонка —
  дёшево, но не бесплатно).

### Singleton как «default» + таблица extras

* Good, потому что `/sso/config` формально сохраняет старую форму для default.
* Bad, потому что два код-пути в каждом потребителе (config read, exchange, admin API,
  тесты) — ровно та сложность, которую убираем.
* Bad, потому что «default»-провайдер и провайдер из коллекции имеют разное поведение
  (перекрытие id, скрытая связь) — источник багов.

### Убрать master-switch (только per-provider `enabled`)

* Good, потому что минус одно поле и одна проверка.
* Bad, потому что incident «выключить весь SSO» превращается в N правок; мастер-свитч
  стоит один boolean.

### OIDC discovery fetch для резолва провайдера

* Good, потому что канонический механизм (issuer → well-known endpoints).
* Bad, потому что сетевой вызов и кэш discovery в критическом login-пути; уже
  rejected в ADR-0036 по тем же причинам; в этом issue не решает ничего нового
  (резолв идёт по `provider_id` из БД, не по issuer).

## More Information

* Issue: [SteeveRan/BigBug#98](https://github.com/SteeveRan/BigBug/issues/98)
  (backend; фронтенд — отдельный issue, блокирует релиз контракта).
* [ADR-0036](0036-oidc-issuer-semantics-rfc-8414.md) — семантика `issuer_url`/`public_url`,
  используемая каждой строкой новой таблицы.
* [ADR-0003](../common/0003-keycloak-oidc-dual-auth.md) — dual-auth, где SSO-кнопки
  появились; [ADR-0010](0010-fernet-secrets-encryption.md) — шифрование
  `client_secret`.
* Non-goals: редактирование провайдеров через публичный (не-admin) API; IdP с
  не-Keycloak структурой issuer; OIDC discovery.
