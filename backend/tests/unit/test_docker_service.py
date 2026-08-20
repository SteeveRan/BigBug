"""
@file test_docker_service.py
@description Unit tests for DockerRegistryService — import_source_from_url,
             index_source, _fetch_tags, _resolve_manifest_digest,
             _normalize_registry_url.
"""

import asyncio
import os
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ExternalServiceError
from app.core.secrets import encrypt_secret
from app.models.credential import Credential, CredentialType
from app.models.docker_image_source import DockerImageSource
from app.models.docker_image_tag import DockerImageTag
from app.models.resource_provider import (
    ProviderCategory,
    ProviderDirection,
    ProviderDomain,
    ProviderSubtype,
    ResourceProvider,
)
from app.services.docker import (
    DockerRegistryService,
    _normalize_registry_url,
    _validate_registry_url,
    find_matching_docker_provider,
    get_compatible_docker_providers,
    get_internal_docker_targets,
)

FAKE_TAGS_RESPONSE = {
    "name": "library/nginx",
    "tags": ["1.27-alpine", "1.26", "latest"],
}


@pytest.fixture
def docker_service() -> DockerRegistryService:
    return DockerRegistryService()


# ─── _normalize_registry_url ────────────────────────────────────────────────


class TestNormalizeRegistryUrl:
    def test_adds_v2_when_missing(self):
        assert _normalize_registry_url("https://registry-1.docker.io") == (
            "https://registry-1.docker.io/v2"
        )

    def test_strips_trailing_slash_then_adds_v2(self):
        assert _normalize_registry_url("https://registry.example.com/") == (
            "https://registry.example.com/v2"
        )

    def test_preserves_existing_v2_suffix(self):
        url = "https://registry.local/v2"
        assert _normalize_registry_url(url) == url


# ─── _validate_registry_url ─────────────────────────────────────────────────


class TestValidateRegistryUrl:
    def test_valid_url(self):
        _validate_registry_url("https://registry.example.com")

    def test_invalid_no_scheme(self):
        with pytest.raises(BadRequestError, match="must start with http"):
            _validate_registry_url("ftp://registry.local")


# ─── repository_path_from_ref ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("image_name", "expected"),
    [
        ("nginx", "library/nginx"),
        ("library/nginx", "library/nginx"),
        ("nginx:1.25", "library/nginx"),
        ("docker.io/library/nginx:1.25", "library/nginx"),
        ("registry-1.docker.io/library/nginx:latest", "library/nginx"),
        ("quay.io/prom/node-exporter:v1.0", "prom/node-exporter"),
        ("harbor.local:443/bigbug/nginx", "bigbug/nginx"),
        ("ghcr.io/org/img@sha256:abc", "org/img"),
        ("", ""),
        ("Docker.io/Library/Nginx", "Library/Nginx"),
    ],
)
def test_repository_path_from_ref(image_name, expected):
    from app.services.docker import repository_path_from_ref

    assert repository_path_from_ref(image_name) == expected


@pytest.mark.parametrize(
    ("image_name", "expected"),
    [
        ("nginx:1.25", "1.25"),
        ("library/nginx", "latest"),
        ("nginx@sha256:abc", "latest"),
        ("nginx", "latest"),
    ],
)
def test_ref_tag(image_name, expected):
    from app.services.docker import ref_tag

    assert ref_tag(image_name) == expected


# ─── _resolve_manifest_digest ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolve_manifest_digest(docker_service):
    """A 200 HEAD response with docker-content-digest returns the digest."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"docker-content-digest": "sha256:abc123"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        digest = await docker_service._resolve_manifest_digest(
            client, "https://registry.local/v2", "library/nginx", "latest"
        )
    assert digest == "sha256:abc123"


@pytest.mark.asyncio
async def test_resolve_manifest_digest_404(docker_service):
    """A 404 response returns None."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        digest = await docker_service._resolve_manifest_digest(
            client, "https://registry.local/v2", "missing/image", "latest"
        )
    assert digest is None


