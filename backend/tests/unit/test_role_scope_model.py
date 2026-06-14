"""
@file test_role_scope_model.py
@description Unit tests for RoleScope models — verifies creation of all three
             scope associations and their relationship links.
@dependencies backend/app/models/role_scope.py
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


class TestRoleScopeSourceGroup:
    """Tests for the RoleScopeSourceGroup model."""

    def test_creation(self):
        """Create a RoleScopeSourceGroup with composite PK."""
        rs = RoleScopeSourceGroup(
            role_id=1,
            source_group_id=2,
        )
        assert rs.role_id == 1
        assert rs.source_group_id == 2
        # created_at is a DB-level default, applied at INSERT time.

    def test_role_relationship(self):
        """RoleScopeSourceGroup can reference a Role."""
        role = Role(name="test-role", description="Test")
        rs = RoleScopeSourceGroup(role_id=1, source_group_id=1)
        rs.role = role
        assert rs.role is role
        assert rs.role.name == "test-role"

    def test_source_group_relationship(self):
        """RoleScopeSourceGroup can reference a SourceGroup."""
        sg = SourceGroup(
            external_id="ext",
            name="MyGroup",
        )
        rs = RoleScopeSourceGroup(role_id=1, source_group_id=1)
        rs.source_group = sg
        assert rs.source_group is sg
        assert rs.source_group.name == "MyGroup"


class TestRoleScopeCredential:
    """Tests for the RoleScopeCredential model."""

    def test_creation(self):
        """Create a RoleScopeCredential with composite PK."""
        rc = RoleScopeCredential(
            role_id=1,
            credential_id=3,
        )
        assert rc.role_id == 1
        assert rc.credential_id == 3
        # created_at is a DB-level default, applied at INSERT time.

    def test_credential_relationship(self):
        """RoleScopeCredential can reference a Credential."""
        cred = Credential(
            name="test-cred",
            credential_type=CredentialType.github_token,
            provider="github",
        )
        rc = RoleScopeCredential(role_id=1, credential_id=1)
        rc.credential = cred
        assert rc.credential is cred
        assert rc.credential.name == "test-cred"


class TestRoleScopeSyncGroup:
    """Tests for the RoleScopeSyncGroup model."""

    def test_creation(self):
        """Create a RoleScopeSyncGroup with composite PK."""
        rs = RoleScopeSyncGroup(
            role_id=1,
            sync_group_id=4,
        )
        assert rs.role_id == 1
        assert rs.sync_group_id == 4
        # created_at is a DB-level default, applied at INSERT time.

    def test_sync_group_relationship(self):
        """RoleScopeSyncGroup can reference a SyncGroup."""
        sg = SyncGroup(name="test-sync-group")
        rs = RoleScopeSyncGroup(role_id=1, sync_group_id=1)
        rs.sync_group = sg
        assert rs.sync_group is sg
        assert rs.sync_group.name == "test-sync-group"
