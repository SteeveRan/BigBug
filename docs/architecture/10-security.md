# 10. Security

## Обзор

Безопасность BigBug строится на нескольких уровнях защиты: аутентификация, авторизация, шифрование данных, защита API и аудит действий.

## Модель угроз

| Угроза | Вектор | Митигация |
|--------|--------|-----------|
| Несанкционированный доступ | Перехват токена | JWT с коротким TTL, HTTPS |
| Утечка credentials интеграций | БД компрометация | Fernet шифрование at rest |
| CSRF атака | Браузер | SameSite cookies, CORS |
| Инъекция через webhook | Поддельный webhook | HMAC/token верификация |
| Privilege escalation | Обход RBAC | Permission check на каждом endpoint |
| Brute force | Перебор паролей | Rate limiting, bcrypt |

## Аутентификация

### JWT токены

```python
# app/core/security.py
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 час

def create_access_token(data: dict) -> str:
    payload = {
        **data,
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": datetime.utcnow(),
        "type": "access"
    }
    return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)
```

**Структура JWT payload:**
```json
{
  "sub": "1",
  "email": "admin@example.com",
  "roles": ["admin"],
  "permissions": ["users:read", "users:write", "..."],
  "exp": 1749254400,
  "iat": 1749250800,
  "type": "access"
}
```

### Хранение паролей

```python
# app/core/security.py
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
```

- Алгоритм: **bcrypt** с cost factor 12
- Соль: автоматически генерируется passlib
- Минимальная длина пароля: 8 символов

### OIDC верификация

```python
# app/services/oidc.py
async def verify_id_token(self, id_token: str, config: OIDCConfig) -> dict:
    """Верификация Keycloak id_token через JWKS."""
    jwks_client = PyJWKClient(config.jwks_uri)
    signing_key = jwks_client.get_signing_key_from_jwt(id_token)
    
    payload = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=config.client_id,
        issuer=config.provider_url
    )
    return payload
```

## Авторизация (RBAC)

### Permission check на каждом endpoint

```python
# app/core/rbac.py
def require_permission(permission: str):
    async def dependency(current_user: User = Depends(get_current_user)):
        user_permissions = await get_user_permissions(current_user)
        if permission not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required"
            )
        return current_user
    return dependency

# Использование в роутере:
@router.post("/users", dependencies=[Depends(require_permission("users:write"))])
async def create_user(...):
    ...
```

### Защита от privilege escalation

- Пользователь не может назначить себе роль выше своей
- Системные роли (admin, operator, viewer) нельзя удалить
- Только admin может управлять ролями

```python
async def assign_roles(
    current_user: User,
    target_user: User,
    role_names: list[str],
    db: AsyncSession
) -> None:
    # Только admin может назначать роли
    if "admin" not in current_user.roles:
        raise ForbiddenError("Only admin can assign roles")
    
    # Нельзя назначить роль, которой нет у текущего пользователя
    # (если не admin)
    ...
```

## Шифрование данных

### Credentials at rest

Все секреты интеграций шифруются через Fernet (симметричное шифрование AES-128-CBC):

```python
# app/core/secrets.py
from cryptography.fernet import Fernet

def get_fernet() -> Fernet:
    key = settings.encryption_key.encode()
    return Fernet(key)

def encrypt(value: str) -> str:
    f = get_fernet()
    return f.encrypt(value.encode()).decode()

def decrypt(value: str) -> str:
    f = get_fernet()
    return f.decrypt(value.encode()).decode()
```

**Текущая реализация:** [`backend/app/core/secrets.py`](../../backend/app/core/secrets.py)

### Ключи шифрования

- `ENCRYPTION_KEY` — Fernet ключ для шифрования credentials
- `SECRET_KEY` — ключ для подписи JWT
- Оба хранятся в `.env` файле, **никогда не коммитятся в git**

```bash
# Генерация Fernet ключа
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Генерация SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"
```

### Данные в транзите

- Все внешние соединения через **HTTPS/TLS**
- Верификация SSL сертификатов (настраивается per-instance через `verify_ssl`)
- Внутренние соединения (backend ↔ PostgreSQL, backend ↔ Redis) через Docker network

## Защита API

### Rate Limiting

```python
# app/main.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Применение к endpoint:
@router.post("/auth/login")
@limiter.limit("10/minute")
async def login(request: Request, ...):
    ...
```

### CORS

