"""
@file trust_store.py
@description TrustStore model — named CA bundle that providers can reference as
              an optional source of trust (ADR-0037). A trust store changes
              *what* to trust, never disables verification.
@dependencies app.database.Base, ./resource_provider.py
@relatedFiles ../services/trust_store.py, ../schemas/trust_store.py, ./resource_provider.py
"""

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class TrustStore(Base):
    __tablename__ = "trust_stores"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Soft-delete aware: providers are hard-deleted (usage-gated), the flag
    # exists only so the partial unique index mirrors resource_providers.
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    certificates = relationship(
        "TrustStoreCertificate",
        back_populates="trust_store",
        cascade="all, delete-orphan",
        order_by="TrustStoreCertificate.id",
    )

    __table_args__ = (
        Index(
            "uq_trust_stores_name",
            "name",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = false"),
        ),
    )

    def __repr__(self) -> str:
        return f"<TrustStore(id={self.id}, name='{self.name}')>"


class TrustStoreCertificate(Base):
    __tablename__ = "trust_store_certificates"

    id = Column(Integer, primary_key=True, index=True)
    trust_store_id = Column(
        Integer,
        ForeignKey("trust_stores.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(255), nullable=False)
    pem = Column(Text, nullable=False)
    # SHA-256 of the DER body, computed by the service at save time.
    fingerprint = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    trust_store = relationship("TrustStore", back_populates="certificates")

    __table_args__ = (
        Index(
            "uq_trust_store_certificates_name",
            "trust_store_id",
            "name",
            unique=True,
        ),
        Index("ix_trust_store_certificates_store", "trust_store_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<TrustStoreCertificate(id={self.id}, name='{self.name}', "
            f"trust_store_id={self.trust_store_id})>"
        )
