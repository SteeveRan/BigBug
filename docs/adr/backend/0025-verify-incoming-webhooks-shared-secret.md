---
status: accepted
date: 2026-10-22
decision-makers: SteeveRan
consulted: SteeveRan
informed: SteeveRan
---

# Верифицировать входящие webhooks shared-secret токеном (constant-time compare)

## Context and Problem Statement

Как backend BigBug должен проверять подлинность входящих webhook-запросов?

Единственный webhook-endpoint — `POST /api/webhooks/gitlab` (`backend/app/api/webhooks.py`, префикс `/api/webhooks` в `app/main.py`). Он принимает события GitLab pipeline (`object_kind: "pipeline"`) и обновляет статусы `BuildLog`, `HelmSyncLog`, `DockerSyncLog` и `PipelineRun` — то есть меняет состояние доменных сущностей на основании полностью недоверенного тела запроса.

**Текущее состояние кода — security gap**: endpoint не выполняет никакой верификации. Нет проверки `X-Gitlab-Token`, нет проверки `Authorization: Bearer`, нет HMAC-сравнения подписи — первый же `curl -X POST` с подобранным `pipeline_id` может пометить любую сборку успешной (`status_flag = 0`). Аутентифицированный пользователь для вызова не нужен: `get_current_user` в endpoint не зависит.

При этом доверенные вызывающие стороны уже передают токен: CI-пресеты BigBug (`backend/app/services/gitlab_projects/presets.py` — gold build, app build, mirror sync, docker sync, helm sync) во всех шаблонах объявляют CI-переменную `BIGBUG_WEBHOOK_TOKEN` («Shared secret for webhook authentication») и шлют заголовок `Authorization: Bearer $BIGBUG_WEBHOOK_TOKEN`. Уведомляющие джобы пресетов готовы к верификации — не готов backend.

Требуется зафиксировать механизм верификации, к которому код endpoint'а будет приведён отдельной задачей по реализации (вне скоупа этого ADR — см. Consequences).

## Decision Drivers

* Endpoint мутирует доменные данные (статусы сборок/синхронизаций) — подделка статуса `success` искажает и родительские сущности (`ImageVersion`, статусы источников), и downstream-логику (например, `mark_helm_version_synced` при успешном helm-sync)
* Вызывающие стороны — не браузер, а GitLab CI джобы (server-to-server); интерактивная аутентификация неуместна, а JWT-схема `get_current_user` требует пользователя, которого у CI-ночи нет
* Пресеты уже используют переменную `BIGBUG_WEBHOOK_TOKEN` и Bearer-заголовок — механизм не должен ломать существующие шаблоны
* Timing attacks: сравнение секрета должно быть constant-time (`hmac.compare_digest`), иначе по времени ответа можно подбирать токен побайтово
* Отказ от GitLab-специфичного `X-Gitlab-Token`-сравнения в пользу Bearer: пресеты также используют fake-payload'ы «в стиле GitLab» из non-GitLab джоб (docker sync шлёт `object_kind: pipeline` сам), поэтому привязка к механизму GitLab Secret Token избыточна
* Минимализм: без подписей HMAC над телом (не совпадает с пресетами), без IP-allowlist (ломается за reverse proxy / ingress)

## Considered Options

* Shared-secret токен: `Authorization: Bearer <BIGBUG_WEBHOOK_TOKEN>`, constant-time сравнение
* GitLab Secret Token: проверка заголовка `X-Gitlab-Token` (native-механизм GitLab webhooks)
* HMAC-подпись тела (GitHub-style `X-Hub-Signature-256`)
* Верификация через TLS mutual auth / IP allowlist

## Decision Outcome

Chosen option: **Shared-secret токен через `Authorization: Bearer` с constant-time сравнением**.

Механика (целевое состояние кода):

1. **Конфиг**: новая настройка `webhook_token: str = ""` в `backend/app/config.py`; в `.env.example` и compose — переменная `BIGBUG_WEBHOOK_TOKEN` (имя совпадает с CI-переменной пресетов, чтобы значение переиспользовалось один-в-один).
2. **Генерация**: токен — криптостойкая случайная строка (`python -c "import secrets; print(secrets.token_urlsafe(32))"`), уникальная на окружение; задаётся админом в `.env` и в переменных GitLab-проектов/групп.
3. **Проверка** (`backend/app/api/webhooks.py`): dependency или первые строки хендлера — чтение заголовка `Authorization`, префикс `Bearer `, затем `hmac.compare_digest(полученный, settings.webhook_token)`. Несовпадение / отсутствие заголовка → `401 Unauthorized`. Сравнение — только `hmac.compare_digest`, никаких `==`.
4. **Fail-closed**: пустой `settings.webhook_token` — верификация невозможна, endpoint отвечает `503 Service Unavailable` (не «пропускает всё»). Разворачивать без настроенного токена нельзя — это осознанно жёстче, чем текущее поведение.
5. **Открытые события**: события, не требующие доверия (например, будущие health-ping), могут остаться без верификации — только если они ничего не мутируют. Все мутирующие обработчики — за проверкой.

Почему Bearer, а не `X-Gitlab-Token`: последний — механизм нативных GitLab webhooks, но половина вызывающих — CI-джобы пресетов, которые шлют Bearer; поддержка двух заголовков удваивает поверхность ошибок. Bearer покрывает и нативные webhooks GitLab (в них можно задать custom header), и CI-джобы одним механизмом.

### Consequences

