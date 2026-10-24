"""merge trust_stores and oidc_multi_provider heads

Revision ID: fb1eef4e684f
Revises: b4c5d6e7f8a9, b7c9d1e3f5a7
Create Date: 2026-10-24 22:03:44.364178+00:00

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "fb1eef4e684f"
down_revision: Union[str, None] = ("b4c5d6e7f8a9", "b7c9d1e3f5a7")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
