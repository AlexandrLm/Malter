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
down_revision: Union[str, Sequence[str], None] = 'f8a3c9d1e2b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Add index on chat_history (user_id, id) for optimized queries."""
    op.create_index(
        'idx_chat_history_user_id_id',
        'chat_history',
        ['user_id', 'id'],
        unique=False
    )


def downgrade() -> None:
    """Downgrade schema: Remove chat_history (user_id, id) index."""
    op.drop_index('idx_chat_history_user_id_id', table_name='chat_history')