# ─── _fetch_tags ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@patch("app.services.docker.oci_request")
async def test_fetch_tags_success(mock_oci, docker_service):
    """_fetch_tags normalizes the ref and returns the parsed JSON response."""
    url = "https://registry.local/v2/library/nginx/tags/list"
    mock_oci.return_value = httpx.Response(
        200, json=FAKE_TAGS_RESPONSE, request=httpx.Request("GET", url)
    )

    tags_data = await docker_service._fetch_tags("https://registry.local/v2", "nginx:latest")

    assert tags_data == FAKE_TAGS_RESPONSE
    assert url in mock_oci.call_args.args[2]


@pytest.mark.asyncio
@patch("app.services.docker.oci_request")
async def test_fetch_tags_404(mock_oci, docker_service):
    """A non-200 response raises ExternalServiceError."""
    url = "https://registry.local/v2/nonexistent/tags/list"
    mock_oci.return_value = httpx.Response(404, request=httpx.Request("GET", url))

    with pytest.raises(ExternalServiceError, match="Docker registry"):
        await docker_service._fetch_tags("https://registry.local/v2", "nonexistent")


@pytest.mark.asyncio
@patch("app.services.docker.oci_request")
async def test_fetch_tags_no_tags_key(mock_oci, docker_service):
    """A response without 'tags' raises ExternalServiceError."""
    url = "https://registry.local/v2/no-tags-image/tags/list"
    mock_oci.return_value = httpx.Response(
        200, json={"other": "data"}, request=httpx.Request("GET", url)
    )

    with pytest.raises(ExternalServiceError, match="tags"):
        await docker_service._fetch_tags("https://registry.local/v2", "no-tags-image")


# ─── index_source ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_index_source_creates_tags(docker_service, db_session: AsyncSession):
    """index_source fetches tags and creates DockerImageTag records."""
    source = DockerImageSource(
        name="docker-test-source",
        registry_url="https://registry.local/v2",
    )
    db_session.add(source)
    await db_session.commit()

    with patch.object(docker_service, "_fetch_tags") as mock_fetch:
        mock_fetch.return_value = {
            "name": "library/nginx",
            "tags": ["1.27-alpine", "latest"],
        }

        # Also need to mock _resolve_manifest_digest since index_source calls it
        with patch.object(docker_service, "_resolve_manifest_digest") as mock_digest:
            mock_digest.return_value = "sha256:test-digest"

            sync_log = await docker_service.index_source(source, "library/nginx", db_session)

    assert sync_log.status_flag == 0  # success
    assert source.status_flag == 0

    result = await db_session.execute(
        select(DockerImageTag).where(DockerImageTag.source_id == source.id)
    )
    tags = result.scalars().all()
    assert len(tags) == 2
    tag_names = {t.tag for t in tags}
    assert tag_names == {"1.27-alpine", "latest"}


@pytest.mark.asyncio
async def test_sync_tags_idempotent(docker_service, db_session: AsyncSession):
    """Re-indexing the same image updates existing tags instead of duplicating."""
    source = DockerImageSource(
        name="idempotent-docker",
        registry_url="https://registry.local/v2",
    )
    db_session.add(source)
    await db_session.commit()

    tags_data = {"name": "library/nginx", "tags": ["1.27-alpine"]}

    # First sync
    with (
        patch.object(docker_service, "_fetch_tags", return_value=tags_data),
        patch.object(docker_service, "_resolve_manifest_digest", return_value="sha256:old"),
    ):
        await docker_service.index_source(source, "library/nginx", db_session)

    # Second sync with updated digest
    with (
        patch.object(docker_service, "_fetch_tags", return_value=tags_data),
        patch.object(docker_service, "_resolve_manifest_digest", return_value="sha256:new"),
    ):
        await docker_service.index_source(source, "library/nginx", db_session)

    result = await db_session.execute(
        select(DockerImageTag).where(DockerImageTag.source_id == source.id)
    )
    tags = result.scalars().all()
    assert len(tags) == 1
    assert tags[0].digest == "sha256:new"


@pytest.mark.asyncio
async def test_index_source_fetch_failure(docker_service, db_session: AsyncSession):
    """When _fetch_tags fails, source and log are marked as failed."""
    source = DockerImageSource(
        name="fail-docker-source",
        registry_url="https://registry.local/v2",
    )
    db_session.add(source)
    await db_session.commit()

    with patch.object(docker_service, "_fetch_tags") as mock_fetch:
        mock_fetch.side_effect = ExternalServiceError("Docker registry", "network error")
        sync_log = await docker_service.index_source(source, "library/nginx", db_session)

    assert sync_log.status_flag == 1  # failed
    assert source.status_flag == 1


