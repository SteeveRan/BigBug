# Auth & RBAC Guide

Руководство по аутентификации и управлению доступом в BigBug.

> **Статус реализации:**
> - ✅ Local auth (login/refresh/me)
> - ✅ OIDC/Keycloak SSO
> - ✅ **RBAC Phase 1 — ЗАВЕРШЁН** (2026-06-06): permission-based модель, JWT-кэширование, Admin API, Frontend hooks

## Текущая реализация

### Аутентификация

BigBug поддерживает два режима аутентификации:

1. **Local auth** (по умолчанию) — email/password с JWT токенами
2. **OIDC/Keycloak SSO** (опционально) — через Keycloak 26

### Роли (текущие)

| Роль | Описание |
|------|----------|
| `admin` | Полный доступ, управление пользователями |
| `operator` | Создание/изменение ресурсов, запуск синхронизации |
| `viewer` | Только чтение |

### Ключевые файлы

**Backend:**
- [`backend/app/core/security.py`](../../backend/app/core/security.py) — JWT, password hashing
- [`backend/app/core/rbac.py`](../../backend/app/core/rbac.py) — `require_permission()`, `require_roles()`, `get_current_user`
- [`backend/app/core/secrets.py`](../../backend/app/core/secrets.py) — Fernet шифрование
- [`backend/app/api/auth.py`](../../backend/app/api/auth.py) — API endpoints (login, refresh, me, me/permissions, sso/config, oidc/exchange)
- [`backend/app/services/oidc.py`](../../backend/app/services/oidc.py) — OIDC интеграция
- [`backend/app/services/rbac_service.py`](../../backend/app/services/rbac_service.py) — ✅ RBAC business logic
- [`backend/app/schemas/rbac.py`](../../backend/app/schemas/rbac.py) — ✅ Pydantic схемы для RBAC

**Frontend:**
- [`frontend/src/store/authSlice.ts`](../../frontend/src/store/authSlice.ts) — Auth state
- [`frontend/src/services/keycloak.ts`](../../frontend/src/services/keycloak.ts) — Keycloak adapter
- [`frontend/src/hooks/useKeycloakAuth.ts`](../../frontend/src/hooks/useKeycloakAuth.ts) — Auth hook
- [`frontend/src/hooks/usePermissions.ts`](../../frontend/src/hooks/usePermissions.ts) — ✅ RBAC permissions hook
- [`frontend/src/components/PermissionGate.tsx`](../../frontend/src/components/PermissionGate.tsx) — ✅ Conditional rendering
- [`frontend/src/router/ProtectedRoute.tsx`](../../frontend/src/router/ProtectedRoute.tsx) — Route guard

## Local Authentication

### Регистрация / Создание пользователя

Только admin может создавать пользователей через Admin UI:

```
POST /api/admin/users
{
  "email": "user@example.com",
  "password": "secure-password",
  "role": "operator"
}
```

### Логин

```
POST /api/auth/login
{
  "email": "user@example.com",
  "password": "secure-password"
}

Response:
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "role": "operator"
  }
}
```

### Хеширование паролей

Используем **bcrypt** (НЕ passlib):

См. [`backend/app/core/security.py`](../../backend/app/core/security.py) — реализация `hash_password()` и `verify_password()` с использованием bcrypt.
### JWT токены

См. [`backend/app/core/security.py`](../../backend/app/core/security.py) — реализация `create_access_token()` и `verify_token()` с использованием JWT.
## OIDC / Keycloak SSO

### Конфигурация

SSO включается через переменные окружения:

```bash
OIDC_ENABLED=true
OIDC_ISSUER=http://localhost:8180/realms/bigbug
OIDC_CLIENT_ID=bigbug-backend
OIDC_CLIENT_SECRET=<from-keycloak>
```

### SSO Flow

```
1. Frontend → GET /api/auth/sso/config
   ← { enabled: true, auth_url: "http://keycloak/..." }

2. Frontend → Redirect to Keycloak login page

3. Keycloak → Redirect to /sso-callback?code=...

4. Frontend → POST /api/auth/sso/callback { code: "..." }
   ← { access_token: "...", user: {...} }
```

### OIDC Service

См. [`backend/app/services/oidc.py`](../../backend/app/services/oidc.py) — реализация `OIDCService` и его методов.
### Синхронизация ролей из Keycloak

Роли из Keycloak realm roles маппятся на роли BigBug:

