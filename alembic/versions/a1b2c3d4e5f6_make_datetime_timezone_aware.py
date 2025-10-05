"""make datetime timezone aware

Revision ID: a1b2c3d4e5f6
Revises: e5f3a7b1c2d4
Create Date: 2025-01-10 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'e5f3a7b1c2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Make datetime columns timezone-aware."""
    # Изменяем колонки на TIMESTAMPTZ (PostgreSQL timezone-aware datetime)
    op.alter_column('user_profiles', 'level_unlocked_at',
                    existing_type=sa.DateTime(),
                    type_=sa.DateTime(timezone=True),
                    existing_nullable=False)
    
    op.alter_column('user_profiles', 'subscription_expires',
                    existing_type=sa.DateTime(),
                    type_=sa.DateTime(timezone=True),
                    existing_nullable=True)


def downgrade() -> None:
    """Downgrade schema: Revert datetime columns to non-timezone-aware."""
    op.alter_column('user_profiles', 'subscription_expires',
                    existing_type=sa.DateTime(timezone=True),
                    type_=sa.DateTime(),
                    existing_nullable=True)
    
    op.alter_column('user_profiles', 'level_unlocked_at',
                    existing_type=sa.DateTime(timezone=True),
                    type_=sa.DateTime(),
                    existing_nullable=False)
