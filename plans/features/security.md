# Security Guide

Руководство по безопасности в BigBug.

## Обзор

BigBug использует несколько уровней защиты:

1. **Аутентификация** — JWT токены или OIDC/Keycloak SSO
2. **Авторизация** — Role-based access control (RBAC)
3. **Шифрование** — Fernet для credentials в БД
4. **Транспорт** — HTTPS в production
5. **Пароли** — bcrypt хеширование

## Хеширование паролей

Используем **bcrypt** (НЕ passlib — это legacy):

См. [`backend/app/core/security.py`](../../backend/app/core/security.py) — реализация `hash_password()` и `verify_password()` с использованием bcrypt.
**Параметры**:
- `rounds=12` — cost factor (2^12 = 4096 итераций)
- Соль генерируется автоматически и встроена в хеш
- Хеш имеет формат `$2b$12$<salt><hash>`

## JWT Токены

См. [`backend/app/core/security.py`](../../backend/app/core/security.py) — реализация `create_access_token()` и `verify_token()` с использованием JWT.
**Генерация SECRET_KEY**:
```bash
openssl rand -hex 32
```

## Fernet Шифрование

Для хранения токенов и credentials в БД используем симметричное шифрование Fernet:

См. [`backend/app/core/secrets.py`](../../backend/app/core/secrets.py) — реализация `encrypt_secret()` и `decrypt_secret()` с использованием Fernet.
**Генерация FERNET_KEY**:
```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

**Важно**: FERNET_KEY должен быть стабильным. Смена ключа требует перешифрования всех данных в БД.

### Что шифруется

| Поле | Таблица | Описание |
|------|---------|----------|
| `gitlab_token_encrypted` | `gitlab_mirrors` | GitLab API токен |
| `token_encrypted` | `gitlab_instances` | GitLab instance токен |
| `password_encrypted` | `harbor_instances` | Harbor пароль |
| `client_secret_encrypted` | `oidc_config` | OIDC client secret |

## OIDC / Keycloak SSO

### Конфигурация

```bash
OIDC_ENABLED=true
OIDC_ISSUER=http://localhost:8180/realms/bigbug
OIDC_CLIENT_ID=bigbug-backend
OIDC_CLIENT_SECRET=<from-keycloak>
```

### PKCE S256

Для frontend используем PKCE (Proof Key for Code Exchange) с S256:

```typescript
// Генерация code_verifier и code_challenge
const codeVerifier = generateRandomString(128);
const codeChallenge = base64URLEncode(sha256(codeVerifier));

// Authorization URL
const authUrl = `${keycloakUrl}/protocol/openid-connect/auth?
  client_id=${clientId}&
  response_type=code&
  redirect_uri=${redirectUri}&
  code_challenge=${codeChallenge}&
  code_challenge_method=S256`;
```

### Token Verification

См. [`backend/app/services/oidc.py`](../../backend/app/services/oidc.py) — реализация `OIDCService` и `verify_token()` метода.
## API Security

### OAuth2 Bearer Token

См. [`backend/app/core/security.py`](../../backend/app/core/security.py) — реализация `get_current_user()` с использованием OAuth2PasswordBearer.
### Rate Limiting ✅ РЕАЛИЗОВАНО

Используется `fastapi-limiter` + `pyrate_limiter` в [`backend/app/core/rate_limit.py`](../../backend/app/core/rate_limit.py).

### CORS Configuration

```python
# app/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,  # ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

## Input Validation

Все входящие данные валидируются через Pydantic:

```python
from pydantic import BaseModel, EmailStr, Field, validator

class UserCreate(BaseModel):
    email: EmailStr                      # Валидация email формата
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(pattern="^(admin|operator|viewer)$")
    
    @validator('password')
    def password_strength(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain uppercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain digit')
        return v
```

## Secrets Management

### Переменные окружения

Все секреты через переменные окружения, никогда в коде:

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SECRET_KEY: str                      # JWT signing key
    FERNET_KEY: str                      # Encryption key
    DATABASE_URL: str                    # DB connection string
    OIDC_CLIENT_SECRET: str | None = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
```

### .env файл

```bash
# .env (в .gitignore!)
SECRET_KEY=<openssl rand -hex 32>
FERNET_KEY=<python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
DATABASE_URL=postgresql+asyncpg://bigbug:bigbug@localhost:5432/bigbug
```

**Никогда не коммитить `.env` в Git!**

## Webhook Security

### Верификация GitLab webhook

```python
import hmac
import hashlib

def verify_gitlab_webhook(
    payload: bytes,
    signature: str,
    secret: str
) -> bool:
    """Verify GitLab webhook signature"""
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(f"sha256={expected}", signature)

# В endpoint
@router.post("/webhooks/gitlab")
async def gitlab_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    token = request.headers.get("X-Gitlab-Token")
    if token != settings.GITLAB_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook token")
    ...
```

## Database Security

### Параметризованные запросы

SQLAlchemy автоматически параметризует запросы, предотвращая SQL injection:

```python
# Безопасно — параметризованный запрос
result = await db.execute(
    select(User).where(User.email == email)  # email экранируется
)

# НЕ делать так — SQL injection!
result = await db.execute(
    text(f"SELECT * FROM users WHERE email = '{email}'")  # ОПАСНО!
)

# Если нужен raw SQL — использовать параметры
result = await db.execute(
    text("SELECT * FROM users WHERE email = :email"),
    {"email": email}  # Безопасно
)
```

### Минимальные привилегии БД

```sql
-- Создать пользователя с минимальными правами
CREATE USER bigbug WITH PASSWORD 'bigbug';
GRANT CONNECT ON DATABASE bigbug TO bigbug;
GRANT USAGE ON SCHEMA public TO bigbug;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO bigbug;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO bigbug;
```

## Production Security Checklist

- [ ] `SECRET_KEY` — случайный 256-bit ключ
- [ ] `FERNET_KEY` — случайный Fernet ключ
- [ ] HTTPS включён (TLS 1.2+)
- [ ] CORS настроен только для нужных origins
- [ ] Rate limiting на auth endpoints
- [ ] Webhook secrets настроены
- [ ] `.env` не в Git
- [ ] Пароли в БД — bcrypt хеши
- [ ] Credentials в БД — Fernet зашифрованы
- [ ] PostgreSQL — минимальные привилегии
- [ ] Docker — non-root пользователь
- [ ] Зависимости обновлены (нет CVE)

## Troubleshooting

### JWT токен не валидируется

```
401 Unauthorized: Invalid or expired token
```

Проверить:
1. `SECRET_KEY` одинаковый при создании и верификации
2. Токен не истёк (30 минут по умолчанию)
3. Токен передаётся в заголовке: `Authorization: Bearer <token>`

### Fernet расшифровка не работает

```
cryptography.fernet.InvalidToken
```

Причины:
1. `FERNET_KEY` изменился
2. Данные повреждены
3. Данные зашифрованы другим ключом

### bcrypt слишком медленный

Уменьшить cost factor (не рекомендуется для production):
```python
bcrypt.gensalt(rounds=10)  # Вместо 12
```

## Полезные ссылки

- [`backend/app/core/security.py`](../../backend/app/core/security.py)
- [`backend/app/core/secrets.py`](../../backend/app/core/secrets.py)
- [`backend/app/core/rbac.py`](../../backend/app/core/rbac.py)
- [`docs/architecture/10-security.md`](../../docs/architecture/10-security.md) — детальный дизайн безопасности
- [bcrypt Documentation](https://pypi.org/project/bcrypt/)
- [cryptography Fernet](https://cryptography.io/en/latest/fernet/)
- [OWASP Authentication Cheatsheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
