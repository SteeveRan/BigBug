"""detach_source_provider_from_group

Revision ID: a7b8c9d0e1f2
Revises: 1a2b3c4d5e6f
Create Date: 2026-06-14 19:18:00.000000+00:00

Detach source_provider_id from source_groups and attach it directly
to source_repositories. SourceGroup becomes a pure grouping entity
(e.g., GitHub org / GitLab group) without a direct link to a provider.

The provider is now determined per-repository, which enables:
- Generic Git providers that have no organisational structure
- Repositories without a group (already supported via nullable source_group_id)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = '1a2b3c4d5e6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Add source_provider_id column to source_repositories ─────────────
    op.add_column(
        'source_repositories',
        sa.Column(
            'source_provider_id',
            sa.Integer(),
            sa.ForeignKey('source_providers.id', ondelete='SET NULL'),
            nullable=True,
        ),
    )

    # ── 2. Create index on the new column ───────────────────────────────────
    op.create_index(
        op.f('ix_source_repositories_source_provider_id'),
        'source_repositories',
        ['source_provider_id'],
        unique=False,
    )

    # ── 3. Populate source_repositories.source_provider_id from source_groups
    op.execute(sa.text("""
        UPDATE source_repositories sr
        SET source_provider_id = sg.source_provider_id
        FROM source_groups sg
        WHERE sr.source_group_id = sg.id
          AND sr.source_group_id IS NOT NULL
    """))

    # ── 4. Drop FK constraint and column from source_groups ─────────────────
    #    NB: ix_source_groups_source_provider_id was never created in the
    #    initial schema, so there is nothing to drop here.
    op.drop_constraint(
        'source_groups_source_provider_id_fkey',
        'source_groups',
        type_='foreignkey',
    )
    op.drop_column('source_groups', 'source_provider_id')


def downgrade() -> None:
    # ── 1. Restore source_provider_id column to source_groups ───────────────
    #    (nullable=True first to allow data population before NOT NULL)
    op.add_column(
        'source_groups',
        sa.Column(
            'source_provider_id',
            sa.Integer(),
            nullable=True,
        ),
    )

    # ── 2. Populate source_groups.source_provider_id from source_repositories
    #    Use MIN(source_provider_id) per group — in practice all repos under
    #    one group share the same provider, but MIN is a safe aggregation.
    op.execute(sa.text("""
        UPDATE source_groups sg
        SET source_provider_id = sub.provider_id
        FROM (
            SELECT source_group_id, MIN(source_provider_id) AS provider_id
            FROM source_repositories
            WHERE source_provider_id IS NOT NULL
              AND source_group_id IS NOT NULL
            GROUP BY source_group_id
        ) sub
        WHERE sg.id = sub.source_group_id
    """))

    # ── 3. Fallback: assign the first available source_provider to any
    #    groups still missing a provider (e.g., empty groups or groups
    #    whose repos had no provider).  This keeps the NOT NULL constraint
    #    satisfiable when data is incomplete.
    op.execute(sa.text("""
        UPDATE source_groups
        SET source_provider_id = (
            SELECT id FROM source_providers ORDER BY id LIMIT 1
        )
        WHERE source_provider_id IS NULL
    """))

    # ── 4. Create FK constraint ────────────────────────────────────────────
    op.create_foreign_key(
        'source_groups_source_provider_id_fkey',
        'source_groups',
        'source_providers',
        ['source_provider_id'],
        ['id'],
        ondelete='CASCADE',
    )

    # ── 5. Make the column NOT NULL (safe after population) ─────────────────
    op.alter_column(
        'source_groups', 'source_provider_id',
        existing_type=sa.Integer(),
        nullable=False,
    )

    # ── 6. Create index on source_groups.source_provider_id ─────────────────
    op.create_index(
        op.f('ix_source_groups_source_provider_id'),
        'source_groups',
        ['source_provider_id'],
        unique=False,
    )

    # ── 7. Remove source_provider_id from source_repositories ───────────────
    op.drop_constraint(
        'source_repositories_source_provider_id_fkey',
        'source_repositories',
        type_='foreignkey',
    )
    op.drop_index(
        op.f('ix_source_repositories_source_provider_id'),
        table_name='source_repositories',
    )
    op.drop_column('source_repositories', 'source_provider_id')
