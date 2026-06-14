"""
@file test_role_model_extended.py
@description Unit tests for Role model — verifies scope relationships
             (source_group_scopes, credential_scopes, sync_group_scopes).
@dependencies backend/app/models/role.py
"""

from app.models.credential import Credential, CredentialType
from app.models.role import Role
from app.models.role_scope import (
    RoleScopeCredential,
    RoleScopeSourceGroup,
    RoleScopeSyncGroup,
)
from app.models.source_group import SourceGroup
from app.models.sync_group import SyncGroup


class TestRoleModelScopes:
    """Tests for Role scope relationships."""

    def test_role_source_group_scopes(self):
        """Role can have RoleScopeSourceGroup entries."""
        role = Role(name="scoped-role", description="Can see specific groups")
        sg = SourceGroup(external_id="ext1", name="GroupA")
        scope = RoleScopeSourceGroup(role_id=1, source_group_id=1)
        scope.source_group = sg
        role.source_group_scopes.append(scope)
        assert len(role.source_group_scopes) == 1
        assert role.source_group_scopes[0].source_group is sg

    def test_role_credential_scopes(self):
        """Role can have RoleScopeCredential entries."""
        role = Role(name="cred-role", description="Can use specific credentials")
        cred = Credential(
            name="gh-token",
            credential_type=CredentialType.github_token,
            provider="github",
        )
        scope = RoleScopeCredential(role_id=1, credential_id=1)
        scope.credential = cred
        role.credential_scopes.append(scope)
        assert len(role.credential_scopes) == 1
        assert role.credential_scopes[0].credential is cred

    def test_role_sync_group_scopes(self):
        """Role can have RoleScopeSyncGroup entries."""
        role = Role(name="sync-role", description="Can manage specific sync groups")
        sg = SyncGroup(name="MySyncGroup")
        scope = RoleScopeSyncGroup(role_id=1, sync_group_id=1)
        scope.sync_group = sg
        role.sync_group_scopes.append(scope)
        assert len(role.sync_group_scopes) == 1
        assert role.sync_group_scopes[0].sync_group is sg
