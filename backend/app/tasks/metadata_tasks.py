"""Taskiq task bodies replacing the former fire-and-forget ``asyncio.create_task``
sites (lost on API pod restart): source-repository metadata fetch and GitHub
project release sync."""

import asyncio
import logging

from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.services.source_repository import fetch_metadata_background
from app.tasks.broker import broker

logger = logging.getLogger(__name__)

_TASK_LABELS = {
    "max_retries": settings.task_max_retries,
    "ack_type": settings.task_ack_type,
}


@broker.task(**_TASK_LABELS)
async def fetch_metadata_task(repo_id: int) -> None:
    """Fetch metadata and releases for a source repository (former background task)."""
    await fetch_metadata_background(repo_id)


@broker.task(**_TASK_LABELS)
async def sync_releases_task(project_id: int, full_name: str) -> None:
    """Sync GitHub releases for a project (former sync_releases_background).

    Resolves the default GitHub provider at execution time — both former call
    sites used the default provider (no explicit provider is passed through
    the API).
    """
    from app.models.github_project import GithubProject
    from app.services.github import github_service

    async with AsyncSessionLocal() as new_db:
        try:
            result = await new_db.execute(
                select(GithubProject).where(GithubProject.id == project_id)
            )
            bg_project = result.scalar_one()

            provider = await github_service.get_default_provider(new_db)
            gh = github_service._get_client(provider)
            bg_gh_repo = gh.get_repo(full_name)

            await asyncio.wait_for(
                github_service._sync_releases(bg_gh_repo, bg_project, new_db),
                timeout=30.0,  # 30 second timeout for the sync operation
            )
        except TimeoutError:
            logger.error(f"Sync releases timed out for project {full_name} after 30 seconds")
        except Exception as e:
            logger.error(f"Background sync releases failed for project {full_name}: {e}")
            if "rate limit" in str(e).lower() or ("403" in str(e) and "exceeded" in str(e).lower()):
                logger.error(
                    "This error may be caused by GitHub API rate limits. "
                    "Please configure a GitHub personal access token "
                    "to increase the rate limit."
                )
