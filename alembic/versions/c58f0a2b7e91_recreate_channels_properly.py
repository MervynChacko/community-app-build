"""properly create channels, channel_members, and messages tables

Revision ID: c58f0a2b7e91
Revises: b47e2a9f1c3d
Create Date: 2026-08-17 16:12:00.000000

This migration replaces schema that was previously created only via
Base.metadata.create_all() (never by a real migration -- see the
c6793e530f73 migration, which only drops a legacy direct_messages table
and never actually creates these). The tables were manually dropped
before this migration was written (confirmed empty, zero rows, so no
data loss).

Also fixes the channeltype enum's label casing (was 'DIRECT'/'GROUP',
now lowercase 'direct'/'group', matching ChannelType's .value and the
values_callable fix applied to the model), and adds two improvements
over the original drifted schema: a uniqueness constraint on
(channel_id, user_id) in channel_members, and a composite index on
messages(channel_id, created_at) for paginated history queries.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c58f0a2b7e91'
down_revision: Union[str, Sequence[str], None] = 'b47e2a9f1c3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Explicitly create the Postgres ENUM type before referencing it
    #    in a column, same pattern as the userrole migration.
    channel_type_enum = postgresql.ENUM('direct', 'group', name='channeltype')
    channel_type_enum.create(op.get_bind(), checkfirst=True)

    # 2. channels
    op.create_table(
        'channels',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('community_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=100), nullable=True),
        sa.Column(
            'type',
            postgresql.ENUM('direct', 'group', name='channeltype', create_type=False),
            nullable=False,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['community_id'], ['communities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_channels_id'), 'channels', ['id'], unique=False)

    # 3. channel_members
    op.create_table(
        'channel_members',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('channel_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('channel_id', 'user_id', name='uq_channel_members_channel_user'),
    )
    op.create_index(op.f('ix_channel_members_id'), 'channel_members', ['id'], unique=False)
    op.create_index(op.f('ix_channel_members_user_id'), 'channel_members', ['user_id'], unique=False)

    # 4. messages
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('channel_id', sa.Integer(), nullable=False),
        sa.Column('sender_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_messages_id'), 'messages', ['id'], unique=False)
    op.create_index('ix_messages_channel_id_created_at', 'messages', ['channel_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_messages_channel_id_created_at', table_name='messages')
    op.drop_index(op.f('ix_messages_id'), table_name='messages')
    op.drop_table('messages')

    op.drop_index(op.f('ix_channel_members_user_id'), table_name='channel_members')
    op.drop_index(op.f('ix_channel_members_id'), table_name='channel_members')
    op.drop_table('channel_members')

    op.drop_index(op.f('ix_channels_id'), table_name='channels')
    op.drop_table('channels')

    channel_type_enum = postgresql.ENUM('direct', 'group', name='channeltype')
    channel_type_enum.drop(op.get_bind(), checkfirst=True)