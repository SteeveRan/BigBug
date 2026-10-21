---
adr: 0001
component: backend
status: Proposed
date: 2026-10-21
deciders: []
supersedes: null
superseded_by: null
---

# ADR-0001: Выбрать backend-стек: Python 3.14 + FastAPI + SQLAlchemy 2 (async) + PostgreSQL 17 / Redis 7

## Контекст и проблема

`docs/adr/` пуст (только README/ARCHIVE/_template). Решение о backend-стеке живёт в разрозненных план-документах (`plans/architecture/decisions.md`, `plans/tech-stack.md`), частично устаревших (например, они упоминают MUI для frontend). Это первый ADR: он фиксирует backend-стек как есть в коде и создаёт точку отсчёта для реестра (roadmap: `.agents/plans/adr-roadmap.md`, 22 ADR — один домен = один ADR).

Источник истины — код, а не план-документы: версии проверены по `backend/pyproject.toml` (см. Решение).

## Decision Drivers

- Нужен **async-first** стек: backend ходит в GitLab API, Harbor, GitHub, Docker/Helm registry через httpx, долгие операции не должны блокировать event loop
- Python-консистентность с DevOps-инструментами (GitLab CI, python-gitlab, PyGithub — зрелая экосистема)
- Реляционная модель: пользователи, роли, RBAC, providers, mirrors — ACID и FK обязательны
- Типизированный код: mypy проходит по всему backend (pragmatic baseline, не strict)
- Минимализм зависимостей: ничего «для будущего», каждый пакет уже используется кодом

## Рассмотренные варианты

### Вариант 1: Django (+ DRF, + Celery)

- **Плюсы**: batteries included (ORM, admin, auth из коробки); огромная экосистема
- **Минусы**: sync-first, тяжёлый для async-интеграций (нужен Celery + отдельные воркеры для фоновых задач); admin не нужен (есть свой React UI); навязывает свою структуру проекта

### Вариант 2: Flask

- **Плюсы**: минималистичный, гибкий
- **Минусы**: нет встроенной async-поддержки; вся асинхронная обвязка (DI, валидация, OpenAPI) собиралась бы вручную

### Вариант 3: Node.js / Express

- **Плюсы**: нативный async, единый язык с frontend
- **Минусы**: потеря Python-экосистемы (python-gitlab, PyGithub); отказ от Python противоречит консистентности с DevOps-инструментами

### Вариант 4: FastAPI + SQLAlchemy 2 + SQLModel

- **Плюсы**: FastAPI — нативный async, автоматический OpenAPI, Pydantic-валидация на границе
- **Минусы**: SQLModel — слишком молодой проект; комбинированный слой ломает типизацию ORM-моделей для mypy

### Вариант 5: FastAPI + SQLAlchemy 2 (async) — **выбран**

- **Плюсы**: нативный async; зрелый ORM с плагином mypy (`sqlalchemy.ext.mypy.plugin`); автоматический OpenAPI (`/docs`); Pydantic v2 как единый язык схем; APScheduler решает фоновые задачи без Celery и брокера
- **Минусы**: больше ручной сборки, чем в Django (auth, админка — свои); async в SQLAlchemy требует дисциплины (lazy loading недоступен)

## Решение

Backend BigBug — **Python 3.14** (`requires-python = ">=3.14"`), веб-фреймворк **FastAPI >= 0.115** (сервер — uvicorn с `[standard]`), ORM — **SQLAlchemy >= 2.0** в async-режиме с драйвером **asyncpg >= 0.29**, СУБД — **PostgreSQL 17** (docker-образ `postgres:17`, два инстанса: backend + keycloak), миграции — **Alembic >= 1.13**. Кэш и очереди — **Redis 7** (`redis:7-alpine`, клиент `redis >= 5.0`). Валидация и конфиг — **Pydantic >= 2.7** + `pydantic-settings`. Планировщик — **APScheduler >= 3.10** (AsyncIOScheduler, без Celery). Аутентификация: **authlib >= 1.3** (OIDC/Keycloak SSO), `python-jose[cryptography]` (JWT), `bcrypt >= 4.0` (пароли), `cryptography` — Fernet-шифрование секретов. Внешние клиенты: **httpx >= 0.27** (Harbor/Docker/Helm API), `python-gitlab >= 4.6`, `PyGithub >= 2.3`. Качество: **pytest + pytest-asyncio**, **mypy >= 1.13** (pragmatic baseline, плагины pydantic и sqlalchemy), **vulture** (dead code).

## Обоснование

Выбран единственный вариант, который одновременно даёт async-first I/O (все интеграции — сетевые), зрелую типизацию под mypy и минимальный набор процессов (uvicorn + APScheduler в одном приложении, без Celery-брокера). Tradeoff принят сознательно: больше ручного кода (auth/SSO, миграции сидов, фоновые задачи — свои модули) в обмен на отсутствие «магии» фреймворка и лишней инфраструктуры. SQLModel отвергнут не из-за недостатка функций, а из-за зрелости и совместимости с mypy-плагинами SQLAlchemy.

## Последствия

- **Положительные**: один язык схем (Pydantic) от API до конфига; OpenAPI бесплатно (`/docs`); весь стек покрыт make-целями (`make lint`, `make typecheck`, `make test-unit-backend`)
- **Отрицательные / принятые риски**: Python 3.14 — свежая версия, часть third-party пакетов может отставать по поддержке (следим через renovate); async-модели SQLAlchemy запрещают lazy loading — все связи грузить явным `selectinload`/`joinedload`
- **Non-goals**: Celery/отдельные воркеры; строгий mypy; фронтенд-стек (ADR-0002) и инфраструктура (ADR-0012/0013); удаление `plans/tech-stack.md` (владелец — ADR-0013)

## Implementation Plan

Решение фиксирует существующее состояние — код уже соответствует ADR; новых файлов и миграций не требуется.

| Файл / область | Действие | Паттерн |
|---|---|---|
| `backend/pyproject.toml` | поддерживать версии в согласии с этим ADR | новые зависимости — только через новый ADR |
| `backend/app/models/` | новые модели по SQLAlchemy 2.0 declarative, async | следовать: `backend/app/models/user.py` |
| `backend/app/schemas/` | Pydantic v2 | следовать: `backend/app/schemas/` |
| `backend/alembic/versions/` | новые миграции поверх `add_helm_mirror_fields` | см. `plans/development/database.md` |
| Фоновые задачи | APScheduler (AsyncIOScheduler), не Celery | следовать: `backend/app/services/` |

## Verification

ADR документарный, код не меняет — make-цели из шаблона неприменимы.
Содержательная проверка одна:

- [x] Версии в разделе «Решение» совпадают с `backend/pyproject.toml` и docker-compose-образами (`postgres:17`, `redis:7-alpine`)

## Связанные ADR и документы

- ADR-0002 (frontend stack) — запланирован, см. `.agents/plans/adr-roadmap.md`
- ADR-0012/0013 (infrastructure, tech-stack doc) — запланированы
- `plans/architecture/decisions.md` — исходные рассуждения по альтернативам (частично устарел, источник истины — код)
- `plans/development/backend.md`, `plans/development/database.md` — конвенции реализации
