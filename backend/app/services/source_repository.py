"""
@file source_repository.py
@description SourceRepositoryService — business logic for git source repositories:
             manual creation (clone URL parsing, default-branch detection),
             metadata refresh and background metadata/release fetch.
             Phase 7E of Providers V3: git providers are resolved exclusively
             from ``resource_providers`` (domain=git, direction=external).
@dependencies sqlalchemy, app.services.source_providers, app.services.audit
@relatedFiles ../models/source_repository.py, ../models/source_group.py,
              ../models/mirror_release_log.py, ../schemas/source_repository.py,
              ./source_providers/dispatcher.py
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, DomainError, NotFoundError
from app.core.secrets import decrypt_secret
from app.models.mirror_release_log import MirrorReleaseLog
from app.models.provider_type import ProviderType
from app.models.resource_provider import ProviderDirection, ProviderDomain, ResourceProvider
from app.models.source_repository import DiscoveryStatus, SourceRepository
from app.models.user import User
from app.services.audit import AuditService
from app.services.rbac_service import RBACService
from app.services.source_providers import create_source_provider

logger = logging.getLogger(__name__)

# ProviderType (legacy enum) → ResourceProvider.subtype value
_PROVIDER_TYPE_TO_SUBTYPE: dict[str, str] = {
    "github": "github",
    "gitlab": "gitlab",
    "generic": "generic_git",
}

# ResourceProvider.subtype → legacy ProviderType (for branch checks in refresh logic)
_SUBTYPE_TO_TYPE = {
    "github": ProviderType.github,
    "gitlab": ProviderType.gitlab,
    "generic_git": ProviderType.generic,
}


# ===================================================================
# Provider resolution (ResourceProvider only)
# ===================================================================


async def resolve_repo_provider(
    repo: SourceRepository,
) -> tuple[ResourceProvider | None, str | None]:
    """Resolve the V2 provider object + decrypted secret for a repository.

    Providers V3 (phase 7E): only ``repo.provider`` (ResourceProvider) is
    supported — the legacy ``source_provider`` path has been removed.

    Returns:
        (provider_obj, credential_secret) where provider_obj is a
        ResourceProvider or ``None`` when nothing is linked.

    Raises:
        DomainError: when the linked provider requires a credential but
                     has none.
    """
    if repo.provider_id is not None and repo.provider is not None:
        rp = repo.provider
        secret: str | None = None
        if rp.credential is not None and rp.credential.encrypted_secret:
            secret = decrypt_secret(rp.credential.encrypted_secret)
        elif rp.credential_id is not None:
            raise DomainError(
                f"Provider {rp.id} has no credential secret configured", status_code=400
            )
        return rp, secret

    return None, None


def _legacy_type(provider_obj: ResourceProvider) -> ProviderType:
    """Map a git ``ResourceProvider`` onto the legacy ProviderType enum."""
    return _SUBTYPE_TO_TYPE.get(
        provider_obj.subtype,
        ProviderType.generic,
    )


async def build_repo_provider(repo: SourceRepository) -> Any:
    """Build the V2 provider client for a repository (see resolve_repo_provider)."""
    provider_obj, secret = await resolve_repo_provider(repo)
    if provider_obj is None:
        raise DomainError(
            f"SourceRepository {repo.id} has no linked provider — cannot refresh",
            status_code=400,
        )
    return await create_source_provider(provider_obj, secret)


# ===================================================================
# Clone URL parsing
# ===================================================================


def parse_clone_url(
    clone_url: str, provider_type: ProviderType
) -> tuple[str, str, str | None, str | None, str | None]:
    """Parse a clone URL into (name, full_name, web_url, clone_url_https, clone_url_ssh).

    Supports:
    - HTTPS: ``https://github.com/org/repo.git`` or ``https://github.com/org/repo``
    - SSH:   ``git@github.com:org/repo.git`` or ``git@github.com:org/repo``
    """
    stripped = clone_url.rstrip("/")

    # Extract name (last path segment, strip .git suffix)
    name = stripped.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]

    # Determine clone_url_https / clone_url_ssh
    if clone_url.startswith("git@"):
        clone_url_ssh = clone_url
        clone_url_https = None
        # Convert SSH to HTTPS for parsing: git@github.com:org/repo → https://github.com/org/repo
        if ":" in clone_url:
            host_part, path_part = clone_url.split(":", 1)
            host = host_part.replace("git@", "")
            cls = path_part.rstrip("/")
            if cls.endswith(".git"):
                cls = cls[:-4]
            parsed_for_web = f"https://{host}/{cls}"
        else:
            parsed_for_web = clone_url
    else:
        clone_url_https = clone_url
        clone_url_ssh = None
        parsed_for_web = clone_url
        if parsed_for_web.endswith(".git"):
            parsed_for_web = parsed_for_web[:-4]

    # Full name: org/repo for github/gitlab, just name for generic
    if provider_type in (ProviderType.github, ProviderType.gitlab):
        # Try to extract org/repo from the HTTPS form
        try:
            parsed = urlparse(parsed_for_web)
            path = parsed.path.strip("/")
            full_name = path if "/" in path else name
        except Exception:
            full_name = name
    else:
        full_name = name

    # Web URL
    if provider_type in (ProviderType.github, ProviderType.gitlab):
        web_url = parsed_for_web
    else:
        web_url = None

    return name, full_name, web_url, clone_url_https, clone_url_ssh


async def detect_default_branch(clone_url: str) -> str | None:
    """Run ``git ls-remote --symref <clone_url> HEAD`` to detect the default branch.

    Returns the branch name (e.g. ``main``) or ``None`` if detection failed.
    Does **not** raise — failures are logged and swallowed.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "git",
            "ls-remote",
            "--symref",
            clone_url,
            "HEAD",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode != 0:
            logger.warning(
                "git ls-remote failed for %s: %s",
                clone_url,
                stderr.decode(errors="replace").strip(),
            )
            return None

        output = stdout.decode(errors="replace")
        match = re.search(r"ref:\s+refs/heads/(\S+)\s+HEAD", output)
        if match:
            return match.group(1)
        return None
    except Exception:
        logger.warning("git ls-remote exception for %s", clone_url, exc_info=True)
        return None