# ─── import_source_from_url ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_import_source_from_url_no_image(docker_service, db_session: AsyncSession):
    """Creating a source without image_name succeeds without indexing."""
    source = await docker_service.import_source_from_url(
        "registry-only",
        "https://registry.example.com",
        image_name=None,
        db=db_session,
    )

    assert source.name == "registry-only"
    assert source.registry_url == "https://registry.example.com/v2"
    assert source.status_flag == 4  # pending (no indexing happened)


@pytest.mark.asyncio
async def test_import_source_from_url_with_image(docker_service, db_session: AsyncSession):
    """Creating a source with image_name triggers indexing."""
    with patch.object(docker_service, "_fetch_tags") as mock_fetch:
        mock_fetch.return_value = {"name": "library/alpine", "tags": ["3.19"]}
        with patch.object(docker_service, "_resolve_manifest_digest", return_value="sha256:abc"):
            source = await docker_service.import_source_from_url(
                "alpine-registry",
                "https://registry.example.com",
                image_name="library/alpine",
                db=db_session,
            )

    assert source.name == "alpine-registry"
    assert source.status_flag == 0  # success after indexing


@pytest.mark.asyncio
async def test_import_source_duplicate_name(docker_service, db_session: AsyncSession):
    """Creating a source with a duplicate name raises BadRequestError."""
    source = DockerImageSource(name="dupe-docker", registry_url="https://registry.local/v2")
    db_session.add(source)
    await db_session.commit()

    with pytest.raises(BadRequestError, match="already exists"):
        await docker_service.import_source_from_url(
            "dupe-docker",
            "https://registry.other.com",
            image_name=None,
            db=db_session,
        )


# ─── Registry provider matching (phase 7C) ──────────────────────────────────


async def _docker_provider(
    db_session: AsyncSession,
    *,
    name: str,
    subtype: ProviderSubtype,
    base_url: str | None,
    priority: int = 0,
    direction: ProviderDirection = ProviderDirection.external,
    is_default: bool = False,
) -> ResourceProvider:
    provider = ResourceProvider(
        domain=ProviderDomain.docker,
        subtype=subtype,
        category=ProviderCategory.public,
        direction=direction,
        name=name,
        label=name,
        base_url=base_url,
        priority=priority,
        is_default=is_default,
    )
    db_session.add(provider)
    await db_session.commit()
    await db_session.refresh(provider)
    return provider


class TestRegistryProviderMatching:
    @pytest.mark.asyncio
    async def test_matches_exact_host_first(self, db_session: AsyncSession):
        """Exact base_url host match wins over subtype/priority matches."""
        await _docker_provider(
            db_session,
            name="quay-default",
            subtype=ProviderSubtype.quay,
            base_url="https://quay.io",
            priority=100,
        )
        exact = await _docker_provider(
            db_session,
            name="my-registry",
            subtype=ProviderSubtype.generic_registry,
            base_url="https://myregistry.example.com",
            priority=0,
        )

        matched = await find_matching_docker_provider(
            db_session, "myregistry.example.com", "generic"
        )
        assert matched is not None
        assert matched.id == exact.id

    @pytest.mark.asyncio
    async def test_matches_subtype_when_no_host_match(self, db_session: AsyncSession):
        """When no host matches, a provider with the detected subtype is returned."""
        provider = await _docker_provider(
            db_session,
            name="quay",
            subtype=ProviderSubtype.quay,
            base_url="https://quay.io",
            priority=0,
        )

        matched = await find_matching_docker_provider(
            db_session, "some.unknown.registry", "quay_io"
        )
        assert matched is not None
        assert matched.id == provider.id

    @pytest.mark.asyncio
    async def test_falls_back_to_highest_priority_external(self, db_session: AsyncSession):
        """With no host/subtype match, the highest-priority external provider wins."""
        low = await _docker_provider(
            db_session,
            name="generic-low",
            subtype=ProviderSubtype.generic_registry,
            base_url="https://low.example.com",
            priority=1,
        )
        high = await _docker_provider(
            db_session,
            name="generic-high",
            subtype=ProviderSubtype.generic_registry,
            base_url="https://high.example.com",
            priority=50,
        )

        matched = await find_matching_docker_provider(db_session, "unknown.example.com", None)
        assert matched is not None
        assert matched.id == high.id
        assert matched.id != low.id

    @pytest.mark.asyncio
    async def test_get_compatible_returns_subtype_and_host_matches(self, db_session: AsyncSession):
        """Compatible list includes exact host and subtype matches, sorted by priority."""
        await _docker_provider(
            db_session,
            name="quay",
            subtype=ProviderSubtype.quay,
            base_url="https://quay.io",
            priority=0,
        )
        exact = await _docker_provider(
            db_session,
            name="generic",
            subtype=ProviderSubtype.generic_registry,
            base_url="https://myregistry.example.com",
            priority=0,
        )

        compatible = await get_compatible_docker_providers(
            db_session, "myregistry.example.com", "generic"
        )
        ids = [p.id for p in compatible]
        assert exact.id in ids


