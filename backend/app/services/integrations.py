"""
@file integrations.py
@description Business logic for managing multiple integration instances
             (GitLab, Harbor, GitHub). Handles CRUD, encryption/decryption of
             secrets at rest, connection testing, and default-instance
             resolution for service consumers.
@dependencies app.core.secrets (encrypt_secret/decrypt_secret),
               app.core.exceptions (domain exceptions),
               httpx (connection testing)
@relatedFiles ../models/gitlab_instance.py, ../models/harbor_instance.py,
               ../models/github_instance.py, ../schemas/integrations.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    NotFoundError,
)
from app.core.secrets import decrypt_secret, encrypt_secret
from app.models.docker_registry_instance import DockerRegistryInstance
from app.models.github_instance import GithubInstance
from app.models.gitlab_instance import GitlabInstance
from app.models.harbor_instance import HarborInstance
from app.models.helm_repository_instance import HelmRepositoryInstance

# ---------------------------------------------------------------------------
# Status flag constants (unified across the platform)
# ---------------------------------------------------------------------------
STATUS_OK = 0
STATUS_FAILED = 1
STATUS_WARNING = 2
STATUS_IN_PROGRESS = 3
STATUS_PENDING = 4


def _status_text(flag: int) -> str:
    """Map a status flag integer to its human-readable label."""
    return {0: "OK", 1: "Failed", 2: "Warning", 3: "In Progress", 4: "Pending"}.get(flag, "Unknown")


# ===================================================================
# Default-instance resolution helpers
# ===================================================================


async def get_default_gitlab_instance(db: AsyncSession) -> GitlabInstance | None:
    """Return the default GitLab instance: prefer is_default=True,
    fallback to first active by id ASC."""
    result = await db.execute(
        select(GitlabInstance)
        .where(GitlabInstance.is_active.is_(True), GitlabInstance.is_default.is_(True))
        .order_by(GitlabInstance.id.asc())
        .limit(1)
    )
    instance = result.scalar_one_or_none()
    if instance is not None:
        return instance
    # Fallback: first active by id
    result = await db.execute(
        select(GitlabInstance)
        .where(GitlabInstance.is_active.is_(True))
        .order_by(GitlabInstance.id.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_default_github_instance(db: AsyncSession) -> GithubInstance | None:
    """Return the default GitHub instance: prefer is_default=True,
    fallback to first active by id ASC."""
    result = await db.execute(
        select(GithubInstance)
        .where(GithubInstance.is_active.is_(True), GithubInstance.is_default.is_(True))
        .order_by(GithubInstance.id.asc())
        .limit(1)
    )
    instance = result.scalar_one_or_none()
    if instance is not None:
        return instance
    # Fallback: first active by id
    result = await db.execute(
        select(GithubInstance)
        .where(GithubInstance.is_active.is_(True))
        .order_by(GithubInstance.id.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_default_harbor_instance(db: AsyncSession) -> HarborInstance | None:
    """Return the default Harbor instance: prefer is_default=True,
    fallback to first active by id ASC."""
    result = await db.execute(
        select(HarborInstance)
        .where(HarborInstance.is_active.is_(True), HarborInstance.is_default.is_(True))
        .order_by(HarborInstance.id.asc())
        .limit(1)
    )
    instance = result.scalar_one_or_none()
    if instance is not None:
        return instance
    # Fallback: first active by id
    result = await db.execute(
        select(HarborInstance)
        .where(HarborInstance.is_active.is_(True))
        .order_by(HarborInstance.id.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_default_docker_registry_instance(
    db: AsyncSession,
) -> DockerRegistryInstance | None:
    """Return the default Docker Registry instance: prefer is_default=True,
    fallback to first active by id ASC."""
    result = await db.execute(
        select(DockerRegistryInstance)
        .where(
            DockerRegistryInstance.is_active.is_(True),
            DockerRegistryInstance.is_default.is_(True),
        )
        .order_by(DockerRegistryInstance.id.asc())
        .limit(1)
    )
    instance = result.scalar_one_or_none()
    if instance is not None:
        return instance
    # Fallback: first active by id
    result = await db.execute(
        select(DockerRegistryInstance)
        .where(DockerRegistryInstance.is_active.is_(True))
        .order_by(DockerRegistryInstance.id.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_default_helm_repository_instance(
    db: AsyncSession,
) -> HelmRepositoryInstance | None:
    """Return the default Helm Repository instance: prefer is_default=True,
    fallback to first active by id ASC."""
    result = await db.execute(
        select(HelmRepositoryInstance)
        .where(
            HelmRepositoryInstance.is_active.is_(True),
            HelmRepositoryInstance.is_default.is_(True),
        )
        .order_by(HelmRepositoryInstance.id.asc())
        .limit(1)
    )
    instance = result.scalar_one_or_none()
    if instance is not None:
        return instance
    # Fallback: first active by id
    result = await db.execute(
        select(HelmRepositoryInstance)
        .where(HelmRepositoryInstance.is_active.is_(True))
        .order_by(HelmRepositoryInstance.id.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


# ===================================================================
# Generic helpers
# ===================================================================


async def _check_unique_name(
    db: AsyncSession,
    model_cls: type,
    name: str,
    exclude_id: int | None = None,
) -> None:
    """
    Verify that *name* is unique within *model_cls*. Raises
    ``ConflictError`` if a different record already uses the name.
    """
    stmt = select(model_cls).where(model_cls.name == name)
    if exclude_id is not None:
        stmt = stmt.where(model_cls.id != exclude_id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is not None:
        raise ConflictError(f"Integration instance with name '{name}' already exists")


async def _get_or_404(
    db: AsyncSession,
    model_cls: type,
    instance_id: int,
    label: str,
) -> Any:
    """Fetch a single instance by id or raise ``NotFoundError``."""
    result = await db.execute(select(model_cls).where(model_cls.id == instance_id))
    instance = result.scalar_one_or_none()
    if instance is None:
        raise NotFoundError(f"{label} with id={instance_id} not found")
    return instance


# ===================================================================
# GitLab Instances
# ===================================================================


class GitlabInstanceService:
    """CRUD and connection testing for :class:`GitlabInstance`."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── CRUD ──────────────────────────────────────────────────────────

    async def list_instances(self) -> list[GitlabInstance]:
        result = await self.db.execute(select(GitlabInstance).order_by(GitlabInstance.name))
        return list(result.scalars().all())

    async def get_instance(self, instance_id: int) -> GitlabInstance:
        return await _get_or_404(self.db, GitlabInstance, instance_id, "GitLab instance")

    async def create_instance(
        self,
        name: str,
        url: str,
        token: str | None,
        is_active: bool = True,
        verify_ssl: bool = True,
        is_default: bool = False,
        default_group_id: int | None = None,
    ) -> GitlabInstance:
        await _check_unique_name(self.db, GitlabInstance, name)

        instance = GitlabInstance(
            name=name,
            url=url.rstrip("/"),
            token=encrypt_secret(token),
            is_active=is_active,
            verify_ssl=verify_ssl,
            is_default=is_default,
            default_group_id=default_group_id,
            status_flag=STATUS_PENDING,
            status_text=_status_text(STATUS_PENDING),
        )
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def update_instance(
        self,
        instance_id: int,
        name: str | None = None,
        url: str | None = None,
        token: str | None = None,
        is_active: bool | None = None,
        verify_ssl: bool | None = None,
        is_default: bool | None = None,
        default_group_id: int | None = None,
    ) -> GitlabInstance:
        instance = await self.get_instance(instance_id)

        if name is not None:
            await _check_unique_name(self.db, GitlabInstance, name, exclude_id=instance_id)
            instance.name = name
        if url is not None:
            instance.url = url.rstrip("/")
        if token is not None:
            instance.token = encrypt_secret(token) if token else None
        if is_active is not None:
            instance.is_active = is_active
        if verify_ssl is not None:
            instance.verify_ssl = verify_ssl
        if is_default is not None:
            instance.is_default = is_default
        if default_group_id is not None:
            instance.default_group_id = default_group_id

        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def delete_instance(self, instance_id: int) -> None:
        instance = await self.get_instance(instance_id)
        await self.db.delete(instance)
        await self.db.commit()

    # ── Connection test ───────────────────────────────────────────────

    async def test_connection(self, instance_id: int) -> dict[str, Any]:
        """
        Verify connectivity to a GitLab instance by calling ``GET /api/v4/version``.
        Updates the instance's status_flag, status_text and last_checked_at accordingly.
        """
        instance = await self.get_instance(instance_id)

        token = decrypt_secret(instance.token)
        headers: dict[str, str] = {"User-Agent": "BigBug/1.0"}
        if token:
            headers["PRIVATE-TOKEN"] = token

        instance.last_checked_at = datetime.now(UTC)

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{instance.url}/api/v4/version", headers=headers)
                if resp.is_success:
                    version = resp.json().get("version", "unknown")
                    instance.status_flag = STATUS_OK
                    instance.status_text = f"OK — GitLab {version}"
                    await self.db.commit()
                    return {
                        "success": True,
                        "message": f"Connected — GitLab {version}",
                        "status_code": resp.status_code,
                    }
                else:
                    instance.status_flag = STATUS_FAILED
                    instance.status_text = f"HTTP {resp.status_code}"
                    await self.db.commit()
                    return {
                        "success": False,
                        "message": f"GitLab returned HTTP {resp.status_code}",
                        "status_code": resp.status_code,
                    }
        except httpx.RequestError as exc:
            instance.status_flag = STATUS_FAILED
            instance.status_text = f"Connection error: {exc!r}"[:255]
            await self.db.commit()
            return {
                "success": False,
                "message": f"Could not reach {instance.url}: {exc}",
                "status_code": None,
            }


