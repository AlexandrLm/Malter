"""add intensity to long_term_memories for emotional memory

Revision ID: c4d5e6f7g8h9
Revises: b2c3d4e5f6a7
Create Date: 2025-01-08 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7g8h9'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Add intensity field to long_term_memories for emotional memory feature."""
    op.add_column(
        'long_term_memories',
        sa.Column('intensity', sa.Integer(), nullable=True, server_default='5')
    )


def downgrade() -> None:
    """Downgrade schema: Remove intensity field from long_term_memories."""
    op.drop_column('long_term_memories', 'intensity')
