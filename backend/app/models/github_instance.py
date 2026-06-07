"""
@file github_instance.py
@description GitHub instance model — stores connection details for multiple
             GitHub tokens (API endpoint is always api.github.com). The token
             is encrypted at rest via Fernet.
@dependencies app.database.Base, app.core.secrets (via service layer)
@relatedFiles ./gitlab_instance.py, ./harbor_instance.py, ../../schemas/integrations.py
"""

from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.database import Base


class GithubInstance(Base):
    __tablename__ = "github_instances"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    token = Column(Text, nullable=True)  # Fernet-encrypted at rest
    is_active = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    status_flag = Column(
        Integer, default=0, nullable=False
    )  # 0=OK,1=Failed,2=Warning,3=In Progress,4=Pending
    status_text = Column(String(255), default="OK", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<GithubInstance(id={self.id}, name='{self.name}')>"
