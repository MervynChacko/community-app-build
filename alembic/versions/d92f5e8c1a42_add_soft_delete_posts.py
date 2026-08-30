"""add soft-delete fields to posts

Revision ID: d92f5e8c1a42
Revises: c58f0a2b7e91
Create Date: 2026-08-21 10:00:00.000000

Adds is_deleted and deleted_at columns to posts, allowing soft deletes
(mark as deleted rather than hard-delete) for audit trail and staff
moderation review. All existing posts are backfilled as not-deleted.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd92f5e8c1a42'
down_revision: Union[str, Sequence[str], None] = 'c58f0a2b7e91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'posts',
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    op.add_column(
        'posts',
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('posts', 'deleted_at')
    op.drop_column('posts', 'is_deleted')