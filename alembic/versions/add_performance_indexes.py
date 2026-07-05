"""add_performance_indexes

Revision ID: add_performance_indexes
Revises: simplify_elo_system_and_add_leaderboard
Create Date: 2024-01-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_performance_indexes'
down_revision = 'simplify_elo_system_and_add_leaderboard'
branch_labels = None
depends_on = None


def upgrade():
    # ClubDiscussion indexes for faster queries
    op.create_index('ix_club_discussions_author_id', 'club_discussions', ['author_id'])
    op.create_index('ix_club_discussions_club_id', 'club_discussions', ['club_id'])
    op.create_index('ix_club_discussions_created_at', 'club_discussions', ['created_at'])
    op.create_index('ix_club_discussions_updated_at', 'club_discussions', ['updated_at'])
    
    # ClubComment indexes
    op.create_index('ix_club_comments_discussion_id', 'club_comments', ['discussion_id'])
    op.create_index('ix_club_comments_author_id', 'club_comments', ['author_id'])
    op.create_index('ix_club_comments_parent_id', 'club_comments', ['parent_id'])
    op.create_index('ix_club_comments_created_at', 'club_comments', ['created_at'])
    
    # Clubs indexes
    op.create_index('ix_clubs_founder_id', 'clubs', ['founder_id'])
    op.create_index('ix_clubs_category', 'clubs', ['category'])
    op.create_index('ix_clubs_created_at', 'clubs', ['created_at'])
    
    # Users indexes (email and username already indexed)
    op.create_index('ix_users_created_at', 'users', ['created_at'])
    op.create_index('ix_users_elo_rating', 'users', ['elo_rating'])
    
    # Debates indexes
    op.create_index('ix_debates_creator_id', 'debates', ['creator_id'])
    op.create_index('ix_debates_status', 'debates', ['status'])
    op.create_index('ix_debates_created_at', 'debates', ['created_at'])
    
    # Votes indexes
    op.create_index('ix_discussion_votes_user_id', 'discussion_votes', ['user_id'])
    op.create_index('ix_discussion_votes_discussion_id', 'discussion_votes', ['discussion_id'])
    op.create_index('ix_comment_votes_user_id', 'comment_votes', ['user_id'])
    op.create_index('ix_comment_votes_comment_id', 'comment_votes', ['comment_id'])
    
    # Notifications indexes
    op.create_index('ix_notifications_user_id', 'notifications', ['user_id'])
    op.create_index('ix_notifications_created_at', 'notifications', ['created_at'])
    op.create_index('ix_notifications_is_read', 'notifications', ['is_read'])
    
    # Friends indexes
    op.create_index('ix_friends_user_id', 'friends', ['user_id'])
    op.create_index('ix_friends_friend_id', 'friends', ['friend_id'])
    op.create_index('ix_friends_status', 'friends', ['status'])


def downgrade():
    # Drop all indexes in reverse order
    op.drop_index('ix_friends_status', table_name='friends')
    op.drop_index('ix_friends_friend_id', table_name='friends')
    op.drop_index('ix_friends_user_id', table_name='friends')
    op.drop_index('ix_notifications_is_read', table_name='notifications')
    op.drop_index('ix_notifications_created_at', table_name='notifications')
    op.drop_index('ix_notifications_user_id', table_name='notifications')
    op.drop_index('ix_comment_votes_comment_id', table_name='comment_votes')
    op.drop_index('ix_comment_votes_user_id', table_name='comment_votes')
    op.drop_index('ix_discussion_votes_discussion_id', table_name='discussion_votes')
    op.drop_index('ix_discussion_votes_user_id', table_name='discussion_votes')
    op.drop_index('ix_debates_created_at', table_name='debates')
    op.drop_index('ix_debates_status', table_name='debates')
    op.drop_index('ix_debates_creator_id', table_name='debates')
    op.drop_index('ix_users_elo_rating', table_name='users')
    op.drop_index('ix_users_created_at', table_name='users')
    op.drop_index('ix_clubs_created_at', table_name='clubs')
    op.drop_index('ix_clubs_category', table_name='clubs')
    op.drop_index('ix_clubs_founder_id', table_name='clubs')
    op.drop_index('ix_club_comments_created_at', table_name='club_comments')
    op.drop_index('ix_club_comments_parent_id', table_name='club_comments')
    op.drop_index('ix_club_comments_author_id', table_name='club_comments')
    op.drop_index('ix_club_comments_discussion_id', table_name='club_comments')
    op.drop_index('ix_club_discussions_updated_at', table_name='club_discussions')
    op.drop_index('ix_club_discussions_created_at', table_name='club_discussions')
    op.drop_index('ix_club_discussions_club_id', table_name='club_discussions')
    op.drop_index('ix_club_discussions_author_id', table_name='club_discussions')