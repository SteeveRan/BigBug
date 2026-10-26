---
status: accepted
date: 2026-10-24
decision-makers: "@SteeveRan"
consulted: ""
informed: ""
---

# OIDC issuer semantics: полный issuer URI по RFC 8414 вместо base URL + hard-coded realm

## Context and Problem Statement

`backend/app/services/oidc.py` жёстко фиксирует Keycloak realm: `_REALM: str = "bigbug"`.
Хардкод размазан по трём местам: построение `token_url`/`jwks_url`
(`issuer_url + "/realms/bigbug/..."`), валидация iss-claim (`_issuer()`) и эндпоинт
`/api/auth/sso/config` (`realm="bigbug"`). На dev-стенде это работает, потому что tofu
создаёт realm `bigbug`; на stage/prod realm будет другим, и SSO сломается без
изменения кода.

Смежная семантическая проблема: `issuer_url` в БД хранит base URL
(`https://keycloak.local`), а код сам дописывает `/realms/<realm>`. Это расходится с
отраслевой конвенцией (RFC 8414 / OIDC Discovery: issuer — полный URI realm, например
`https://keycloak.local/realms/myrealm`). UI-placeholder уже показывает полный issuer, и
админ, вставивший полный issuer сегодня, получает задвоение пути (Keycloak 404 на token
endpoint — уже наблюдалось).

Вопрос: как хранить и интерпретировать `issuer_url`, чтобы убрать hard-coded realm и
совпасть с конвенцией RFC 8414?

