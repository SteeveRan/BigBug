"""add_is_anon_is_builtin_to_source_providers

Revision ID: e5f6a7b8c9d0
Revises: dc0ef2cfb148
Create Date: 2026-06-14 22:53:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'dc0ef2cfb148'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Добавляем колонки is_anon и is_builtin
    op.add_column(
        'source_providers',
        sa.Column('is_anon', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        'source_providers',
        sa.Column('is_builtin', sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # 2. Идемпотентно добавляем 'generic' в enum на ОТДЕЛЬНОМ соединении.
    # PostgreSQL (asyncpg) запрещает использовать новое значение enum в DML
    # в рамках той же транзакции, где был ALTER TYPE ... ADD VALUE.
    # Alembic оборачивает все миграции в одну транзакцию, поэтому берём
    # СВЕЖЕЕ соединение из пула (engine.connect()) — оно существует вне
    # транзакции Alembic. Явный .commit() финализирует DDL.
    bind = op.get_bind()
    engine = bind.engine  # sync Engine (миграция внутри run_sync)
    with engine.connect() as independent_conn:
        independent_conn.execute(
            sa.text(
                """
                DO $$
                BEGIN
                    ALTER TYPE provider_type_enum ADD VALUE 'generic';
                EXCEPTION WHEN duplicate_object THEN
                    NULL;
                END $$;
                """
            )
        )
        independent_conn.commit()

    # 3. Создаём три builtin анонимных провайдера.
    # Выполняется в транзакции Alembic — к этому моменту 'generic' уже
    # закоммичен через независимое соединение выше.
    op.execute(
        sa.text(
            """
            INSERT INTO source_providers
                (credential_id, provider_type, label, is_anon, is_builtin,
                 is_deleted, created_at, updated_at)
            VALUES
                (NULL, 'github',  'GitHub (Anonymous)',  TRUE, TRUE, FALSE, NOW(), NOW()),
                (NULL, 'gitlab',  'GitLab (Anonymous)',  TRUE, TRUE, FALSE, NOW(), NOW()),
                (NULL, 'generic', 'Generic (Anonymous)', TRUE, TRUE, FALSE, NOW(), NOW())
            """
        )
    )


def downgrade() -> None:
    # Удаляем builtin-провайдеров
    op.execute(
        sa.text(
            "DELETE FROM source_providers WHERE is_builtin = TRUE AND is_anon = TRUE"
        )
    )
    # Удаляем колонки
    op.drop_column('source_providers', 'is_builtin')
    op.drop_column('source_providers', 'is_anon')
