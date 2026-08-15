"""
@file service.py
@description Unified :class:`ProviderService` for Providers V3 — CRUD, connection
             test, domain-action dispatch and category-based access control (6.4).
             Raises :class:`app.core.exceptions.DomainError` (not HTTPException) so
             the API layer can map business rules to HTTP status codes.
@dependencies sqlalchemy, app.models.resource_provider, app.core.secrets, ./registry, ./clients
@relatedFiles ./registry.py, ../../schemas/provider.py, ../../core/exceptions.py
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import DomainError
from app.core.secrets import decrypt_secret
from app.models.credential import Credential
from app.models.resource_provider import (
    ProviderCapability,
    ProviderCategory,
    ProviderDirection,
    ProviderSubtype,
    ProviderVisibility,
    ResourceProvider,
)
from app.models.team_member import TeamMember
from app.models.user import User
from app.services.providers.clients.docker_harbor import HarborClient
from app.services.providers.clients.docker_registry import registry_client_for_subtype
from app.services.providers.clients.git_generic import GenericGitClient
from app.services.providers.clients.git_github import GitHubClient
from app.services.providers.clients.git_gitlab import GitLabClient
from app.services.providers.clients.helm_repo import HelmRepoClient
from app.services.providers.registry import get_spec

# Status flags (unified convention, matches integrations.py)
STATUS_OK = 0
STATUS_FAILED = 1
STATUS_PENDING = 4


class ProviderService:
    """Business logic for the unified ``resource_providers`` entity."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Permission helpers ──────────────────────────────────────────────

    async def _permissions_async(self, user: User) -> set[str]:
        """Resolve the caller's permission names.

        Uses the JWT-cached set when present (set by ``get_current_user``);
        otherwise falls back to a DB lookup. In unit tests the caller may set
        ``user._cached_permissions`` directly.
        """
        cached = getattr(user, "_cached_permissions", [])
        if cached:
            return set(cached)
        from app.services.rbac_service import RBACService

        return set(await RBACService(self.db).get_user_permissions(user.id))

    # ── Access matrix (6.4) ─────────────────────────────────────────────

    async def _ensure_can_read(self, provider: ResourceProvider, user: User) -> None:
        perms = await self._permissions_async(user)
        # Admin / read_all sees everything.
        if "providers:read_all" in perms:
            return
        if provider.category == ProviderCategory.private:
            # Owner sees their own; team members see team-shared providers.
            if provider.owner_user_id == user.id:
                return
            if (
                provider.visibility == ProviderVisibility.team
                and provider.team_id is not None
                and await self._is_team_member(provider.team_id, user.id)
            ):
                return
            raise DomainError("Access denied: not the owner of this private provider", 403)

    async def _is_team_member(self, team_id: int, user_id: int) -> bool:
        result = await self.db.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def _ensure_can_mutate(self, provider: ResourceProvider, user: User) -> None:
        perms = await self._permissions_async(user)
        if provider.category == ProviderCategory.system:
            if "providers_system:write" not in perms:
                raise DomainError("System providers require providers_system:write", 403)
            return
        # 12.2.2: mutations of team/private providers are owner- or admin-only.
        if (
            provider.category == ProviderCategory.private
            and provider.owner_user_id != user.id
            and "providers:read_all" not in perms
        ):
            raise DomainError("Access denied: not the owner of this private provider", 403)

    @staticmethod
    def _ensure_category_valid(category: ProviderCategory, owner_user_id: int | None) -> None:
        if category == ProviderCategory.private and owner_user_id is None:
            raise DomainError("private providers require an owner_user_id", 400)

    # ── CRUD ────────────────────────────────────────────────────────────

    async def _get_or_404(self, provider_id: int) -> ResourceProvider:
        result = await self.db.execute(
            select(ResourceProvider)
            .options(selectinload(ResourceProvider.team))
            .where(ResourceProvider.id == provider_id)
        )
        provider = result.scalar_one_or_none()
        if provider is None or provider.is_deleted:
            raise DomainError(f"Provider {provider_id} not found", 404)
        return provider

    async def list_providers(self, user: User) -> list[ResourceProvider]:
        perms = await self._permissions_async(user)
        stmt = select(ResourceProvider).where(ResourceProvider.is_deleted.is_(False))
        if "providers:read_all" not in perms:
            # 12.2.4: public | own private | team-shared private (membership).
            stmt = stmt.where(
                (ResourceProvider.visibility == ProviderVisibility.public)
                | (ResourceProvider.owner_user_id == user.id)
                | (
                    (ResourceProvider.visibility == ProviderVisibility.team)
                    & ResourceProvider.team_id.in_(
                        select(TeamMember.team_id).where(TeamMember.user_id == user.id)
                    )
                )
            )
        result = await self.db.execute(
            stmt.options(selectinload(ResourceProvider.team)).order_by(ResourceProvider.name)
        )
        return list(result.scalars().all())

    async def get_provider(self, provider_id: int, user: User) -> ResourceProvider:
        provider = await self._get_or_404(provider_id)
        await self._ensure_can_read(provider, user)
        return provider

    async def create_provider(
        self,
        *,
        domain,
        subtype: ProviderSubtype,
        category: ProviderCategory,
        direction: ProviderDirection,
        name: str,
        label: str,
        user: User,
        description: str | None = None,
        base_url: str | None = None,
        config: dict | None = None,
        credential_id: int | None = None,
        visibility: ProviderVisibility = ProviderVisibility.owner,
        team_id: int | None = None,
    ) -> ResourceProvider:
        perms = await self._permissions_async(user)
        if category == ProviderCategory.system and "providers_system:write" not in perms:
            raise DomainError("System providers require providers_system:write", 403)

        # Unique name among live rows.
        existing = await self.db.execute(
            select(ResourceProvider).where(
                ResourceProvider.name == name,
                ResourceProvider.is_deleted.is_(False),
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise DomainError(f"Provider name '{name}' already exists", 409)

        owner_user_id = user.id if category == ProviderCategory.private else None
        self._ensure_category_valid(category, owner_user_id)

        # 12.2.2: creating a team-shared provider requires current_user == owner
        # and membership in the target team.
        if visibility == ProviderVisibility.team:
            if team_id is None:
                raise DomainError("team_id is required when visibility is 'team'", 422)
            if category != ProviderCategory.private or owner_user_id != user.id:
                raise DomainError("team visibility requires a private provider owned by you", 422)
            if (
                not await self._is_team_member(team_id, user.id)
                and "providers:read_all" not in perms
            ):
                raise DomainError("you must be a member of the target team", 422)

        if category == ProviderCategory.public:
            visibility = ProviderVisibility.public
        elif category == ProviderCategory.system:
            visibility = ProviderVisibility.owner

        provider = ResourceProvider(
            domain=domain,
            subtype=subtype,
            category=category,
            visibility=visibility,
            direction=direction,
            name=name,
            label=label,
            description=description,
            base_url=base_url,
            config=config or {},
            credential_id=credential_id,
            owner_user_id=owner_user_id,
            team_id=team_id if visibility == ProviderVisibility.team else None,
            is_protected=(category == ProviderCategory.system),
            status_flag=STATUS_PENDING,
        )
        self.db.add(provider)
        await self.db.commit()
        # Re-fetch with the team relationship eager-loaded so `team_name` can be
        # serialized without a lazy load in the async context.
        return await self._get_or_404(provider.id)

    async def update_provider(
        self,
        provider_id: int,
        user: User,
        *,
        category: ProviderCategory | None = None,
        direction: ProviderDirection | None = None,
        label: str | None = None,
        description: str | None = None,
        base_url: str | None = None,
        config: dict | None = None,
        credential_id: int | None = None,
        is_active: bool | None = None,
        is_default: bool | None = None,
        verify_ssl: bool | None = None,
        priority: int | None = None,
        visibility: ProviderVisibility | None = None,
        team_id: int | None = None,
    ) -> ResourceProvider:
        provider = await self._get_or_404(provider_id)
        await self._ensure_can_mutate(provider, user)

        if category is not None and category != provider.category:
            raise DomainError("Changing a provider's category is not supported", 400)

        if label is not None:
            provider.label = label
        if description is not None:
            provider.description = description
        if base_url is not None:
            provider.base_url = base_url.rstrip("/")
        if config is not None:
            provider.config = config
        if credential_id is not None:
            provider.credential_id = credential_id
        if is_active is not None:
            provider.is_active = is_active
        if verify_ssl is not None:
            provider.verify_ssl = verify_ssl
        if priority is not None:
            provider.priority = priority

        if visibility is not None or team_id is not None:
            await self._apply_visibility(provider, user, visibility, team_id)

        if is_default is True:
            await self._unset_previous_default(provider)

        await self.db.commit()
        return await self._get_or_404(provider.id)

    async def _apply_visibility(
        self,
        provider: ResourceProvider,
        user: User,
        visibility: ProviderVisibility | None,
        team_id: int | None,
    ) -> None:
        """Apply visibility/team_id changes with the same rules as share/unshare."""
        perms = await self._permissions_async(user)
        if "providers:share" not in perms and "providers:read_all" not in perms:
            raise DomainError("Permission denied: 'providers:share' required", 403)

        if provider.category != ProviderCategory.private:
            raise DomainError("Only private providers can change visibility", 400)

        new_visibility = visibility if visibility is not None else provider.visibility
        new_team_id = team_id if team_id is not None else provider.team_id

        if new_visibility == ProviderVisibility.team:
            if new_team_id is None:
                raise DomainError("team_id is required when visibility is 'team'", 422)
            if (
                not await self._is_team_member(new_team_id, user.id)
                and "providers:read_all" not in perms
            ):
                raise DomainError("you must be a member of the target team", 422)
            provider.team_id = new_team_id
        else:
            provider.team_id = None

        provider.visibility = new_visibility

    async def _unset_previous_default(self, provider: ResourceProvider) -> None:
        """Switch ``is_default`` off for the previous default in the same scope."""
        others = (
            (
                await self.db.execute(
                    select(ResourceProvider).where(
                        ResourceProvider.domain == provider.domain,
                        ResourceProvider.subtype == provider.subtype,
                        ResourceProvider.category == provider.category,
                        ResourceProvider.direction == provider.direction,
                        ResourceProvider.is_default.is_(True),
                        ResourceProvider.id != provider.id,
                        ResourceProvider.is_deleted.is_(False),
                    )
                )
            )
            .scalars()
            .all()
        )
        for other in others:
            other.is_default = False
        provider.is_default = True

    async def share_provider(self, provider_id: int, team_id: int, user: User) -> ResourceProvider:
        """Share a provider with a team (12.3): owner + providers:share + member
        of the target team."""
        provider = await self._get_or_404(provider_id)
        perms = await self._permissions_async(user)
        if "providers:share" not in perms and "providers:read_all" not in perms:
            raise DomainError("Permission denied: 'providers:share' required", 403)

        if provider.owner_user_id != user.id and "providers:read_all" not in perms:
            raise DomainError("Access denied: not the owner of this private provider", 403)

        if provider.category != ProviderCategory.private:
            raise DomainError("Only private providers can be shared", 400)

        if provider.visibility == ProviderVisibility.team:
            raise DomainError("Provider is already shared with a team", 409)

        if not await self._is_team_member(team_id, user.id) and "providers:read_all" not in perms:
            raise DomainError("you must be a member of the target team", 422)

        provider.visibility = ProviderVisibility.team
        provider.team_id = team_id
        await self.db.commit()
        return await self._get_or_404(provider.id)

    async def unshare_provider(self, provider_id: int, user: User) -> ResourceProvider:
        """Revert a provider to owner visibility (12.3)."""
        provider = await self._get_or_404(provider_id)
        perms = await self._permissions_async(user)
        if "providers:share" not in perms and "providers:read_all" not in perms:
            raise DomainError("Permission denied: 'providers:share' required", 403)

        if provider.owner_user_id != user.id and "providers:read_all" not in perms:
            raise DomainError("Access denied: not the owner of this private provider", 403)

        if provider.visibility != ProviderVisibility.team:
            raise DomainError("Provider is not shared with a team", 409)

        provider.visibility = ProviderVisibility.owner
        provider.team_id = None
        await self.db.commit()
        return await self._get_or_404(provider.id)

    async def delete_provider(self, provider_id: int, user: User) -> None:
        provider = await self._get_or_404(provider_id)
        await self._ensure_can_mutate(provider, user)

        if provider.is_protected:
            raise DomainError("Protected provider cannot be deleted", 409)

        usage = await self.get_usage(provider_id)
        if usage:
            raise DomainError(f"Provider is in use: {usage}", 409)

        provider.is_deleted = True
        provider.deleted_at = datetime.now(UTC)
        await self.db.commit()

    # ── Usage ───────────────────────────────────────────────────────────

    async def get_usage(self, provider_id: int) -> list[dict[str, int]]:
        """Return consumers referencing ``provider_id``.

        Counts live (non-deleted) rows in every consumer table that links to
        the provider: pipelines, source_repositories (source git providers),
        docker_image_sources (source and target side) and helm_chart_sources.
        """
        from app.models.docker_image_source import DockerImageSource
        from app.models.helm_chart_source import HelmChartSource
        from app.models.pipeline import Pipeline
        from app.models.source_repository import SourceRepository

        usage: list[dict[str, int]] = []

        # (resource, table, column) — soft-deleted rows are excluded where the
        # model supports soft delete (pipelines, source_repositories).
        checks: list[tuple[str, object, object]] = [
            ("pipelines", Pipeline, Pipeline.provider_id),
            ("source_repositories", SourceRepository, SourceRepository.provider_id),
            ("docker_image_sources.source", DockerImageSource, DockerImageSource.provider_id),
            (
                "docker_image_sources.target",
                DockerImageSource,
                DockerImageSource.target_provider_id,
            ),
            ("helm_chart_sources", HelmChartSource, HelmChartSource.provider_id),
        ]

        for resource, model, column in checks:
            stmt = select(func.count()).select_from(model).where(column == provider_id)
            if hasattr(model, "is_deleted"):
                stmt = stmt.where(~model.is_deleted)
            result = await self.db.execute(stmt)
            count = result.scalar_one()
            if count:
                usage.append({"resource": resource, "count": count})

        return usage

    # ── Connection test ─────────────────────────────────────────────────

    async def test_connection(self, provider_id: int, user: User) -> dict:
        provider = await self.get_provider(provider_id, user)
        secret = await self._decrypt_credential_secret(provider.credential_id)

        try:
            result = await self._dispatch_test(provider, secret)
        except Exception as exc:  # noqa: BLE001 — surface as failure status
            provider.status_flag = STATUS_FAILED
            provider.status_text = str(exc)[:500]
            provider.last_checked_at = datetime.now(UTC)
            await self.db.commit()
            return {"ok": False, "status_flag": STATUS_FAILED, "status_text": str(exc)}

        provider.status_flag = STATUS_OK if result.get("ok") else STATUS_FAILED
        provider.status_text = result.get("status_text")
        provider.last_checked_at = datetime.now(UTC)
        await self.db.commit()
        return {
            "ok": bool(result.get("ok")),
            "status_flag": provider.status_flag,
            "status_text": provider.status_text,
        }

    async def _decrypt_credential_secret(self, credential_id: int | None) -> str | None:
        if credential_id is None:
            return None
        credential = await self.db.get(Credential, credential_id)
        if credential is None:
            return None
        return decrypt_secret(credential.encrypted_secret)

    # ── Action dispatch ─────────────────────────────────────────────────

    async def dispatch_action(
        self,
        provider_id: int,
        action: ProviderCapability,
        user: User,
        params: dict | None = None,
    ) -> dict:
        provider = await self.get_provider(provider_id, user)
        spec = get_spec(provider.subtype)
        allowed = spec.allowed_capabilities(provider.category, provider.direction)
        if action.value not in allowed:
            raise DomainError(
                f"action '{action.value}' not allowed for "
                f"{provider.subtype.value}/{provider.category.value}/{provider.direction.value}",
                403,
            )
        secret = await self._decrypt_credential_secret(provider.credential_id)
        params = params or {}
        return await self._dispatch(provider, action, secret, params)

    # ── Client dispatch ─────────────────────────────────────────────────

    async def _dispatch_test(self, provider: ResourceProvider, secret: str | None) -> dict:
        subtype = provider.subtype
        if subtype == ProviderSubtype.github:
            return await GitHubClient(
                api_url=(provider.config or {}).get("api_url", "https://api.github.com"),
                secret=secret,
                verify_ssl=provider.verify_ssl,
            ).test_connection()
        if subtype == ProviderSubtype.gitlab:
            return await GitLabClient(
                base_url=provider.base_url,
                secret=secret,
                verify_ssl=provider.verify_ssl,
            ).test_connection()
        if subtype == ProviderSubtype.generic_git:
            return await GenericGitClient(
                base_url=provider.base_url,
                secret=secret,
                verify_ssl=provider.verify_ssl,
            ).test_connection()
        if subtype == ProviderSubtype.harbor:
            return await HarborClient(
                base_url=provider.base_url,
                secret=secret,
                verify_ssl=provider.verify_ssl,
            ).test_connection()
        if subtype == ProviderSubtype.helm_repo:
            return await HelmRepoClient(
                base_url=provider.base_url,
                secret=secret,
                verify_ssl=provider.verify_ssl,
                index_path=(provider.config or {}).get("index_path", "/index.yaml"),
            ).test_connection()
        # docker subtypes
        return await registry_client_for_subtype(
            subtype.value,
            base_url=provider.base_url,
            secret=secret,
            verify_ssl=provider.verify_ssl,
        ).test_connection()

    async def _dispatch(
        self,
        provider: ResourceProvider,
        action: ProviderCapability,
        secret: str | None,
        params: dict,
    ) -> dict:
        subtype = provider.subtype
        items: list[dict] = []
        if subtype == ProviderSubtype.github:
            client = GitHubClient(
                api_url=(provider.config or {}).get("api_url", "https://api.github.com"),
                secret=secret,
                verify_ssl=provider.verify_ssl,
            )
            if action == ProviderCapability.list_groups:
                items = await client.list_groups()
            elif action == ProviderCapability.list_repositories:
                items = await client.list_repositories(params.get("group_external_id", ""))
            elif action == ProviderCapability.get_commit:
                items = [
                    await client.get_commit(params.get("repo_external_id", ""), params.get("ref"))
                ]
        elif subtype == ProviderSubtype.gitlab:
            client = GitLabClient(
                base_url=provider.base_url, secret=secret, verify_ssl=provider.verify_ssl
            )
            if action == ProviderCapability.list_groups:
                items = await client.list_groups()
            elif action == ProviderCapability.list_repositories:
                items = await client.list_repositories(params.get("group_external_id", ""))
            elif action == ProviderCapability.get_commit:
                items = [
                    await client.get_commit(params.get("repo_external_id", ""), params.get("ref"))
                ]
        elif subtype == ProviderSubtype.generic_git:
            client = GenericGitClient(base_url=provider.base_url, secret=secret)
            if action == ProviderCapability.list_repositories:
                items = await client.list_repositories(params.get("group_external_id", ""))
        elif subtype == ProviderSubtype.harbor:
            client = HarborClient(base_url=provider.base_url, secret=secret)
            if action == ProviderCapability.list_projects:
                items = await client.list_projects()
            elif action == ProviderCapability.list_repositories:
                items = await client.list_repositories(params.get("project_name", ""))
        elif subtype == ProviderSubtype.helm_repo:
            client = HelmRepoClient(
                base_url=provider.base_url,
                secret=secret,
                index_path=(provider.config or {}).get("index_path", "/index.yaml"),
            )
            if action == ProviderCapability.list_charts:
                items = await client.list_charts((provider.config or {}).get("chart_allowlist"))
        else:
            client = registry_client_for_subtype(
                subtype.value, base_url=provider.base_url, secret=secret
            )
            if action == ProviderCapability.list_repositories:
                repos = await client.list_repositories(
                    (provider.config or {}).get("namespace") or (provider.config or {}).get("org")
                )
                items = repos
        return {"action": action.value, "items": items}