* Good, because подделка webhook'а требует знания секрета — статус сборок больше нельзя подделать одним POST-запросом
* Good, because пресеты (`presets.py`) уже шлют `Authorization: Bearer $BIGBUG_WEBHOOK_TOKEN` — на стороне GitLab CI ничего менять не нужно
* Good, because один механизм покрывает все источники событий (GitLab webhooks, CI-джобы, будущие источники)
* Bad, because текущий код endpoint'а проверку не выполняет — до реализации этой задачи gap остаётся; ADR фиксирует целевое состояние, реализация — отдельный issue
* Bad, because токен в CI-переменных GitLab виден maintainer'ам проекта — модель доверия «хоть кто-то с доступом к CI-переменным» (приемлемо: они и так могут запустить произвольный код сборки)
* Bad, because token rotation — ручная операция: обновить `.env`, перезапустить backend, обновить переменные GitLab (согласованный rollout не автоматизирован)
* Neutral, because сравнение не привязано к телу запроса — replay старого валидного запроса возможен; риск низкий (эффект повторного применения идемпотентен — перезапись того же статуса тем же `pipeline_id`)
* Non-goals: HMAC-подпись тела; mTLS; IP-allowlist; отдельные токены на источник; реализация проверки в коде (отдельный issue после принятия ADR)

### Confirmation

* Unit-тест `backend/tests/unit/test_webhook_verification.py` (новый): (a) POST без заголовка → 401; (b) с неверным токеном → 401; (c) с верным `Bearer` → обработка события (для `object_kind != "pipeline"` — `{"status": "ignored"}`); (d) пустой `webhook_token` в settings → 503; (e) проверка реализована через `hmac.compare_digest` (fitness: grep запрещает `== ` сравнение токена).
* E2E: обновить `backend/tests/e2e/test_webhooks.py` — все запросы к `/api/webhooks/gitlab` шлют Bearer-заголовок с токеном из окружения стенда.
* Ревью-критерий: в `presets.py` переменная `BIGBUG_WEBHOOK_TOKEN` остаётся единственным упоминанием секрета webhook'ов; появление второго механизма верификации — триггер пересмотра ADR.

## Pros and Cons of the Options

### Shared-secret Bearer токен — chosen

См. Decision Outcome.

* Good, because уже используется пресетами (`BIGBUG_WEBHOOK_TOKEN` + Bearer) — нулевой change на стороне GitLab CI
* Good, because тривиальная реализация: dependency + `hmac.compare_digest`, без зависимостей
* Good, because работает для любого источника событий, не только нативных GitLab webhooks
* Bad, because секрет — общий для всех источников: компрометация одного CI-проекта компрометирует весь webhook-канал
* Bad, because нет привязки к телу — replay возможен (идемпотентный эффект снижает риск)

### GitLab Secret Token (`X-Gitlab-Token`)

Нативный механизм GitLab: GitLab шлёт заданный токен в заголовке `X-Gitlab-Token` при каждом webhook-событии.

* Good, because нативная поддержка в UI GitLab — не нужен custom header в webhooks
* Good, because familiar-механизм для всех, кто настраивал GitLab webhooks
* Bad, because CI-джобы пресетов (главный источник событий!) не шлют `X-Gitlab-Token` — им пришлось бы слать второй заголовок, то есть два механизма
* Bad, because привязывает безопасность к конвенции одного вендора (fake-payload'ы docker-sync джобы не «GitLab»-события)

### HMAC-подпись тела (GitHub-style)

Отправитель подписывает тело ключом: `X-Hub-Signature-256: sha256=hmac_sha256(key, body)`; backend пересчитывает.

* Good, because защищает и подделку, и подмену тела, и (с timestamp) replay
* Good, because криптографически сильнее статичного токена
* Bad, потому что пресеты не подписывают тела — все 5 шаблонов пришлось бы менять + поддерживать обратную совместимость
* Bad, потому что для события «pipeline завершился со статусом X» избыточно: угроза подмены тела другим валидным телом (например, `failed` → `success`) реальна, но закрывается тем же секретом в токене: без секрета нельзя послать ничего

### mTLS / IP allowlist

* Good, because mTLS — сильнейшая проверка подлинности клиента
* Bad, потому что CI-джобы за shared runners — клиентские сертификаты нереалистичны; IP-allowlist ломается за reverse proxy/ingress (реальный client IP неизвестен без доверия к `X-Forwarded-For`, который подделывается)

## More Information

* Единственный webhook-endpoint: `backend/app/api/webhooks.py` (`POST /api/webhooks/gitlab`), регистрация — `app/main.py` (`prefix="/api/webhooks"`).
* Пресеты с `BIGBUG_WEBHOOK_TOKEN`: `backend/app/services/gitlab_projects/presets.py` (gold build, app build, mirror sync, docker sync, helm sync). Docker-sync пресет уже шлёт `Authorization: Bearer $BIGBUG_WEBHOOK_TOKEN` условно — «если токен задан»; после реализации проверка станет обязательной.
* Связанные ADR: ADR-0009 (pull-based sync + опциональные webhooks — этот ADR закрывает security-сторону webhook-канала), ADR-0011 (GitLab CI/CD интеграция и пресеты), ADR-0003 (JWT-аутентификация — webhook-канал сознательно вне её: у CI-джоб нет пользователя).
* Деплой-чеклист: `docs/runbooks/deploy-security-checklist.md` — после реализации добавить пункт «`BIGBUG_WEBHOOK_TOKEN` уникален и задан».
* Происхождение: legacy-документ `docs/architecture/10-security.md` (удалён в #49) обещал «HMAC/token верификация» webhook'ов и три webhook-endpoint'а (GitLab/GitHub/Harbor) — фактически endpoint один и не проверял ничего. Этот ADR фиксирует решение по фактам кода.
* Условие пересмотра: появление требования неотказуемости/подписи событий (криптографическая привязка к телу) — тогда HMAC-вариант новым ADR; появление второго webhook-провайдера с нативным механизмом (например, Harbor) — пересмотреть «один Bearer для всех источников».
