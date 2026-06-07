from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class ImageVersion(Base):
    """Unified version table for both GoldImage and AppImage versions."""

    __tablename__ = "image_versions"

    id = Column(Integer, primary_key=True, index=True)

    # Discriminator: "gold" or "app"
    image_type = Column(String(10), nullable=False, index=True)

    # FK to parent image — one of these is set, the other is NULL
    gold_image_id = Column(
        Integer,
        ForeignKey("gold_images.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    app_image_id = Column(
        Integer,
        ForeignKey("app_images.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Version info
    version_tag = Column(String(255), nullable=False)
    arch = Column(String(50), nullable=False, default="amd64")  # amd64 | arm64 | arm/v7

    # Registry
    registry_url = Column(String(500), nullable=True)
    sha256_digest = Column(String(255), nullable=True)

    # Cosign signing
    cosign_signature = Column(String(1000), nullable=True)
    is_signed = Column(Boolean, default=False, nullable=False)

    # Status: 0=ok, 1=failed, 2=warn, 3=in_progress, 4=pending
    status_flag = Column(Integer, nullable=False, default=4)
    status_text = Column(String(500), nullable=True)

    # Vulnerability scanning (from Harbor)
    vulnerabilities = Column(Integer, nullable=True)  # Total CVE count
    vulnerability_severity = Column(
        String(20), nullable=True
    )  # Worst severity: none/low/medium/high/critical

    built_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Relationships
    gold_image = relationship(
        "GoldImage",
        primaryjoin="and_(ImageVersion.gold_image_id == GoldImage.id, "
        "ImageVersion.image_type == 'gold')",
        back_populates="versions",
        foreign_keys=[gold_image_id],
    )
    app_image = relationship(
        "AppImage",
        primaryjoin="and_(ImageVersion.app_image_id == AppImage.id, "
        "ImageVersion.image_type == 'app')",
        back_populates="versions",
        foreign_keys=[app_image_id],
    )
    build_logs = relationship(
        "BuildLog", back_populates="image_version", cascade="all, delete-orphan"
    )