```python
KEYCLOAK_ROLE_MAPPING = {
    "bigbug-admin": "admin",
    "bigbug-operator": "operator",
    "bigbug-viewer": "viewer",
}
```

## Backend: Защита endpoints

### Dependencies ✅ РЕАЛИЗОВАНО

См. [`backend/app/core/rbac.py`](../../backend/app/core/rbac.py) — реализация `get_current_user()`, `require_permission()`, `require_roles()` и алиасов (`require_admin`, `require_operator`, `require_viewer`).

## Frontend: Защита маршрутов

### ProtectedRoute

```typescript
// src/router/ProtectedRoute.tsx
import { Navigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { RootState } from '../store';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: 'admin' | 'operator' | 'viewer';
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  requiredRole
}) => {
  const { isAuthenticated, user } = useSelector((state: RootState) => state.auth);
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  if (requiredRole && !hasRole(user?.role, requiredRole)) {
    return <Navigate to="/dashboard" replace />;
  }
  
  return <>{children}</>;
};

function hasRole(userRole: string | undefined, required: string): boolean {
  const hierarchy = { admin: 3, operator: 2, viewer: 1 };
  return (hierarchy[userRole] || 0) >= (hierarchy[required] || 0);
}
```

### Использование в роутере

```typescript
// src/router/index.tsx
{
  path: '/admin',
  element: (
    <ProtectedRoute requiredRole="admin">
      <AdminPage />
    </ProtectedRoute>
  ),
},
{
  path: '/mirrors',
  element: (
    <ProtectedRoute requiredRole="operator">
      <MirrorsPage />
    </ProtectedRoute>
  ),
},
```

## RBAC Phase 1 ✅ ЗАВЕРШЁН

### Permission-based модель ✅ РЕАЛИЗОВАНО

32 permissions по паттерну `resource:action`, реализованы в миграции [`20260606_1932_bde12d699ca4_add_rbac_permissions.py`](../../backend/alembic/versions/20260606_1932_bde12d699ca4_add_rbac_permissions.py):

| Resource | Permissions |
|----------|-------------|
| `mirrors` | `read`, `write`, `delete`, `sync` |
| `projects` | `read`, `write`, `delete` |
| `helm` | `read`, `write`, `delete`, `sync`, `index` |
| `docker` | `read`, `write`, `delete`, `sync`, `index` |
| `gold_images` | `read`, `write`, `delete`, `build` |
| `app_images` | `read`, `write`, `delete`, `build` |
| `users` | `read`, `write`, `delete` |
| `roles` | `read`, `write`, `delete` |
| `system` | `config` |

### Предустановленные роли ✅ РЕАЛИЗОВАНО

| Роль | Permissions |
|------|-------------|
| `admin` | Все 32 permissions |
| `operator` | read + write + sync/index/build для ресурсов; без delete и admin-разделов |
| `viewer` | Только `*:read` permissions (6 permissions) |

Builtin-роли (`is_custom=False`) **защищены от модификации и удаления** через [`RBACService`](../../backend/app/services/rbac_service.py).

### JWT Payload с Permissions ✅ РЕАЛИЗОВАНО

При `login`, `refresh` и `oidc/exchange` в JWT payload вшиваются permissions:

```python
# app/api/auth.py (login, refresh, oidc/exchange)
rbac_service = RBACService(db)
permissions = await rbac_service.get_user_permissions(user.id)

token_data = {
    "sub": str(user.id),
    "username": user.username,
    "permissions": permissions,  # ["mirrors:read", "helm:write", ...]
}
return TokenResponse(
    access_token=create_access_token(token_data),
    refresh_token=create_refresh_token(token_data),
)
```

`get_current_user` читает permissions из payload и кэширует в `user._cached_permissions` — позволяет `require_permission()` работать без DB-запроса на каждый endpoint.

### RBACService ✅ РЕАЛИЗОВАНО

[`backend/app/services/rbac_service.py`](../../backend/app/services/rbac_service.py) — сервис бизнес-логики:

