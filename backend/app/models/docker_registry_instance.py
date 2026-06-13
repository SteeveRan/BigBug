"""
@file docker_registry_instance.py
@description Docker Registry instance model — stores connection details for
             multiple Docker Registry instances. Password is encrypted at rest
             via Fernet.
@dependencies app.database.Base, app.core.secrets (via service layer)
@relatedFiles ./helm_repository_instance.py, ./harbor_instance.py,
              ../../schemas/integrations.py
"""

import enum
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String, Text

from app.database import Base


class RegistryType(str, enum.Enum):
    """Classification of registries for UI grouping and matching logic."""
    INTERNAL = "internal"
    EXTERNAL = "external"


class RegistryProvider(str, enum.Enum):
    """Known registry providers for auto-detection and matching."""
    DOCKER_HUB = "docker_hub"
    QUAY_IO = "quay_io"
    GCR = "gcr"          # Google Container Registry
    ECR = "ecr"          # AWS Elastic Container Registry
    ACR = "acr"          # Azure Container Registry
    GHCR = "ghcr"        # GitHub Container Registry
    HARBOR = "harbor"
    GENERIC = "generic"


class DockerRegistryInstance(Base):
    __tablename__ = "docker_registry_instances"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    url = Column(String(500), nullable=False)  # e.g. registry.example.com
    username = Column(String(255), nullable=True)
    password = Column(Text, nullable=True)  # Fernet-encrypted at rest
    is_active = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    verify_ssl = Column(Boolean, default=True, nullable=False)
    registry_type = Column(
        Enum(RegistryType),
        default=RegistryType.EXTERNAL,
        nullable=False,
        comment="Classification: internal (company registries) or external (third-party)",
    )
    registry_provider = Column(
        Enum(RegistryProvider),
        default=RegistryProvider.GENERIC,
        nullable=False,
        comment="Known registry provider for auto-detection and matching",
    )
    priority = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Higher priority = preferred for auto-selection when multiple registries match",
    )
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
        return f"<DockerRegistryInstance(id={self.id}, name='{self.name}', url='{self.url}')>"
