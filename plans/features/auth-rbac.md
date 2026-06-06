# Auth & RBAC Guide

Руководство по аутентификации и управлению доступом в BigBug.

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

- [`backend/app/core/security.py`](../../backend/app/core/security.py) — JWT, password hashing, dependencies
- [`backend/app/core/rbac.py`](../../backend/app/core/rbac.py) — роли и права доступа
- [`backend/app/core/secrets.py`](../../backend/app/core/secrets.py) — Fernet шифрование
- [`backend/app/api/auth.py`](../../backend/app/api/auth.py) — API endpoints
- [`backend/app/services/oidc.py`](../../backend/app/services/oidc.py) — OIDC интеграция
- [`frontend/src/store/authSlice.ts`](../../frontend/src/store/authSlice.ts) — Auth state
- [`frontend/src/services/keycloak.ts`](../../frontend/src/services/keycloak.ts) — Keycloak adapter
- [`frontend/src/hooks/useKeycloakAuth.ts`](../../frontend/src/hooks/useKeycloakAuth.ts) — Auth hook
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

```python
import bcrypt

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )
```

### JWT токены

```python
from jose import jwt
from datetime import datetime, timedelta

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

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

```python
# app/services/oidc.py
from authlib.integrations.httpx_client import AsyncOAuth2Client

class OIDCService:
    async def get_config(self, db: AsyncSession) -> OIDCConfig | None:
        """Get OIDC configuration from database"""
        ...
    
    async def verify_token(self, access_token: str) -> dict:
        """Verify Keycloak access token and return user info"""
        ...
    
    async def exchange_code(self, code: str, redirect_uri: str) -> dict:
        """Exchange authorization code for tokens"""
        ...
    
    async def sync_user_from_keycloak(
        self, db: AsyncSession, user_info: dict
    ) -> User:
        """Create or update user from Keycloak user info"""
        ...
```

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

### Dependencies

```python
# app/core/security.py
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    payload = verify_token(token)
    user = await get_user_by_email(db, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive user")
    return user

async def require_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """Require admin role"""
    if current_user.role.name != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

async def require_operator(
    current_user: User = Depends(get_current_user)
) -> User:
    """Require operator or admin role"""
    if current_user.role.name not in ("admin", "operator"):
        raise HTTPException(status_code=403, detail="Operator access required")
    return current_user
```

### Использование в роутерах

```python
@router.get("/mirrors", response_model=list[MirrorOut])
async def list_mirrors(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator)  # Требует operator+
):
    ...

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)  # Только admin
):
    ...
```

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

## Планируемый RBAC (Phase 1)

### Permission-based модель

Переход от role-based к permission-based:

```
resource:action
```

Примеры permissions:
- `mirrors:read` — просмотр зеркал
- `mirrors:write` — создание/изменение зеркал
- `mirrors:delete` — удаление зеркал
- `mirrors:sync` — запуск синхронизации
- `users:manage` — управление пользователями
- `settings:read` — просмотр настроек
- `settings:write` — изменение настроек

### Новые таблицы

```sql
-- Права доступа
CREATE TABLE permissions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,  -- "mirrors:read"
    description TEXT
);

-- Связь ролей и прав
CREATE TABLE role_permissions (
    role_id INTEGER REFERENCES roles(id),
    permission_id INTEGER REFERENCES permissions(id),
    PRIMARY KEY (role_id, permission_id)
);
```

### Предустановленные роли

| Роль | Permissions |
|------|-------------|
| `admin` | Все permissions |
| `operator` | read/write/sync для всех ресурсов, без users:manage |
| `viewer` | Только read permissions |

### Backend: require_permission()

```python
# app/core/rbac.py
def require_permission(permission: str):
    """Dependency factory for permission check"""
    async def check_permission(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> User:
        user_permissions = await get_user_permissions(db, current_user.id)
        if permission not in user_permissions:
            raise HTTPException(
                status_code=403,
                detail=f"Permission '{permission}' required"
            )
        return current_user
    return check_permission

# Использование
@router.post("/mirrors/{id}/sync")
async def sync_mirror(
    id: int,
    current_user: User = Depends(require_permission("mirrors:sync"))
):
    ...
```

### Frontend: usePermissions() hook

```typescript
// src/hooks/usePermissions.ts
export function usePermissions() {
  const user = useSelector((state: RootState) => state.auth.user);
  
  const hasPermission = (permission: string): boolean => {
    return user?.permissions?.includes(permission) ?? false;
  };
  
  const hasAnyPermission = (...permissions: string[]): boolean => {
    return permissions.some(p => hasPermission(p));
  };
  
  return { hasPermission, hasAnyPermission };
}

// Использование
function MirrorActions({ mirror }) {
  const { hasPermission } = usePermissions();
  
  return (
    <Box>
      {hasPermission('mirrors:sync') && (
        <Button onClick={handleSync}>Sync</Button>
      )}
      {hasPermission('mirrors:delete') && (
        <Button color="error" onClick={handleDelete}>Delete</Button>
      )}
    </Box>
  );
}
```

### Frontend: PermissionGate компонент

```typescript
// src/components/PermissionGate.tsx
interface PermissionGateProps {
  permission: string;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export const PermissionGate: React.FC<PermissionGateProps> = ({
  permission,
  children,
  fallback = null
}) => {
  const { hasPermission } = usePermissions();
  
  if (!hasPermission(permission)) {
    return <>{fallback}</>;
  }
  
  return <>{children}</>;
};

// Использование
<PermissionGate permission="users:manage">
  <AdminPanel />
</PermissionGate>
```

## Шифрование секретов

Для хранения токенов и credentials в БД используем Fernet:

```python
# app/core/secrets.py
from cryptography.fernet import Fernet

def get_fernet() -> Fernet:
    key = settings.FERNET_KEY.encode()
    return Fernet(key)

def encrypt_secret(value: str) -> str:
    """Encrypt sensitive value for storage"""
    f = get_fernet()
    return f.encrypt(value.encode()).decode()

def decrypt_secret(encrypted_value: str) -> str:
    """Decrypt stored sensitive value"""
    f = get_fernet()
    return f.decrypt(encrypted_value.encode()).decode()
```

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