| Метод | Описание |
|-------|----------|
| `get_user_permissions(user_id)` | Список `"resource:action"` строк для пользователя (через user → roles → permissions) |
| `get_all_permissions()` | Все permissions в системе |
| `get_all_roles()` | Все роли с embedded permissions |
| `get_role_by_id(role_id)` | Одна роль с permissions |
| `create_role(name, description, permission_names, created_by_user_id)` | Создание кастомной роли |
| `update_role(role_id, name, description, permission_names)` | Обновление (только `is_custom=True`) |
| `delete_role(role_id)` | Удаление (только `is_custom=True`, без assigned пользователей) |
| `assign_permissions_to_role(role_id, permission_names)` | Замена permissions роли |

**Доменные исключения** (из [`backend/app/core/exceptions.py`](../../backend/app/core/exceptions.py)):
- `RoleNotFoundError`
- `CannotModifyBuiltinRoleError`
- `RoleHasUsersError`
- `PermissionNotFoundError`

### Frontend: usePermissions() ✅ РЕАЛИЗОВАНО

[`frontend/src/hooks/usePermissions.ts`](../../frontend/src/hooks/usePermissions.ts):

```typescript
export function usePermissions() {
  const permissions = useAppSelector(selectUserPermissions)  // string[]

  const hasPermission = useCallback(
    (permission: string): boolean => permissions.includes(permission),
    [permissions]
  )

  const hasAnyPermission = useCallback(
    (requiredPermissions: string[]): boolean =>
      requiredPermissions.some((p) => permissions.includes(p)),
    [permissions]
  )

  const hasAllPermissions = useCallback(
    (requiredPermissions: string[]): boolean =>
      requiredPermissions.every((p) => permissions.includes(p)),
    [permissions]
  )

  return { permissions, hasPermission, hasAnyPermission, hasAllPermissions }
}

// Использование:
function MirrorActions() {
  const { hasPermission } = usePermissions()
  return (
    <>
      {hasPermission('mirrors:sync') && <Button>Sync</Button>}
      {hasPermission('mirrors:delete') && <Button color="error">Delete</Button>}
    </>
  )
}
```

### Frontend: PermissionGate ✅ РЕАЛИЗОВАНО

[`frontend/src/components/PermissionGate.tsx`](../../frontend/src/components/PermissionGate.tsx):

```typescript
interface PermissionGateProps {
  permission?: string        // одиночная проверка
  anyOf?: string[]           // OR-логика
  allOf?: string[]           // AND-логика
  fallback?: ReactNode       // что показать если нет доступа
  children: ReactNode
}

// Использование:
<PermissionGate permission="users:write">
  <CreateUserButton />
</PermissionGate>

<PermissionGate anyOf={["helm:write", "helm:delete"]} fallback={<ReadOnlyView />}>
  <HelmActions />
</PermissionGate>

<PermissionGate allOf={["mirrors:read", "mirrors:write"]}>
  <MirrorManager />
</PermissionGate>
```

## Шифрование секретов

Для хранения токенов и credentials в БД используем Fernet:

См. [`backend/app/core/secrets.py`](../../backend/app/core/secrets.py) — реализация `encrypt_secret()` и `decrypt_secret()` с использованием Fernet.
Использование:

```python
# Сохранить токен
mirror.gitlab_token_encrypted = encrypt_secret(gitlab_token)
await db.commit()

# Получить токен
token = decrypt_secret(mirror.gitlab_token_encrypted)
```

## Troubleshooting

### JWT токен истёк

```
401 Unauthorized: Token has expired
```

Frontend должен перенаправить на `/login` и очистить auth state.

### Keycloak SSO не работает

```bash
# Проверить Keycloak
curl http://localhost:8180/realms/bigbug

# Проверить конфигурацию
curl http://localhost:8000/api/auth/sso/config

# Проверить OIDC_CLIENT_SECRET в .env
```

### Fernet ключ не совпадает

```
cryptography.fernet.InvalidToken
```

Если FERNET_KEY изменился, все зашифрованные данные в БД станут нечитаемыми. Нужно:
1. Расшифровать данные старым ключом
2. Зашифровать новым ключом
3. Обновить FERNET_KEY

## Полезные ссылки

- [`backend/app/core/security.py`](../../backend/app/core/security.py)
- [`backend/app/core/rbac.py`](../../backend/app/core/rbac.py)
- [`backend/app/services/oidc.py`](../../backend/app/services/oidc.py)
- [`docs/architecture/02-rbac-design.md`](../../docs/architecture/02-rbac-design.md) — детальный дизайн RBAC
- [`docs/architecture/03-authentication.md`](../../docs/architecture/03-authentication.md) — детальный дизайн Auth
