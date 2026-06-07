"""
@file integrations/__init__.py
@description Combined router for all integration instance endpoints:
             GitLab, Harbor, GitHub, Docker Registry, Helm Repository.
@dependencies .gitlab, .harbor, .github, .docker_registry, .helm_repository
@relatedFiles ../../main.py
"""

from fastapi import APIRouter

from app.api.integrations.docker_registry import router as docker_registry_router
from app.api.integrations.github import router as github_router
from app.api.integrations.gitlab import router as gitlab_router
from app.api.integrations.harbor import router as harbor_router
from app.api.integrations.helm_repository import router as helm_repository_router

router = APIRouter()
router.include_router(gitlab_router)
router.include_router(harbor_router)
router.include_router(github_router)
router.include_router(docker_registry_router)
router.include_router(helm_repository_router)
