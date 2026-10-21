---
status: proposed
date: 2026-10-21
decision-makers: SteeveRan
consulted: SteeveRan
informed: SteeveRan
---

# Авторизация: permission-based RBAC (`resource:action`) со scope-providers

## Context and Problem Statement

Как BigBug должен авторизовывать действия пользователей после того, как их личность установлена (аутентификация — см. [ADR-0003](0003-keycloak-oidc-sso-dual-mode.md))? Изначально backend использовал иерархию фиксированных ролей (`require_admin` / `require_operator` / `require_viewer` — `app/core/rbac.py`), которая не позволяет:

- выдавать доступ частично (например, «read везде, write только в Helm»);
- ограничивать видимость ресурсов (например, «operator видит только провайдеры своего scope»);
- настраивать права без релиза кода.

Нужно выбрать модель авторизации, которая поддерживает granular permissions, кастомные роли без деплоя и scoping на уровне конкретных ресурсов (source groups, credentials, sync groups, providers, gitlab projects), и зафиксировать её в ADR — до сих пор она была описана только в планах (`plans/features/auth-rbac.md`, `plans/architecture/permissions.md`).

## Decision Drivers

* Гранулярность: действия различаются в пределах одного ресурса (`mirrors:read` vs `mirrors:sync` vs `mirrors:manage_orphaned`) — бинарной роли «operator» недостаточно.
* Scoping: доступ к конкретным инстансам ресурсов должен управляться отдельно от типа действия (role scope tables: `role_scope_source_groups`, `role_scope_credentials`, `role_scope_sync_groups`, `role_scope_providers`, `role_scope_gitlab_projects`).
* Управление ролями в runtime: кастомные роли создаются через Admin UI, без релиза; builtin-роли (`admin`/`operator`/`viewer`, `is_custom=False`) защищены от модификации.
* Производительность: проверка permissions не должна ходить в БД на каждый запрос.
* Frontend тоже различает действия: кнопки скрываются по permission (`PermissionGate`, `usePermissions`), а не по роли.
* Минимализм: без внешних библиотек авторизации (Casbin, OPA) — домен небольшой, права простые строковые.

## Considered Options

* Permission-based RBAC: строковые permissions `resource:action`, роли как наборы permissions, `require_permission()` dependency
* Ролевая иерархия (fix-роли admin > operator > viewer, `require_roles()`)
* Per-endpoint роли (каждый endpoint объявляет минимальную роль)

## Decision Outcome

Chosen option: **Permission-based RBAC**.

Роль = именованный набор permissions. Permission — строка `resource:action` (например, `mirrors:sync`), сидируется миграциями Alembic в таблицу `permissions`, привязывается к ролям через `role_permissions`. Проверка — FastAPI-зависимостью `require_permission("resource:action")` в backend и hook'ом `usePermissions()` + `<PermissionGate>` во frontend.

Механика (проверено по коду):

1. **Формат**: `resource:action` — плоские строки без иерархии и wildcard-раскрытия. Канонический список — `plans/architecture/permissions.md` (61 право: admin=61, operator=34, viewer=15) и миграция-сид `20260816_1200_a1b2c3d4e5f6_seed_initial_data.py`.
2. **JWT embedding + кэш**: при `login`, `refresh` и `oidc/exchange` в JWT payload вшивается список permissions; `get_current_user` кладёт его в `user._cached_permissions`, `require_permission()` проверяет по кэшу и ходит в БД (RBACService.get_user_permissions) только когда кэш пуст или протух (токен выпущен до добавления permission-а).
3. **Builtin-роли защищены**: `update_role`/`delete_role` поднимают `CannotModifyBuiltinRoleError` для ролей с `is_custom=False`; `delete_role` также запрещает удаление роли, у которой есть пользователи (`RoleHasUsersError`).
4. **Кастомные роли**: `create_role`/`update_role`/`delete_role` в `RBACService` (Admin API), доменные исключения — `RoleNotFoundError`, `PermissionNotFoundError`.
5. **Scope-providers (ограничение доступа к инстансам)**: поверх permissions существует второй слой — scope-таблицы `role_scope_providers` (+ source groups, credentials, sync groups, gitlab projects). `require_scope_permission(permission, resource_type, resource_id_param)` проверяет сначала permission, затем `RBACService.check_scope_access()`: admin (`None` = «все ресурсы») или `resource_id` ∈ effective scope (UNION scopes всех ролей пользователя). Для POST/PUT, создающих новый ресурс (path param отсутствует), scope-проверка пропускается.
6. **Frontend**: те же строки-permissions приходят из JWT/`/me/permissions` в Redux; `usePermissions()` даёт `hasPermission/hasAnyPermission/hasAllPermissions`, `PermissionGate` скрывает UI (props `permission` / `anyOf` / `allOf` / `fallback`).

### Consequences