# ===================================================================
# Harbor Instances
# ===================================================================


class HarborInstanceService:
    """CRUD and connection testing for :class:`HarborInstance`."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── CRUD ──────────────────────────────────────────────────────────

    async def list_instances(self) -> list[HarborInstance]:
        result = await self.db.execute(select(HarborInstance).order_by(HarborInstance.name))
        return list(result.scalars().all())

    async def get_instance(self, instance_id: int) -> HarborInstance:
        return await _get_or_404(self.db, HarborInstance, instance_id, "Harbor instance")

    async def create_instance(
        self,
        name: str,
        url: str,
        username: str,
        password: str | None,
        is_active: bool = True,
        verify_ssl: bool = True,
        is_default: bool = False,
        default_project: str | None = None,
    ) -> HarborInstance:
        await _check_unique_name(self.db, HarborInstance, name)

        instance = HarborInstance(
            name=name,
            url=url.rstrip("/"),
            username=username,
            password=encrypt_secret(password),
            is_active=is_active,
            verify_ssl=verify_ssl,
            is_default=is_default,
            default_project=default_project,
            status_flag=STATUS_PENDING,
            status_text=_status_text(STATUS_PENDING),
        )
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def update_instance(
        self,
        instance_id: int,
        name: str | None = None,
        url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        is_active: bool | None = None,
        verify_ssl: bool | None = None,
        is_default: bool | None = None,
        default_project: str | None = None,
    ) -> HarborInstance:
        instance = await self.get_instance(instance_id)

        if name is not None:
            await _check_unique_name(self.db, HarborInstance, name, exclude_id=instance_id)
            instance.name = name
        if url is not None:
            instance.url = url.rstrip("/")
        if username is not None:
            instance.username = username
        if password is not None:
            instance.password = encrypt_secret(password) if password else None
        if is_active is not None:
            instance.is_active = is_active
        if verify_ssl is not None:
            instance.verify_ssl = verify_ssl
        if is_default is not None:
            instance.is_default = is_default
        if default_project is not None:
            instance.default_project = default_project

        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def delete_instance(self, instance_id: int) -> None:
        instance = await self.get_instance(instance_id)
        await self.db.delete(instance)
        await self.db.commit()

    # ── Connection test ───────────────────────────────────────────────

    async def test_connection(self, instance_id: int) -> dict[str, Any]:
        """
        Verify connectivity to a Harbor instance by calling ``GET /api/v2.0/ping``.
        Updates the instance's status_flag, status_text and last_checked_at accordingly.
        """
        instance = await self.get_instance(instance_id)

        password = decrypt_secret(instance.password)
        auth: tuple[str, str] | None = None
        if instance.username and password:
            auth = (instance.username, password)

        instance.last_checked_at = datetime.now(UTC)

        try:
            async with httpx.AsyncClient(timeout=15.0, auth=auth) as client:
                resp = await client.get(f"{instance.url}/api/v2.0/ping")
                if resp.is_success:
                    instance.status_flag = STATUS_OK
                    instance.status_text = "OK — Harbor reachable"
                    await self.db.commit()
                    return {
                        "success": True,
                        "message": "Connected — Harbor reachable",
                        "status_code": resp.status_code,
                    }
                else:
                    instance.status_flag = STATUS_FAILED
                    instance.status_text = f"HTTP {resp.status_code}"
                    await self.db.commit()
                    return {
                        "success": False,
                        "message": f"Harbor returned HTTP {resp.status_code}",
                        "status_code": resp.status_code,
                    }
        except httpx.RequestError as exc:
            instance.status_flag = STATUS_FAILED
            instance.status_text = f"Connection error: {exc!r}"[:255]
            await self.db.commit()
            return {
                "success": False,
                "message": f"Could not reach {instance.url}: {exc}",
                "status_code": None,
            }


# ===================================================================
# GitHub Instances
# ===================================================================


class GithubInstanceService:
    """CRUD and connection testing for :class:`GithubInstance`."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── CRUD ──────────────────────────────────────────────────────────

    async def list_instances(self) -> list[GithubInstance]:
        result = await self.db.execute(select(GithubInstance).order_by(GithubInstance.name))
        return list(result.scalars().all())

    async def get_instance(self, instance_id: int) -> GithubInstance:
        return await _get_or_404(self.db, GithubInstance, instance_id, "GitHub instance")

    async def create_instance(
        self,
        name: str,
        token: str | None,
        is_active: bool = True,
        is_default: bool = False,
    ) -> GithubInstance:
        await _check_unique_name(self.db, GithubInstance, name)

        instance = GithubInstance(
            name=name,
            token=encrypt_secret(token),
            is_active=is_active,
            is_default=is_default,
            status_flag=STATUS_PENDING,
            status_text=_status_text(STATUS_PENDING),
        )
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def update_instance(
        self,
        instance_id: int,
        name: str | None = None,
        token: str | None = None,
        is_active: bool | None = None,
        is_default: bool | None = None,
    ) -> GithubInstance:
        instance = await self.get_instance(instance_id)

        if name is not None:
            await _check_unique_name(self.db, GithubInstance, name, exclude_id=instance_id)
            instance.name = name
        if token is not None:
            instance.token = encrypt_secret(token) if token else None
        if is_active is not None:
            instance.is_active = is_active
        if is_default is not None:
            instance.is_default = is_default

        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def delete_instance(self, instance_id: int) -> None:
        instance = await self.get_instance(instance_id)
        await self.db.delete(instance)
        await self.db.commit()

    # ── Connection test ───────────────────────────────────────────────

    async def test_connection(self, instance_id: int) -> dict[str, Any]:
        """
        Verify connectivity to GitHub by calling ``GET /user`` (requires token).
        Updates the instance's status_flag, status_text and last_checked_at accordingly.
        """
        instance = await self.get_instance(instance_id)

        token = decrypt_secret(instance.token)
        headers: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "BigBug/1.0",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        instance.last_checked_at = datetime.now(UTC)

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get("https://api.github.com/user", headers=headers)
                if resp.is_success:
                    login = resp.json().get("login", "unknown")
                    instance.status_flag = STATUS_OK
                    instance.status_text = f"OK — authenticated as {login}"
                    await self.db.commit()
                    return {
                        "success": True,
                        "message": f"Connected — authenticated as {login}",
                        "status_code": resp.status_code,
                    }
                else:
                    instance.status_flag = STATUS_FAILED
                    instance.status_text = f"HTTP {resp.status_code}"
                    await self.db.commit()
                    return {
                        "success": False,
                        "message": f"GitHub returned HTTP {resp.status_code}",
                        "status_code": resp.status_code,
                    }
        except httpx.RequestError as exc:
            instance.status_flag = STATUS_FAILED
            instance.status_text = f"Connection error: {exc!r}"[:255]
            await self.db.commit()
            return {
                "success": False,
                "message": f"Could not reach api.github.com: {exc}",
                "status_code": None,
            }


