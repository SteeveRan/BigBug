"""
@file integrations.py
@description Business logic for managing multiple integration instances
             (GitLab, Harbor, GitHub). Handles CRUD, encryption/decryption of
             secrets at rest, and connection testing.
@dependencies app.core.secrets (encrypt_secret/decrypt_secret),
              app.core.exceptions (domain exceptions),
              httpx (connection testing)
@relatedFiles ../models/gitlab_instance.py, ../models/harbor_instance.py,
              ../models/github_instance.py, ../schemas/integrations.py
"""

from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    NotFoundError,
)
from app.core.secrets import decrypt_secret, encrypt_secret
from app.models.github_instance import GithubInstance
from app.models.gitlab_instance import GitlabInstance
from app.models.harbor_instance import HarborInstance

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
        self, name: str, url: str, token: str | None, is_active: bool = True
    ) -> GitlabInstance:
        await _check_unique_name(self.db, GitlabInstance, name)

        instance = GitlabInstance(
            name=name,
            url=url.rstrip("/"),
            token=encrypt_secret(token),
            is_active=is_active,
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
        Updates the instance's status_flag and status_text accordingly.
        """
        instance = await self.get_instance(instance_id)

        token = decrypt_secret(instance.token)
        headers: dict[str, str] = {"User-Agent": "BigBug/1.0"}
        if token:
            headers["PRIVATE-TOKEN"] = token

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
    ) -> HarborInstance:
        await _check_unique_name(self.db, HarborInstance, name)

        instance = HarborInstance(
            name=name,
            url=url.rstrip("/"),
            username=username,
            password=encrypt_secret(password),
            is_active=is_active,
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
        Updates the instance's status_flag and status_text accordingly.
        """
        instance = await self.get_instance(instance_id)

        password = decrypt_secret(instance.password)
        auth: tuple[str, str] | None = None
        if instance.username and password:
            auth = (instance.username, password)

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
    ) -> GithubInstance:
        await _check_unique_name(self.db, GithubInstance, name)

        instance = GithubInstance(
            name=name,
            token=encrypt_secret(token),
            is_active=is_active,
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
    ) -> GithubInstance:
        instance = await self.get_instance(instance_id)

        if name is not None:
            await _check_unique_name(self.db, GithubInstance, name, exclude_id=instance_id)
            instance.name = name
        if token is not None:
            instance.token = encrypt_secret(token) if token else None
        if is_active is not None:
            instance.is_active = is_active

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
        Updates the instance's status_flag and status_text accordingly.
        """
        instance = await self.get_instance(instance_id)

        token = decrypt_secret(instance.token)
        headers: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "BigBug/1.0",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

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
