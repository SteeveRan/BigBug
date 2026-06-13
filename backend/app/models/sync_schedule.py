from datetime import UTC, datetime

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class SyncSchedule(Base):
    __tablename__ = "sync_schedules"

    id = Column(Integer, primary_key=True, index=True)

    # Discriminator: 'docker_image', 'helm_chart'
    sync_type = Column(String(20), nullable=False, index=True)

    # FK to parent entity — exactly one of these is set, the others are NULL
    docker_image_source_id = Column(
        Integer,
        ForeignKey("docker_image_sources.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    helm_chart_source_id = Column(
        Integer,
        ForeignKey("helm_chart_sources.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Schedule config
    cron_expression = Column(String(100), nullable=True)
    is_enabled = Column(Boolean, default=True, nullable=False)
    use_default_schedule = Column(Boolean, default=True, nullable=False)

    next_run_at = Column(DateTime(timezone=True), nullable=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships (conditional joins, same pattern as BuildSchedule)
    docker_image_source = relationship(
        "DockerImageSource",
        primaryjoin="and_(SyncSchedule.docker_image_source_id == DockerImageSource.id, "
        "SyncSchedule.sync_type == 'docker_image')",
        back_populates="sync_schedules",
        foreign_keys=[docker_image_source_id],
    )
    helm_chart_source = relationship(
        "HelmChartSource",
        primaryjoin="and_(SyncSchedule.helm_chart_source_id == HelmChartSource.id, "
        "SyncSchedule.sync_type == 'helm_chart')",
        back_populates="sync_schedules",
        foreign_keys=[helm_chart_source_id],
    )

    __table_args__ = (
        CheckConstraint(
            "(docker_image_source_id IS NOT NULL AND helm_chart_source_id IS NULL) OR "
            "(docker_image_source_id IS NULL AND helm_chart_source_id IS NOT NULL)",
            name="chk_sync_schedule_only_one_fk",
        ),
    )
