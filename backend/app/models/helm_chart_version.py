from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class HelmChartVersion(Base):
    """A specific version of a Helm chart from a chart source."""

    __tablename__ = "helm_chart_versions"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(
        Integer,
        ForeignKey("helm_chart_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Chart identity
    chart_name = Column(String(255), nullable=False, index=True)
    version = Column(String(100), nullable=False)
    app_version = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)

    # Package metadata (from index.yaml entry)
    digest = Column(String(255), nullable=True)  # SHA-256 digest from index.yaml
    urls = Column(Text, nullable=True)  # JSON array of download URLs
    chart_url = Column(String(500), nullable=True)  # Primary download URL

    # GitLab mirror tracking
    gitlab_project_id = Column(String(255), nullable=True)

    # Status
    # 0=ok (synced), 1=failed, 2=warning/stale, 3=in_progress, 4=pending (not synced)
    status_flag = Column(Integer, nullable=False, default=4)
    status_text = Column(String(500), nullable=True)

    # Sync tracking
    is_synced = Column(Boolean, default=False, nullable=False)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Relationships
    source = relationship("HelmChartSource", back_populates="versions")