# ===================================================================
# Status / metadata / releases helpers
# ===================================================================


def set_repo_status(repo: SourceRepository, status_flag: int, status_text: str) -> None:
    """Set status tracking fields on a SourceRepository instance."""
    repo.status_flag = status_flag
    repo.status_text = status_text


async def sync_releases_from_github(
    db: AsyncSession, source_repository_id: int, full_name: str, provider
) -> int:
    """Fetch all releases from a GitHub repository and create MirrorReleaseLog records.

    Returns the number of new records created.
    """
    from github import GithubException

    from app.services.source_providers.github import _map_github_exception

    try:
        gh = provider._get_client()
        gh_repo = gh.get_repo(full_name)
        releases = gh_repo.get_releases()

        created = 0
        for release in releases:
            tag: str = release.tag_name
            existing = await db.execute(
                select(MirrorReleaseLog).where(
                    MirrorReleaseLog.source_repository_id == source_repository_id,
                    MirrorReleaseLog.tag == tag,
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue

            log = MirrorReleaseLog(
                source_repository_id=source_repository_id,
                tag=tag,
                name=getattr(release, "title", None) or tag,
                description=getattr(release, "body", None),
                url=getattr(release, "html_url", None),
                published_at=release.published_at,
                is_prerelease=getattr(release, "prerelease", False),
            )
            db.add(log)
            created += 1

        if created > 0:
            await db.flush()

        return created
    except GithubException as exc:
        raise _map_github_exception(exc, f"sync_releases/{full_name}") from exc


async def sync_releases_from_gitlab(
    db: AsyncSession, source_repository_id: int, full_name: str, provider
) -> int:
    """Fetch all releases from a GitLab project and create MirrorReleaseLog records.

    Returns the number of new records created.
    """
    from gitlab import GitlabError

    from app.services.source_providers.gitlab import _is_prerelease_tag, _map_gitlab_exception

    try:
        gl = provider._get_client()

        def _fetch():
            project = gl.projects.get(full_name)
            releases = project.releases.list(per_page=100, order_by="released_at", sort="desc")
            return project, releases

        project, releases = await asyncio.to_thread(_fetch)

        created = 0
        for release in releases:
            tag: str | None = getattr(release, "tag_name", None)
            if not tag:
                continue

            existing = await db.execute(
                select(MirrorReleaseLog).where(
                    MirrorReleaseLog.source_repository_id == source_repository_id,
                    MirrorReleaseLog.tag == tag,
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue

            is_prerelease = _is_prerelease_tag(tag)
            log = MirrorReleaseLog(
                source_repository_id=source_repository_id,
                tag=tag,
                name=getattr(release, "name", None) or tag,
                description=getattr(release, "description", None),
                url=f"{project.web_url}/-/releases/{tag}",
                published_at=getattr(release, "released_at", None),
                is_prerelease=is_prerelease,
            )
            db.add(log)
            created += 1

        if created > 0:
            await db.flush()

        return created
    except GitlabError as exc:
        raise _map_gitlab_exception(exc, f"sync_releases/{full_name}") from exc


async def fetch_generic_commit_info(repo: SourceRepository) -> None:
    """Fetch HEAD commit info from a generic Git repository using GitPython (bare clone)."""
    import shutil
    import tempfile

    clone_url: str | None = repo.clone_url_https or repo.clone_url_ssh
    if not clone_url:
        set_repo_status(repo, 1, "No clone URL available")
        return

    tmpdir = tempfile.mkdtemp(prefix="bigbug_bg_")
    try:
        from git import Repo

        repo_obj = Repo.clone_from(clone_url, tmpdir, bare=True, depth=1)

        try:
            head_commit = repo_obj.head.commit
        except ValueError:
            # No commits in repository
            set_repo_status(repo, 0, "OK (empty repository)")
            return

        repo.last_commit_sha = head_commit.hexsha
        repo.last_commit_date = head_commit.committed_datetime
        repo.last_commit_author = head_commit.author.name
        repo.last_commit_message = head_commit.message[:500] if head_commit.message else None

    except Exception as exc:
        logger.warning("GitPython clone failed for '%s': %s", clone_url, exc)
        set_repo_status(repo, 1, f"Git clone failed: {exc}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


async def fill_repo_metadata(repo: SourceRepository, fresh_data: dict) -> None:
    """Fill SourceRepository metadata fields from provider response dict."""
    repo.description = fresh_data.get("description")
    repo.language = fresh_data.get("language")
    repo.stars_count = fresh_data.get("stars", 0)
    repo.forks_count = fresh_data.get("forks", 0)
    repo.is_private = fresh_data.get("private", False)
    repo.is_archived = fresh_data.get("archived", False)
    repo.is_fork = fresh_data.get("fork", False)
    repo.is_disabled = fresh_data.get("disabled", False)
    if fresh_data.get("default_branch"):
        repo.default_branch = fresh_data["default_branch"]
    if fresh_data.get("html_url"):
        repo.web_url = fresh_data["html_url"]
    if fresh_data.get("clone_url"):
        repo.clone_url_https = fresh_data["clone_url"]
    if fresh_data.get("ssh_url"):
        repo.clone_url_ssh = fresh_data["ssh_url"]
    repo.source_created_at = fresh_data.get("created_at")
    repo.source_updated_at = fresh_data.get("updated_at")
    repo.source_pushed_at = fresh_data.get("pushed_at")

    # Last commit
    repo.last_commit_sha = fresh_data.get("last_commit_sha")
    repo.last_commit_date = fresh_data.get("last_commit_date")
    repo.last_commit_author = fresh_data.get("last_commit_author")
    repo.last_commit_message = fresh_data.get("last_commit_message")

    # License
    if fresh_data.get("license_spdx") or fresh_data.get("license_name"):
        repo.license_spdx = fresh_data.get("license_spdx")
        repo.license_name = fresh_data.get("license_name")

    # README
    if "readme_html" in fresh_data:
        repo.readme_html = fresh_data["readme_html"]
        repo.readme_fetched_at = datetime.now(UTC)

    # Latest release
    if fresh_data.get("latest_release_tag"):
        repo.latest_release_tag = fresh_data["latest_release_tag"]
        repo.latest_release_name = fresh_data.get("latest_release_name")
        published_at = fresh_data.get("latest_release_published_at")
        repo.latest_release_date = datetime.fromisoformat(published_at) if published_at else None
        repo.latest_release_url = fresh_data.get("latest_release_html_url")

    # Latest prerelease
    if fresh_data.get("latest_prerelease_tag"):
        repo.latest_prerelease_tag = fresh_data["latest_prerelease_tag"]
        repo.latest_prerelease_name = fresh_data.get("latest_prerelease_name")
        prerelease_published_at = fresh_data.get("latest_prerelease_published_at")
        repo.latest_prerelease_date = (
            datetime.fromisoformat(prerelease_published_at) if prerelease_published_at else None
        )
        repo.latest_prerelease_url = fresh_data.get("latest_prerelease_html_url")
    else:
        repo.latest_prerelease_tag = None
        repo.latest_prerelease_name = None
        repo.latest_prerelease_date = None
        repo.latest_prerelease_url = None

    repo.last_seen_at = datetime.now(UTC)


async def sync_repo_releases(
    db: AsyncSession,
    repo: SourceRepository,
    provider_obj: Any,
    provider_client: Any,
) -> int:
    """Sync releases for API-based providers (github/gitlab). No-op for generic."""
    legacy_type = _legacy_type(provider_obj)
    external_id = repo.full_name or repo.external_id
    try:
        if legacy_type == ProviderType.github:
            return await sync_releases_from_github(db, repo.id, external_id, provider_client)
        if legacy_type == ProviderType.gitlab:
            return await sync_releases_from_gitlab(db, repo.id, external_id, provider_client)
    except DomainError as release_exc:
        logger.warning(
            "Release sync failed during refresh for repo_id=%d: %s",
            repo.id,
            release_exc,
        )
    return 0


async def fetch_metadata_background(repo_id: int) -> None:
    """Background task: fetch metadata and releases for a newly created source repository.

    Creates an independent database session, fetches repository metadata via
    the source provider API (GitHub/GitLab) or GitPython (generic Git), saves
    all fields including ``last_commit_*`` and ``MirrorReleaseLog`` records,
    and updates ``status_flag`` to 0 (success) or 1 (error).
    """
    from app.database import AsyncSessionLocal

    logger.info("Background metadata fetch started for repo_id=%d", repo_id)

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(SourceRepository)
                .options(
                    selectinload(SourceRepository.provider).selectinload(
                        ResourceProvider.credential
                    ),
                )
                .where(SourceRepository.id == repo_id)
            )
            repo = result.unique().scalar_one_or_none()
            if repo is None:
                logger.error("Background fetch: repo id=%d not found", repo_id)
                return

            provider_obj, credential_secret = await resolve_repo_provider(repo)
            if provider_obj is None:
                set_repo_status(repo, 1, "No source provider configured")
                await db.commit()
                return

            provider = await create_source_provider(provider_obj, credential_secret)
            external_id: str = repo.full_name or repo.external_id
            legacy_type = _legacy_type(provider_obj)

            if legacy_type in (ProviderType.github, ProviderType.gitlab):
                # Fetch metadata via provider API
                fresh_data = await provider.get_repository(external_id)
                await fill_repo_metadata(repo, fresh_data)
                set_repo_status(repo, 0, "OK")
                await db.commit()

                # Sync releases in a separate transaction to isolate failures
                releases_created = 0
                try:
                    async with AsyncSessionLocal() as db2:
                        releases_created = await sync_repo_releases(
                            db2, repo, provider_obj, provider
                        )
                        await db2.commit()
                except Exception as release_exc:
                    logger.warning(
                        "Background release sync failed for repo_id=%d: %s",
                        repo_id,
                        release_exc,
                    )

                logger.info(
                    "Background fetch OK for repo_id=%d: releases_created=%d",
                    repo_id,
                    releases_created,
                )

            elif legacy_type == ProviderType.generic:
                await fetch_generic_commit_info(repo)
                # status_flag is set inside fetch_generic_commit_info
                await db.commit()
                logger.info("Background fetch OK for generic repo_id=%d", repo_id)

    except Exception as exc:
        logger.error("Background fetch failed for repo_id=%d: %s", repo_id, exc, exc_info=True)
        # Update status to error in a fresh session
        try:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(SourceRepository).where(SourceRepository.id == repo_id)
                )
                repo = result.scalar_one_or_none()
                if repo:
                    set_repo_status(repo, 1, f"Error: {exc}")
                    await db.commit()
        except Exception as inner_exc:
            logger.error("Failed to update error status for repo_id=%d: %s", repo_id, inner_exc)


# ===================================================================
# Service
# ===================================================================


class SourceRepositoryService:
    """Service layer for manual SourceRepository management (phase 4)."""

    @staticmethod
    async def create_repository(
        db: AsyncSession,
        *,
        clone_url: str,
        provider_type: ProviderType,
        provider_id: int | None,
        current_user: User,
    ) -> SourceRepository:
        """Create a source repository manually (Generic Git or any provider).

        Parses clone_url to derive name and full_name, auto-detects the
        default branch via ``git ls-remote``, resolves the group and provider,
        checks duplicates and persists. The background metadata fetch is
        launched by the caller (API layer) after commit.
        """
        from app.models.source_group import SourceGroup

        clone_url = clone_url.strip()

        # ── 1. Parse clone_url ──────────────────────────────────────────
        name, full_name, web_url, clone_url_https, clone_url_ssh = parse_clone_url(
            clone_url, provider_type
        )

        # ── 2. Resolve source_group_id automatically ────────────────────
        rbac = RBACService(db)
        source_group_id: int | None = None
        if provider_type in (ProviderType.github, ProviderType.gitlab):
            group_name = full_name.split("/")[0]

            group_web_url: str | None = None
            if web_url:
                group_web_url = web_url.rsplit("/", 1)[0]

            grp_result = await db.execute(
                select(SourceGroup).where(
                    SourceGroup.name == group_name,
                    ~SourceGroup.is_deleted,
                )
            )
            group = grp_result.scalar_one_or_none()

            if group is None:
                group = SourceGroup(
                    external_id=group_name,
                    name=group_name,
                    full_path=group_name,
                    web_url=group_web_url,
                )
                db.add(group)
                await db.flush()
                logger.info(
                    "Auto-created SourceGroup id=%d name='%s'",
                    group.id,
                    group.name,
                )

            source_group_id = group.id

            if not await rbac.check_scope_access(current_user.id, "source_group", source_group_id):
                raise DomainError("Access denied: resource not in your role scope", status_code=403)

        # ── 3. Resolve provider (ResourceProvider only) ───────────────────────
        resolved_provider_id: int | None = None

        if provider_id is not None:
            prov_result = await db.execute(
                select(ResourceProvider).where(
                    ResourceProvider.id == provider_id,
                    ~ResourceProvider.is_deleted,
                    ResourceProvider.domain == ProviderDomain.git,
                    ResourceProvider.direction == ProviderDirection.external,
                )
            )
            rp = prov_result.scalar_one_or_none()
            if rp is None:
                raise NotFoundError(
                    f"Provider with id={provider_id} not found (expected git/external)"
                )
            subtype = str(rp.subtype)
            if subtype != provider_type:
                raise DomainError(
                    f"Provider type mismatch: provider {provider_id} is "
                    f"'{subtype}' but request specified '{provider_type}'",
                    status_code=422,
                )
            resolved_provider_id = rp.id
        else:
            # Auto-assign the default git provider for this subtype
            subtype_value = _PROVIDER_TYPE_TO_SUBTYPE.get(provider_type)
            if subtype_value is None:
                raise DomainError(f"Unsupported provider type '{provider_type}'", status_code=422)
            default_result = await db.execute(
                select(ResourceProvider).where(
                    ResourceProvider.domain == ProviderDomain.git,
                    ResourceProvider.subtype == subtype_value,
                    ResourceProvider.direction == ProviderDirection.external,
                    ResourceProvider.is_default == True,  # noqa: E712
                    ~ResourceProvider.is_deleted,
                )
            )
            default_provider = default_result.scalar_one_or_none()
            if default_provider is None:
                raise DomainError(
                    f"No default provider found for '{provider_type}'. "
                    "Create one in Settings → Providers first.",
                    status_code=500,
                )
            resolved_provider_id = default_provider.id
            logger.info(
                "Auto-assigned default provider id=%d for provider_type='%s'",
                default_provider.id,
                provider_type,
            )

        # ── 4. Auto-detect default branch via git ls-remote ─────────────
        default_branch = await detect_default_branch(clone_url)

        # ── 5. Check for duplicates ─────────────────────────────────────
        dup_query = select(SourceRepository).where(
            SourceRepository.full_name == full_name,
            ~SourceRepository.is_deleted,
        )
        if source_group_id is not None:
            dup_query = dup_query.where(SourceRepository.source_group_id == source_group_id)
        else:
            dup_query = dup_query.where(SourceRepository.source_group_id.is_(None))

        dup_result = await db.execute(dup_query)
        if dup_result.scalar_one_or_none() is not None:
            detail = f"Repository '{full_name}' already exists" + (
                f" in source group {source_group_id}" if source_group_id else ""
            )
            raise ConflictError(detail)

        # ── 6. Persist ──────────────────────────────────────────────────
        now = datetime.now(UTC)
        repo = SourceRepository(
            source_group_id=source_group_id,
            provider_id=resolved_provider_id,
            external_id=str(uuid.uuid4()),
            name=name,
            full_name=full_name,
            clone_url_https=clone_url_https,
            clone_url_ssh=clone_url_ssh,
            default_branch=default_branch,
            web_url=web_url,
            discovery_status=DiscoveryStatus.new,
            discovered_at=now,
            last_seen_at=now,
            is_archived=False,
            is_fork=False,
            is_disabled=False,
        )
        # ── 7. Set status_flag=3 (in progress) and let the caller launch the fetch ──
        repo.status_flag = 3
        repo.status_text = "Fetching metadata..."
        db.add(repo)
        await db.flush()

        await AuditService.log_event(
            db,
            user_id=current_user.id,
            username=current_user.username,
            action="source_repository.created",
            resource_type="source_repository",
            resource_id=repo.id,
            resource_name=repo.full_name,
        )

        await db.commit()

        # Reload with eager-loaded relationships to avoid MissingGreenlet
        result = await db.execute(
            select(SourceRepository)
            .options(
                selectinload(SourceRepository.source_group),
                selectinload(SourceRepository.provider),
                selectinload(SourceRepository.mirrors),
            )
            .where(SourceRepository.id == repo.id)
        )
        return result.unique().scalar_one()

    @staticmethod
    async def refresh_repository(
        db: AsyncSession,
        repo: SourceRepository,
        *,
        current_user: User,
    ) -> SourceRepository:
        """Re-fetch repository metadata from the upstream provider.

        Looks up the linked ``ResourceProvider``, creates the appropriate V2
        provider client, calls ``get_repository()`` to retrieve fresh metadata,
        persists all fields and syncs release logs.
        """
        # ── 1. Validate provider + credential ──────────────────────────
        provider_obj, credential_secret = await resolve_repo_provider(repo)
        if provider_obj is None:
            raise DomainError(
                "SourceRepository has no linked provider — cannot refresh",
                status_code=400,
            )
        provider = await create_source_provider(provider_obj, credential_secret)

        # ── 2. Set status to "in progress" ──────────────────────────────
        repo.status_flag = 3
        repo.status_text = "Fetching metadata..."
        await db.flush()

        # ── 3. Fetch fresh metadata from upstream ───────────────────────
        external_id = repo.full_name or repo.external_id
        try:
            fresh_data = await provider.get_repository(external_id)
        except DomainError as exc:
            repo.status_flag = 1
            repo.status_text = f"Error: {exc.detail}"
            await db.commit()
            raise

        # ── 4. Update all fields via shared helper ──────────────────────
        await fill_repo_metadata(repo, fresh_data)

        # ── 5. Sync releases for API-based providers ────────────────────
        await sync_repo_releases(db, repo, provider_obj, provider)

        set_repo_status(repo, 0, "OK")

        # ── 6. Audit + persist ──────────────────────────────────────────
        await AuditService.log_event(
            db,
            user_id=current_user.id,
            username=current_user.username,
            action="source_repository.refreshed",
            resource_type="source_repository",
            resource_id=repo.id,
            resource_name=repo.full_name,
        )

        await db.commit()
        await db.refresh(repo)

        logger.info(
            "Refresh completed: repository_id=%d, full_name='%s'",
            repo.id,
            repo.full_name,
        )
        return repo
