"""
RBAC Permission model and role_permissions association table.

Permissions follow the format "resource:action" (e.g., "mirrors:read").
The role_permissions table links roles to their assigned permissions.
"""

from sqlalchemy import Column, ForeignKey, Integer, String, Table, Text

from app.database import Base


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)  # "resource:action"
    description = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Permission(id={self.id}, name='{self.name}')>"


role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column(
        "role_id",
        Integer,
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "permission_id",
        Integer,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