```python
# app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # Из .env
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

### Input Validation

FastAPI + Pydantic автоматически валидируют все входные данные:

```python
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r'^[a-zA-Z0-9_]+$')
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    roles: list[str] = Field(default=["viewer"])
```

## Webhook Security

### GitLab Webhook

```python
def _verify_gitlab_token(self, token: str, expected: str) -> bool:
    """Constant-time comparison для предотвращения timing attacks."""
    return hmac.compare_digest(token, expected)
```

### GitHub Webhook

```python
def _verify_github_signature(
    self, payload: bytes, signature: str, secret: str
) -> bool:
    """HMAC-SHA256 верификация."""
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

### Harbor Webhook

```python
def _verify_harbor_token(self, token: str, expected: str) -> bool:
    return hmac.compare_digest(token, expected)
```

## Аудит (Audit Log)

### Таблица audit_log

```sql
CREATE TABLE audit_log (
    id          BIGSERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action      VARCHAR(100) NOT NULL,  -- 'user.create', 'role.assign', etc.
    resource    VARCHAR(100),           -- 'user', 'role', 'mirror', etc.
    resource_id VARCHAR(50),            -- ID ресурса
    details     JSONB,                  -- Дополнительные данные
    ip_address  INET,
    user_agent  TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX idx_audit_log_action ON audit_log(action);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at DESC);
```

### Middleware для аудита

```python
# app/core/audit.py
async def log_action(
    user_id: int,
    action: str,
    resource: str,
    resource_id: str | None,
    details: dict | None,
    request: Request,
    db: AsyncSession
) -> None:
    log = AuditLog(
        user_id=user_id,
        action=action,
        resource=resource,
        resource_id=resource_id,
        details=details,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    db.add(log)
    await db.commit()

# Использование:
await log_action(
    user_id=current_user.id,
    action="user.create",
    resource="user",
    resource_id=str(new_user.id),
    details={"username": new_user.username, "roles": data.roles},
    request=request,
    db=db
)
```

### Аудируемые действия

| Действие | Описание |
|----------|----------|
| `user.create` | Создание пользователя |
| `user.update` | Обновление пользователя |
| `user.delete` | Удаление пользователя |
| `user.login` | Успешный вход |
| `user.login_failed` | Неудачная попытка входа |
| `role.create` | Создание роли |
| `role.assign` | Назначение роли пользователю |
| `integration.create` | Добавление интеграции |
| `integration.delete` | Удаление интеграции |
| `mirror.sync` | Запуск синхронизации зеркала |
| `image.build` | Запуск сборки образа |
| `oidc.config_update` | Изменение OIDC конфигурации |

## Переменные окружения

### Обязательные секреты

```bash
# .env (никогда не коммитить!)
SECRET_KEY=<32-byte hex string>
ENCRYPTION_KEY=<Fernet key>
DATABASE_URL=postgresql+asyncpg://user:password@localhost/bigbug
```

### Опциональные

```bash
# OIDC (если используется)
KEYCLOAK_URL=https://keycloak.example.com
KEYCLOAK_REALM=bigbug
KEYCLOAK_CLIENT_ID=bigbug
KEYCLOAK_CLIENT_SECRET=<secret>

# CORS
CORS_ORIGINS=["http://localhost:5173","https://bigbug.example.com"]

# Rate limiting
RATE_LIMIT_PER_MINUTE=100
```

### Пример `.env.example`

```bash
# Обязательные
SECRET_KEY=change_me_generate_with_secrets_token_hex_32
ENCRYPTION_KEY=change_me_generate_with_fernet_generate_key
DATABASE_URL=postgresql+asyncpg://bigbug:bigbug@localhost:5432/bigbug

# Опциональные
CORS_ORIGINS=["http://localhost:5173"]
```

**Текущий пример:** [`.env.example`](../../.env.example)

## Checklist безопасности

### При деплое

- [ ] Сгенерированы уникальные `SECRET_KEY` и `ENCRYPTION_KEY`
- [ ] HTTPS настроен на reverse proxy (nginx/traefik)
- [ ] PostgreSQL доступен только из Docker network
- [ ] Redis доступен только из Docker network
- [ ] `.env` файл не в git репозитории
- [ ] Настроен firewall (только 80/443 открыты наружу)

### При разработке

- [ ] Все новые endpoints имеют `require_permission()` dependency
- [ ] Все credentials сохраняются через `encrypt()`
- [ ] Webhook handlers верифицируют подпись
- [ ] Новые поля форм валидируются через Pydantic
- [ ] Тесты покрывают сценарии с недостаточными правами (403)
