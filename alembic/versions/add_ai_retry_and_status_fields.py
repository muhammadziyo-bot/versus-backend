"""add score_status, retry_count, error_message to ai_argument_scores

Revision ID: add_ai_retry_and_status_fields
Revises: add_ai_calibration_fields
Create Date: 2026-07-26 22:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_ai_retry_and_status_fields'
down_revision = 'add_ai_calibration_fields'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('ai_argument_scores', sa.Column('score_status', sa.String(), nullable=False, server_default='pending'))
    op.add_column('ai_argument_scores', sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('ai_argument_scores', sa.Column('error_message', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('ai_argument_scores', 'error_message')
    op.drop_column('ai_argument_scores', 'retry_count')
    op.drop_column('ai_argument_scores', 'score_status')
