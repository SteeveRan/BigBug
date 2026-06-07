# Harbor в kind — Локальный Docker Registry для разработки

> Развёртывание [Harbor](https://goharbor.io/) в [kind](https://kind.sigs.k8s.io/) кластере одной командой.
> Используется для отладки синхронизации образов и чартов BigBug.

## Архитектура

```
┌──────────────────────────────────────────────────────────────────┐
│  kind cluster: harbor                                            │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Namespace: harbor                                         │  │
│  │  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌─────────────┐  │  │
│  │  │ Harbor   │ │ Chart     │ │ Registry │ │ OIDC →       │  │  │
│  │  │ Core +   │ │ Museum    │ │ + DB/    │ │ Keycloak     │  │  │
│  │  │ Portal   │ │           │ │ Redis    │ │ :8180        │  │  │
│  │  └──────────┘ └───────────┘ └──────────┘ └─────────────┘  │  │
│  │       ▲                                                    │  │
│  │       │ NodePort 30080 (HTTP)                              │  │
│  │       │ NodePort 30443 (HTTPS)                             │  │
│  └───────┼────────────────────────────────────────────────────┘  │
│          │                                                       │
└──────────┼───────────────────────────────────────────────────────┘
           │ port mapping
     ┌─────┴─────┐
     │  Docker   │
     │  host     │
     │  :80      │ → 30080
     │  :443     │ → 30443
     └───────────┘
```

## Зависимости

| Инструмент | Мин. версия | Проверка |
|-----------|-------------|---------|
| [kind](https://kind.sigs.k8s.io/) | 0.20+ | `kind version` |
| [kubectl](https://kubernetes.io/docs/tasks/tools/) | 1.27+ | `kubectl version --client` |
| [helm](https://helm.sh/) | 3.12+ | `helm version` |
| [docker](https://docs.docker.com/engine/install/) | 24+ | `docker version` |
| [curl](https://curl.se/) | 7.0+ | `curl --version` |
| [jq](https://jqlang.github.io/jq/) | 1.6+ | `jq --version` |
| [OpenTofu](https://opentofu.org/) | 1.6+ | `tofu version` |

## Быстрый старт

```bash
# 1. Клонировать репозиторий (если ещё не)
cd BigBug

# 2. Развернуть Harbor
./infrastructure/harbor/deploy.sh

# 3. Инициализировать проекты и OIDC через OpenTofu
cd infrastructure/terraform
cp terraform.tfvars.example terraform.tfvars
# Отредактируйте terraform.tfvars (harbor_password, harbor_client_secret)
tofu init && tofu apply

# 4. Открыть Harbor UI
# https://harbor.local:30443
# Логин: admin / Harbor12345
```

## Полная последовательность шагов

### Шаг 1: Развернуть Harbor в kind

```bash
./infrastructure/harbor/deploy.sh
```

Скрипт автоматически:
- Проверяет зависимости (kind, kubectl, helm, docker)
- Добавляет `harbor.local` в `/etc/hosts`
- Настраивает Docker insecure registry для `harbor.local:30080`
- Создаёт kind-кластер `harbor` с пробросом портов
- Устанавливает Harbor через Helm с параметрами из [`harbor-values.yaml`](harbor-values.yaml)
- Ждёт готовности подов (до 300 секунд)

### Шаг 2: Инициализировать проекты и OIDC в Harbor

**Через OpenTofu** (декларативно, идемпотентно):

```bash
cd ../terraform
cp terraform.tfvars.example terraform.tfvars
# Отредактируйте terraform.tfvars (harbor_password, oidc_client_secret)
tofu init && tofu apply
```

Корневой модуль `infrastructure/terraform/` создаст:
- Проекты: `gold-images`, `app-images`, `mirrors`
- OIDC-интеграцию с Keycloak
- Robot accounts для CI/CD
- Внешние registries (Docker Hub, Quay.io)
- Webhook для уведомлений backend

### Шаг 3: Протестировать Harbor

```bash
./infrastructure/harbor/test-push.sh
```

Выполняет: docker login → pull alpine → tag → push → API-проверка → очистка.

### Шаг 3.1 (Опционально): Настроить OIDC через Keycloak

См. подробное руководство: [`keycloak-integration.md`](keycloak-integration.md)

Кратко:
1. Создать OIDC client `harbor` в Keycloak (realm `bigbug`) — **автоматически через OpenTofu**
2. Настроить redirect URI: `https://harbor.local:30443/c/oidc/callback`
3. OpenTofu передаёт Client Secret из Keycloak в Harbor автоматически
4. В Harbor UI → Administration → Configuration → Authentication выбрать OIDC
5. Заполнить endpoint: `http://localhost:8180/realms/bigbug`
6. Включить Auto Onboarding

## Доступ к Harbor

| Ресурс | URL | Порт |
|--------|-----|------|
| Harbor UI (HTTPS) | https://harbor.local:30443 | 30443 → 443 |
| Docker Registry (HTTP) | harbor.local:30080 | 30080 → 80 |
| Chart Repo (HTTPS) | https://harbor.local:30443/chartrepo/library | 30443 |
| Harbor API (HTTPS) | https://harbor.local:30443/api/v2.0 | 30443 |

### Учётные данные

| Назначение | Username | Password | Источник |
|------------|----------|----------|----------|
| Harbor Admin | `admin` | `Harbor12345` | [`harbor-values.yaml`](harbor-values.yaml) |
| Keycloak Admin | `admin` | `admin` | [`infrastructure/docker-compose.yml`](../docker-compose.yml) |
| BigBug Test User | `bigbug` | `bigbug` | Keycloak realm `bigbug` |

### Добавление Helm репозитория

```bash
helm repo add harbor-local \
  https://harbor.local:30443/chartrepo/library \
  --username=admin --password=Harbor12345
```

## Конфигурация /etc/hosts

Для разрешения `harbor.local` скрипт [`deploy.sh`](deploy.sh) автоматически добавляет строку в `/etc/hosts`:

```
127.0.0.1 harbor.local
```

Проверить вручную:

```bash
grep harbor.local /etc/hosts
```

## Insecure Registry (HTTP без TLS)

Для работы с Harbor через HTTP (`harbor.local:30080`) необходима настройка insecure registry.

### Автоматическая настройка (deploy.sh)

[`deploy.sh`](deploy.sh) автоматически обновляет `/etc/docker/daemon.json`:

```json
{
  "insecure-registries": ["harbor.local:30080"]
}
```

### Ручная настройка

Если автоматическая настройка не сработала:

```bash
# 1. Добавить insecure registry
sudo mkdir -p /etc/docker
cat <<EOF | sudo tee /etc/docker/daemon.json
{
  "insecure-registries": ["harbor.local:30080"]
}
EOF

# 2. Перезапустить Docker
sudo systemctl restart docker

# 3. Проверить
docker info | grep -A3 "Insecure Registries"
```

## Интеграция с Keycloak (OIDC)

Подробная документация по настройке OIDC-аутентификации через Keycloak: [`keycloak-integration.md`](keycloak-integration.md)

**Краткая схема:**
1. Keycloak (realm `bigbug`, client `harbor`) — провайдер идентификации
2. Harbor — RP (Relying Party), перенаправляет на Keycloak для аутентификации
3. Группы Keycloak (`harbor-admin`, `harbor-dev`, `harbor-guest`) → роли Harbor
4. Auto Onboarding — пользователи создаются при первом OIDC-входе

**Важно:** При локальной разработке Keycloak работает на `localhost:8180`, что недоступно изнутри kind-кластера. Используйте IP docker-хоста (обычно `172.17.0.1`):

```bash
# Узнать IP docker bridge
docker network inspect bridge -f '{{(index .IPAM.Config 0).Gateway}}'
# → 172.17.0.1

# OIDC Endpoint в Harbor:
# http://172.17.0.1:8180/realms/bigbug
```

## Тестирование

```bash
./infrastructure/harbor/test-push.sh
```

Скрипт выполняет:

1. Docker login в harbor.local:30080
2. Pull `alpine:latest`
3. Tag образа для Harbor
4. Push в `library/alpine:test`
5. Проверку проектов через Harbor REST API
6. Проверку тегов репозитория `library/alpine`
7. Очистку локального тега

### Ручное тестирование

```bash
# Логин
docker login harbor.local:30080 -u admin -p Harbor12345

# Push
docker pull alpine:latest
docker tag alpine:latest harbor.local:30080/library/alpine:test
docker push harbor.local:30080/library/alpine:test

# API
curl -k -u admin:Harbor12345 https://harbor.local:30443/api/v2.0/projects
```

## Удаление

```bash
# Удалить кластер (запись /etc/hosts сохраняется)
./infrastructure/harbor/teardown.sh

# Полная очистка: кластер + /etc/hosts
./infrastructure/harbor/teardown.sh --all
```

## Структура файлов

```
harbor/
├── README.md                 # Этот файл
├── deploy.sh                 # Главный скрипт развёртывания
├── teardown.sh               # Скрипт удаления
├── kind-config.yaml          # Конфигурация kind кластера
├── harbor-values.yaml        # Helm values для Harbor chart
├── test-push.sh              # Скрипт тестирования push образов
└── keycloak-integration.md   # Руководство по интеграции OIDC с Keycloak
```

> **Инициализация проектов и OIDC через OpenTofu**: [`infrastructure/terraform/`](../terraform/).
> Модуль `harbor` в [`infrastructure/terraform/modules/harbor/`](../terraform/modules/harbor/) вызывается корневым модулем.

## Порты (сводка)

| Порт | Назначение | Сервис |
|------|------------|--------|
| 80 | Harbor HTTP (mapped от NodePort 30080) | Harbor Registry |
| 443 | Harbor HTTPS (mapped от NodePort 30443) | Harbor UI + API |
| 30080 | NodePort HTTP (внутри kind) | Harbor Registry |
| 30443 | NodePort HTTPS (внутри kind) | Harbor Portal + API |
| 8080 | GitLab HTTP | GitLab CE |
| 8180 | Keycloak HTTP | Keycloak |
| 8000 | Backend API | BigBug Backend |
| 5173 | Frontend Dev Server | BigBug Frontend |

Порты проверены на конфликты — пересечений нет.

## Troubleshooting

### Проблема: «kind cluster already exists»

```bash
kind delete cluster --name=harbor
./infrastructure/harbor/deploy.sh
```

### Проблема: «connection refused» при push

Проверьте insecure registry:

```bash
docker info | grep -A3 "Insecure Registries"
# Должно быть: harbor.local:30080
```

Если отсутствует — выполните ручную настройку (см. раздел Insecure Registry).

### Проблема: «harbor.local не резолвится»

```bash
# Проверить запись в /etc/hosts
grep harbor.local /etc/hosts

# Добавить вручную
echo "127.0.0.1 harbor.local" | sudo tee -a /etc/hosts

# Проверить
ping -c 1 harbor.local
```

### Проблема: поды не стартуют

```bash
# Проверить состояние подов
kubectl get pods -n harbor

# Логи конкретного пода
kubectl logs -n harbor deployment/harbor-core

# Описание пода (Events)
kubectl describe pod -n harbor -l app=harbor
```

### Проблема: недостаточно ресурсов

Harbor требует ~2 GB RAM для всех компонентов. Проверьте ресурсы Docker:

```bash
docker info | grep -i memory
```

При необходимости увеличьте лимиты в Docker Desktop / daemon settings.

### Проблема: «ImagePullBackOff»

```bash
# Проверить, что образы доступны
kubectl describe pod -n harbor harbor-core-xxx | grep -A5 Events

# Принудительно обновить образы
docker pull goharbor/harbor-core:v2.10.3
kind load docker-image goharbor/harbor-core:v2.10.3 --name=harbor
```

### Проблема: сертификат не доверяется браузером

Harbor использует самоподписанный сертификат. В браузере:

- Примите предупреждение безопасности
- Или добавьте `-k` флаг для curl
- Для production используйте cert-manager + Let's Encrypt

### Проблема: OIDC-редирект не работает (Keycloak изнутри kind)

См. раздел [Интеграция с Keycloak (OIDC)](#интеграция-с-keycloak-oidc) и [`keycloak-integration.md`](keycloak-integration.md)

Ключевое: используйте IP docker bridge (`172.17.0.1`) вместо `localhost` для OIDC Endpoint в Harbor.

## Ссылки

- [Harbor Documentation](https://goharbor.io/docs/)
- [Harbor Helm Chart](https://github.com/goharbor/harbor-helm)
- [Harbor OIDC Authentication](https://goharbor.io/docs/2.10.0/administration/configure-oidc-auth/)
- [kind Quick Start](https://kind.sigs.k8s.io/docs/user/quick-start/)
- [kind Configuration](https://kind.sigs.k8s.io/docs/user/configuration/)
- [Keycloak Documentation](https://www.keycloak.org/documentation)
