import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.app_image import AppImage
from app.models.gold_image import GoldImage

pytestmark = pytest.mark.e2e


@pytest.fixture
async def sample_gold_image(db_session: AsyncSession):
    image = GoldImage(
        name="ubuntu-22.04",
        os_family="ubuntu",
        description="Ubuntu 22.04 LTS base image",
        dockerfile="FROM ubuntu:22.04\nRUN apt-get update",
    )
    db_session.add(image)
    await db_session.commit()
    await db_session.refresh(image)
    return image


@pytest.fixture
async def sample_app_image(db_session: AsyncSession, sample_gold_image):
    image = AppImage(
        gold_image_id=sample_gold_image.id,
        name="myapp",
        description="My application image",
        dockerfile="FROM ubuntu-22.04:latest\nCOPY . /app",
    )
    db_session.add(image)
    await db_session.commit()
    await db_session.refresh(image)
    return image


@pytest.mark.asyncio
async def test_list_gold_images(client: AsyncClient, operator_token: str, sample_gold_image):
    response = await client.get(
        "/api/gold-images",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_create_gold_image(client: AsyncClient, operator_token: str):
    response = await client.post(
        "/api/gold-images",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={
            "name": "alpine-3.19",
            "os_family": "alpine",
            "description": "Alpine Linux 3.19",
            "dockerfile": "FROM alpine:3.19",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "alpine-3.19"
    assert data["os_family"] == "alpine"


@pytest.mark.asyncio
async def test_get_gold_image(client: AsyncClient, operator_token: str, sample_gold_image):
    response = await client.get(
        f"/api/gold-images/{sample_gold_image.id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "ubuntu-22.04"


@pytest.mark.asyncio
async def test_update_gold_image(client: AsyncClient, operator_token: str, sample_gold_image):
    response = await client.patch(
        f"/api/gold-images/{sample_gold_image.id}",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={"description": "Updated description"},
    )
    assert response.status_code == 200
    assert response.json()["description"] == "Updated description"


@pytest.mark.asyncio
async def test_list_app_images(client: AsyncClient, operator_token: str, sample_app_image):
    response = await client.get(
        "/api/app-images",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_create_app_image(client: AsyncClient, operator_token: str, sample_gold_image):
    response = await client.post(
        "/api/app-images",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={
            "name": "nginx-app",
            "gold_image_id": sample_gold_image.id,
            "description": "Nginx application",
            "dockerfile": "FROM ubuntu-22.04:latest\nRUN apt-get install -y nginx",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "nginx-app"
    assert data["gold_image_id"] == sample_gold_image.id


@pytest.mark.asyncio
async def test_delete_gold_image(client: AsyncClient, admin_token: str, sample_gold_image):
    response = await client.delete(
        f"/api/gold-images/{sample_gold_image.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 204