# ─── get_internal_docker_targets ─────────────────────────────────────────────


class TestGetInternalDockerTargets:
    @pytest.mark.asyncio
    async def test_filters_internal_harbor_and_generic_only(self, db_session: AsyncSession):
        """Only active, non-deleted, internal harbor/generic_registry rows match."""
        harbor = await _docker_provider(
            db_session,
            name="harbor-target",
            subtype=ProviderSubtype.harbor,
            base_url="https://harbor.local",
            direction=ProviderDirection.internal,
        )
        generic = await _docker_provider(
            db_session,
            name="generic-target",
            subtype=ProviderSubtype.generic_registry,
            base_url="https://mirror.local",
            direction=ProviderDirection.internal,
        )
        external_hub = await _docker_provider(
            db_session,
            name="dockerhub-source",
            subtype=ProviderSubtype.docker_hub,
            base_url="https://registry-1.docker.io",
            direction=ProviderDirection.external,
        )
        internal_quay = await _docker_provider(
            db_session,
            name="quay-internal",
            subtype=ProviderSubtype.quay,
            base_url="https://quay.io",
            direction=ProviderDirection.internal,
        )

        targets = await get_internal_docker_targets(db_session)
        ids = {t.id for t in targets}

        assert harbor.id in ids
        assert generic.id in ids
        assert external_hub.id not in ids
        assert internal_quay.id not in ids

    @pytest.mark.asyncio
    async def test_sorted_by_priority_desc_then_name(self, db_session: AsyncSession):
        """Targets are sorted by ``(-priority, name)``."""
        low = await _docker_provider(
            db_session,
            name="a-low",
            subtype=ProviderSubtype.harbor,
            base_url="https://low.local",
            direction=ProviderDirection.internal,
            priority=1,
        )
        high = await _docker_provider(
            db_session,
            name="z-high",
            subtype=ProviderSubtype.harbor,
            base_url="https://high.local",
            direction=ProviderDirection.internal,
            priority=100,
        )
        # Same priority as high, but sorts before by name.
        high_same_priority = await _docker_provider(
            db_session,
            name="a-high",
            subtype=ProviderSubtype.generic_registry,
            base_url="https://high2.local",
            direction=ProviderDirection.internal,
            priority=100,
        )

        targets = await get_internal_docker_targets(db_session)
        names = [t.name for t in targets]

        assert names.index(high_same_priority.name) < names.index(high.name)
        assert names.index(high.name) < names.index(low.name)


# ─── mirror_image ────────────────────────────────────────────────────────────


class _FakeProcess:
    def __init__(self, returncode: int, stdout: bytes, stderr: bytes) -> None:
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self) -> tuple[bytes, bytes]:
        return self._stdout, self._stderr


