import asyncio

import bcrypt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.core.security import get_password_hash
from app.database import Base, get_db
from app.main import app
from app.models.permission import Permission, role_permissions
from app.models.role import Role, UserRole
from app.models.user import User

# Disable environment-dependent behaviour (rate limiting) for the whole test
# run. The app is imported above; rate_limit() checks this value lazily at
# request time, so setting it here is sufficient regardless of how pytest was
# invoked.
settings.environment = "test"

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def _fast_bcrypt():
    """Lower bcrypt cost factor for tests while keeping the real algorithm.

    Production uses rounds=12 (~250ms per hash); tests only need a valid,
    verifiable hash, so rounds=4 (~60x faster) is enough and still exercises
    the real bcrypt code path.
    """
    original_gensalt = bcrypt.gensalt

    def fast_gensalt(rounds=None, prefix=None):
        return original_gensalt(rounds=4, prefix=prefix)

    bcrypt.gensalt = fast_gensalt
    yield
    bcrypt.gensalt = original_gensalt


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Single engine for the whole session: the schema is created once.

    In-memory SQLite lives and dies with this engine, so no ``drop_all`` is
    needed. Per-test isolation is provided by ``db_transaction`` below.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_transaction(test_engine) -> AsyncConnection:
    """Wrap each test in an outer transaction that is rolled back afterwards.

    ``db_session`` and ``client`` join this transaction via SAVEPOINTs, so an
    endpoint's ``commit()`` becomes a savepoint release rather than a real
    commit. Rolling back the outer transaction restores an empty DB per test.

    Uses ``begin_nested()`` instead of ``begin()``: SQLite issues deferred
    BEGINs, which would leak committed savepoints past a plain ``rollback()``.
    A nested transaction forces a real BEGIN up front, making the rollback
    actually discard everything emitted by the test.
    """
    connection = await test_engine.connect()
    trans = await connection.begin_nested()
    yield connection
    await trans.rollback()
    await connection.close()


