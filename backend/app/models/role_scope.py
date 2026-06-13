"""
@file role_scope.py
@description Role-scope association models — link roles to specific resources
             (source groups, credentials, sync groups) for fine-grained RBAC.
@dependencies app.database.Base, ./role.py, ./source_group.py, ./credential.py, ./sync_group.py
@relatedFiles ./role.py, ./source_group.py, ./credential.py, ./sync_group.py
"""

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app.database import Base


class RoleScopeSourceGroup(Base):
    __tablename__ = "role_scope_source_groups"

    role_id = Column(
        Integer,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    source_group_id = Column(
        Integer,
        ForeignKey("source_groups.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Relationships
    role = relationship("Role", back_populates="source_group_scopes")
    source_group = relationship("SourceGroup", back_populates="role_scopes")

    def __repr__(self) -> str:
        return (
            f"<RoleScopeSourceGroup(role_id={self.role_id}, "
            f"source_group_id={self.source_group_id})>"
        )


class RoleScopeCredential(Base):
    __tablename__ = "role_scope_credentials"

    role_id = Column(
        Integer,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    credential_id = Column(
        Integer,
        ForeignKey("credentials.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Relationships
    role = relationship("Role", back_populates="credential_scopes")
    credential = relationship("Credential", back_populates="role_scopes")

    def __repr__(self) -> str:
        return f"<RoleScopeCredential(role_id={self.role_id}, credential_id={self.credential_id})>"


class RoleScopeSyncGroup(Base):
    __tablename__ = "role_scope_sync_groups"

    role_id = Column(
        Integer,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    sync_group_id = Column(
        Integer,
        ForeignKey("sync_groups.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Relationships
    role = relationship("Role", back_populates="sync_group_scopes")
    sync_group = relationship("SyncGroup", back_populates="role_scopes")

    def __repr__(self) -> str:
        return f"<RoleScopeSyncGroup(role_id={self.role_id}, sync_group_id={self.sync_group_id})>"
