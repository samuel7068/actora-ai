"""add talent_media ai_summary (RAG scene_summary 합침)

Revision ID: b1c2d3e4f5a6
Revises: ff7c8b02a52c
Create Date: 2026-06-01 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'ff7c8b02a52c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('talent_media', sa.Column('ai_summary', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('talent_media', 'ai_summary')
