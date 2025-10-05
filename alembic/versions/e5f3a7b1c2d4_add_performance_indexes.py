"""add performance indexes

Revision ID: e5f3a7b1c2d4
Revises: 44fa2e2662e1
Create Date: 2025-01-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f3a7b1c2d4'
down_revision: Union[str, Sequence[str], None] = '44fa2e2662e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Add performance indexes."""
    # Индексы для user_profiles
    op.create_index('idx_subscription_expires', 'user_profiles', ['subscription_expires'], unique=False)
    op.create_index('idx_last_message_date', 'user_profiles', ['last_message_date'], unique=False)
    
    # Индекс для long_term_memories
    op.create_index('idx_long_term_memory_user_category', 'long_term_memories', ['user_id', 'category'], unique=False)


def downgrade() -> None:
    """Downgrade schema: Remove performance indexes."""
    # Удаляем индексы в обратном порядке
    op.drop_index('idx_long_term_memory_user_category', table_name='long_term_memories')
    op.drop_index('idx_last_message_date', table_name='user_profiles')
    op.drop_index('idx_subscription_expires', table_name='user_profiles')
