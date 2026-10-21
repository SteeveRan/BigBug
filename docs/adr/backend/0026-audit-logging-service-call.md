---
status: proposed
date: 2026-10-22
decision-makers: SteeveRan
consulted: SteeveRan
informed: SteeveRan
---

# Аудит действий: service-call журналирование в таблицу `audit_logs` с never-raise политикой

## Context and Problem Statement

Как BigBug должен журналировать значимые действия пользователей и системы для последующего расследования инцидентов?

Аудит в BigBug **уже реализован**, но нигде не зафиксирован как архитектурное решение (legacy-документ `docs/architecture/10-security.md`, удалён в #49, описывал несуществующий middleware `app/core/audit.py`). Фактическая реализация проверена по коду:

- **Модель**: `backend/app/models/audit_log.py` — таблица `audit_logs` (создана в `20260816_1159_37590bb4a2ec_initial_schema.py`): `user_id` (FK → `users.id`, `ondelete="SET NULL"`, nullable), `username` (денормализовано), `action` (индексирована), `resource_type` (индексирована), `resource_id`, `resource_name` (денормализовано), `details` (JSON), `ip_address`, `created_at` (индексирована).
- **Сервис**: `backend/app/services/audit.py` — `AuditService.log_event(...)` с документированной **never-raise политикой**: любая ошибка записи ловится, транзакция откатывается (`db.rollback()` — чтобы не отравить общую сессию `PendingRollbackError`), ошибка пишется в лог приложения, основной запрос продолжается.
- **API чтения**: `GET /api/admin/audit-logs` (`backend/app/api/audit.py`, префикс в `main.py`) с permission `audit:read`; фильтры по `user_id`/`action`/`resource_type`/`date_from`/`date_to`, пагинация.
- **Вызовы**: 54 точки журналирования в API-роутерах (`admin.py`, `auth.py`, `mirroring.py`, `pipelines.py`, `gitlab_projects.py`, `credentials.py`) и сервисах (`webhooks.py` — системные события `mirror.sync_completed`/`mirror.sync_failed` от имени `username="system"`); всего 45 уникальных значений `action` (`create`, `update`, `delete`, `login`, `mirror.*`, `sync_group.*`, `pipeline.*`, `credential.*`, `gitlab_project.*`, ...).

Нужно зафиксировать: что журналируем, где вызывается журналирование (service-call, а не middleware), политику отказоустойчивости и что сознательно НЕ журналируем.

## Decision Drivers

* Аудит не должен ломать основной сценарий: недоступность/ошибка записи аудита не вправе ронять бизнес-операцию (создание зеркала важнее записи о нём)
* В JWT-кэше permissions + JWT-аутентификация (ADR-0003/0004) — middleware-подход не знает доменного контекста (resource_id, resource_name, details), который есть только в точке действия
* Требование расследуемости: запись должна переживать удаление пользователя (`user_id` → NULL через `SET NULL`, но `username` денормализован и остаётся)
* Чтение — admin-операция с отдельным правом (`audit:read`), а не публичная
* Простота: без внешних audit-бэкендов (ELK, syslog) — таблица в том же PostgreSQL достаточна для масштаба платформы
* Удалённые сущности: soft-delete доминирует, но hard-delete (пользователи) не должен стирать след

## Considered Options

* Service-call журналирование: явный `AuditService.log_event()` в точках мутаций (текущая реализация)
* ASGI middleware: автоматическое журналирование всех мутирующих запросов
* Внешний audit-бэкенд (syslog/ELK через log shipping)

## Decision Outcome

Chosen option: **Service-call журналирование** — явные вызовы `AuditService.log_event()` из API-роутеров и сервисов в точках значимых мутаций, запись в таблицу `audit_logs` того же PostgreSQL, never-raise политика.

Правила, зафиксированные по фактической реализации:

1. **Что журналируем**: мутации значимых доменных сущностей (пользователи, роли, credentials, зеркала, sync/source группы, pipeline-конфигурации, GitLab-проекты, mirror sync завершения системных джоб) и аутентификационные события (`login`). Формат `action` — `<entity>.<verb>` для доменных событий (`mirror.created`) и голый глагол для admin-CRUD (`create`/`update`/`delete` над user/role).
2. **Как вызывается**: `await AuditService.log_event(db, user_id=..., username=..., action=..., resource_type=..., resource_id=..., resource_name=..., details=..., ip_address=...)` — после успешного коммита основной операции, в той же сессии.
3. **Never-raise**: `log_event` не поднимает исключений никогда: try/except вокруг записи, при ошибке — `db.rollback()` (защита общей сессии от `PendingRollbackError`) + `logger.error`. Бизнес-операция, уже закоммиченная, не откатывается и не репортит ошибку из-за аудита.
4. **Живучесть записей**: `user_id` — FK с `ondelete="SET NULL"`; `username` и `resource_name` денормализованы — удаление пользователя/ресурса не стирает контекст записи. Hard-delete пользователя обязан логироваться с `user_id=None` (комментарий в `admin.py`: нарушение FK `audit_logs_user_id_fkey` иначе отравляет сессию).
5. **Чтение**: только `GET /api/admin/audit-logs` с `audit:read`; фильтры + пагинация. Изменение/удаление записей через API не предусмотрено (append-only по построению).
6. **Системные события**: действия фоновых джоб/вебхуков логируются с `user_id=None, username="system"`.

### Consequences

* Good, because ошибка аудита никогда не роняет и не откатывает бизнес-операцию (never-raise + rollback защищает общую сессию)
* Good, because в точке вызова доступен доменный контекст (`details`, `resource_name`) — записи содержательнее, чем «POST /api/mirrors 200» от middleware
* Good, because записи переживают удаление пользователей и ресурсов (денормализация + SET NULL)
* Bad, because журналирование вручную: новая мутация без вызова `log_event` молча не попадёт в аудит — полагаемся на ревью (fitness-критерий ниже не автоматизирован полностью)
* Bad, because запись в ту же БД: недоступный PostgreSQL = нет и аудита; при недоступности БД бизнес-запросы всё равно не работают, так что отдельного сценария потери аудита нет
* Bad, because нет автоматического экспорта/ретеншена: таблица растёт неограниченно (при необходимости чистки — будущая задача `cleanup_cron_hour`-семейства)
* Neutral, because голые глаголы (`create`) против `entity.verb` (`mirror.created`) — историческое разнообразие форматов; унификация не требуется, но новые доменные события должны следовать `entity.verb`
* Non-goals: middleware/декоратор автожурналирования; экспорт во внешние SIEM; тампер-защита (подпись строк); журналирование read-операций; уведомления/alerts по событиям

### Confirmation

* `make test-unit-backend TEST_ARGS="tests/unit/test_audit_service.py -v"` — зелёный: покрывает `log_event` (создание записи в БД).
* `make test-unit-backend TEST_ARGS="tests/unit/test_audit_mirroring.py -v"` — зелёный: покрывает системные события mirror-sync от имени `system`.
* Never-raise покрыт тестом на невалидную запись (ошибка не всплывает из `log_event`) в `test_audit_service.py`.
* Fitness-критерий на ревью: новый мутирующий API-эндпоинт (POST/PATCH/DELETE над доменными сущностями) содержит вызов `AuditService.log_event` либо явный комментарий, почему аудит не нужен. Проверка ревью: `git diff` новых роутеров.

## Pros and Cons of the Options

### Service-call журналирование — chosen

См. Decision Outcome.

* Good, because полный доменный контекст в точке вызова
* Good, because never-raise изолирован в одном методе — легко тестировать
* Good, потому что явный вызов виден в diff'е ревью (новый endpoint без аудита заметен)
* Bad, потому что забытый вызов = дыра в аудите без автоматического сигнала
* Bad, because Boilerplate: 54 точки вызова с похожими аргументами

### ASGI middleware (автожурналирование мутаций)

Middleware перехватывает POST/PATCH/DELETE и пишет «кто, куда, когда» автоматически.

* Good, because ничего не забывается: покрытие полное по определению
* Good, потому что нет boilerplate в роутерах
* Bad, потому что записи бессодержательны: middleware не знает resource_name/details/доменного смысла; body парсить в middleware дорого и хрупко
* Bad, потому что фильтрация шума (не всё мутации значимы) в middleware вырождается в список исключений — неявную конфигурацию маршрутов
* Bad, потому что не работает для системных событий (webhook от `system`, фоновые джобы) — всё равно нужен service-call путь

### Внешний audit-бэкенд (syslog/ELK)

* Good, because тампер-защита (вне БД приложения) и ретеншен вне ответственности приложения
* Bad, потому что новая обязательная инфраструктура для standalone-деплоев (противоречит драйверу минимализма)
* Bad, потому что фильтрация/чтение через admin UI требуют отдельного query-канала; таблица + API уже работают

## More Information

* Реализация: `backend/app/services/audit.py`, `backend/app/models/audit_log.py`, `backend/app/api/audit.py`; схема — `20260816_1159_37590bb4a2ec_initial_schema.py` (таблица `audit_logs`).
* Пример never-raise контракта с rollback-защитой: `AuditService.log_event` (комментарий в коде объясняет `PendingRollbackError` на shared session).
* Пример системного события: `backend/app/api/webhooks.py` — `mirror.sync_completed` / `mirror.sync_failed` при завершении pipeline.
* Связанные ADR: ADR-0005 (service layer — аудит живёт в service/API-слое по тем же правилам), ADR-0003 (аутентификация — источник `username`/`user_id`), ADR-0004 (право `audit:read` в RBAC-матрице, `docs/development/permissions.md`).
* Происхождение: legacy-документ `docs/architecture/10-security.md` (удалён в #49) описывал несуществующий middleware `app/core/audit.py` и таблицу `audit_log` (не `audit_logs`); этот ADR фиксирует реализацию по фактам.
* Триггеры пересмотра: требование тампер-защиты или SIEM-экспорта (регуляторика); рост таблицы до проблемных размеров (нужен ретеншен); требование журналировать read-операции.
