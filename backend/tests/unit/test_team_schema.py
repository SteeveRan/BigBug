"""
@file test_team_schema.py
@description Unit tests for team schemas and ProviderCreate/Update visibility
             validation (stage 24).
@dependencies backend/app/schemas/team.py, backend/app/schemas/provider.py
"""

import pytest
from pydantic import ValidationError

from app.schemas.provider import ProviderCreate
from app.schemas.team import TeamCreate, TeamMemberAdd, TeamUpdate


class TestTeamSchemas:
    def test_team_create_valid(self):
        data = TeamCreate(name="team-a", description="desc", owner_user_id=1)
        assert data.name == "team-a"
        assert data.owner_user_id == 1

    def test_team_update_all_optional(self):
        data = TeamUpdate()
        assert data.name is None
        assert data.owner_user_id is None

    def test_team_member_add(self):
        data = TeamMemberAdd(user_id=42)
        assert data.user_id == 42


class TestProviderVisibilityValidation:
    def _payload(self, **overrides):
        payload = {
            "domain": "git",
            "subtype": "github",
            "category": "private",
            "direction": "external",
            "name": "gh",
            "label": "GitHub",
        }
        payload.update(overrides)
        return payload

    def test_team_without_team_id_raises(self):
        with pytest.raises(ValidationError, match="team_id"):
            ProviderCreate(**self._payload(visibility="team"))

    def test_team_with_team_id_ok(self):
        data = ProviderCreate(**self._payload(visibility="team", team_id=1))
        assert data.visibility.value == "team"
        assert data.team_id == 1

    def test_default_visibility_is_owner(self):
        data = ProviderCreate(**self._payload())
        assert data.visibility.value == "owner"

    def test_public_visibility_for_system_raises(self):
        with pytest.raises(ValidationError, match="public"):
            ProviderCreate(
                domain="git",
                subtype="gitlab",
                category="system",
                direction="internal",
                name="sys",
                label="Sys",
                base_url="https://gitlab.example.com",
                visibility="public",
            )
