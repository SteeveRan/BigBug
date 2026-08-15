"""
@file test_auth_me.py
@description Unit tests for GET /api/auth/me — verifies the response now
             includes the ``full_name`` field (and a null fallback).
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


@pytest.mark.asyncio
async def test_get_me_includes_full_name(
    client: AsyncClient, db_session: AsyncSession, admin_token: str
):
    """GET /api/auth/me returns the user's full_name when set."""
    result = await db_session.execute(select(User).where(User.username == "testadmin"))
    user = result.scalar_one()
    user.full_name = "Test Admin"
    await db_session.commit()

    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testadmin"
    assert data["full_name"] == "Test Admin"
    assert "admin" in data["roles"]


@pytest.mark.asyncio
async def test_get_me_full_name_none_fallback(client: AsyncClient, admin_token: str):
    """GET /api/auth/me returns full_name=null when not set (backward-compatible)."""
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testadmin"
    assert data["full_name"] is None
