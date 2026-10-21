---
status: proposed
date: 2026-10-21
decision-makers: SteeveRan
---

# Выбрать backend-стек: Python 3.14 + FastAPI + SQLAlchemy 2 (async) + PostgreSQL 17 / Redis 7

## Context and Problem Statement

Решение о backend-стеке BigBug до сих пор нигде официально не зафиксировано: оно подразумевается кодом (`backend/pyproject.toml`).

## Decision Drivers

- Нужен **async-first** стек: backend ходит в GitLab API, Harbor, GitHub, Docker/Helm registry через httpx, долгие операции не должны блокировать event loop
- Python-консистентность с DevOps-инструментами (GitLab CI, python-gitlab, PyGithub — зрелая экосистема)
- Реляционная модель: пользователи, роли, RBAC, providers, mirrors — ACID и FK обязательны
- Типизированный код: mypy проходит по всему backend (pragmatic baseline, не strict)
- Минимализм зависимостей: ничего «для будущего», каждый пакет уже используется кодом

## Considered Options

* Django (+ DRF, + Celery)
* Flask
* Node.js / Express
* FastAPI + SQLAlchemy 2 + SQLModel
* FastAPI + SQLAlchemy 2 (async) + PostgreSQL 17 / Redis 7

## Decision Outcome

Chosen option: **FastAPI + SQLAlchemy 2 (async) + PostgreSQL 17 / Redis 7** — единственный вариант, который одновременно даёт async-first I/O (все интеграции — сетевые), зрелую типизацию под mypy и минимальный набор процессов (uvicorn + APScheduler в одном приложении, без Celery-брокера). Трейдофф принят сознательно: больше ручного кода (auth/SSO, миграции сидов, фоновые задачи — свои модули) в обмен на отсутствие «магии» фреймворка и лишней инфраструктуры.

Конкретный стек (версии проверены по `backend/pyproject.toml`):

- **Python 3.14** (`requires-python = ">=3.14"`), сервер — **uvicorn[standard] >= 0.30**
- **FastAPI >= 0.115**
- **SQLAlchemy >= 2.0** async-режим, драйвер **asyncpg >= 0.29**, СУБД **PostgreSQL 17** (docker-образ `postgres:17`, два инстанса: backend + keycloak), миграции — **Alembic >= 1.13**
- **Redis 7** (`redis:7-alpine`, клиент `redis >= 5.0`) — кэш и очереди
- **Pydantic >= 2.7** + `pydantic-settings` — валидация и конфиг
- **APScheduler >= 3.10** (AsyncIOScheduler, без Celery)
- Auth: **authlib >= 1.3** (OIDC/Keycloak SSO), `python-jose[cryptography]` (JWT), `bcrypt >= 4.0` (пароли), `cryptography` — Fernet-шифрование секретов
- Внешние клиенты: **httpx >= 0.27** (Harbor/Docker/Helm API), `python-gitlab >= 4.6`, `PyGithub >= 2.3`
- Качество: **pytest + pytest-asyncio**, **mypy >= 1.13** (pragmatic baseline, плагины pydantic и sqlalchemy), **vulture** (dead code)

### Consequences

* Good, because один язык схем (Pydantic) от API до конфига; OpenAPI бесплатно (`/docs`)
* Bad, because Python 3.14 — свежая версия, часть third-party пакетов может отставать по поддержке (следим через renovate)
* Bad, because async-модели SQLAlchemy запрещают lazy loading — все связи грузить явным `selectinload`/`joinedload`
* Neutral, because больше ручной сборки, чем в Django (auth, админка — свои), в обмен на отсутствие лишней инфраструктуры
* Non-goals: Celery/отдельные воркеры; строгий mypy; выбор фронтенд-стека и инфраструктуры (отдельные ADR: 0002, 0012, 0013); `plans/tech-stack.md` удалён [ADR-0013](../infrastructure/0013-opentofu-iac-keycloak-gitlab-harbor.md)

### Confirmation

Версии в разделе Decision Outcome сверяются с `backend/pyproject.toml` и docker-compose-образами (`postgres:17`, `redis:7-alpine`) — на 2026-10-21 сверены, расхождений нет. Правило на будущее: новая backend-зависимость или смена версии вне этого списка требует нового ADR (триггер — «новая зависимость» из README). Архитектурный fitness-критерий: `backend/pyproject.toml` не должен содержать пакетов, не упомянутых здесь, и vice versa; `requirements`-файлы не вводятся — только `pyproject.toml`.

## Pros and Cons of the Options

### Django (+ DRF, + Celery)

Batteries included, но sync-first.

* Good, because ORM, admin, auth из коробки; огромная экосистема
* Bad, because sync-first: тяжёлый для async-интеграций (нужен Celery + отдельные воркеры)
* Bad, because admin не нужен (есть свой React UI); навязывает свою структуру проекта

### Flask

* Good, because минималистичный, гибкий
* Bad, because нет встроенной async-поддержки; вся асинхронная обвязка (DI, валидация, OpenAPI) собиралась бы вручную

### Node.js / Express

* Good, because нативный async, единый язык с frontend
* Bad, because потеря Python-экосистемы (python-gitlab, PyGithub); отказ от Python противоречит консистентности с DevOps-инструментами

### FastAPI + SQLAlchemy 2 + SQLModel

* Good, because нативный async; автоматический OpenAPI; Pydantic-валидация на границе
* Bad, because SQLModel — слишком молодой проект; комбинированный слой ломает типизацию ORM-моделей для mypy

### FastAPI + SQLAlchemy 2 (async) + PostgreSQL 17 / Redis 7 — chosen

* Good, because нативный async; зрелый ORM с плагином mypy (`sqlalchemy.ext.mypy.plugin`)
* Good, because Pydantic v2 как единый язык схем; APScheduler решает фоновые задачи без Celery и брокера
* Bad, because больше ручной сборки, чем в Django (auth, админка — свои)
* Bad, because async в SQLAlchemy требует дисциплины (lazy loading недоступен)

## More Information

- Исходные рассуждения по альтернативам — `plans/architecture/decisions.md` (частично устарел, источник истины — код)
- Конвенции реализации — `plans/development/backend.md`, [ADR-0006](0006-database-postgresql-alembic.md)
- Условие пересмотра: если экосистема Python 3.14 создаст блокеры (отставание ключевых пакетов) или нагрузка потребует распределённых воркеров — переоткрыть решение через новый ADR
