# Интеграция Harbor с Keycloak через OIDC

> Пошаговое руководство по настройке Single Sign-On (SSO) для Harbor с использованием Keycloak в качестве OIDC-провайдера.

## Обзор архитектуры

```
┌──────────────┐        OIDC (Authorization Code)        ┌──────────────┐
│   Harbor     │ ◄──────────────────────────────────────► │   Keycloak   │
│  (kind)      │    redirect_uri → harbor callback        │  (Docker)    │
│              │    client_id/secret → verify             │  :8180       │
│  :30443      │                                          │              │
└──────────────┘                                          └──────────────┘
```

## Шаг 1: Создание OIDC Client в Keycloak

### 1.1 Войти в Keycloak Admin Console

- URL: `http://localhost:8180`
- Username: `admin`
- Password: `admin`

### 1.2 Выбрать Realm

Убедитесь, что выбран realm `bigbug` (выпадающий список в левом верхнем углу). Если realm не создан — выполните инициализацию:

```bash
cd ../keycloak
cp terraform.tfvars.example terraform.tfvars
tofu init && tofu apply
```

### 1.3 Создать новый Client

1. Перейдите: **Clients** → **Create client**
2. Заполните поля:

| Поле | Значение | Примечание |
|------|----------|------------|
| Client type | `OpenID Connect` | Протокол OIDC |
| Client ID | `harbor` | Идентификатор клиента для Harbor |
| Name | `Harbor Registry` | Человекочитаемое имя |
| Description | `OIDC client for Harbor container registry SSO` | Описание |

3. Нажмите **Next**

### 1.4 Настройка Capability Config

| Поле | Значение |
|------|----------|
| Client authentication | `On` |
| Authorization | `Off` |
| Authentication flow | ✅ Standard flow |
| | ✅ Direct access grants |
| | ❌ Implicit flow |
| | ❌ Service accounts roles |

Нажмите **Next**.

### 1.5 Настройка Login Settings

| Поле | Значение |
|------|----------|
| Root URL | `https://harbor.local:30443` |
| Home URL | `https://harbor.local:30443` |
| Valid redirect URIs | `https://harbor.local:30443/c/oidc/callback` |
| | `https://harbor.local:30443/*` |
| Valid post logout redirect URIs | `https://harbor.local:30443/c/oidc/logout` |
| | `https://harbor.local:30443/` |
| Web origins | `https://harbor.local:30443` |

Нажмите **Save**.

### 1.6 Получение Client Secret

1. После сохранения перейдите на вкладку **Credentials**
2. Скопируйте значение **Client Secret** — оно понадобится для конфигурации Harbor

```
Client ID:     harbor
Client Secret: <скопировать отсюда>
```

## Шаг 2: Конфигурация Harbor OIDC

### 2.1 Через Harbor Web UI

1. Откройте Harbor UI: `https://harbor.local:30443`
2. Войдите как `admin` / `Harbor12345`
3. Перейдите: **Administration** → **Configuration** → **Authentication**
4. Выберите **OIDC** в качестве Auth Mode
5. Заполните поля:

| Поле | Значение |
|------|----------|
| Auth Mode | `OIDC` |
| OIDC Provider Name | `Keycloak` |
| OIDC Endpoint | `http://localhost:8180/realms/bigbug` |
| OIDC Client ID | `harbor` |
| OIDC Client Secret | `<client_secret_из_шага_1.6>` |
| Group Claim Name | `groups` |
| OIDC Scope | `openid,profile,email,groups` |
| Verify Certificate | `☐` (выключить для dev, Keycloak на HTTP) |
| Automatic onboarding | `☑` (автоматически создавать пользователей при первом входе) |
| Username Claim | `preferred_username` |

6. Нажмите **Test OIDC Server** — должна появиться зелёная галочка
7. Нажмите **Save**

### 2.2 Через Harbor API (альтернативный способ)

