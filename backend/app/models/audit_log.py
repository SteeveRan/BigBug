"""Audit log model."""

from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    username = Column(String, nullable=False)  # денормализовано
    action = Column(
        String, nullable=False, index=True
    )  # create/update/delete/login/logout/sync/build
    resource_type = Column(
        String, nullable=False, index=True
    )  # mirror/helm_source/docker_source/user/role/integration/pipeline/oidc_config
    resource_id = Column(Integer, nullable=True)
    resource_name = Column(String, nullable=True)  # денормализовано
    details = Column(
        JSON, nullable=True
    )  # {"before": {...}, "after": {...}, "changed_fields": [...]}
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), index=True)

    user = relationship("User", lazy="select")
