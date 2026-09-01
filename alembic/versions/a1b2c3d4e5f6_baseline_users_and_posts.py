"""baseline: create users and posts tables

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-08-31 09:00:00.000000

These two tables predate Alembic being introduced to this project --
they were originally created by Base.metadata.create_all() and never
captured as a migration. This migration establishes the true schema
baseline so a fresh database can be built entirely from
`alembic upgrade head` with no manual steps.

The schema here reflects the state of users and posts BEFORE any
subsequent migrations ran (i.e. before report_count/is_flagged,
before community_id, before role, before is_deleted/deleted_at).
Those columns are added by the migrations that follow in the chain.

Note: the userrole enum is NOT created here -- it was introduced in
b47e2a9f1c3d (add role to users). That migration is responsible for
creating the type and altering the users table to add the role column.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users -- base form, before community_id and role were added
    #    (community_id added by 574613be4cc6, role added by b47e2a9f1c3d)
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=False),
        sa.Column('apartment_number', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 2. posts -- base form, before report_count/is_flagged (f77abf7475c5),
    #    community_id (574613be4cc6), and is_deleted/deleted_at (d92f5e8c1a42)
    op.create_table(
        'posts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('price', sa.String(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_posts_id'), 'posts', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_posts_id'), table_name='posts')
    op.drop_table('posts')

    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')