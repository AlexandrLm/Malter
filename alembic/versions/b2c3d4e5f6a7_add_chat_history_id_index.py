"""add chat_history id index

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2025-01-10 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'g9h8i7j6k5l4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Add index on chat_history (user_id, id) for optimized queries."""
    # Проверяем, существует ли индекс, чтобы избежать ошибки
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    indexes = [idx['name'] for idx in inspector.get_indexes('chat_history')]
    
    if 'idx_chat_history_user_id_id' not in indexes:
        op.create_index(
            'idx_chat_history_user_id_id',
            'chat_history',
            ['user_id', 'id'],
            unique=False
        )
    else:
        print("Index idx_chat_history_user_id_id already exists, skipping")


def downgrade() -> None:
    """Downgrade schema: Remove chat_history (user_id, id) index."""
    op.drop_index('idx_chat_history_user_id_id', table_name='chat_history')
