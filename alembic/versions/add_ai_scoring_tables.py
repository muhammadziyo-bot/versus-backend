"""add_ai_scoring_tables

Revision ID: add_ai_scoring_tables
Revises: add_performance_indexes
Create Date: 2024-01-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_ai_scoring_tables'
down_revision = 'add_performance_indexes'
branch_labels = None
depends_on = None


def upgrade():
    # Create ai_argument_scores table
    op.create_table(
        'ai_argument_scores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('battle_round_id', sa.Integer(), nullable=False),
        sa.Column('side', sa.String(), nullable=False),
        sa.Column('logical_coherence', sa.Integer(), nullable=True, server_default='5'),
        sa.Column('evidence_quality', sa.Integer(), nullable=True, server_default='5'),
        sa.Column('clarity', sa.Integer(), nullable=True, server_default='5'),
        sa.Column('relevance', sa.Integer(), nullable=True, server_default='5'),
        sa.Column('counter_effectiveness', sa.Integer(), nullable=True, server_default='5'),
        sa.Column('overall_score', sa.Integer(), nullable=True, server_default='5'),
        sa.Column('strengths', sa.Text(), nullable=True),
        sa.Column('weaknesses', sa.Text(), nullable=True),
        sa.Column('detailed_feedback', sa.Text(), nullable=True),
        sa.Column('model_used', sa.String(), nullable=True),
        sa.Column('scored_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['battle_round_id'], ['battle_rounds.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_argument_scores_battle_round_id'), 'ai_argument_scores', ['battle_round_id'])
    op.create_index(op.f('ix_ai_argument_scores_side'), 'ai_argument_scores', ['side'])
    
    # Create ai_battle_results table
    op.create_table(
        'ai_battle_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('battle_room_id', sa.Integer(), nullable=False),
        sa.Column('pro_total_score', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('con_total_score', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('winner_side', sa.String(), nullable=True),
        sa.Column('confidence', sa.Integer(), nullable=True, server_default='5'),
        sa.Column('pro_strengths', sa.Text(), nullable=True),
        sa.Column('pro_weaknesses', sa.Text(), nullable=True),
        sa.Column('con_strengths', sa.Text(), nullable=True),
        sa.Column('con_weaknesses', sa.Text(), nullable=True),
        sa.Column('overall_analysis', sa.Text(), nullable=True),
        sa.Column('round_breakdown', postgresql.JSON(), nullable=True),
        sa.Column('status', sa.String(), nullable=True, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('model_used', sa.String(), nullable=True),
        sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('processing_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['battle_room_id'], ['battle_rooms.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_battle_results_battle_room_id'), 'ai_battle_results', ['battle_room_id'])
    op.create_index(op.f('ix_ai_battle_results_status'), 'ai_battle_results', ['status'])
    op.create_index(op.f('ix_ai_battle_results_winner_side'), 'ai_battle_results', ['winner_side'])


def downgrade():
    # Drop ai_battle_results table
    op.drop_index(op.f('ix_ai_battle_results_winner_side'), table_name='ai_battle_results')
    op.drop_index(op.f('ix_ai_battle_results_status'), table_name='ai_battle_results')
    op.drop_index(op.f('ix_ai_battle_results_battle_room_id'), table_name='ai_battle_results')
    op.drop_table('ai_battle_results')
    
    # Drop ai_argument_scores table
    op.drop_index(op.f('ix_ai_argument_scores_side'), table_name='ai_argument_scores')
    op.drop_index(op.f('ix_ai_argument_scores_battle_round_id'), table_name='ai_argument_scores')
    op.drop_table('ai_argument_scores')
