"""
Test script to verify that the audit log datetime timezone issue is fixed.
"""
import asyncio
import sys
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.audit_log import AuditLog


async def test_audit_log_creation():
    """Test that audit log creation works without timezone errors."""
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        print("Testing audit log creation...")

        # Try to create an audit log entry
        audit_entry = AuditLog(
            user_id=1,
            username="test_user",
            action="create",
            resource_type="integration",
            resource_id=1,
            resource_name="test_integration",
            ip_address="127.0.0.1",
            created_at=datetime.now(UTC)  # Explicitly use timezone-aware datetime
        )

        try:
            db.add(audit_entry)
            await db.commit()
            print("✓ Audit log entry created successfully!")

            # Refresh to get the ID assigned by the database
            await db.refresh(audit_entry)
            print(f"✓ Audit log ID: {audit_entry.id}")
            print(f"✓ Created at: {audit_entry.created_at} (type: {type(audit_entry.created_at)})")

        except Exception as e:
            print(f"✗ Error creating audit log: {e}")
            await db.rollback()
            return False

        # Test with service-style creation (using datetime.now(UTC) as in the actual service)
        # Using the same user_id as the first entry to avoid FK constraint issues
        try:
            audit_entry2 = AuditLog(
                user_id=1,  # Use existing user ID to avoid FK constraint violation
                username="service_user",
                action="test",
                resource_type="audit_test",
                created_at=datetime.now(UTC)  # This was causing the original issue
            )

            db.add(audit_entry2)
            await db.commit()
            print("✓ Audit log entry with datetime.now(UTC) created successfully!")

            await db.refresh(audit_entry2)
            print(f"✓ Second audit log ID: {audit_entry2.id}")
            created_info = (
                f"✓ Created at: {audit_entry2.created_at}"
                f" (type: {type(audit_entry2.created_at)})"
            )
            print(created_info)

        except Exception as e:
            print(f"✗ Error creating second audit log: {e}")
            await db.rollback()
            return False

    return True


if __name__ == "__main__":
    success = asyncio.run(test_audit_log_creation())
    if success:
        print("\n✓ All tests passed! The timezone issue appears to be fixed.")
        sys.exit(0)
    else:
        print("\n✗ Tests failed! The issue may not be completely resolved.")
        sys.exit(1)