* Good, because права меняются в рантайме (кастомные роли в Admin UI), без релиза
* Good, because гранулярность достаточно для UI-скрытия кнопок и API-проверок без рассинхрона: frontend и backend используют одинаковые строки-permissions
* Good, because JWT-кэш permissions: проверка обычно без DB round-trip
* Bad, because permissions в JWT протухают до refresh токена — добавление/снятие права применяется с задержкой (fallback на DB-lookup смягчает, но не отменяет)
* Bad, because строки-permissions в коде не типизированы полностью: `PermissionName` enum покрывает только 8 gitlab-project/component прав, остальные 50+ передаются inline строками — опечатка в строке компилируется и молча запрещает доступ
* Neutral, because scope-слой (5 таблиц + `check_scope_access`) — отдельная сущность от permissions: permission отвечает «можно ли действие с типом ресурса», scope — «какие инстансы видны»
* Non-goals: внешние движки авторизации (Casbin/OPA); attribute-based access control; иерархии ролей; удаление `plans/architecture/permissions.md` (он остаётся operational permissions index)

### Confirmation

* `make test-unit-backend TEST_ARGS="tests/unit/test_rbac_providers.py -v"` — зелёный: покрывает seed-матрицу ролей (admin/operator/viewer), отсутствие legacy-прав, scope-провайдеров (доступ к чужим private через scope), `providers_system:write` и `providers:read_all`.
* `make test-unit-backend TEST_ARGS="tests/unit/test_rbac_scope.py -v"` — зелёный: покрывает CRUD scope-таблиц, идемпотентность, `check_scope_access` (admin → все, иначе membership в effective scope).
* Fitness-критерий: новые endpoint'ы защищаются через `require_permission()` / `require_scope_permission()`, а не через `require_admin()`/`require_operator()`/`require_viewer()` — legacy role-dependencies остались ровно в одном месте (`app/api/health_check.py`), их количество не должно расти. Проверка на ревью: `grep -rn "require_admin\(\)\|require_operator\(\)\|require_viewer\(\)" backend/app/api` → только `health_check.py`.

## Pros and Cons of the Options

### Permission-based RBAC

Роли = наборы строковых permissions `resource:action`; проверка через `require_permission()` + scope-слой для инстансов.

* Good, because гранулярность покрывает реальные различия действий внутри одного ресурса
* Good, because рантайм-настройка ролей без деплоя; builtin-роли — просто предустановленные наборы
* Good, because единый формат строк для backend и frontend
* Bad, because протухание permissions в JWT до refresh
* Bad, because отсутствие типизации большинства строк (опечатки не ловятся компиляцией)

### Ролевая иерархия (fix-роли admin > operator > viewer)

Текущий `require_roles()` с проверкой имени роли.

* Good, because тривиальная реализация, уже работает
* Bad, because нет частичного доступа: нельзя «read везде, write только в Helm»
* Bad, because изменение матрицы ролей = релиз кода
* Bad, because не поддерживает scoping по инстансам ресурсов

### Per-endpoint роли

Каждый endpoint объявляет минимальную роль (по сути — то же, что иерархия, но с явной настройкой на endpoint).

* Good, because явная настройка доступа в месте использования
* Bad, because та же бинарность: роль либо есть, либо нет, между «operator» и «admin» ничего настроить нельзя
* Bad, because доступ настраивается правкой кода, а не данными; Admin UI управления доступом невозможен
* Bad, because дублирование матрицы доступа по всем endpoint'ам вместо централизованного списка в permissions

## More Information

* ADR опирается на [ADR-0003](0003-keycloak-oidc-sso-dual-mode.md) (аутентификация: Keycloak OIDC SSO + local users, dual mode) — permission'ы вшиваются в JWT, выпускаемый обоими режимами входа.
* Канонический operational-список прав: [`plans/architecture/permissions.md`](../../../plans/architecture/permissions.md) — обновлять при любом изменении прав (правило AGENTS.md). Спроектированные, но ещё не сидируемые права (`gitlab_projects:*`, `components:*`) — там же, раздел «Спроектированные права».
* История вопроса: `plans/features/auth-rbac.md` (удалён после принятия этого ADR — RBAC-разделы переехали сюда, SSO-разделы — в ADR-0003); operational-рецепты — в `AGENTS.md`.
* Доменные исключения RBAC: `backend/app/core/exceptions.py` (`RoleNotFoundError`, `CannotModifyBuiltinRoleError`, `RoleHasUsersError`, `PermissionNotFoundError`).
* Триггеры пересмотра: появление необходимости в иерархии ролей или наследовании permissions; права, зависящие от атрибутов ресурса (ABCD); взрывной рост числа permissions (>150) или массовые inline-строки вместо enum — тогда рассмотреть централизованный registry permissions в коде.
* Roadmap ADR: `.agents/plans/adr-roadmap.md` (one domain = one ADR).
