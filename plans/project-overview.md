# BigBug - Project Overview

## Что такое BigBug?

BigBug — централизованная DevOps платформа для управления жизненным циклом Docker образов, Helm чартов и Git репозиториев.

## Основные возможности

### 1. Docker Images Management
- **Gold Images** - базовые образы (OS + runtime)
  - Ubuntu, Alpine, Debian и т.д.
  - Python, Node.js, Java runtimes
  - Автоматические обновления при выходе новых версий
- **App Images** - приложения поверх Gold образов
  - Используют Gold образы как base
  - Связаны с GitHub проектами
  - Версионирование и CI/CD

### 2. Mirroring
- **Git Repositories**: GitHub → GitLab
  - Автоматическое зеркалирование репозиториев
  - CI/CD пайплайны для зеркал
  - Stale detection (устаревшие зеркала)
  - Delta tracking (сколько релизов отстаём)
  
- **Docker Images**: Registry → Harbor
  - Синхронизация образов между registry
  - Индексация тегов
  - Metadata сохранение
  
- **Helm Charts**: Repository → Harbor/ChartMuseum
  - Синхронизация Helm чартов
  - Версионирование
  - Metadata из index.yaml

### 3. CI/CD Integration
- GitLab CI/CD пайплайны
- GitLab Components (переиспользуемые блоки)
- Webhook интеграция
- Расписания (cron schedules)

### 4. Management UI
- React-based веб-интерфейс
- Role-based доступ (Admin/Operator/Viewer)
- Real-time статусы
- История операций

## Архитектура высокого уровня

```
┌─────────────┐
│   Browser   │
│  (React UI) │
└──────┬──────┘
       │ HTTPS
       ▼
┌─────────────────┐
│  FastAPI        │◄────── Redis (cache)
│  Backend        │
└────────┬────────┘
         │
    ┌────┴────┬─────────┬──────────┐
    ▼         ▼         ▼          ▼
┌────────┐ ┌──────┐ ┌────────┐ ┌────────┐
│PostgeSQL GitLab │ │ GitHub │ │ Harbor │
└────────┘ │  API │ │  API   │ │  API   │
           └──────┘ └────────┘ └────────┘
                │
                ▼
         ┌──────────────┐
         │ GitLab Runner│
         │  (CI/CD)     │
         └──────────────┘
```

## Workflow примеры

### Создание Gold Image
1. Operator создаёт Gold Image в UI (Ubuntu 22.04 + Python 3.12)
2. Система создаёт GitLab проект с Dockerfile
3. Триггерится GitLab CI/CD pipeline
4. Образ собирается и пушится в registry
5. Статус обновляется через webhook
6. Cosign подпись (опционально)

### GitHub → GitLab Mirror
1. Operator добавляет GitHub репозиторий
2. Система создаёт GitLab проект
3. Настраивается CI/CD pipeline для синхронизации
4. По расписанию или вручную запускается sync
5. Отслеживается delta (сколько релизов отстаём)

### Helm Chart Sync
1. Operator добавляет Helm repository
2. Система индексирует index.yaml
3. Находит все чарты и версии
4. Опционально триггерит GitLab pipeline для pull
5. Метаданные сохраняются в БД

## Целевая аудитория

- **DevOps инженеры** - управление образами и CI/CD
- **Platform teams** - централизованная платформа для разработчиков
- **Security teams** - контроль версий, подписи, сканирование

## Ключевые преимущества

1. **Централизация** - одно место для всех DevOps операций
2. **Автоматизация** - scheduled syncs, автоматические сборки
3. **Visibility** - история, статусы, логи
4. **Security** - RBAC, шифрование credentials, audit log
5. **Интеграция** - работает с существующими GitLab/Harbor/GitHub

## Текущий статус

**Реализовано**:
- ✅ Docker infrastructure (Compose + OpenTofu)
- ✅ SSO через Keycloak (OIDC)
- ✅ Helm Charts синхронизация
- ✅ Docker Images синхронизация
- ✅ Frontend UI (12 страниц)
- ✅ Расширенная RBAC (permission-based, 32 permissions, кастомные роли)
- ✅ Multi-instance интеграции (GitLab, Harbor, GitHub, Docker Registry, Helm Repository)
- ✅ Pipeline management UI (запуск, cancel, retry, компоненты)
- ✅ Audit logging (фильтрация, пагинация, детали)
- ✅ Harbor полная интеграция (multi-instance, test connection)
- ✅ Advanced scheduling (sync_schedules, build_schedules, APScheduler)
- ✅ Тесты (backend: 9 unit + 8 e2e; frontend: 16+ unit/integration)

**Запланировано**:
- ⏳ Notifications (email/telegram/webhook)

## Связанные документы

- Детальная архитектура: [`/docs/architecture/`](../docs/architecture/)
- Быстрый старт: [`/AGENTS.md`](../AGENTS.md)
- Технический стек: [`tech-stack.md`](tech-stack.md)
- Текущее состояние: [`current-state.md`](current-state.md)
