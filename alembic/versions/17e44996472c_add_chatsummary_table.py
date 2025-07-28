"""Add ChatSummary table

Revision ID: 17e44996472c
Revises: 020abbe2b0d3
Create Date: 2025-07-27 16:15:14.823390

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '17e44996472c'
down_revision: Union[str, Sequence[str], None] = '020abbe2b0d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('chat_summaries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('summary', sa.String(), nullable=False),
        sa.Column('last_message_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('chat_summaries', schema=None) as batch_op:
        batch_op.create_index('idx_chat_summary_user_id_timestamp', ['user_id', 'timestamp'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('chat_summaries', schema=None) as batch_op:
        batch_op.drop_index('idx_chat_summary_user_id_timestamp')

    op.drop_table('chat_summaries')
