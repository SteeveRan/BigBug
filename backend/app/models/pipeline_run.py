"""
@file pipeline_run.py
@description Pipeline run model — tracks GitLab pipeline executions triggered
             from BigBug. Stores status, timing, and reference to the GitLab instance.
@dependencies app.database.Base, ../models/gitlab_instance.py, ../models/user.py
@relatedFiles ../../schemas/pipeline.py, ../../services/pipeline.py
"""

from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, index=True)
    gitlab_instance_id = Column(Integer, ForeignKey("gitlab_instances.id"), nullable=False)
    gitlab_project_id = Column(Integer, nullable=False)
    gitlab_pipeline_id = Column(Integer, nullable=True)  # null until triggered
    triggered_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    trigger_type = Column(String, default="manual")  # manual / scheduled / webhook
    ref = Column(String, nullable=False)  # branch, tag or commit SHA
    variables = Column(JSON, default=dict)
    status_flag = Column(Integer, default=4, nullable=False)  # 0=OK, 1=Failed, 3=Running, 4=Pending
    status_text = Column(String(255), default="Pending", nullable=False)
    duration = Column(Integer, nullable=True)  # seconds
    web_url = Column(String(1024), nullable=True)  # link to GitLab pipeline page
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    # Relationships
    gitlab_instance = relationship("GitlabInstance", lazy="select")
    triggered_by = relationship("User", lazy="select")

    def __repr__(self) -> str:
        return (
            f"<PipelineRun(id={self.id}, project={self.gitlab_project_id}, "
            f"ref='{self.ref}', status={self.status_text})>"
        )
