"""
@file harbor_scan.py
@description Harbor vulnerability scanning service — triggers scans and fetches
             results for Docker image artifacts stored in Harbor registries.
             Updates ImageVersion.vulnerabilities / vulnerability_severity.
@dependencies httpx, app.core.secrets (decrypt_secret),
              app.models.image_version, app.models.harbor_instance
@relatedFiles ../models/image_version.py, ../models/harbor_instance.py,
              ../api/gold_images.py, ../api/app_images.py
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.secrets import decrypt_secret
from app.models.harbor_instance import HarborInstance
from app.models.image_version import ImageVersion

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status flag constants (mirrors integrations.py)
# ---------------------------------------------------------------------------
STATUS_IN_PROGRESS = 3
STATUS_OK = 0
STATUS_FAILED = 1

# Ordered severity levels: 0 = clean, 5 = critical
_SEVERITY_RANK: dict[str, int] = {
    "none": 0,
    "negligible": 1,
    "low": 2,
    "medium": 3,
    "high": 4,
    "critical": 5,
}


def _worst_severity(counts: dict[str, int]) -> str:
    """
    Determine the worst severity present given a mapping of
    severity label → count. Returns 'none' when no vulnerabilities exist.
    """
    worst = "none"
    worst_rank = 0
    for sev, rank in _SEVERITY_RANK.items():
        if counts.get(sev, 0) > 0 and rank > worst_rank:
            worst = sev
            worst_rank = rank
    return worst


def _parse_scan_overview(
    artifact: dict[str, Any],
) -> dict[str, int] | None:
    """
    Extract vulnerability summary from a Harbor artifact payload.

    Harbor nests the summary under::

        artifact["scan_overview"]
          ["application/vnd.security.vulnerability.report; version=1.1"]
          ["summary"]["summary"]

    Returns a dict like
    ``{"Critical": 0, "High": 2, "Medium": 5, "Low": 1, "Negligible": 0}``
    or ``None`` when no scan data is available.
    """
    try:
        scan_overview = artifact.get("scan_overview")
        if not scan_overview:
            return None
        # Harbor may use different MIME keys; try the standard one first
        for mime_key, report in scan_overview.items():
            if "vulnerability" in mime_key.lower():
                summary = report.get("summary", {}).get("summary") or report.get("summary", {})
                if summary:
                    return summary
        return None
    except KeyError, TypeError, AttributeError:
        logger.debug("Failed to parse scan_overview from artifact payload", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Harbor HTTP client helper
# ---------------------------------------------------------------------------


async def _get_harbor_client(harbor_instance: HarborInstance) -> httpx.AsyncClient:
    """Create an authenticated httpx AsyncClient for a Harbor instance."""
    password = decrypt_secret(harbor_instance.password)
    return httpx.AsyncClient(
        base_url=harbor_instance.url.rstrip("/"),
        auth=(harbor_instance.username, password),
        verify=harbor_instance.verify_ssl,
        timeout=30.0,
    )


# ---------------------------------------------------------------------------
# HarborScanService
# ---------------------------------------------------------------------------


class HarborScanService:
    """Service for triggering and fetching Harbor vulnerability scans."""

    @staticmethod
    async def scan_image(
        db: AsyncSession,
        image_version_id: int,
        harbor_instance_id: int,
        project_name: str,
        repository_name: str,
        artifact_digest: str,
    ) -> dict[str, Any]:
        """
        Trigger a Harbor vulnerability scan for an image artifact.

        Uses Harbor API:
        ``POST /api/v2.0/projects/{project}/repositories/{repo}/artifacts/{digest}/scan``
        """
        # Fetch and validate ImageVersion
        result = await db.execute(select(ImageVersion).where(ImageVersion.id == image_version_id))
        image_version = result.scalar_one_or_none()
        if image_version is None:
            raise NotFoundError(f"Image version with id={image_version_id} not found")

        # Fetch Harbor instance
        result = await db.execute(
            select(HarborInstance).where(HarborInstance.id == harbor_instance_id)
        )
        harbor_instance = result.scalar_one_or_none()
        if harbor_instance is None:
            raise NotFoundError(f"Harbor instance with id={harbor_instance_id} not found")

        # Trigger scan via Harbor API
        async with await _get_harbor_client(harbor_instance) as client:
            scan_url = (
                f"/api/v2.0/projects/{project_name}"
                f"/repositories/{repository_name}"
                f"/artifacts/{artifact_digest}/scan"
            )
            logger.info("Triggering Harbor scan: %s", scan_url)
            resp = await client.post(scan_url)

            if not resp.is_success:
                logger.error(
                    "Harbor scan trigger failed: HTTP %s — %s",
                    resp.status_code,
                    resp.text[:500],
                )
                raise RuntimeError(
                    f"Harbor scan trigger failed (HTTP {resp.status_code}): {resp.text[:300]}"
                )

        # Update image version status
        image_version.status_flag = STATUS_IN_PROGRESS
        image_version.status_text = "Scanning"
        await db.commit()

        return {
            "status": "scanning",
            "message": "Scan triggered successfully",
        }

    @staticmethod
    async def get_scan_results(
        db: AsyncSession,
        image_version_id: int,
        harbor_instance_id: int,
        project_name: str,
        repository_name: str,
        artifact_digest: str,
    ) -> dict[str, Any]:
        """
        Fetch vulnerability scan results from Harbor.

        Uses Harbor API:
        ``GET /api/v2.0/projects/{project}/repositories/{repo}/artifacts/{reference}``
        with ``?with_scan_overview=true`` query parameter.

        Parses the ``scan_overview`` block and updates ``ImageVersion``.
        """
        # Fetch and validate ImageVersion
        result = await db.execute(select(ImageVersion).where(ImageVersion.id == image_version_id))
        image_version = result.scalar_one_or_none()
        if image_version is None:
            raise NotFoundError(f"Image version with id={image_version_id} not found")

        # Fetch Harbor instance
        result = await db.execute(
            select(HarborInstance).where(HarborInstance.id == harbor_instance_id)
        )
        harbor_instance = result.scalar_one_or_none()
        if harbor_instance is None:
            raise NotFoundError(f"Harbor instance with id={harbor_instance_id} not found")

        # Get artifact with scan overview
        async with await _get_harbor_client(harbor_instance) as client:
            artifact_url = (
                f"/api/v2.0/projects/{project_name}"
                f"/repositories/{repository_name}"
                f"/artifacts/{artifact_digest}"
            )
            logger.info("Fetching Harbor artifact for scan results: %s", artifact_url)
            resp = await client.get(artifact_url, params={"with_scan_overview": "true"})

            if not resp.is_success:
                logger.error(
                    "Harbor artifact fetch failed: HTTP %s — %s",
                    resp.status_code,
                    resp.text[:500],
                )
                raise RuntimeError(
                    f"Harbor artifact fetch failed (HTTP {resp.status_code}): {resp.text[:300]}"
                )

            artifact = resp.json()

        # Parse scan overview
        scan_summary = _parse_scan_overview(artifact)

        if scan_summary is None:
            image_version.status_flag = STATUS_FAILED
            image_version.status_text = "Scan results not available"
            image_version.vulnerabilities = 0
            image_version.vulnerability_severity = "unknown"
            await db.commit()
            return {
                "total": 0,
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "negligible": 0,
                "severity": "unknown",
                "message": "No scan results available for this artifact",
            }

        # Normalize keys (Harbor returns capitalized: Critical, High, ...)
        normalized: dict[str, int] = {}
        total = 0
        for key, value in scan_summary.items():
            sev = key.lower()
            count = int(value) if isinstance(value, (int, float)) else 0
            normalized[sev] = count
            total += count

        # Determine worst severity
        severity = _worst_severity(normalized)

        # Update image version
        image_version.vulnerabilities = total
        image_version.vulnerability_severity = severity
        image_version.status_flag = STATUS_OK
        image_version.status_text = f"Scanned — {total} CVE"
        await db.commit()

        result_data = {
            "total": total,
            "critical": normalized.get("critical", 0),
            "high": normalized.get("high", 0),
            "medium": normalized.get("medium", 0),
            "low": normalized.get("low", 0),
            "negligible": normalized.get("negligible", 0),
            "severity": severity,
        }
        logger.info("Scan results for image version %d: %s", image_version_id, result_data)
        return result_data
