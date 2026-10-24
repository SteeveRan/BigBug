"""
@file test_trust_store_service.py
@description Unit tests for TrustStoreService (ADR-0037, issue #89):
              valid/invalid PEM, fingerprint, multi-PEM chain split,
              duplicate names, 409 usage gate (RESTRICT), usage list.
@dependencies backend/app/services/trust_store.py, backend/tests/conftest.py
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.models.resource_provider import (
    ProviderCategory,
    ProviderDirection,
    ProviderDomain,
    ProviderSubtype,
    ResourceProvider,
)
from app.services.trust_store import TrustStoreService
from tests.unit._trust_certs_fixtures import PEM_CA1, PEM_CA2


def _pem_text(*pems: str) -> str:
    return "\n".join(pems)


class TestCreate:
    async def test_create_ok(self, db_session: AsyncSession):
        svc = TrustStoreService(db_session)
        store = await svc.create_store(name="corp-ca", description="Corporate roots")
        assert store.id is not None
        assert store.name == "corp-ca"

    async def test_duplicate_name_409(self, db_session: AsyncSession):
        svc = TrustStoreService(db_session)
        await svc.create_store(name="dup")
        with pytest.raises(DomainError) as exc:
            await svc.create_store(name="dup")
        assert exc.value.status_code == 409

    async def test_get_missing_404(self, db_session: AsyncSession):
        svc = TrustStoreService(db_session)
        with pytest.raises(DomainError) as exc:
            await svc.get_store(99999)
        assert exc.value.status_code == 404


class TestCertificates:
    async def test_add_valid_certificate(self, db_session: AsyncSession):
        svc = TrustStoreService(db_session)
        store = await svc.create_store(name="s1")
        await svc.add_certificates(store.id, [("root", PEM_CA1)])
        store = await svc.get_store(store.id)
        assert len(store.certificates) == 1
        cert = store.certificates[0]
        assert cert.name == "root"
        assert cert.pem == PEM_CA1
        # SHA-256 hex = 64 lowercase hex chars
        assert len(cert.fingerprint) == 64
        assert cert.fingerprint == cert.fingerprint.lower()
        int(cert.fingerprint, 16)  # valid hex

    async def test_invalid_pem_422(self, db_session: AsyncSession):
        svc = TrustStoreService(db_session)
        store = await svc.create_store(name="s2")
        with pytest.raises(DomainError) as exc:
            await svc.add_certificates(store.id, [("bad", "not a pem")])
        assert exc.value.status_code == 422

    async def test_garbage_block_422(self, db_session: AsyncSession):
        svc = TrustStoreService(db_session)
        store = await svc.create_store(name="s2b")
        garbage = "-----BEGIN CERTIFICATE-----\nZm9vYmFy\n-----END CERTIFICATE-----"
        with pytest.raises(DomainError) as exc:
            await svc.add_certificates(store.id, [("bad", garbage)])
        assert exc.value.status_code == 422

    async def test_chain_of_three_pem_blocks_creates_three_rows(self, db_session: AsyncSession):
        svc = TrustStoreService(db_session)
        store = await svc.create_store(name="chain")
        # 3 certificates: CA1, CA2, CA1 again — unique row names via -N suffix.
        await svc.add_certificates(
            store.id, [("chain", _pem_text(PEM_CA1, PEM_CA2, PEM_CA1))]
        )
        store = await svc.get_store(store.id)
        assert len(store.certificates) == 3
        assert {c.name for c in store.certificates} == {"chain-1", "chain-2", "chain-3"}
        assert all(len(c.fingerprint) == 64 for c in store.certificates)

    async def test_single_block_keeps_plain_name(self, db_session: AsyncSession):
        svc = TrustStoreService(db_session)
        store = await svc.create_store(name="single")
        await svc.add_certificates(store.id, [("root", PEM_CA1)])
        store = await svc.get_store(store.id)
        assert store.certificates[0].name == "root"

    async def test_duplicate_cert_name_409(self, db_session: AsyncSession):
        svc = TrustStoreService(db_session)
        store = await svc.create_store(name="s3")
        await svc.add_certificates(store.id, [("root", PEM_CA1)])
        with pytest.raises(DomainError) as exc:
            await svc.add_certificates(store.id, [("root", PEM_CA2)])
        assert exc.value.status_code == 409

    async def test_delete_one_certificate(self, db_session: AsyncSession):
        svc = TrustStoreService(db_session)
        store = await svc.create_store(name="s4")
        await svc.add_certificates(store.id, [("a", PEM_CA1), ("b", PEM_CA2)])
        store = await svc.get_store(store.id)
        target_id = store.certificates[0].id
        await svc.delete_certificate(store.id, target_id)
        store = await svc.get_store(store.id)
        assert len(store.certificates) == 1
        assert all(c.id != target_id for c in store.certificates)

    async def test_delete_missing_certificate_404(self, db_session: AsyncSession):
        svc = TrustStoreService(db_session)
        store = await svc.create_store(name="s5")
        with pytest.raises(DomainError) as exc:
            await svc.delete_certificate(store.id, 99999)
        assert exc.value.status_code == 404


class TestDeleteUsageGate:
    async def _provider(self, db: AsyncSession, name: str, trust_store_id: int) -> ResourceProvider:
        provider = ResourceProvider(
            domain=ProviderDomain.git,
            subtype=ProviderSubtype.gitlab,
            category=ProviderCategory.public,
            direction=ProviderDirection.external,
            name=name,
            label=name,
            trust_store_id=trust_store_id,
        )
        db.add(provider)
        await db.flush()
        return provider

    async def test_delete_unused_store_ok(self, db_session: AsyncSession):
        svc = TrustStoreService(db_session)
        store = await svc.create_store(name="unused")
        await svc.delete_store(store.id)
        with pytest.raises(DomainError):
            await svc.get_store(store.id)

    async def test_delete_store_with_provider_409_with_names(self, db_session: AsyncSession):
        svc = TrustStoreService(db_session)
        store = await svc.create_store(name="in-use")
        await self._provider(db_session, "gitlab-prod", store.id)
        await self._provider(db_session, "harbor-prod", store.id)
        with pytest.raises(DomainError) as exc:
            await svc.delete_store(store.id)
        assert exc.value.status_code == 409
        assert "gitlab-prod" in str(exc.value)
        assert "harbor-prod" in str(exc.value)

    async def test_usage_lists_only_live_providers(self, db_session: AsyncSession):
        svc = TrustStoreService(db_session)
        store = await svc.create_store(name="usage")
        live = await self._provider(db_session, "live-provider", store.id)
        dead = await self._provider(db_session, "dead-provider", store.id)
        dead.is_deleted = True
        await db_session.flush()

        usage = await svc.get_usage(store.id)
        assert usage == ["live-provider"]
        assert live.trust_store_id == store.id

    async def test_delete_store_soft_deleted_provider_does_not_block(
        self, db_session: AsyncSession
    ):
        svc = TrustStoreService(db_session)
        store = await svc.create_store(name="only-dead")
        dead = await self._provider(db_session, "dead-only", store.id)
        dead.is_deleted = True
        await db_session.flush()
        # Soft-deleted provider does not block (usage gate counts live rows).
        await svc.delete_store(store.id)
        with pytest.raises(DomainError):
            await svc.get_store(store.id)
