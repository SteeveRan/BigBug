# Harbor в kind — Локальный Docker Registry для разработки

> Развёртывание [Harbor](https://goharbor.io/) в [kind](https://kind.sigs.k8s.io/) кластере одной командой.
> Используется для отладки синхронизации образов и чартов BigBug.

## Архитектура

```
┌─────────────────────────────────────────────────┐
│  kind cluster: harbor                            │
│  ┌───────────────────────────────────────────┐  │
│  │  Namespace: harbor                         │  │
│  │  ┌─────────┐ ┌──────────┐ ┌───────────┐  │  │
│  │  │ Harbor  │ │ Chart    │ │ Registry  │  │  │
│  │  │ Core    │ │ Museum   │ │ + DB/Redis│  │  │
│  │  └─────────┘ └──────────┘ └───────────┘  │  │
│  │       ▲                                   │  │
│  │       │ NodePort 30080 (HTTP)             │  │
│  │       │ NodePort 30443 (HTTPS)            │  │
│  └───────┼───────────────────────────────────┘  │
│          │                                       │
└──────────┼───────────────────────────────────────┘
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

## Быстрый старт

```bash
# 1. Клонировать репозиторий (если ещё не)
cd BigBug

# 2. Развернуть Harbor
./harbor/deploy.sh

# 3. Открыть Harbor UI
# https://harbor.local:30443
# Логин: admin / Harbor12345
```

## Доступ к Harbor

| Ресурс | URL | Порт |
|--------|-----|------|
| Harbor UI (HTTPS) | https://harbor.local:30443 | 30443 → 443 |
| Docker Registry (HTTP) | harbor.local:30080 | 30080 → 80 |
| Chart Repo (HTTPS) | https://harbor.local:30443/chartrepo/library | 30443 |

### Учётные данные

- **Username:** `admin`
- **Password:** `Harbor12345` (только для dev!)

### Добавление Helm репозитория

```bash
helm repo add harbor-local \
  https://harbor.local:30443/chartrepo/library \
  --username=admin --password=Harbor12345
```

## Конфигурация /etc/hosts

Для разрешения `harbor.local` скрипт `deploy.sh` автоматически добавляет строку в `/etc/hosts`:

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

`deploy.sh` автоматически обновляет `/etc/docker/daemon.json`:

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

### Настройка containerd в kind

Настроена через [`kind-config.yaml`](kind-config.yaml):

- Mirror для `harbor.local:30080`
- `insecure_skip_verify = true`

## Тестирование

```bash
./harbor/test-push.sh
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
./harbor/teardown.sh

# Полная очистка: кластер + /etc/hosts
./harbor/teardown.sh --all
```

## Структура файлов

```
harbor/
├── README.md            # Этот файл
├── deploy.sh            # Главный скрипт развёртывания
├── teardown.sh          # Скрипт удаления
├── kind-config.yaml     # Конфигурация kind кластера
├── harbor-values.yaml   # Helm values для Harbor chart
└── test-push.sh         # Скрипт тестирования push образов
```

## Troubleshooting

### Проблема: «kind cluster already exists»

```bash
kind delete cluster --name=harbor
./harbor/deploy.sh
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

## Ссылки

- [Harbor Documentation](https://goharbor.io/docs/)
- [Harbor Helm Chart](https://github.com/goharbor/harbor-helm)
- [kind Quick Start](https://kind.sigs.k8s.io/docs/user/quick-start/)
- [kind Configuration](https://kind.sigs.k8s.io/docs/user/configuration/)
