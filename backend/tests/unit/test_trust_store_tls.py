"""
@file test_trust_store_tls.py
@description Unit tests for the ADR-0037 TLS injection helper (#90): SSLContext
              from a TrustStore PEM, verify_ssl=False precedence, default
              env/system trust, bundle file cache, and the _dispatch regression
              (verify reaches GenericGitClient/HarborClient).
@dependencies app.services.trust_store_tls, app.services.providers.service
"""

import ssl
from unittest.mock import AsyncMock, patch

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resource_provider import (
    ProviderCategory,
    ProviderDirection,
    ProviderDomain,
    ProviderSubtype,
    ResourceProvider,
)
from app.services.trust_store_tls import (
    provider_httpx_verify,
    provider_ssl_verify,
    resolve_bundle_path,
    ssl_context_for,
)
from tests.unit._trust_certs_fixtures import PEM_CA1


def _real_ca_pem(cn: str = "Test Trust Anchor") -> str:
    """Generate a real CA cert (BasicConstraints CA:TRUE) — OpenSSL only loads
    certs with CA constraints into a trust store; the #89 fixtures lack them
    (they only prove PEM parsing, not trust anchoring)."""
    import datetime

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM).decode()


class TestSslContextFor:
    def test_pem_builds_ssl_context(self):
        ctx = ssl_context_for(True, _real_ca_pem())
        assert isinstance(ctx, ssl.SSLContext)
        # The store's CA is loaded into the context.
        assert ctx.get_ca_certs()

    def test_verify_ssl_false_wins(self):
        assert ssl_context_for(False, _real_ca_pem()) is False

    def test_no_pem_defaults_to_env_or_true(self):
        result = ssl_context_for(True, None)
        # Env bundle path (dev stand) or plain True — never a context.
        assert result is True or isinstance(result, str)


class TestBundlePath:
    async def test_bundle_file_written_and_regenerated(self, db_session: AsyncSession, tmp_path):
        from app.services.trust_store import TrustStoreService

        svc = TrustStoreService(db_session)
        store = await svc.create_store(name="tls-bundle")
        await svc.add_certificates(store.id, [("root", _real_ca_pem("Root A"))])

        with patch("app.services.trust_store_tls.settings") as mock_settings:
            mock_settings.data_dir = str(tmp_path)
            path = await resolve_bundle_path(db_session, store.id)
            assert path is not None
            with open(path) as f:
                assert "BEGIN CERTIFICATE" in f.read()

            # Store content changes → file is regenerated in place.
            await svc.add_certificates(store.id, [("intermediate", _real_ca_pem("Root B"))])
            path2 = await resolve_bundle_path(db_session, store.id)
            assert path2 == path
            with open(path) as f:
                content = f.read()
            assert content.count("BEGIN CERTIFICATE") == 2

    async def test_missing_store_returns_none(self, db_session: AsyncSession):
        assert await resolve_bundle_path(db_session, 987654) is None
        assert await resolve_bundle_path(db_session, None) is None


class TestProviderVerify:
    def _provider(self, **overrides) -> ResourceProvider:
        values = {
            "domain": ProviderDomain.git,
            "subtype": ProviderSubtype.gitlab,
            "category": ProviderCategory.system,
            "direction": ProviderDirection.internal,
            "name": "tls-prov",
            "label": "tls-prov",
        }
        values.update(overrides)
        return ResourceProvider(**values)

    async def test_ssl_verify_false_without_store(self, db_session: AsyncSession):
        assert await provider_ssl_verify(db_session, self._provider(verify_ssl=False)) is False
        assert await provider_httpx_verify(db_session, self._provider(verify_ssl=False)) is False

    async def test_ssl_verify_true_without_store(self, db_session: AsyncSession):
        provider = self._provider(verify_ssl=True, trust_store_id=None)
        assert await provider_ssl_verify(db_session, provider) is True

    async def test_store_gives_bundle_path_and_context(self, db_session: AsyncSession, tmp_path):
        from app.services.trust_store import TrustStoreService

        svc = TrustStoreService(db_session)
        store = await svc.create_store(name="tls-prov-store")
        await svc.add_certificates(store.id, [("root", _real_ca_pem("Root A"))])

        with patch("app.services.trust_store_tls.settings") as mock_settings:
            mock_settings.data_dir = str(tmp_path)
            provider = self._provider(trust_store_id=store.id, verify_ssl=True)
            await db_session.flush()

            ssl_verify = await provider_ssl_verify(db_session, provider)
            assert ssl_verify == f"{tmp_path}/trust_stores/{store.id}.pem"

            httpx_verify = await provider_httpx_verify(db_session, provider)
            assert isinstance(httpx_verify, ssl.SSLContext)

    async def test_verify_ssl_false_ignores_store(self, db_session: AsyncSession):
        provider = self._provider(verify_ssl=False, trust_store_id=42)
        # No store with id=42 exists — if the store were consulted, resolve
        # would log a warning; False must short-circuit either way.
        assert await provider_ssl_verify(db_session, provider) is False
        assert await provider_httpx_verify(db_session, provider) is False


