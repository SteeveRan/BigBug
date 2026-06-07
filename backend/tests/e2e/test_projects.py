import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.github_org import GithubOrg
from app.models.github_project import GithubProject

pytestmark = pytest.mark.e2e


@pytest_asyncio.fixture
async def sample_project(db_session: AsyncSession):
    org = GithubOrg(login="testorg", type="Organization")
    db_session.add(org)
    await db_session.flush()

    project = GithubProject(
        org_id=org.id,
        name="testrepo",
        full_name="testorg/testrepo",
        github_url="https://github.com/testorg/testrepo",
        description="Test repository",
        default_branch="main",
        is_archived=False,
        is_fork=False,
        is_stale=False,
        stale_threshold_days=30,
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest.mark.asyncio
async def test_list_projects_requires_auth(client: AsyncClient):
    response = await client.get("/api/projects")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient, operator_token: str, sample_project):
    response = await client.get(
        "/api/projects",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_project(client: AsyncClient, operator_token: str, sample_project):
    response = await client.get(
        f"/api/projects/{sample_project.id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "testorg/testrepo"


@pytest.mark.asyncio
async def test_get_project_not_found(client: AsyncClient, operator_token: str):
    response = await client.get(
        "/api/projects/99999",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_project_description(client: AsyncClient, operator_token: str, sample_project):
    response = await client.patch(
        f"/api/projects/{sample_project.id}",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={"custom_description": "My custom description"},
    )
    assert response.status_code == 200
    assert response.json()["custom_description"] == "My custom description"


@pytest.mark.asyncio
async def test_delete_project(client: AsyncClient, admin_token: str, sample_project):
    response = await client.delete(
        f"/api/projects/{sample_project.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 204