class TestMirrorImage:
    async def _make_source(
        self,
        db_session: AsyncSession,
        *,
        name: str,
        target_registry_url: str | None = "https://harbor.local",
        target_provider_id: int | None = None,
    ) -> DockerImageSource:
        source = DockerImageSource(
            name=name,
            registry_url="https://registry-1.docker.io/v2",
            target_registry_url=target_registry_url,
            target_provider_id=target_provider_id,
        )
        db_session.add(source)
        await db_session.commit()
        await db_session.refresh(source)
        return source

    @pytest.mark.asyncio
    async def test_success_builds_refs_without_v2(
        self, docker_service, db_session: AsyncSession, monkeypatch
    ):
        """crane argv uses refs without the /v2 suffix; rc=0 marks success."""
        source = await self._make_source(db_session, name="mirror-ok")
        captured: dict = {}

        async def fake_exec(*args, **kwargs):
            captured["args"] = args
            return _FakeProcess(0, b"", b"")

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

        log = await docker_service.mirror_image(source, "library/nginx", "latest", db_session)

        assert log.status_flag == 0
        assert captured["args"] == (
            "crane",
            "copy",
            "registry-1.docker.io/library/nginx:latest",
            "harbor.local/library/nginx:latest",
        )
        assert all("/v2" not in arg for arg in captured["args"])
        assert all("://" not in arg for arg in captured["args"])

    @pytest.mark.asyncio
    async def test_failure_marks_log_failed(
        self, docker_service, db_session: AsyncSession, monkeypatch
    ):
        """A non-zero crane exit records the stderr output and marks failed."""
        source = await self._make_source(db_session, name="mirror-fail")

        async def fake_exec(*args, **kwargs):
            return _FakeProcess(1, b"", b"manifest unknown")

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

        log = await docker_service.mirror_image(source, "nginx", "1.25", db_session)

        assert log.status_flag == 1
        assert log.log_output == "manifest unknown"

    @pytest.mark.asyncio
    async def test_missing_crane_raises_external_service_error(
        self, docker_service, db_session: AsyncSession, monkeypatch
    ):
        """FileNotFoundError from subprocess maps to ExternalServiceError."""
        source = await self._make_source(db_session, name="mirror-no-crane")

        async def fake_exec(*args, **kwargs):
            raise FileNotFoundError("crane")

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

        with pytest.raises(ExternalServiceError, match="crane"):
            await docker_service.mirror_image(source, "nginx", "latest", db_session)

    @pytest.mark.asyncio
    async def test_insecure_flag_when_target_verify_ssl_false(
        self, docker_service, db_session: AsyncSession, monkeypatch
    ):
        """``--insecure`` is appended when the target provider disables TLS."""
        target = await _docker_provider(
            db_session,
            name="harbor-insecure",
            subtype=ProviderSubtype.harbor,
            base_url="https://harbor.local",
            direction=ProviderDirection.internal,
        )
        target.verify_ssl = False
        await db_session.commit()

        source = await self._make_source(
            db_session, name="mirror-insecure", target_provider_id=target.id
        )
        captured: dict = {}

        async def fake_exec(*args, **kwargs):
            captured["args"] = args
            return _FakeProcess(0, b"", b"")

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

        await docker_service.mirror_image(source, "nginx", "1.25", db_session)
        assert "--insecure" in captured["args"]

    @pytest.mark.asyncio
    async def test_writes_docker_config_and_removes_it(
        self, docker_service, db_session: AsyncSession, monkeypatch
    ):
        """Secrets land in a 0600 config.json via DOCKER_CONFIG, then are removed."""
        credential = Credential(
            name="harbor-robot",
            credential_type=CredentialType.https_basic,
            provider="harbor",
            username="robot$bigbug",
            encrypted_secret=encrypt_secret("sekret"),
        )
        db_session.add(credential)
        await db_session.commit()
        await db_session.refresh(credential)

        target = await _docker_provider(
            db_session,
            name="harbor-cred",
            subtype=ProviderSubtype.harbor,
            base_url="https://harbor.local",
            direction=ProviderDirection.internal,
        )
        target.credential_id = credential.id
        await db_session.commit()

        source = await self._make_source(
            db_session, name="mirror-creds", target_provider_id=target.id
        )
        captured: dict = {}

        async def fake_exec(*args, **kwargs):
            captured["kwargs"] = kwargs
            return _FakeProcess(0, b"", b"")

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

        await docker_service.mirror_image(source, "nginx", "latest", db_session)

        env = captured["kwargs"]["env"]
        assert "DOCKER_CONFIG" in env
        assert not os.path.isdir(env["DOCKER_CONFIG"])
