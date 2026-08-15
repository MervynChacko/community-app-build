"""add role to users and create activation_codes table

Revision ID: b47e2a9f1c3d
Revises: 574613be4cc6
Create Date: 2026-08-14 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b47e2a9f1c3d'
down_revision: Union[str, Sequence[str], None] = '574613be4cc6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Explicitly create the Postgres ENUM type before referencing it in
    #    a column. create_type=False on the column definition below stops
    #    SQLAlchemy from trying to issue a second CREATE TYPE and failing
    #    with a duplicate-type error.
    user_role_enum = postgresql.ENUM('resident', 'staff', name='userrole')
    user_role_enum.create(op.get_bind(), checkfirst=True)

    # 2. Add role to users. server_default backfills all existing rows as
    #    'resident' in the same statement -- no separate data migration
    #    needed, and no NULL roles left behind.
    op.add_column(
        'users',
        sa.Column(
            'role',
            postgresql.ENUM('resident', 'staff', name='userrole', create_type=False),
            nullable=False,
            server_default='resident',
        ),
    )

    # 3. Create activation_codes table
    op.create_table(
        'activation_codes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('community_id', sa.Integer(), nullable=False),
        sa.Column('apartment_number', sa.String(length=20), nullable=True),
        sa.Column('max_uses', sa.Integer(), nullable=False, server_default='4'),
        sa.Column('used_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['community_id'], ['communities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    op.create_index(op.f('ix_activation_codes_id'), 'activation_codes', ['id'], unique=False)
    op.create_index(op.f('ix_activation_codes_code'), 'activation_codes', ['code'], unique=True)
    # Supports "list codes for my community" queries from the staff endpoints
    op.create_index(op.f('ix_activation_codes_community_id'), 'activation_codes', ['community_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_activation_codes_community_id'), table_name='activation_codes')
    op.drop_index(op.f('ix_activation_codes_code'), table_name='activation_codes')
    op.drop_index(op.f('ix_activation_codes_id'), table_name='activation_codes')
    op.drop_table('activation_codes')

    op.drop_column('users', 'role')

    user_role_enum = postgresql.ENUM('resident', 'staff', name='userrole')
    user_role_enum.drop(op.get_bind(), checkfirst=True)