---
status: accepted
date: 2026-10-21
decision-makers: SteeveRan
---

# Зашифровывать stored credentials в БД симметричным Fernet с ключом из переменной окружения `ENCRYPTION_KEY`

## Context and Problem Statement

BigBug хранит в PostgreSQL credentials внешних систем: токены GitHub/GitLab, пароли registry (Harbor, Docker, Helm), OIDC client secret. Эти данные живут в БД вместе с её dump/backup'ами; компрометация dump (или SQL-инъекция, или доступ на чтение к БД) не должна выдавать токены внешних систем. Решение о том, **как защищать credentials at rest**, до сих пор нигде не зафиксировано — оно существует только в коде (`backend/app/core/secrets.py`) и частично в удаляемом `plans/features/security.md`.

Фактический вопрос: **принимать ли существующую схему как стандарт** — симметричное шифрование Fernet на уровне отдельных колонок, ключ в env-переменной `ENCRYPTION_KEY`, без внешнего хранилища секретов?

## Decision Drivers

- Секреты не должны храниться в БД в plaintext: dump/backup/read-доступ к БД не должен давать токены внешних систем
- Ключ должен жить **вне БД** (env backend-контейнера), иначе шифрование не защищает от утечки dump
- Минимализм (драйвер ADR-0001): без внешних сервисов (vault) в dev-инфраструктуре; каждый компонент — цена поддержки
- Зависимость `cryptography` уже в `backend/pyproject.toml` (через `python-jose[cryptography]`) — новая зависимость не нужна
- Классический ключ env-конфигурации (ADR-0001: `pydantic-settings`): пустое значение должно падать **громко**, а не молча терять данные

## Considered Options

* Fernet (симметрично, per-column), ключ в `ENCRYPTION_KEY` env — фактический стандарт кода
* AES-GCM напрямую (своя обвязка поверх `cryptography.hazmat`)
* Асимметричное шифрование (RSA/ECIES)
* External vault (HashiCorp Vault / облачный KMS)
* Plaintext env-only (секреты только в env, в БД не хранить)

## Decision Outcome

Chosen option: **Fernet, ключ в `ENCRYPTION_KEY` env** — это уже работающий стандарт кода; Fernet из `cryptography` даёт authenticated encryption (AES-128-CBC + HMAC-SHA256) без необходимости самому собирать crypto-обвязку, а per-column шифрование покрывает угрозу «утёк dump БД» при минимальной цене.

Реализация (`backend/app/core/secrets.py`, ~90 строк):

- `SecretCipher` — обёртка над единственным `Fernet`-ключом; ключ валидируется (URL-safe base64, 32 байта) eagerly при создании — misconfigured ключ падает при старте, а не на первом `encrypt()`
- `get_cipher()` — process-wide instance, `@lru_cache(maxsize=1)`; если `settings.encryption_key` пуст — `RuntimeError` с инструкцией генерации ключа, **никаких fallback'ов на случайный ключ** (иначе данные терялись бы при каждом рестарте)
- `encrypt_secret()` / `decrypt_secret()` — единственная точка входа для сервисов; `None` и `""` прозрачны (→ `None`)
- Ошибка расшифровки — доменное исключение `SecretEncryptionError` (wrong key или corrupt data), API-слой маппит его в 500 без утечки internals библиотеки

Источник ключа: `settings.encryption_key` (`backend/app/config.py`), env-переменная **`ENCRYPTION_KEY`** (не `FERNET_KEY` — историческое имя переменной отличается от имени алгоритма; переименование не требуется). Ключ живёт только в env backend-контейнера (`docker-compose.yml` пробрасывает `ENCRYPTION_KEY`), никогда — в образе, репозитории или БД. Генерация:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Зашифрованные колонки (после миграции Providers V3, [ADR-0007](../common/0007-providers-v3-registry.md) — legacy-таблицы инстансов удалены):

| Колонка | Таблица | Что хранит |
|---|---|---|
| `encrypted_secret` | `credentials` | секреты провайдеров (типы `CredentialType`: `github_token`, `gitlab_token`, `https_basic`, `ssh_key`) |
| `client_secret` | `oidc_config` | OIDC client secret (singleton-строка) |

Все провайдеры (`resource_providers`) ссылаются на credential и получают расшифрованный секрет только через `decrypt_secret()` в сервисном слое ([ADR-0005](0005-service-layer-no-repository.md)).

### Consequences

* Good, because утечка dump/backup БД не даёт токенов внешних систем без доступа к env backend-контейнера
* Good, because минимум кода и ноль новых зависимостей: Fernet — готовый authenticated encryption, `cryptography` уже в стеке (ADR-0001)
* Good, because единая точка шифрования: сервисы не касаются ключа и сырых crypto-примитивов, тесты подменяют ключ без monkey-patching настроек (`SecretCipher` принимает key в конструкторе)
* Bad, because доступ к env backend-контейнера = доступ ко всем секретам: env-ключ защищает только от утечки БД, не от компрометации хоста
* Bad, because **ротация ключа не поддержана**: смена `ENCRYPTION_KEY` делает все существующие ciphertext'ы нечитаемыми (`InvalidToken` → `SecretEncryptionError`); см. «Key rotation policy» ниже
* Bad, because пустой `ENCRYPTION_KEY` не падает на старте приложения, а только при первом обращении к шифрованию — фичи, зависящие от секретов (Helm/Docker sync), отказывают в рантайме (принятая цена: шифрование нужно не всем процессам)
* Neutral, because шифрование — column-level, а не уровне хранилища (PostgreSQL TDE не используется): метаданные (username, base_url, имена) остаются в plaintext
* Non-goals: ротация ключей (отдельная задача, см. ниже); внешний vault; TDE/disks-encryption; хеширование паролей пользователей (bcrypt, [ADR-0003](../common/0003-keycloak-oidc-dual-auth.md)); JWT/`SECRET_KEY` (тот же ADR-0003); rate limiting, CORS, webhook-подписи (не домен secrets)

