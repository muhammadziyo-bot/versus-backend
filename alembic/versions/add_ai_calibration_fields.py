"""add calibration fields to ai_argument_scores

Revision ID: add_ai_calibration_fields
Revises: add_moderation_tables
Create Date: 2026-07-26 22:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_ai_calibration_fields'
down_revision = 'add_moderation_tables'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('ai_argument_scores', sa.Column('community_average_score', sa.Integer(), nullable=True))
    op.add_column('ai_argument_scores', sa.Column('score_deviation', sa.Integer(), nullable=True))
    op.add_column('ai_argument_scores', sa.Column('calibration_status', sa.String(), nullable=False, server_default='pending'))


def downgrade():
    op.drop_column('ai_argument_scores', 'calibration_status')
    op.drop_column('ai_argument_scores', 'score_deviation')
    op.drop_column('ai_argument_scores', 'community_average_score')
