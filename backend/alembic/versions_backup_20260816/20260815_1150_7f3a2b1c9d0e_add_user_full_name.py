"""add user full_name

Revision ID: 7f3a2b1c9d0e
Revises: 0cce18c6c867
Create Date: 2026-08-15 11:50:00.000000+00:00

Adds a nullable ``full_name`` column to ``users`` so the profile page can show
the user's display name (sourced from the OIDC ``name`` claim). Nullable with
no default keeps the migration safe for tables that already contain rows.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7f3a2b1c9d0e"
down_revision: str | None = "0cce18c6c867"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("full_name", sa.String(255), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "full_name")