@pytest_asyncio.fixture
async def db_session(db_transaction: AsyncConnection):
    session_factory = async_sessionmaker(
        bind=db_transaction,
        join_transaction_mode="create_savepoint",
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_transaction: AsyncConnection):
    """HTTP client with a fresh DB session per request.

    Each FastAPI request gets its own AsyncSession so that ``commit()``
    inside one endpoint handler never interferes with the next request.
    """
    session_factory = async_sessionmaker(
        bind=db_transaction,
        join_transaction_mode="create_savepoint",
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


# Full set of permissions needed for test coverage (mirrors, pipelines, credentials,
# integrations, source_groups, sync_groups, roles, users, oidc, audit).
_ALL_PERMISSIONS = [
    # Mirroring
    "mirrors:read",
    "mirrors:write",
    "mirrors:delete",
    "mirrors:sync",
    "mirrors:import",
    "mirrors:integrity_check",
    "mirrors:manage_orphaned",
    # Source groups
    "source_groups:read",
    "source_groups:write",
    "source_groups:refresh",
    # Sync groups
    "sync_groups:read",
    "sync_groups:write",
    "sync_groups:delete",
    # Credentials (read for list/get; write for create/update/delete/test)
    "credentials:read",
    "credentials:write",
    "credentials:use",
    # Pipelines
    "pipelines:read",
    "pipelines:write",
    "pipelines:delete",
    # Gitlab projects (gitlab-project-management)
    "gitlab_projects:read",
    "gitlab_projects:write",
    "gitlab_projects:delete",
    "gitlab_projects:read_all",
    # Components (gitlab-project-management)
    "components:read",
    "components:write",
    "components:delete",
    "components:push",
    # Providers system (needed to attach projects to system providers)
    "providers_system:write",
    # Integrations
    "integrations:read",
    "integrations:write",
    # Docker / Helm (may be needed by other tests)
    "docker:read",
    "docker:write",
    "docker:delete",
    "docker:sync",
    "docker:index",
    "helm:read",
    "helm:write",
    "helm:delete",
    "helm:sync",
    "helm:index",
    # Gold / App images
    "gold_images:read",
    "gold_images:write",
    "gold_images:delete",
    "gold_images:build",
    "app_images:read",
    "app_images:write",
    "app_images:delete",
    "app_images:build",
    # Projects
    "projects:read",
    "projects:write",
    "projects:delete",
    # Users, Roles, System, OIDC, Audit
    "users:read",
    "users:write",
    "users:delete",
    "roles:read",
    "roles:write",
    "roles:delete",
    "system:config",
    "oidc:read",
    "oidc:write",
    "audit:read",
    # Reports
    "reports:read",
]


async def _seed_all_test_permissions(db: AsyncSession, role) -> None:
    """Insert all known permissions and assign them to *role*.

    Set-based: two SELECTs (existing permissions + existing role links) and one
    bulk INSERT for anything missing, instead of per-permission SELECT/flush.
    """
    existing = (await db.execute(select(Permission))).scalars().all()
    by_name: dict[str, Permission] = {p.name: p for p in existing}

    new_perms = [
        Permission(name=name, description=f"Auto-seeded: {name}")
        for name in _ALL_PERMISSIONS
        if name not in by_name
    ]
    if new_perms:
        db.add_all(new_perms)
        await db.flush()
        for p in new_perms:
            by_name[p.name] = p

    assigned = {
        row[0]
        for row in (
            await db.execute(
                select(role_permissions.c.permission_id).where(
                    role_permissions.c.role_id == role.id
                )
            )
        ).all()
    }
    missing = [
        {"role_id": role.id, "permission_id": by_name[name].id}
        for name in _ALL_PERMISSIONS
        if by_name[name].id not in assigned
    ]
    if missing:
        await db.execute(role_permissions.insert().values(missing))

    await db.commit()


@pytest_asyncio.fixture
async def admin_role(db_session: AsyncSession):
    """Get or create the admin role with all permissions seeded."""
    result = await db_session.execute(select(Role).where(Role.name == "admin"))
    role = result.scalar_one_or_none()
    if role is None:
        role = Role(name="admin", description="Administrator")
        db_session.add(role)
        await db_session.commit()
    await _seed_all_test_permissions(db_session, role)
    return role


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession, admin_role):
    """Get or create the admin user (idempotent across tests)."""
    result = await db_session.execute(select(User).where(User.username == "testadmin"))
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    user = User(
        username="testadmin",
        email="admin@test.com",
        hashed_password=get_password_hash("testpassword"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    db_session.add(UserRole(user_id=user.id, role_id=admin_role.id))
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def operator_role(db_session: AsyncSession):
    """Get or create the operator role (idempotent across tests)."""
    result = await db_session.execute(select(Role).where(Role.name == "operator"))
    role = result.scalar_one_or_none()
    if role is None:
        role = Role(name="operator", description="Operator")
        db_session.add(role)
        await db_session.commit()
    return role


@pytest_asyncio.fixture
async def operator_user(db_session: AsyncSession, operator_role):
    """Get or create the operator user (idempotent across tests)."""
    result = await db_session.execute(select(User).where(User.username == "testoperator"))
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    user = User(
        username="testoperator",
        email="operator@test.com",
        hashed_password=get_password_hash("testpassword"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    db_session.add(UserRole(user_id=user.id, role_id=operator_role.id))
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def admin_token(client, admin_user):
    """Get JWT token for admin user."""
    response = await client.post(
        "/api/auth/login",
        json={"username": "testadmin", "password": "testpassword"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest_asyncio.fixture
async def login_headers(admin_token):
    """Get Authorization headers for authenticated requests (admin user)."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest_asyncio.fixture
async def operator_token(client, operator_user):
    """Get JWT token for operator user."""
    response = await client.post(
        "/api/auth/login",
        json={"username": "testoperator", "password": "testpassword"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest_asyncio.fixture
async def viewer_role(db_session: AsyncSession):
    """Get or create the viewer role (idempotent across tests)."""
    from app.core.rbac import RoleName

    result = await db_session.execute(select(Role).where(Role.name == RoleName.VIEWER.value))
    role = result.scalar_one_or_none()
    if role is None:
        role = Role(name=RoleName.VIEWER.value, description="Viewer")
        db_session.add(role)
        await db_session.commit()
    return role


@pytest_asyncio.fixture
async def viewer_user(db_session: AsyncSession, viewer_role):
    """Get or create the viewer user (idempotent across tests)."""
    result = await db_session.execute(select(User).where(User.username == "testviewer"))
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    user = User(
        username="testviewer",
        email="viewer@test.com",
        hashed_password=get_password_hash("testpassword"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    db_session.add(UserRole(user_id=user.id, role_id=viewer_role.id))
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def viewer_token(client, viewer_user):
    """Get JWT token for viewer user."""
    response = await client.post(
        "/api/auth/login",
        json={"username": "testviewer", "password": "testpassword"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]
