"""
@file source_group.py
@description SourceGroupService — business logic for source groups: import
             (discovery of an org/group and its repositories from an upstream
             git provider) and refresh (re-fetch of the repository list).
             Phase 7E of Providers V3: the git provider is a
             ``resource_providers`` row (domain=git, direction=external).
@dependencies sqlalchemy, app.services.source_providers, app.services.audit
@relatedFiles ../models/source_group.py, ../models/source_repository.py,
              ./source_providers/dispatcher.py, ./source_repository.py
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestError, DomainError, NotFoundError
from app.core.secrets import decrypt_secret
from app.models.resource_provider import (
    ProviderDirection,
    ProviderDomain,
    ResourceProvider,
)
from app.models.source_group import SourceGroup
from app.models.source_repository import SourceRepository
from app.models.user import User
from app.services.audit import AuditService
from app.services.source_providers import create_source_provider

logger = logging.getLogger(__name__)


async def _provider_secret(provider_obj: Any) -> str | None:
    """Decrypt the credential secret of a provider row (None for anonymous)."""
    credential = getattr(provider_obj, "credential", None)
    if credential is not None and credential.encrypted_secret:
        return decrypt_secret(credential.encrypted_secret)
    return None


async def _build_client(db: AsyncSession, provider_id: int) -> tuple[Any, Any]:
    """Load a git ResourceProvider by id and build the V2 client for it.

    Returns:
        (provider_row, v2_client)

    Raises:
        NotFoundError: when no non-deleted git/external provider has this id.
        BadRequestError: when the provider requires a credential but has none.
    """
    result = await db.execute(
        select(ResourceProvider)
        .options(selectinload(ResourceProvider.credential))
        .where(
            ResourceProvider.id == provider_id,
            ResourceProvider.domain == ProviderDomain.git,
            ResourceProvider.direction == ProviderDirection.external,
            ~ResourceProvider.is_deleted,
        )
    )
    provider_row = result.scalar_one_or_none()
    if provider_row is None:
        raise NotFoundError(f"Provider with id={provider_id} not found (git/external)")

    if provider_row.credential_id is not None:
        secret = await _provider_secret(provider_row)
        if secret is None:
            raise BadRequestError(f"Provider {provider_id} has no credential secret configured")
    else:
        secret = None

    client = await create_source_provider(provider_row, secret)
    return provider_row, client


async def _import_repositories(
    db: AsyncSession,
    *,
    group: SourceGroup,
    repos: list[dict],
    provider_row: Any,
    update_existing: bool,
) -> int:
    """Upsert discovered repositories into a group. Returns the new-repo count."""
    imported_count = 0
    for repo in repos:
        repo_ext_id = repo.get("external_id") or repo.get("full_name")
        if not repo_ext_id:
            continue

        existing_repo = await db.execute(
            select(SourceRepository).where(
                SourceRepository.source_group_id == group.id,
                SourceRepository.external_id == repo_ext_id,
                ~SourceRepository.is_deleted,
            )
        )
        sr = existing_repo.scalar_one_or_none()
        if sr is not None:
            if update_existing:
                # Update last_seen_at and other mutable fields
                sr.last_seen_at = datetime.now(UTC)
                sr.is_archived = repo.get("archived", False)
                sr.is_disabled = repo.get("disabled", False)
                sr.source_pushed_at = repo.get("pushed_at")
                sr.source_updated_at = repo.get("updated_at")
            continue

        sr = SourceRepository(
            source_group_id=group.id,
            provider_id=provider_row.id,
            external_id=repo_ext_id,
            name=repo.get("name", ""),
            full_name=repo.get("full_name", ""),
            web_url=repo.get("html_url"),
            clone_url_https=repo.get("clone_url"),
            clone_url_ssh=repo.get("ssh_url"),
            description=repo.get("description"),
            default_branch=repo.get("default_branch"),
            license_spdx=repo.get("license_spdx"),
            license_name=repo.get("license_name"),
            is_archived=repo.get("archived", False),
            is_fork=repo.get("fork", False),
            is_disabled=repo.get("disabled", False),
            discovery_status="discovered",
            discovered_at=datetime.now(UTC),
            source_created_at=repo.get("created_at"),
            source_updated_at=repo.get("updated_at"),
            source_pushed_at=repo.get("pushed_at"),
        )
        db.add(sr)
        imported_count += 1

    return imported_count


class SourceGroupService:
    """Service layer for source-group discovery (import/refresh, phase 4)."""

    @staticmethod
    async def import_group(
        db: AsyncSession,
        *,
        group_name: str,
        provider_id: int,
        current_user: User,
        ip_address: str | None = None,
    ) -> SourceGroup:
        """Import an organization/group from a git provider and its repositories.

        Uses the provider's credential to fetch group metadata and all
        repositories via the V2 provider client. Anonymous (public) providers
        work without a credential.
        """
        # 1. Resolve provider + build client (validates git/external + credential)
        provider_row, gh_provider = await _build_client(db, provider_id)

        # 2. Find the group on the provider
        provider_groups = await gh_provider.list_groups()
        target_group = None
        for g in provider_groups:
            if (
                g.get("name", "").lower() == group_name.lower()
                or g.get("login", "").lower() == group_name.lower()
            ):
                target_group = g
                break

        if target_group is None:
            raise NotFoundError(f"Group '{group_name}' not found for provider {provider_id}")

        external_id = (
            target_group.get("external_id") or target_group.get("login") or target_group.get("name")
        )

        # 3. Upsert SourceGroup (groups are independent of providers)
        existing_result = await db.execute(
            select(SourceGroup).where(
                SourceGroup.external_id == external_id,
                ~SourceGroup.is_deleted,
            )
        )
        source_group = existing_result.scalar_one_or_none()

        if source_group is None:
            source_group = SourceGroup(
                external_id=external_id,
                name=target_group.get("name", group_name),
                full_path=target_group.get("full_name") or target_group.get("html_url"),
                web_url=target_group.get("html_url"),
                description=target_group.get("description"),
            )
            db.add(source_group)
            await db.flush()
            logger.info("Created SourceGroup id=%d name='%s'", source_group.id, source_group.name)
        else:
            logger.info(
                "SourceGroup id=%d name='%s' already exists", source_group.id, source_group.name
            )

        # 4. Import repositories
        repos = await gh_provider.list_repositories(external_id)
        imported_count = await _import_repositories(
            db,
            group=source_group,
            repos=repos,
            provider_row=provider_row,
            update_existing=False,
        )

        await db.commit()

        # 5. Re-fetch with relations
        result = await db.execute(
            select(SourceGroup)
            .options(
                selectinload(SourceGroup.source_repositories),
            )
            .where(SourceGroup.id == source_group.id)
        )
        source_group = result.unique().scalar_one()

        logger.info(
            "Import completed: group_id=%d, repos_imported=%d",
            source_group.id,
            imported_count,
        )

        await AuditService.log_event(
            db,
            user_id=current_user.id,
            username=current_user.username,
            action="source_group.imported",
            resource_type="source_group",
            resource_id=source_group.id,
            resource_name=source_group.name,
            details={"repos_imported": imported_count},
            ip_address=ip_address,
        )
        await db.commit()

        return source_group

    @staticmethod
    async def refresh_group(
        db: AsyncSession,
        *,
        group_id: int,
        current_user: User,
        ip_address: str | None = None,
    ) -> tuple[SourceGroup, Any]:
        """Re-fetch the repository list for a group from the upstream provider.

        The provider is resolved from the group's repositories:
        the first repository with a linked ``ResourceProvider`` wins.

        Returns:
            (group, provider_row)
        """
        # Get group
        result = await db.execute(
            select(SourceGroup)
            .options(
                selectinload(SourceGroup.source_repositories),
            )
            .where(SourceGroup.id == group_id, ~SourceGroup.is_deleted)
        )
        group = result.unique().scalar_one_or_none()
        if group is None:
            raise NotFoundError(f"SourceGroup with id={group_id} not found")

        # Find a provider through the group's repositories
        repo_with_provider_result = await db.execute(
            select(SourceRepository)
            .options(
                selectinload(SourceRepository.provider).selectinload(ResourceProvider.credential),
            )
            .where(
                SourceRepository.source_group_id == group_id,
                ~SourceRepository.is_deleted,
            )
            .limit(1)
        )
        repo_with_provider = repo_with_provider_result.scalars().first()

        provider_obj = repo_with_provider.provider if repo_with_provider is not None else None

        if provider_obj is None:
            raise DomainError(
                "SourceGroup has no linked provider — cannot refresh", status_code=400
            )

        if provider_obj.credential_id is not None:
            secret = await _provider_secret(provider_obj)
            if secret is None:
                raise DomainError(
                    f"Provider {provider_obj.id} has no credential secret configured",
                    status_code=400,
                )
        else:
            secret = None

        gh_provider = await create_source_provider(provider_obj, secret)

        external_id = group.external_id or group.name
        repos = await gh_provider.list_repositories(external_id)
        imported_count = await _import_repositories(
            db,
            group=group,
            repos=repos,
            provider_row=provider_obj,
            update_existing=True,
        )

        await db.commit()

        # Re-fetch
        result = await db.execute(
            select(SourceGroup)
            .options(
                selectinload(SourceGroup.source_repositories),
            )
            .where(SourceGroup.id == group.id)
        )
        group = result.unique().scalar_one()

        logger.info(
            "Refresh completed: group_id=%d, new_repos=%d",
            group.id,
            imported_count,
        )

        await AuditService.log_event(
            db,
            user_id=current_user.id,
            username=current_user.username,
            action="source_group.refreshed",
            resource_type="source_group",
            resource_id=group.id,
            resource_name=group.name,
            details={"new_repos": imported_count},
            ip_address=ip_address,
        )
        await db.commit()

        return group, provider_obj