```bash
# Получить текущую конфигурацию
curl -s -k -u admin:Harbor12345 \
  https://harbor.local:30443/api/v2.0/configurations \
  | jq '.oidc'

# Установить OIDC конфигурацию
curl -s -k -u admin:Harbor12345 \
  -X PUT \
  -H "Content-Type: application/json" \
  https://harbor.local:30443/api/v2.0/configurations \
  -d '{
    "auth_mode": "oidc_auth",
    "oidc_name": "Keycloak",
    "oidc_endpoint": "http://localhost:8180/realms/bigbug",
    "oidc_client_id": "harbor",
    "oidc_client_secret": "<client_secret>",
    "oidc_groups_claim": "groups",
    "oidc_scope": "openid,profile,email,groups",
    "oidc_verify_cert": false,
    "oidc_auto_onboard": true,
    "oidc_user_claim": "preferred_username"
  }'
```

### 2.3 Включение OIDC в harbor-values.yaml

Для автоматической настройки при развёртывании добавьте в [`harbor-values.yaml`](harbor-values.yaml) следующие параметры:

```yaml
# OIDC Authentication (Keycloak integration)
# Раскомментируйте и заполните перед деплоем
# oidc:
#   enabled: false                    # Включить после ручной настройки client secret
#   authMode: oidc_auth
#   providerName: Keycloak
#   endpoint: http://localhost:8180/realms/bigbug
#   clientId: harbor
#   clientSecret: ""                  # Заполнить из Keycloak → Clients → harbor → Credentials
#   groupsClaim: groups
#   scope: openid,profile,email,groups
#   verifyCert: false
#   autoOnboard: true
#   userClaim: preferred_username
```

## Шаг 3: Настройка групп и ролей

### 3.1 Группы в Keycloak

Harbor сопоставляет группы Keycloak с ролями Harbor. Создайте группы в Keycloak, соответствующие ролям Harbor:

1. Keycloak Admin → **Groups** → **Create group**
2. Создайте группы:

| Keycloak Group | Harbor Role | Описание |
|----------------|-------------|----------|
| `harbor-admin` | Administrator | Полный доступ к Harbor |
| `harbor-dev` | Developer | Push/Pull, управление проектами |
| `harbor-guest` | Guest | Только Pull |

### 3.2 Назначение групп пользователям

1. Keycloak Admin → **Users** → выберите пользователя
2. Вкладка **Groups** → **Join Group**
3. Выберите нужную группу (например, `harbor-admin`)

### 3.3 Проверка Mappings

Harbor автоматически сопоставляет первую аутентификацию OIDC пользователя, используя группы из токена. При первом входе пользователя через OIDC:

- Если пользователь состоит в группе `harbor-admin` → назначается роль Harbor System Admin
- Если группа не найдена → назначается роль по умолчанию (Guest)

## Шаг 4: Проверка интеграции

### 4.1 Тестирование через Harbor UI

1. Откройте `https://harbor.local:30443`
2. На странице логина должна появиться кнопка **LOGIN VIA OIDC PROVIDER** (или имя провайдера "Keycloak")
3. Нажмите кнопку — произойдёт редирект на Keycloak
4. Войдите с учётными данными пользователя (например, `bigbug` / `bigbug`)
5. После успешной аутентификации — редирект обратно в Harbor

### 4.2 Тестирование через curl

```bash
# 1. Получить authorization URL (Harbor сам инициирует OIDC flow)
# В браузере откройте:
# https://harbor.local:30443/c/oidc/login

# 2. API запрос с OIDC токеном
# (получите токен через Keycloak token endpoint)
TOKEN=$(curl -s -X POST \
  "http://localhost:8180/realms/bigbug/protocol/openid-connect/token" \
  -d "client_id=harbor" \
  -d "client_secret=<client_secret>" \
  -d "username=bigbug" \
  -d "password=bigbug" \
  -d "grant_type=password" \
  | jq -r '.access_token')

# 3. Использовать токен для доступа к Harbor API
curl -s -k \
  -H "Authorization: Bearer $TOKEN" \
  https://harbor.local:30443/api/v2.0/projects \
  | jq '.[].name'
```

### 4.3 Тестирование Docker login через OIDC

> **Примечание:** Docker CLI не поддерживает OIDC напрямую. Для аутентификации в Docker registry через OIDC используйте **Harbor CLI** или **OCI Distribution Spec tokens**:

```bash
# Через Harbor API получить secret для Docker CLI
# При первом логине через OIDC пользователь может сгенерировать
# CLI secret в Harbor UI: User Profile → CLI Secret

# Затем использовать CLI secret для docker login
docker login harbor.local:30080 -u bigbug -p <cli_secret>
```

