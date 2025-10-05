"""add fulltext search to long term memory

Revision ID: f8a3c9d1e2b5
Revises: e5f3a7b1c2d4
Create Date: 2025-01-10 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f8a3c9d1e2b5'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Add fulltext search to long_term_memories."""
    # Добавляем столбец fact_tsv для полнотекстового поиска
    op.add_column('long_term_memories',
        sa.Column('fact_tsv', postgresql.TSVECTOR(), nullable=True)
    )
    
    # Заполняем существующие записи tsvector значениями
    op.execute("""
        UPDATE long_term_memories
        SET fact_tsv = to_tsvector('russian', fact)
        WHERE fact_tsv IS NULL
    """)
    
    # Создаём триггер для автоматического обновления fact_tsv
    op.execute("""
        CREATE OR REPLACE FUNCTION long_term_memories_fact_tsv_trigger() RETURNS trigger AS $$
        BEGIN
            NEW.fact_tsv := to_tsvector('russian', NEW.fact);
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        CREATE TRIGGER tsvectorupdate BEFORE INSERT OR UPDATE
        ON long_term_memories FOR EACH ROW
        EXECUTE FUNCTION long_term_memories_fact_tsv_trigger();
    """)
    
    # Создаём GIN индекс для полнотекстового поиска
    op.create_index(
        'idx_long_term_memory_fact_tsv',
        'long_term_memories',
        ['fact_tsv'],
        unique=False,
        postgresql_using='gin'
    )


def downgrade() -> None:
    """Downgrade schema: Remove fulltext search from long_term_memories."""
    # Удаляем индекс
    op.drop_index('idx_long_term_memory_fact_tsv', table_name='long_term_memories', postgresql_using='gin')
    
    # Удаляем триггер
    op.execute("DROP TRIGGER IF EXISTS tsvectorupdate ON long_term_memories")
    op.execute("DROP FUNCTION IF EXISTS long_term_memories_fact_tsv_trigger()")
    
    # Удаляем столбец
    op.drop_column('long_term_memories', 'fact_tsv')
