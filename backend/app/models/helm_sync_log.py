from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class HelmSyncLog(Base):
    """Sync run history for Helm chart source indexing."""

    __tablename__ = "helm_sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(
        Integer,
        ForeignKey("helm_chart_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    pipeline_id = Column(String(255), nullable=True)
    pipeline_url = Column(String(500), nullable=True)

    # 0=ok, 1=failed, 2=warn, 3=in_progress, 4=pending
    status_flag = Column(Integer, nullable=False, default=4)
    status_text = Column(String(500), nullable=True)
    log_output = Column(Text, nullable=True)

    triggered_by = Column(
        String(100), nullable=True
    )  # "scheduler" | "manual" | "webhook"

    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Relationships
    source = relationship("HelmChartSource", back_populates="sync_logs")