# ===================================================================
# Docker Registry Instances
# ===================================================================


class DockerRegistryInstanceService:
    """CRUD and connection testing for :class:`DockerRegistryInstance`."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── CRUD ──────────────────────────────────────────────────────────

    async def list_instances(self) -> list[DockerRegistryInstance]:
        result = await self.db.execute(
            select(DockerRegistryInstance).order_by(DockerRegistryInstance.name)
        )
        return list(result.scalars().all())

    async def get_instance(self, instance_id: int) -> DockerRegistryInstance:
        return await _get_or_404(
            self.db, DockerRegistryInstance, instance_id, "Docker Registry instance"
        )

    async def create_instance(
        self,
        name: str,
        url: str,
        username: str | None,
        password: str | None,
        is_active: bool = True,
        verify_ssl: bool = True,
        is_default: bool = False,
        registry_type: str = "external",
        registry_provider: str = "generic",
        priority: int = 0,
    ) -> DockerRegistryInstance:
        await _check_unique_name(self.db, DockerRegistryInstance, name)

        instance = DockerRegistryInstance(
            name=name,
            url=url.rstrip("/"),
            username=username,
            password=encrypt_secret(password),
            is_active=is_active,
            verify_ssl=verify_ssl,
            is_default=is_default,
            registry_type=registry_type,  # type: ignore[call-arg]
            registry_provider=registry_provider,  # type: ignore[call-arg]
            priority=priority,  # type: ignore[call-arg]
            status_flag=STATUS_PENDING,
            status_text=_status_text(STATUS_PENDING),
        )
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def update_instance(
        self,
        instance_id: int,
        name: str | None = None,
        url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        is_active: bool | None = None,
        verify_ssl: bool | None = None,
        is_default: bool | None = None,
        registry_type: str | None = None,
        registry_provider: str | None = None,
        priority: int | None = None,
    ) -> DockerRegistryInstance:
        instance = await self.get_instance(instance_id)

        if name is not None:
            await _check_unique_name(self.db, DockerRegistryInstance, name, exclude_id=instance_id)
            instance.name = name
        if url is not None:
            instance.url = url.rstrip("/")
        if username is not None:
            instance.username = username
        if password is not None:
            instance.password = encrypt_secret(password) if password else None
        if is_active is not None:
            instance.is_active = is_active
        if verify_ssl is not None:
            instance.verify_ssl = verify_ssl
        if is_default is not None:
            instance.is_default = is_default
        if registry_type is not None:
            instance.registry_type = registry_type  # type: ignore[assignment]
        if registry_provider is not None:
            instance.registry_provider = registry_provider  # type: ignore[assignment]
        if priority is not None:
            instance.priority = priority  # type: ignore[assignment]

        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def delete_instance(self, instance_id: int) -> None:
        instance = await self.get_instance(instance_id)
        await self.db.delete(instance)
        await self.db.commit()

    # ── Connection test ───────────────────────────────────────────────

    async def test_connection(self, instance_id: int) -> dict[str, Any]:
        """
        Verify connectivity to a Docker Registry by calling
        ``GET {url}/v2/`` (Docker Registry API v2 base check).
        Updates status_flag, status_text and last_checked_at.
        """
        instance = await self.get_instance(instance_id)

        password = decrypt_secret(instance.password)
        auth: tuple[str, str] | None = None
        if instance.username and password:
            auth = (instance.username, password)

        instance.last_checked_at = datetime.now(UTC)

        try:
            async with httpx.AsyncClient(timeout=15.0, auth=auth) as client:
                resp = await client.get(f"{instance.url}/v2/")
                if resp.is_success:
                    instance.status_flag = STATUS_OK
                    instance.status_text = "OK — Docker Registry reachable"
                    await self.db.commit()
                    return {
                        "success": True,
                        "message": "Connected — Docker Registry reachable",
                        "status_code": resp.status_code,
                    }
                elif resp.status_code == 401:
                    instance.status_flag = STATUS_FAILED
                    instance.status_text = "HTTP 401 — authentication required"
                    await self.db.commit()
                    return {
                        "success": False,
                        "message": "Docker Registry requires authentication (HTTP 401)",
                        "status_code": resp.status_code,
                    }
                else:
                    instance.status_flag = STATUS_FAILED
                    instance.status_text = f"HTTP {resp.status_code}"
                    await self.db.commit()
                    return {
                        "success": False,
                        "message": f"Docker Registry returned HTTP {resp.status_code}",
                        "status_code": resp.status_code,
                    }
        except httpx.RequestError as exc:
            instance.status_flag = STATUS_FAILED
            instance.status_text = f"Connection error: {exc!r}"[:255]
            await self.db.commit()
            return {
                "success": False,
                "message": f"Could not reach {instance.url}: {exc}",
                "status_code": None,
            }

    # ── Registry matching ──────────────────────────────────────────────

    async def find_matching_registry(
        self,
        registry_host: str,
        provider: str | None = None,
    ) -> DockerRegistryInstance | None:
        """
        Find the best matching DockerRegistryInstance for a given registry
        host (e.g. 'registry-1.docker.io') and optional provider.
        Prioritizes exact URL match, then provider match, then default.
        """
        registries = await self.list_instances()
        active = [r for r in registries if r.is_active]

        if not active:
            return None

        # 1. Exact URL match (contains the host)
        for r in active:
            if registry_host in r.url:
                return r

        # 2. Provider match
        if provider:
            for r in active:
                if r.registry_provider == provider:
                    return r

        # 3. Default by priority (highest first)
        active_sorted = sorted(
            [r for r in active if r.registry_type == "external"],
            key=lambda r: (-r.priority, -int(r.is_default), r.name),
        )
        if active_sorted:
            return active_sorted[0]

        return None

    async def get_compatible_registries(
        self,
        registry_host: str,
        provider: str | None = None,
    ) -> list[DockerRegistryInstance]:
        """Return all active registries that could serve the given host/provider."""
        registries = await self.list_instances()
        active = [r for r in registries if r.is_active]
        if not active:
            return []

        # Filter by host match or provider match
        compatible = []
        for r in active:
            if registry_host in r.url or provider and r.registry_provider == provider:
                compatible.append(r)

        if not compatible:
            # Return all active external registries as fallback
            compatible = [r for r in active if r.registry_type == "external"]

        return sorted(compatible, key=lambda r: (-r.priority, r.name))


# ===================================================================
# Helm Repository Instances
# ===================================================================


class HelmRepositoryInstanceService:
    """CRUD and connection testing for :class:`HelmRepositoryInstance`."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── CRUD ──────────────────────────────────────────────────────────

    async def list_instances(self) -> list[HelmRepositoryInstance]:
        result = await self.db.execute(
            select(HelmRepositoryInstance).order_by(HelmRepositoryInstance.name)
        )
        return list(result.scalars().all())

    async def get_instance(self, instance_id: int) -> HelmRepositoryInstance:
        return await _get_or_404(
            self.db, HelmRepositoryInstance, instance_id, "Helm Repository instance"
        )

    async def create_instance(
        self,
        name: str,
        url: str,
        username: str | None,
        password: str | None,
        is_active: bool = True,
        verify_ssl: bool = True,
        is_default: bool = False,
    ) -> HelmRepositoryInstance:
        await _check_unique_name(self.db, HelmRepositoryInstance, name)

        instance = HelmRepositoryInstance(
            name=name,
            url=url.rstrip("/"),
            username=username,
            password=encrypt_secret(password),
            is_active=is_active,
            verify_ssl=verify_ssl,
            is_default=is_default,
            status_flag=STATUS_PENDING,
            status_text=_status_text(STATUS_PENDING),
        )
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def update_instance(
        self,
        instance_id: int,
        name: str | None = None,
        url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        is_active: bool | None = None,
        verify_ssl: bool | None = None,
        is_default: bool | None = None,
    ) -> HelmRepositoryInstance:
        instance = await self.get_instance(instance_id)

        if name is not None:
            await _check_unique_name(self.db, HelmRepositoryInstance, name, exclude_id=instance_id)
            instance.name = name
        if url is not None:
            instance.url = url.rstrip("/")
        if username is not None:
            instance.username = username
        if password is not None:
            instance.password = encrypt_secret(password) if password else None
        if is_active is not None:
            instance.is_active = is_active
        if verify_ssl is not None:
            instance.verify_ssl = verify_ssl
        if is_default is not None:
            instance.is_default = is_default

        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def delete_instance(self, instance_id: int) -> None:
        instance = await self.get_instance(instance_id)
        await self.db.delete(instance)
        await self.db.commit()

    # ── Connection test ───────────────────────────────────────────────

    async def test_connection(self, instance_id: int) -> dict[str, Any]:
        """
        Verify connectivity to a Helm Repository by calling
        ``GET {url}/index.yaml``.
        Updates status_flag, status_text and last_checked_at.
        """
        instance = await self.get_instance(instance_id)

        password = decrypt_secret(instance.password)
        auth: tuple[str, str] | None = None
        if instance.username and password:
            auth = (instance.username, password)

        instance.last_checked_at = datetime.now(UTC)

        try:
            async with httpx.AsyncClient(timeout=15.0, auth=auth) as client:
                resp = await client.get(f"{instance.url}/index.yaml")
                if resp.is_success:
                    instance.status_flag = STATUS_OK
                    instance.status_text = "OK — Helm Repository reachable"
                    await self.db.commit()
                    return {
                        "success": True,
                        "message": "Connected — Helm Repository reachable",
                        "status_code": resp.status_code,
                    }
                else:
                    instance.status_flag = STATUS_FAILED
                    instance.status_text = f"HTTP {resp.status_code}"
                    await self.db.commit()
                    return {
                        "success": False,
                        "message": f"Helm Repository returned HTTP {resp.status_code}",
                        "status_code": resp.status_code,
                    }
        except httpx.RequestError as exc:
            instance.status_flag = STATUS_FAILED
            instance.status_text = f"Connection error: {exc!r}"[:255]
            await self.db.commit()
            return {
                "success": False,
                "message": f"Could not reach {instance.url}: {exc}",
                "status_code": None,
            }
