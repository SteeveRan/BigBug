"""
@file test_cosign_service.py
@description Unit tests for CosignService — sign_image() and verify_image()
             with mocked subprocess calls.
@dependencies pytest, pytest-asyncio, backend/tests/conftest.py
@relatedFiles ../../app/services/cosign.py, ../../app/models/image_version.py
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.image_version import ImageVersion
from app.services.cosign import CosignService

# ──────────────────────────────────────────────────────────────────────
# sign_image
# ──────────────────────────────────────────────────────────────────────


class TestCosignServiceSignImage:
    """Tests for CosignService.sign_image()"""

    async def _create_image_version(self, db_session: AsyncSession) -> ImageVersion:
        """Create a test ImageVersion record."""
        version = ImageVersion(
            image_type="gold",
            version_tag="1.0.0",
            arch="amd64",
            registry_url="registry.example.com",
            sha256_digest="sha256:abc123",
            is_signed=False,
        )
        db_session.add(version)
        await db_session.commit()
        await db_session.refresh(version)
        return version

    @pytest.mark.asyncio
    async def test_sign_image_success(self, db_session: AsyncSession):
        """sign_image marks version as signed when cosign succeeds."""
        version = await self._create_image_version(db_session)
        image_ref = "registry.example.com/myimage:1.0.0"

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"tlog entry created", b""))

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_process

            result = await CosignService.sign_image(
                db_session,
                version.id,
                image_ref,
                cosign_private_key="fake-private-key",
            )

        assert result["signed"] is True
        assert result["image"] == image_ref

        # Verify DB was updated
        await db_session.refresh(version)
        assert version.is_signed is True
        assert version.cosign_signature == image_ref

    @pytest.mark.asyncio
    async def test_sign_image_cosign_not_found(self, db_session: AsyncSession):
        """sign_image falls back gracefully when cosign not installed."""
        version = await self._create_image_version(db_session)
        image_ref = "registry.example.com/myimage:1.0.0"

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock,
            side_effect=FileNotFoundError("No such file: cosign"),
        ):
            result = await CosignService.sign_image(
                db_session,
                version.id,
                image_ref,
                cosign_private_key="fake-private-key",
            )

        assert result["signed"] is True
        assert result["image"] == image_ref
        assert "note" in result
        assert "simulated" in result["note"]

        # Verify DB was still marked as signed (dev fallback)
        await db_session.refresh(version)
        assert version.is_signed is True
        assert version.cosign_signature == f"simulated:{image_ref}"

    @pytest.mark.asyncio
    async def test_sign_image_cosign_failure(self, db_session: AsyncSession):
        """sign_image raises RuntimeError when cosign returns non-zero."""
        version = await self._create_image_version(db_session)
        image_ref = "registry.example.com/myimage:1.0.0"

        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"Error: signing failed"))

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_process

            with pytest.raises(RuntimeError, match="Cosign signing failed"):
                await CosignService.sign_image(
                    db_session,
                    version.id,
                    image_ref,
                    cosign_private_key="fake-private-key",
                )

        # Verify DB was NOT marked as signed
        await db_session.refresh(version)
        assert version.is_signed is False


# ──────────────────────────────────────────────────────────────────────
# verify_image
# ──────────────────────────────────────────────────────────────────────


class TestCosignServiceVerifyImage:
    """Tests for CosignService.verify_image()"""

    async def _create_image_version(self, db_session: AsyncSession) -> ImageVersion:
        version = ImageVersion(
            image_type="gold",
            version_tag="2.0.0",
            arch="amd64",
            registry_url="registry.example.com",
            sha256_digest="sha256:def456",
            is_signed=True,
            cosign_signature="registry.example.com/myimage:2.0.0",
        )
        db_session.add(version)
        await db_session.commit()
        await db_session.refresh(version)
        return version

    @pytest.mark.asyncio
    async def test_verify_image_success(self, db_session: AsyncSession):
        """verify_image returns verified=True when cosign succeeds."""
        version = await self._create_image_version(db_session)
        image_ref = "registry.example.com/myimage:2.0.0"

        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"Verification successful", b""))

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_process

            result = await CosignService.verify_image(
                db_session,
                version.id,
                image_ref,
                cosign_public_key="fake-public-key",
            )

        assert result["verified"] is True
        assert result["image"] == image_ref

    @pytest.mark.asyncio
    async def test_verify_image_failure(self, db_session: AsyncSession):
        """verify_image returns verified=False when cosign fails."""
        version = await self._create_image_version(db_session)
        image_ref = "registry.example.com/myimage:2.0.0"

        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.communicate = AsyncMock(return_value=(b"", b"Error: no matching signatures"))

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = mock_process

            result = await CosignService.verify_image(
                db_session,
                version.id,
                image_ref,
                cosign_public_key="fake-public-key",
            )

        assert result["verified"] is False

    @pytest.mark.asyncio
    async def test_verify_image_cosign_not_found(self, db_session: AsyncSession):
        """verify_image returns error when cosign not installed."""
        version = await self._create_image_version(db_session)
        image_ref = "registry.example.com/myimage:2.0.0"

        with patch(
            "asyncio.create_subprocess_exec",
            new_callable=AsyncMock,
            side_effect=FileNotFoundError("No such file: cosign"),
        ):
            result = await CosignService.verify_image(
                db_session,
                version.id,
                image_ref,
                cosign_public_key="fake-public-key",
            )

        assert result["verified"] is False
        assert "error" in result
        assert "not available" in result["error"]