class TestDispatchInjectsVerify:
    """Regression (#90): _dispatch/_dispatch_test must not drop the TLS trust
    for GenericGitClient/HarborClient — previously constructed without
    verify_ssl at all."""

    @staticmethod
    def _provider(subtype: ProviderSubtype, **overrides) -> ResourceProvider:
        domain = (
            ProviderDomain.git
            if subtype in (ProviderSubtype.generic_git,)
            else ProviderDomain.docker
        )
        values = {
            "domain": domain,
            "subtype": subtype,
            "category": ProviderCategory.system,
            "direction": ProviderDirection.internal,
            "name": f"prov-{subtype.value}",
            "label": f"prov-{subtype.value}",
            "base_url": "https://prov.example.com",
        }
        values.update(overrides)
        return ResourceProvider(**values)

    @pytest.mark.parametrize(
        ("subtype", "client_cls"),
        [
            (ProviderSubtype.generic_git, "GenericGitClient"),
            (ProviderSubtype.harbor, "HarborClient"),
        ],
    )
    async def test_dispatch_passes_verify(
        self, db_session: AsyncSession, subtype: ProviderSubtype, client_cls: str
    ):
        from app.models.resource_provider import ProviderCapability
        from app.services.providers.service import ProviderService

        provider = self._provider(subtype, verify_ssl=False)
        db_session.add(provider)
        await db_session.flush()

        svc = ProviderService(db_session)
        action = (
            ProviderCapability.list_repositories
            if subtype == ProviderSubtype.generic_git
            else ProviderCapability.list_projects
        )

        with (
            patch(f"app.services.providers.service.{client_cls}", autospec=True) as mock_cls,
            patch.object(
                ProviderService, "_decrypt_credential_secret", new=AsyncMock(return_value=None)
            ),
        ):
            mock_cls.return_value.list_repositories = AsyncMock(return_value=[])
            mock_cls.return_value.list_projects = AsyncMock(return_value=[])
            if subtype == ProviderSubtype.generic_git:
                await svc._dispatch(provider, action, None, {"group_external_id": "x"})
            else:
                await svc._dispatch(provider, action, None, {})

        # verify_ssl=False must reach the client (as verify=False / ssl_context
        # False) — not be dropped the way it was before #90.
        _, kwargs = mock_cls.call_args
        assert kwargs.get("ssl_context") is False or kwargs.get("verify_ssl") is False

    @pytest.mark.asyncio
    async def test_dispatch_test_passes_store_context(self, db_session: AsyncSession, tmp_path):
        from app.services.providers.service import ProviderService
        from app.services.trust_store import TrustStoreService

        store_svc = TrustStoreService(db_session)
        store = await store_svc.create_store(name="dispatch-store")
        await store_svc.add_certificates(store.id, [("root", PEM_CA1)])

        provider = self._provider(ProviderSubtype.harbor, trust_store_id=store.id)
        db_session.add(provider)
        await db_session.flush()

        with patch("app.services.trust_store_tls.settings") as mock_settings:
            mock_settings.data_dir = str(tmp_path)
            svc = ProviderService(db_session)
            with (
                patch("app.services.providers.service.HarborClient", autospec=True) as mock_cls,
                patch.object(
                    ProviderService, "_decrypt_credential_secret", new=AsyncMock(return_value=None)
                ),
            ):
                mock_cls.return_value.test_connection = AsyncMock(return_value={"ok": True})
                await svc._dispatch_test(provider, None)

        _, kwargs = mock_cls.call_args
        assert isinstance(kwargs.get("ssl_context"), ssl.SSLContext)
