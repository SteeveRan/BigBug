"""
@file health_check.py
@description HealthCheckService — validates credentials, source providers,
             sync groups, and individual mirrors. Produces structured reports.
@dependencies sqlalchemy, app.core.secrets, app.models, app.services.source_providers
@relatedFiles ../schemas/health_check.py, ../api/health_check.py, ../services/mirror.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

import gitlab as _gitlab_module
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.secrets import SecretEncryptionError, decrypt_secret
from app.models.credential import Credential
from app.models.mirror import Mirror
from app.models.pipeline import Pipeline as PipelineModel
from app.models.resource_provider import ProviderDomain, ResourceProvider
from app.models.source_repository import SourceRepository
from app.models.sync_group import SyncGroup
from app.services.source_providers import create_source_provider

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────
# Enums
# ────────────────────────────────────────────────────────────────────


class HealthCheckSeverity(StrEnum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


# ────────────────────────────────────────────────────────────────────
# Data classes
# ────────────────────────────────────────────────────────────────────


@dataclass
class HealthCheckItem:
    """A single component health check result."""

    component: str
    severity: HealthCheckSeverity
    message: str
    detail: dict | None = None


@dataclass
class HealthCheckReport:
    """Full health check report for system, sync group, or mirror."""

    items: list[HealthCheckItem] = field(default_factory=list)
    mirror_id: int | None = None
    sync_group_id: int | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def overall(self) -> HealthCheckSeverity:
        """Return the worst severity across all items."""
        if not self.items:
            return HealthCheckSeverity.OK
        severities = [item.severity for item in self.items]
        if HealthCheckSeverity.ERROR in severities:
            return HealthCheckSeverity.ERROR
        if HealthCheckSeverity.WARNING in severities:
            return HealthCheckSeverity.WARNING
        return HealthCheckSeverity.OK


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────


def _severity_from_bool(ok: bool) -> HealthCheckSeverity:
    return HealthCheckSeverity.OK if ok else HealthCheckSeverity.ERROR


async def _check_credential(
    credential: Credential,
) -> HealthCheckItem:
    """Verify a single credential can be decrypted."""
    component = f"credential:{credential.id}"
    if not credential.encrypted_secret:
        return HealthCheckItem(
            component=component,
            severity=HealthCheckSeverity.WARNING,
            message=f"Credential '{credential.name}' has no secret configured",
        )
    try:
        secret = decrypt_secret(credential.encrypted_secret)
        if not secret:
            return HealthCheckItem(
                component=component,
                severity=HealthCheckSeverity.WARNING,
                message=f"Credential '{credential.name}' secret is empty",
            )
        return HealthCheckItem(
            component=component,
            severity=HealthCheckSeverity.OK,
            message=f"Credential '{credential.name}' is valid",
        )
    except SecretEncryptionError:
        return HealthCheckItem(
            component=component,
            severity=HealthCheckSeverity.ERROR,
            message=f"Credential '{credential.name}' cannot be decrypted (wrong key or corrupt)",
        )


async def _check_source_provider(
    provider_obj: ResourceProvider,
) -> HealthCheckItem:
    """Verify a unified resource provider is accessible."""
    component = f"provider:{provider_obj.id}"
    is_anon = provider_obj.credential_id is None
    label = provider_obj.label
    secret: str | None = None
    if not is_anon:
        if provider_obj.credential is None or not provider_obj.credential.encrypted_secret:
            return HealthCheckItem(
                component=component,
                severity=HealthCheckSeverity.WARNING,
                message=f"Provider '{label}' has no credential configured",
            )
        secret = decrypt_secret(provider_obj.credential.encrypted_secret)

    try:
        provider = await create_source_provider(provider_obj, secret)
        await provider.check_access()
        anon_suffix = " (anonymous)" if is_anon else ""
        return HealthCheckItem(
            component=component,
            severity=HealthCheckSeverity.OK,
            message=f"Provider '{label}'{anon_suffix} is accessible",
        )
    except Exception as exc:
        return HealthCheckItem(
            component=component,
            severity=HealthCheckSeverity.ERROR,
            message=f"Provider '{label}' access failed: {exc}",
        )


async def _check_single_mirror(
    mirror: Mirror,
) -> list[HealthCheckItem]:
    """Run all checks for a single mirror, returning items."""
    items: list[HealthCheckItem] = []
    component = f"mirror:{mirror.id}"

    # 1. Credential check
    sr = mirror.source_repository
    if sr is None:
        items.append(
            HealthCheckItem(
                component=component,
                severity=HealthCheckSeverity.ERROR,
                message=f"Mirror {mirror.id} has no linked SourceRepository",
            )
        )
        return items

    sg = sr.source_group
    if sg is None:
        items.append(
            HealthCheckItem(
                component=component,
                severity=HealthCheckSeverity.ERROR,
                message=f"SourceRepository {sr.id} has no linked SourceGroup",
            )
        )
        return items

    # Phase 7E: unified ResourceProvider only
    provider_obj: ResourceProvider | None = sr.provider
    if provider_obj is None:
        items.append(
            HealthCheckItem(
                component=component,
                severity=HealthCheckSeverity.ERROR,
                message=f"SourceRepository {sr.id} has no linked provider",
            )
        )
        return items

    provider_credential = getattr(provider_obj, "credential", None)
    if provider_credential is not None:
        cred_item = await _check_credential(provider_credential)
        items.append(cred_item)

    # 2. Source accessibility
    try:
        is_anon = provider_obj.credential_id is None
        if is_anon:
            provider = await create_source_provider(provider_obj, None)
        elif provider_credential and provider_credential.encrypted_secret:
            secret = decrypt_secret(provider_credential.encrypted_secret)
            provider = await create_source_provider(provider_obj, secret)
        else:
            items.append(
                HealthCheckItem(
                    component=component,
                    severity=HealthCheckSeverity.WARNING,
                    message=f"Provider '{provider_obj.label}' has no credential",
                )
            )
            # Skip source accessibility + commit checks
            provider = None

        if provider is not None:
            repo_external_id = sr.full_name or sr.external_id
            await provider.get_repository(repo_external_id)
            items.append(
                HealthCheckItem(
                    component=component,
                    severity=HealthCheckSeverity.OK,
                    message=f"Source repo '{repo_external_id}' is accessible",
                )
            )

            # 3. Source commit info
            commit_info = await provider.get_commit_info(repo_external_id)
            source_sha = commit_info.get("sha")
            if source_sha:
                items.append(
                    HealthCheckItem(
                        component=component,
                        severity=HealthCheckSeverity.OK,
                        message=f"Source HEAD: {source_sha[:8]}",
                        detail={"source_sha": source_sha},
                    )
                )
            else:
                items.append(
                    HealthCheckItem(
                        component=component,
                        severity=HealthCheckSeverity.WARNING,
                        message="Source has no commits",
                    )
                )
    except Exception as exc:
        items.append(
            HealthCheckItem(
                component=component,
                severity=HealthCheckSeverity.ERROR,
                message=f"Source access failed: {exc}",
            )
        )

    # 4. Target project check (via python-gitlab if pipeline configured)
    try:
        pipeline = mirror.pipeline
        target_resolved = pipeline is not None and pipeline.provider is not None
        if target_resolved:
            rp = pipeline.provider
            token = (
                decrypt_secret(rp.credential.encrypted_secret)
                if rp.credential is not None and rp.credential.encrypted_secret
                else None
            )
            gl = _gitlab_module.Gitlab(
                url=rp.base_url,
                private_token=token,
                ssl_verify=rp.verify_ssl,
                user_agent="BigBug/1.0",
            )
            if mirror.target_project_id and mirror.target_project_id.isdigit():
                project = gl.projects.get(int(mirror.target_project_id))
                items.append(
                    HealthCheckItem(
                        component=component,
                        severity=HealthCheckSeverity.OK,
                        message=f"Target project '{project.path_with_namespace}' exists in GitLab",
                        detail={"gitlab_project_id": project.id},
                    )
                )
            else:
                items.append(
                    HealthCheckItem(
                        component=component,
                        severity=HealthCheckSeverity.WARNING,
                        message="Mirror has no valid target_project_id",
                    )
                )
        else:
            items.append(
                HealthCheckItem(
                    component=component,
                    severity=HealthCheckSeverity.WARNING,
                    message="No pipeline/GitLab provider configured — target check skipped",
                )
            )
    except Exception as exc:
        items.append(
            HealthCheckItem(
                component=component,
                severity=HealthCheckSeverity.ERROR,
                message=f"Target GitLab project check failed: {exc}",
            )
        )

    return items


# ────────────────────────────────────────────────────────────────────
# HealthCheckService
# ────────────────────────────────────────────────────────────────────


class HealthCheckService:
    """Service for performing health checks on mirroring infrastructure."""

    @staticmethod
    async def check_system(db: AsyncSession) -> HealthCheckReport:
        """Check the overall system health.

        Checks:
        - All active credentials can be decrypted
        - All active SourceProviders can be accessed
        - All SyncGroups have at least one mirror

        Returns:
            HealthCheckReport with ``mirror_id=None``.
        """
        report = HealthCheckReport()

        # 1. Check all active credentials
        cred_result = await db.execute(select(Credential).where(~Credential.is_deleted))
        credentials = cred_result.scalars().all()
        if credentials:
            for cred in credentials:
                report.items.append(await _check_credential(cred))
        else:
            report.items.append(
                HealthCheckItem(
                    component="credentials",
                    severity=HealthCheckSeverity.WARNING,
                    message="No credentials configured",
                )
            )

        # 2. Check all active git providers (phase 7E: resource_providers only)
        rp_result = await db.execute(
            select(ResourceProvider)
            .options(selectinload(ResourceProvider.credential))
            .where(
                ResourceProvider.domain == ProviderDomain.git,
                ~ResourceProvider.is_deleted,
            )
        )
        git_providers = rp_result.scalars().all()
        if git_providers:
            for rp in git_providers:
                report.items.append(await _check_source_provider(rp))
        else:
            report.items.append(
                HealthCheckItem(
                    component="providers",
                    severity=HealthCheckSeverity.WARNING,
                    message="No git providers configured",
                )
            )

        # 3. Check all sync groups have at least one mirror
        sg_result = await db.execute(
            select(SyncGroup).options(selectinload(SyncGroup.mirrors)).where(~SyncGroup.is_deleted)
        )
        sync_groups = sg_result.unique().scalars().all()
        if sync_groups:
            for sg in sync_groups:
                active_mirrors = [m for m in sg.mirrors if not m.is_deleted]
                if active_mirrors:
                    report.items.append(
                        HealthCheckItem(
                            component=f"sync_group:{sg.id}",
                            severity=HealthCheckSeverity.OK,
                            message=f"SyncGroup '{sg.name}' has {len(active_mirrors)} mirror(s)",
                        )
                    )
                else:
                    report.items.append(
                        HealthCheckItem(
                            component=f"sync_group:{sg.id}",
                            severity=HealthCheckSeverity.WARNING,
                            message=f"SyncGroup '{sg.name}' has no active mirrors",
                        )
                    )
        else:
            report.items.append(
                HealthCheckItem(
                    component="sync_groups",
                    severity=HealthCheckSeverity.WARNING,
                    message="No sync groups configured",
                )
            )

        return report

    @staticmethod
    async def check_sync_group(
        db: AsyncSession,
        sync_group_id: int,
    ) -> HealthCheckReport:
        """Check health of a specific SyncGroup and all its mirrors.

        Checks:
        - Credentials of all mirrors in the group
        - Target project existence in GitLab
        - All mirrors share the same target (if applicable)

        Returns:
            HealthCheckReport with ``sync_group_id`` set.
        """
        report = HealthCheckReport(sync_group_id=sync_group_id)

        result = await db.execute(
            select(SyncGroup)
            .options(
                selectinload(SyncGroup.mirrors)
                .selectinload(Mirror.source_repository)
                .selectinload(SourceRepository.source_group),
                selectinload(SyncGroup.mirrors)
                .selectinload(Mirror.source_repository)
                .selectinload(SourceRepository.provider)
                .selectinload(ResourceProvider.credential),
                selectinload(SyncGroup.pipeline)
                .selectinload(PipelineModel.provider)
                .selectinload(ResourceProvider.credential),
            )
            .where(SyncGroup.id == sync_group_id, ~SyncGroup.is_deleted)
        )
        sync_group = result.unique().scalar_one_or_none()
        if sync_group is None:
            report.items.append(
                HealthCheckItem(
                    component="sync_group",
                    severity=HealthCheckSeverity.ERROR,
                    message=f"SyncGroup with id={sync_group_id} not found",
                )
            )
            return report

        active_mirrors = [m for m in sync_group.mirrors if not m.is_deleted]
        if not active_mirrors:
            report.items.append(
                HealthCheckItem(
                    component=f"sync_group:{sync_group.id}",
                    severity=HealthCheckSeverity.WARNING,
                    message=f"SyncGroup '{sync_group.name}' has no active mirrors",
                )
            )
            return report

        # Check credentials across all mirrors (deduplicate by provider;
        # phase 7E: ResourceProvider only)
        seen_provider_ids: set[int] = set()
        for mirror in active_mirrors:
            sr = mirror.source_repository
            if sr is None:
                continue
            provider_obj = sr.provider
            if provider_obj is None:
                continue
            if provider_obj.id in seen_provider_ids:
                continue
            seen_provider_ids.add(provider_obj.id)
            credential = getattr(provider_obj, "credential", None)
            if credential is not None:
                report.items.append(await _check_credential(credential))

        # Check all mirrors
        for mirror in active_mirrors:
            mirror_items = await _check_single_mirror(mirror)
            report.items.extend(mirror_items)

        # Check target consistency: all mirrors should have same target path pattern
        target_paths: set[str] = set()
        for mirror in active_mirrors:
            target_paths.add(
                f"{mirror.target_namespace}/{mirror.target_project_name}"
                if mirror.target_namespace
                else mirror.target_project_name or ""
            )
        if len(target_paths) > 1:
            report.items.append(
                HealthCheckItem(
                    component=f"sync_group:{sync_group.id}",
                    severity=HealthCheckSeverity.WARNING,
                    message=f"Mirrors in SyncGroup '{sync_group.name}' target different paths",
                    detail={"target_paths": sorted(target_paths)},
                )
            )
        else:
            report.items.append(
                HealthCheckItem(
                    component=f"sync_group:{sync_group.id}",
                    severity=HealthCheckSeverity.OK,
                    message="All mirrors target the same path",
                )
            )

        return report

    @staticmethod
    async def check_mirror(
        db: AsyncSession,
        mirror_id: int,
    ) -> HealthCheckReport:
        """Check health of a single mirror.

        Checks:
        - Credential validity
        - Target project existence in GitLab
        - Source repository accessibility
        - Source HEAD exists

        Returns:
            HealthCheckReport with ``mirror_id`` set.
        """
        report = HealthCheckReport(mirror_id=mirror_id)

        result = await db.execute(
            select(Mirror)
            .options(
                selectinload(Mirror.source_repository).selectinload(SourceRepository.source_group),
                selectinload(Mirror.source_repository)
                .selectinload(SourceRepository.provider)
                .selectinload(ResourceProvider.credential),
                selectinload(Mirror.sync_group)
                .selectinload(SyncGroup.pipeline)
                .selectinload(PipelineModel.provider)
                .selectinload(ResourceProvider.credential),
            )
            .where(Mirror.id == mirror_id, ~Mirror.is_deleted)
        )
        mirror = result.scalar_one_or_none()
        if mirror is None:
            report.items.append(
                HealthCheckItem(
                    component="mirror",
                    severity=HealthCheckSeverity.ERROR,
                    message=f"Mirror with id={mirror_id} not found",
                )
            )
            return report

        items = await _check_single_mirror(mirror)
        report.items.extend(items)

        return report