### Key rotation policy

Текущее состояние: **ключ стабильный**, ротация не поддержана. Известное ограничение и план задела (зафиксированы в docstring `secrets.py`):

- При необходимости ротации — перейти с `Fernet` на `MultiFernet` (decrypt любым из ключей, encrypt актуальным) внутри `SecretCipher` — сигнатуры `encrypt_secret`/`decrypt_secret` и все вызыватели не меняются
- Существующие строки перешифровываются one-off Alembic-миграцией (data migration: `SELECT` → `decrypt_secret` → `encrypt_secret` актуальным ключом → `UPDATE`)
- До реализации ротации: потеря/смена `ENCRYPTION_KEY` = потеря credentials → единственное восстановление — повторный ввод секретов через UI (`/admin/credentials`, пере-сохранение OIDC config)

### Confirmation

Контрольный unit-тест: `backend/tests/unit/test_secrets.py` — round-trip `encrypt/decrypt` (включая unicode и пустую строку), `decrypt` чужим ключом и мусором → `SecretEncryptionError`, прозрачность `None`/`""` на уровне helpers. Запуск:

```bash
make test-unit-backend TEST_ARGS="tests/unit/test_secrets.py -v"
```

Ожидаемый результат: все тесты проходят.

Правила для ревью (fitness-критерии):

1. Новые секретные поля хранятся **только** через `encrypt_secret()`; появление в `app/models/` колонки с plaintext-секретом (имя без `_encrypted`/comment `Fernet-encrypted at rest`) — нарушение
2. `app.core.secrets` не импортирует `fastapi`; ключ не читается где-либо кроме `get_cipher()`
3. Секреты не попадают в логи: `decrypt_secret()` вызывается в точке использования, результат не сериализуется в ответы API (schema `oidc_config.py` отдаёт `client_secret` только на запись)

## Pros and Cons of the Options

### Fernet + ключ в `ENCRYPTION_KEY` env — chosen

Фактический стандарт кода, ~90 строк в `app/core/secrets.py`.

* Good, because ready-made authenticated encryption (HMAC встроен) — не собираем crypto-конструкции вручную
* Good, because зависимость уже есть; минимальная поверхность кода
* Good, because ключ вне БД — dump сам по себе бесполезен
* Bad, because env — слабое место: доступ к хосту/оркестрации = доступ к секретам
* Bad, because ротация — ручная процедура с one-off миграцией (сейчас не реализована)

### AES-GCM напрямую

Своя обвязка поверх `cryptography.hazmat.primitives.ciphers.aead.AESGCM`.

* Good, because современный AEAD, аппаратное ускорение AES-NI
* Bad, because самому управлять nonce, форматом токена и сериализацией — ровно то, от чего Fernet избавляет; риск ошибки в crypto-деталях выше ценности

### Асимметричное шифрование (RSA/ECIES)

* Good, because шифровать может кто угодно, расшифровывать — только владелец private key (подписывающий сервис мог бы не иметь ключа расшифровки)
* Bad, because в BigBug один процесс и шифрует, и расшифровывает — разделение ключей ничего не даёт
* Bad, because размер ciphertext неограничен только через гибридную схему (RSA + session key) — лишняя сложность ради отсутствующей угрозы

### External vault (HashiCorp Vault / облачный KMS)

* Good, because централизованная ротация, аудит доступа, динамические секреты
* Bad, because отдельный сервис в dev-инфраструктуре ради ~2 колонок в одной БД — прямое противоречие драйверу «минимализм» (ADR-0001)
* Bad, because новая операционная зависимость: vault сам требует bootstrap-секрета и availability — проблема смещается, не решается
* Условие пересмотра: мультиинстанс-деплой, компрометация ключа или требование аудита доступа к секретам

### Plaintext env-only (секреты не в БД)

* Good, потому что совсем нет шифрования — нечего расшифровывать
* Bad, because секреты нужны как данные: CRUD credentials через UI, шаринг credential между провайдерами, связи FK — env не даёт модели хранения
* Bad, because env-переменные утекают легче, чем кажется (ps/`/proc`, compose-файлы, логи запуска)

## More Information

- Реализация: [`backend/app/core/secrets.py`](../../../backend/app/core/secrets.py), ключ — `settings.encryption_key` в [`backend/app/config.py`](../../../backend/app/config.py), проброс env — `docker-compose.yml` (`ENCRYPTION_KEY`)
- Тесты: [`backend/tests/unit/test_secrets.py`](../../../backend/tests/unit/test_secrets.py), мок ключа в `backend/tests/unit/conftest.py`
- Этот ADR владеет доменом «secrets» и заменяет раздел Fernet-шифрования из удалённого `plans/features/security.md` (файл удалён; остальные темы того файла — JWT/bcrypt/OIDC → [ADR-0003](../common/0003-keycloak-oidc-dual-auth.md), rate limiting/CORS/webhooks — не зафиксированы ADR, см. roadmap). Заметка о стабильности ключа из удалённого `plans/features/integrations.md` (handover по [ADR-0007](../common/0007-providers-v3-registry.md)) также поглощена этим ADR.
- Источник истины по домену integrations после удаления plans-файлов: [ADR-0007](../common/0007-providers-v3-registry.md) (Providers V3) и код
- Реестр ADR и конвенции: [docs/adr/README.md](../README.md)
- Условие пересмотра: мультиинстанс-деплой с разными env, требование аудита/ротации секретов, компрометация `ENCRYPTION_KEY` — переоткрыть через новый ADR (кандидаты: vault/KMS, MultiFernet-ротация)
