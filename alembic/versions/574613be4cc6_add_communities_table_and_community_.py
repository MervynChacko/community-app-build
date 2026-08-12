"""add communities table and community scoping foreign keys

Revision ID: 574613be4cc6
Revises: c6793e530f73
Create Date: 2026-08-12 20:12:40.196539

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '574613be4cc6'
down_revision: Union[str, Sequence[str], None] = 'c6793e530f73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create communities table
    op.create_table(
        'communities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
        sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_communities_id'), 'communities', ['id'], unique=False)

    # 2. Add nullable community_id to users
    op.add_column('users', sa.Column('community_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_users_community_id', 'users', 'communities', ['community_id'], ['id'], ondelete='SET NULL')

    # 3. Add community_id to posts
    op.add_column('posts', sa.Column('community_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_posts_community_id', 'posts', 'communities', ['community_id'], ['id'], ondelete='CASCADE')

    # 4. Add community_id to channels
    op.add_column('channels', sa.Column('community_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_channels_community_id', 'channels', 'communities', ['community_id'], ['id'], ondelete='CASCADE')



def downgrade() -> None:
    # 1. Drop foreign keys and columns from dependent tables
    op.drop_constraint('fk_channels_community_id', 'channels', type_='foreignkey')
    op.drop_column('channels', 'community_id')

    op.drop_constraint('fk_posts_community_id', 'posts', type_='foreignkey')
    op.drop_column('posts', 'community_id')

    op.drop_constraint('fk_users_community_id', 'users', type_='foreignkey')
    op.drop_column('users', 'community_id')

    # 2. Drop communities table and its index
    op.drop_index(op.f('ix_communities_id'), table_name='communities')
    op.drop_table('communities')

