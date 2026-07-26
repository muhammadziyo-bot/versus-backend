"""add moderation tables (reports, user_bans) and moderation fields to users

Revision ID: add_moderation_tables
Revises: add_views_to_club_discussions
Create Date: 2026-07-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_moderation_tables'
down_revision = 'add_views_to_club_discussions'
branch_labels = None
depends_on = None


def upgrade():
    # Add moderation fields to app_users
    op.add_column('app_users', sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('app_users', sa.Column('is_muted', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('app_users', sa.Column('is_banned', sa.Boolean(), nullable=False, server_default='false'))

    # Create reports table
    op.create_table(
        'reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reporter_id', sa.Integer(), nullable=False),
        sa.Column('reported_user_id', sa.Integer(), nullable=False),
        sa.Column('target_type', sa.String(), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('resolved_by', sa.Integer(), nullable=True),
        sa.Column('resolution', sa.String(), nullable=True),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['reporter_id'], ['app_users.id'], ),
        sa.ForeignKeyConstraint(['reported_user_id'], ['app_users.id'], ),
        sa.ForeignKeyConstraint(['resolved_by'], ['app_users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reports_id'), 'reports', ['id'], unique=False)
    op.create_index(op.f('ix_reports_status'), 'reports', ['status'], unique=False)
    op.create_index(op.f('ix_reports_reported_user_id'), 'reports', ['reported_user_id'], unique=False)

    # Create user_bans table
    op.create_table(
        'user_bans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('banned_by', sa.Integer(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('ban_type', sa.String(), nullable=False, server_default='mute'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('lifted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('lifted_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['app_users.id'], ),
        sa.ForeignKeyConstraint(['banned_by'], ['app_users.id'], ),
        sa.ForeignKeyConstraint(['lifted_by'], ['app_users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_bans_id'), 'user_bans', ['id'], unique=False)
    op.create_index(op.f('ix_user_bans_user_id'), 'user_bans', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_bans_is_active'), 'user_bans', ['is_active'], unique=False)


def downgrade():
    # Drop user_bans table
    op.drop_index(op.f('ix_user_bans_is_active'), table_name='user_bans')
    op.drop_index(op.f('ix_user_bans_user_id'), table_name='user_bans')
    op.drop_index(op.f('ix_user_bans_id'), table_name='user_bans')
    op.drop_table('user_bans')

    # Drop reports table
    op.drop_index(op.f('ix_reports_reported_user_id'), table_name='reports')
    op.drop_index(op.f('ix_reports_status'), table_name='reports')
    op.drop_index(op.f('ix_reports_id'), table_name='reports')
    op.drop_table('reports')

    # Remove moderation fields from app_users
    op.drop_column('app_users', 'is_banned')
    op.drop_column('app_users', 'is_muted')
    op.drop_column('app_users', 'is_admin')
