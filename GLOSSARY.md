# BigBug

Централизованная DevOps платформа: управление Docker-образами, зеркалированием GitHub → GitLab, синхронизацией registry/repo и GitLab CI/CD. Один домен для backend и frontend.

## Language

### Providers

**Resource Provider**:
Внешняя интеграция платформы (GitHub, GitLab, Harbor, Helm repo и т.д.), представленная единой сущностью с типизированными credentials.
_Avoid_: source provider, provider instance, инстанс (legacy V2/V3-термины)

**Provider Subtype**:
Конкретный вид провайдера из реестра подтипов в коде; определяет поля, тип credentials и доступные действия.
_Avoid_: provider type (в API — `/api/providers/types`, но в речи — subtype)

**Credentials**:
Учётные данные провайдера, хранятся зашифрованными (Fernet).
_Avoid_: tokens, secrets (secret — про механизм шифрования, не про значение)

### Git Mirroring

**Git Mirror** (зеркало):
Настроенное зеркало одного git-репозитория GitHub → GitLab с автоматическим CI/CD-пайплайном. «Зеркало» — только про git.
_Avoid_: mirror pair, sync job

**Sync**:
Pull-based актуализация состояния (mirror, registry, helm repo) средствами APScheduler или по webhook.
_Avoid_: synchronization, refresh, pull

**Webhook**:
Входящее уведомление от внешней системы, тригерящее Sync или обновление статуса.
_Avoid_: callback

### Image Builds

**Gold Image**:
Базовый образ OS/runtime, от которого собираются App Images.
_Avoid_: base image, OS image

**App Image**:
Образ приложения, собранный поверх Gold Image через GitLab CI.
_Avoid_: application image, artifact

### Registry / Helm Sync

**Registry Sync**:
Синхронизация Docker-образов между Docker Registry (провайдерами). Не «зеркало» — зеркало только про git.
_Avoid_: registry mirror, mirror, docker sync

**Helm Sync**:
Синхронизация чартов между Helm Repository (провайдерами).
_Avoid_: helm mirror, chart sync

### CI/CD

**GitLab Project**:
Управляемая платформой сущность GitLab — не только git-репозиторий, но и весь его функционал: CI/CD pipelines, components, permissions, issues/work items.
_Avoid_: repo, repository (репозиторий — про git-содержимое, GitLab Project — про сущность и её функционал)

**Component**:
Переиспользуемый GitLab CI/CD component, подключаемый к пайплайнам.
_Avoid_: template

**Pipeline**:
GitLab CI/CD pipeline, запущенный платформой или событием.
_Avoid_: build (build — про сборку образа), job

**Preset**:
Готовая in-code заготовка CI-конфигурации (например, сборка Gold Image), предлагаемая при создании pipeline-проекта; раздаётся через `GET /api/components/presets`.
_Avoid_: template

### RBAC

**Permission**:
Право вида `resource:action`, единый механизм авторизации.
_Avoid_: role action, scope (scope — отдельное понятие)

**Scope Provider**:
Провайдер, ограничивающий область действия permission конкретной интеграцией.
_Avoid_: provider scope

**Team**:
Группа пользователей с общими permissions на scope providers.
_Avoid_: group, org

**Status Flag**:
Унифицированный числовой статус в ответах API: 0 OK, 1 Failed, 2 Warning/Stale, 3 In Progress, 4 Pending.
_Avoid_: status code (это HTTP), state

### Security

**Secret**:
Любое значение, открывающее доступ к внешней системе (токен, PAT, пароль, ключ), попавшее в git — независимо от того, живое оно или считалось временным.
_Avoid_: credentials (они — про хранимые в БД провайдера), leaked token

**False Positive**:
Срабатывание gitleaks на значение, которое не является живым секретом (фейковый токен в доках/фикстурах, пример в `.env.example`).
_Avoid_: noise, ложное срабатывание

**Allowlist**:
Набор правил в `.gitleaks.toml` (пути, stopwords), исключающий известные false positives из сканирования; единственный легальный способ подавить срабатывание.
_Avoid_: ignore, whitelist, exclusion

### OIDC / SSO

**Issuer URL**:
Полный URI realm по RFC 8414 (например, `https://keycloak.local/realms/myrealm`), хранится в `oidc_config.issuer_url`. Token/jwks endpoints строятся из него напрямую, realm парсится из сегмента пути `/realms/<realm>`.
_Avoid_: base URL, realm URL без пути, отдельное поле realm

**Public URL**:
Происхождение (scheme+host), под которым браузер видит Keycloak; используется только как origin-подстановка ожидаемого iss-claim (Keycloak с `KC_HOSTNAME_STRICT=false` кладёт в iss публичный хост).
_Avoid_: external URL, frontend URL

**Realm**:
Изолированное пространство пользователей/клиентов в Keycloak; в BigBug не хранится отдельно, а выводится из Issuer URL.
_Avoid_: tenant (в контексте Keycloak), hard-coded bigbug

