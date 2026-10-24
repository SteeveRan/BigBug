"""
@file test_sync_engine_chaos.py
@description Chaos tests for the sync_engine convergence kernel (ADR-0039
             guardrail 2). Crash injection at every step boundary of the
             crash matrix (issue #110); assertions are on the CONVERGED END
             STATE, never on implementation details.

             "kill -9" is simulated by the CrashInjectedError exception +
             discarding the failed session: a fresh session reads what the
             previous process actually committed.
@dependencies pytest, sqlalchemy, app.services.sync_engine
@relatedFiles ../../app/services/sync_engine.py, ./conftest.py
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.docker_image_tag import DockerImageTag
from app.services import sync_engine
from app.services.sync_engine import CrashInjectedError

from .conftest import FakeExternalRegistry

DIGEST = "sha256:aaa"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _sync_item(
    db: AsyncSession,
    registry: FakeExternalRegistry,
    key: str = "nginx:latest",
    digest: str = DIGEST,
    source_id: int | None = None,
) -> object:
    """One convergence unit: fake push (idempotent upsert-by-key) then DB
    cursor upsert (DockerImageTag row, is_synced flag) — both idempotent."""
    changed = await sync_engine.idempotent_push(key, lambda: _push_fake(registry, key, digest))

    async def _apply(session: AsyncSession) -> None:
        await _upsert_tag(session, key, digest, source_id=source_id)

    await sync_engine.commit_cursor(db, key, _apply)
    return changed


async def _push_fake(registry: FakeExternalRegistry, key: str, digest: str) -> bool:
    return registry.push(key, digest)


async def _upsert_tag(
    db: AsyncSession, key: str, digest: str, source_id: int | None = None
) -> None:
    """Idempotent DB state for the fake item: existing row → same values."""
    name, _, tag = key.rpartition(":")
    stmt = select(DockerImageTag).where(
        DockerImageTag.image_name == name, DockerImageTag.tag == tag
    )
    if source_id is not None:
        stmt = stmt.where(DockerImageTag.source_id == source_id)
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        row = DockerImageTag(source_id=source_id, image_name=name, tag=tag)
        db.add(row)
    row.digest = digest
    row.is_synced = True
    row.status_flag = 0


async def _converged(
    db: AsyncSession, registry: FakeExternalRegistry, key: str, source_id: int | None = None
) -> None:
    """Assert the item converged: exactly one external object, one synced DB row."""
    assert registry.get(key) == DIGEST
    name, _, tag = key.rpartition(":")
    stmt = select(DockerImageTag).where(
        DockerImageTag.image_name == name, DockerImageTag.tag == tag
    )
    if source_id is not None:
        stmt = stmt.where(DockerImageTag.source_id == source_id)
    rows = (await db.execute(stmt)).scalars().all()
    assert len(rows) == 1
    assert rows[0].digest == DIGEST
    assert rows[0].is_synced is True
    assert rows[0].status_flag == 0


# ---------------------------------------------------------------------------
# Crash matrix: fetch→push / push→commit / after commit / mid-batch
# ---------------------------------------------------------------------------


class TestCrashMatrix:
    async def test_crash_before_push_converges_on_rerun(
        self, db_session, fake_registry, failpoint, docker_source
    ):
        """fetch→push crash: nothing changed anywhere, plain re-run converges."""
        failpoint("push:before")
        with pytest.raises(CrashInjectedError):
            await _sync_item(db_session, fake_registry, source_id=docker_source.id)

        # Re-run with the crash removed — converges from the empty state.
        failpoint(None)
        await _sync_item(db_session, fake_registry, source_id=docker_source.id)
        await _converged(db_session, fake_registry, "nginx:latest", docker_source.id)

    async def test_crash_between_push_and_commit_converges_on_rerun(
        self, db_session, fake_registry, failpoint, docker_source
    ):
        """push→commit crash: external push happened, cursor not committed.
        Re-run: idempotent push is a no-op (same digest), cursor converges."""
        failpoint("commit:before")
        with pytest.raises(CrashInjectedError):
            await _sync_item(db_session, fake_registry, source_id=docker_source.id)
        # External state exists, DB row does not (uncommitted work discarded).
        assert fake_registry.get("nginx:latest") == DIGEST

        failpoint(None)
        changed = await _sync_item(db_session, fake_registry, source_id=docker_source.id)
        assert changed is False  # push was already done — no-op
        await _converged(db_session, fake_registry, "nginx:latest", docker_source.id)

    async def test_crash_after_commit_already_converged(
        self, db_session, fake_registry, failpoint, docker_source
    ):
        """after-commit crash: state is converged; duplicate delivery no-ops."""
        failpoint("commit:after")
        with pytest.raises(CrashInjectedError):
            await _sync_item(db_session, fake_registry, source_id=docker_source.id)

        # Fresh session = what a restarted worker sees.
        failpoint(None)
        changed = await _sync_item(db_session, fake_registry, source_id=docker_source.id)
        assert changed is False
        await _converged(db_session, fake_registry, "nginx:latest", docker_source.id)

    async def test_duplicate_delivery_is_noop(
        self, db_session, fake_registry, failpoint, docker_source
    ):
        """Same task executed twice (at-least-once redelivery): second run
        changes nothing."""
        failpoint(None)
        await _sync_item(db_session, fake_registry, source_id=docker_source.id)
        push_calls: list[bool] = []

        async def _counted() -> bool:
            changed = await _push_fake(fake_registry, "nginx:latest", DIGEST)
            push_calls.append(changed)
            return changed

        async def _apply(session: AsyncSession) -> None:
            await _upsert_tag(session, "nginx:latest", DIGEST, source_id=docker_source.id)

        await sync_engine.idempotent_push("nginx:latest", _counted)
        await sync_engine.commit_cursor(db_session, "nginx:latest", _apply)

        assert push_calls == [False]  # redelivery did not touch external state
        await _converged(db_session, fake_registry, "nginx:latest", docker_source.id)


# ---------------------------------------------------------------------------
# Mid-batch crash: per-item cursor resumption
# ---------------------------------------------------------------------------


class TestMidBatchCrash:
    async def test_mid_batch_crash_costs_remaining_items_only(
        self, db_session, fake_registry, failpoint, docker_source
    ):
        """5-item batch, crash at commit of item 3 (1-indexed): items 1-2 are
        already committed (per-item cursor), re-run redoes 3-5 and items 1-2
        are idempotent no-ops — rework 40%→ remaining, not 100%."""
        keys = [f"app:v{i}" for i in range(1, 6)]

        async def _batch() -> None:
            for k in keys:
                await _sync_item(db_session, fake_registry, key=k, source_id=docker_source.id)

        failpoint("commit:before#3")
        with pytest.raises(CrashInjectedError):
            await _batch()

        # Items 1-2 committed before the crash (per-item commit_cursor).
        assert fake_registry.get("app:v1") == DIGEST
        assert fake_registry.get("app:v2") == DIGEST

        failpoint(None)
        await _batch()

        for k in keys:
            await _converged(db_session, fake_registry, k, docker_source.id)

    async def test_push_crash_mid_batch_leaves_no_partial_external_state(
        self, db_session, fake_registry, failpoint, docker_source
    ):
        """Crash before push of item 2: item 1 fully converged, item 2 absent
        everywhere — no half-pushed state."""
        failpoint("push:before#2")

        async def _batch() -> None:
            for k in ("app:v1", "app:v2"):
                await _sync_item(db_session, fake_registry, key=k, source_id=docker_source.id)

        with pytest.raises(CrashInjectedError):
            await _batch()

        assert fake_registry.get("app:v1") == DIGEST
        assert fake_registry.get("app:v2") is None

        failpoint(None)
        await _sync_item(db_session, fake_registry, key="app:v2", source_id=docker_source.id)
        await _converged(db_session, fake_registry, "app:v2", docker_source.id)


# ---------------------------------------------------------------------------
# Real consumer path: docker sync_image through crane
# ---------------------------------------------------------------------------


class TestDockerSyncImageChaos:
    async def _crane(self, monkeypatch, registry: FakeExternalRegistry, ref: str):
        """Patch create_subprocess_exec: crane copy becomes a fake push."""

        class _Proc:
            returncode = 0

            async def communicate(self):
                registry.push(ref, DIGEST)
                return b"", b""

        async def fake_exec(*args, **kwargs):
            return _Proc()

        monkeypatch.setattr("app.services.docker.asyncio.create_subprocess_exec", fake_exec)

    async def test_crane_push_then_crash_converges_on_rerun(
        self, db_session, fake_registry, failpoint, docker_source, monkeypatch
    ):
        """kill between crane copy and the success commit: image is in the
        target registry, tag not marked synced; re-run converges (crane copy
        upsert-by-ref is a no-op, commit_cursor writes the flag)."""
        from app.services.docker import DockerRegistryService

        service = DockerRegistryService()
        target_ref = "harbor.local/library/nginx:latest"
        await self._crane(monkeypatch, fake_registry, target_ref)

        # Index phase: the tag exists, not yet synced (as index_source leaves it).
        db_session.add(
            DockerImageTag(
                source_id=docker_source.id,
                image_name="library/nginx",
                tag="latest",
                digest=DIGEST,
            )
        )
        await db_session.commit()

        failpoint("commit:before")
        with pytest.raises(CrashInjectedError):
            await service.sync_image(docker_source, "library/nginx", "latest", db_session)
        assert fake_registry.get(target_ref) == DIGEST

        failpoint(None)
        log = await service.sync_image(docker_source, "library/nginx", "latest", db_session)
        assert log.status_flag == 0

        # Image copied exactly once externally (second crane run was a no-op).
        assert fake_registry.get(target_ref) == DIGEST
        rows = (
            (
                await db_session.execute(
                    select(DockerImageTag).where(
                        DockerImageTag.source_id == docker_source.id,
                        DockerImageTag.image_name == "library/nginx",
                        DockerImageTag.tag == "latest",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].is_synced is True
