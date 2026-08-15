from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class HelmChartSource(Base):
    """Helm chart repository source (e.g., https://charts.bitnami.com/bitnami)."""

    __tablename__ = "helm_chart_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    repo_url = Column(String(500), nullable=False)  # URL to index.yaml
    description = Column(Text, nullable=True)

    # Providers V3 (phase 4): helm source is a resource_providers row
    # (domain=helm, subtype=helm_repo, direction=external).
    provider_id = Column(
        Integer,
        ForeignKey("resource_providers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # GitLab mirror project for Helm chart sync pipelines
    gitlab_project_id = Column(String(255), nullable=True)
    gitlab_project_url = Column(String(500), nullable=True)

    # Sync tracking
    last_synced_at = Column(DateTime(timezone=True), nullable=True)

    # 0=ok, 1=failed, 2=warn/stale, 3=in_progress, 4=pending
    status_flag = Column(Integer, nullable=False, default=4)
    status_text = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    provider = relationship("ResourceProvider", foreign_keys=[provider_id])
    versions = relationship(
        "HelmChartVersion", back_populates="source", cascade="all, delete-orphan"
    )
    sync_logs = relationship("HelmSyncLog", back_populates="source", cascade="all, delete-orphan")
    sync_schedules = relationship(
        "SyncSchedule", back_populates="helm_chart_source", cascade="all, delete-orphan"
    )