Связано: [ADR-0003](../common/0003-keycloak-oidc-dual-auth.md) (dual-auth Keycloak OIDC),
issue [SteeveRan/BigBug#96](https://github.com/SteeveRan/BigBug/issues/96).

## Decision Drivers

* Realm должен отличаться между окружениями (dev `bigbug`, stage/prod — свой) без
  изменения кода.
* Отраслевая конвенция RFC 8414/OIDC Discovery: issuer — полный URI realm; админы
  копируют его из Keycloak admin console как есть.
* Минимум кода: команда осознанно отказалась от обратной совместимости ради
  упрощения (см. Rejected).
* `public_url` нужен для валидации iss при `KC_HOSTNAME_STRICT=false` (iss в токене
  соответствует public-хосту, с которого браузер ходил в Keycloak).

## Considered Options

* **Полный issuer в `issuer_url` + парсинг realm из пути** (выбрано)
* Отдельная колонка `realm` рядом с `issuer_url`
* OIDC discovery fetch (`/.well-known/openid-configuration`) вместо ручного
  конструирования URL
* Data migration: дописать `/realms/bigbug` к legacy-значениям
* Fallback на hard-coded `bigbug` для legacy-строк без сегмента `/realms/`

## Decision Outcome

Chosen option: "Полный issuer в `issuer_url` + парсинг realm из пути", потому что это
устраняет единственный источник истины о realm (сам URL), совпадает с RFC 8414 и тем,
что админ копирует из Keycloak, и требует минимум кода: один парсер пути вместо
колонки, миграции или discovery-клиента.

Семантика:

* `oidc_config.issuer_url` хранит **полный issuer URI realm** (RFC 8414), например
  `https://keycloak.local/realms/myrealm`. Realm парсится бэкендом из сегмента пути
  `/realms/<realm>`. Отдельной колонки `realm` нет.
* `public_url` остаётся и используется **только** как origin-подстановка для ожидаемого
  iss-claim: Keycloak с `KC_HOSTNAME_STRICT=false` кладёт в iss публичный URL, который
  может отличаться от admin-введённого хоста issuer. `token_url`/`jwks_url` строятся
  **только** из `issuer_url`.
* Ожидаемый iss = `origin(public_url или issuer_url) + path(issuer_url)`.
* URL эндпоинтов: `{issuer}/protocol/openid-connect/token` и
  `{issuer}/protocol/openid-connect/certs`.
* Legacy-значения без парсируемого сегмента `/realms/` считаются неполной конфигурацией:
  `is_configured()` → `False`, `/sso/config` → `enabled=false`, warning
  `oidc_issuer_missing_realm_segment` в лог. Миграции данных и fallback на `bigbug` нет —
  админ пересохраняет issuer вручную. Осознанное решение: обратная совместимость не стоит
  кода (одна env-специфичная строка в dev-БД).
* Валидация на границе доверия: непустой `issuer_url` в `OIDCConfigUpdate` обязан
  парситься как URL с путём `/realms/<непустой сегмент>`, без query/fragment — иначе 422.
  Пустая строка валидна (SSO не сконфигурирован).
* OIDC discovery не используется (rejected, ниже); может быть добавлен позже без
  изменения контракта.

### Consequences

* Good, потому что realm конфигурируется админом через существующий PATCH-эндпоинт —
  stage/prod не требуют изменения кода.
* Good, потому что семантика поля совпадает с RFC 8414 и UI-placeholder'ом — вставка
  issuer "как из Keycloak" работает.
* Bad, потому что legacy-строки (dev-стенд, `issuer_url="https://keycloak.local"`)
  ломаются без миграции: SSO отключается до ручного пересохранения. Принято осознанно.
* Bad, потому что парсинг realm из пути предполагает Keycloak-структуру URL
  (`/realms/<realm>`); другие OIDC-провайдеры с иной структурой issuer не поддерживаются.
  Мультипровайдерная поддержка — отдельный issue (#TBD, зависимый).

### Confirmation

* Unit-тесты `backend/tests/unit/test_oidc.py::TestIssuerSemantics`: realm-parsing
  (стандартный, нестандартное имя realm, issuer с `/realms/` глубоко в пути), построение
  `token_url`/`jwks_url`/expected iss, origin-подстановка через `public_url`,
  неполная конфигурация (`is_configured() == False`).
  Прогон: `make test-unit-backend TEST_ARGS="-k TestIssuerSemantics"`.
* Integration-тест `GET /api/auth/sso/config`: `realm`/`url` вычисляются бэкендом из
  полного issuer + public_url; legacy-значение → `enabled=false` без падения.
* Контракт: `grep -rn "bigbug" backend/app/services/oidc.py backend/app/api/auth.py`
  не даёт realm-зависимых совпадений.

## Pros and Cons of the Options

### Полный issuer в `issuer_url` + парсинг realm из пути (chosen)

* Good, because один источник истины: realm выводим из URL, хардкод исчезает.
* Good, because совпадает с RFC 8414 и копипастой из Keycloak admin console.
* Bad, because legacy-строки требуют ручного пересохранения (нет миграции).
* Bad, because парсер привязан к Keycloak-структуре пути.

### Отдельная колонка `realm`

* Good, потому что явное поле без парсинга.
* Bad, потому что два поля для одного факта — рассинхронизация возможна
  (`issuer_url` с одним realm, `realm` с другим); нужна валидация согласованности.
* Bad, потому что миграция схемы + изменения API/UI-placeholder'а.

### OIDC discovery fetch

* Good, потому что канонический механизм: issuer → `/.well-known/openid-configuration`
  → token/jwks endpoints без ручного конструирования.
* Bad, потому что сетевой вызов при каждом cold-старте/ротации конфига, обработка
  ошибок discovery, кэш — заметно больше кода; issue решило 90% ценности без этого.
* Neutral: может быть добавлен позже, не ломая контракт (`url`/`realm` вычисляются
  бэкендом и так).

### Data migration `/realms/bigbug`

* Good, потому что dev-данные продолжают работать автоматически.
* Bad, потому что миграция цементирует неверное допущение (что все legacy-строки
  указывали на realm `bigbug`) и добавляет одноразовый код, который потом удалять.

### Fallback на hard-coded `bigbug` для legacy-строк

* Good, потому что нулевой труд для админа на dev-стенде.
* Bad, потому что возвращает тот самый хардкод, который убираем, и молча маскирует
  неполную конфигурацию.

## More Information

* Issue: [SteeveRan/BigBug#96](https://github.com/SteeveRan/BigBug/issues/96)
* RFC 8414 (OAuth 2.0 Authorization Server Metadata), OIDC Discovery 1.0 — семантика
  issuer как полного URI.
* [ADR-0003](../common/0003-keycloak-oidc-dual-auth.md) — dual-auth; данный ADR
  уточняет семантику поля `issuer_url`, введённого там.
* Триггер пересмотра: если появится OIDC-провайдер с не-Keycloak структурой issuer —
  рассмотреть discovery fetch (сейчас rejected).