## Шаг 5: Устранение неполадок

### Проблема: «Invalid redirect_uri» от Keycloak

**Причина:** Несоответствие redirect URI между Harbor и Keycloak.

**Решение:**
1. Проверьте в Keycloak: Clients → `harbor` → Settings → Valid redirect URIs
2. Убедитесь, что там есть `https://harbor.local:30443/c/oidc/callback`
3. Проверьте в Harbor: Configuration → Authentication → OIDC Endpoint
4. Убедитесь, что endpoint начинается с `http://` (не `https://`) для локального Keycloak

### Проблема: «SSL certificate verify failed»

**Причина:** Не удаётся проверить сертификат (Harbor использует самоподписанный, Keycloak на HTTP).

**Решение:**
- В настройках Harbor OIDC отключите **Verify Certificate**
- Для Keycloak endpoint используйте `http://` схему

### Проблема: Keycloak недоступен изнутри kind кластера

**Причина:** Harbor работает внутри kind-кластера и не может достучаться до `localhost:8180`.

**Решение:**
Используйте IP хоста вместо localhost. Узнайте IP docker-хоста:

```bash
# На Linux (docker network bridge)
HOST_IP=$(ip -4 addr show docker0 2>/dev/null | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1)

# Или
HOST_IP=$(docker network inspect bridge -f '{{(index .IPAM.Config 0).Gateway}}')

echo "Host IP: $HOST_IP"
# Пример: 172.17.0.1
```

Затем обновите OIDC Endpoint в Harbor:
```
http://172.17.0.1:8180/realms/bigbug
```

И в Keycloak → Clients → `harbor` → Valid redirect URIs:
```
https://harbor.local:30443/c/oidc/callback
https://harbor.local:30443/*
```

### Проблема: «User not found» после OIDC логина

**Причина:** Внешний OIDC пользователь не прошёл автоматический onboarding.

**Решение:**
1. Убедитесь, что `Automatic onboarding` включён в настройках Harbor OIDC
2. Проверьте, что пользователь существует в Keycloak (realm `bigbug`)
3. Проверьте group claim — пользователь должен иметь хотя бы одну группу
4. Проверьте логи Harbor Core:
   ```bash
   kubectl logs -n harbor deployment/harbor-core | grep -i oidc
   ```

### Проблема: Conflicts с локальным admin аккаунтом

**Примечание:** Локальный `admin` аккаунт продолжает работать даже после включения OIDC. Если OIDC не работает, всегда можно войти через `admin` / `Harbor12345` и отключить OIDC.

```bash
# API для отключения OIDC и возврата к db_auth
curl -s -k -u admin:Harbor12345 \
  -X PUT \
  -H "Content-Type: application/json" \
  https://harbor.local:30443/api/v2.0/configurations \
  -d '{"auth_mode": "db_auth"}'
```

## Сводная таблица конфигурации

| Параметр | Значение | Источник |
|----------|----------|----------|
| Keycloak URL | `http://localhost:8180` | [`docker-compose.infra.yml`](../../docker-compose.infra.yml) |
| Realm | `bigbug` | [`realm.tf`](../keycloak/realm.tf) |
| Client ID | `harbor` | Создаётся вручную (этот гайд) |
| Client Secret | `<генерируется>` | Keycloak → Clients → harbor → Credentials |
| OIDC Endpoint | `http://localhost:8180/realms/bigbug` | Формируется из Keycloak URL + Realm |
| Redirect URI | `https://harbor.local:30443/c/oidc/callback` | Стандартный путь Harbor OIDC callback |
| Harbor Admin | `admin` / `Harbor12345` | [`harbor-values.yaml`](harbor-values.yaml) |
| Harbor UI | `https://harbor.local:30443` | [`deploy.sh`](deploy.sh) |

## Ссылки

- [Harbor OIDC Authentication](https://goharbor.io/docs/2.10.0/administration/configure-oidc-auth/)
- [Keycloak Server Administration Guide](https://www.keycloak.org/docs/latest/server_admin/)
- [Keycloak OIDC Client Configuration](https://www.keycloak.org/docs/latest/server_admin/#_oidc_clients)
- [Docker CLI Authenticate with OIDC](https://goharbor.io/docs/2.10.0/working-with-projects/working-with-images/managing-helm-charts/#authenticate-with-oidc)
