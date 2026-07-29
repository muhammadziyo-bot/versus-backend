-- Complete database schema for Versus
-- Run this in Supabase SQL Editor after creating your project
-- This includes all tables, indexes, and AI scoring functionality

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Users table
CREATE TABLE IF NOT EXISTS app_users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    bio TEXT,
    avatar_url VARCHAR(500),
    elo_rating INTEGER DEFAULT 400,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    
    -- User settings
    language VARCHAR(50) DEFAULT 'english',
    notifications_enabled BOOLEAN DEFAULT true,
    email_alerts BOOLEAN DEFAULT false,
    sound_effects BOOLEAN DEFAULT true,
    privacy VARCHAR(50) DEFAULT 'public',
    telegram_username VARCHAR(255) UNIQUE,
    telegram_chat_id VARCHAR(255) UNIQUE,
    
    -- Security fields
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP WITH TIME ZONE,

    -- Moderation fields
    is_admin BOOLEAN DEFAULT false,
    is_muted BOOLEAN DEFAULT false,
    is_banned BOOLEAN DEFAULT false
);

-- Create indexes for users
CREATE INDEX IF NOT EXISTS idx_users_email ON app_users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON app_users(username);
CREATE INDEX IF NOT EXISTS idx_users_telegram_username ON app_users(telegram_username);
CREATE INDEX IF NOT EXISTS idx_users_telegram_chat_id ON app_users(telegram_chat_id);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON app_users(created_at);
CREATE INDEX IF NOT EXISTS idx_users_elo_rating ON app_users(elo_rating);

-- Add moderation columns to existing users table if missing
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT false;
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS is_muted BOOLEAN DEFAULT false;
ALTER TABLE app_users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN DEFAULT false;

-- Clubs table
CREATE TABLE IF NOT EXISTS clubs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    badge VARCHAR(10) DEFAULT '🤖',
    founder_id INTEGER REFERENCES app_users(id),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes for clubs
CREATE INDEX IF NOT EXISTS idx_clubs_founder_id ON clubs(founder_id);
CREATE INDEX IF NOT EXISTS idx_clubs_category ON clubs(category);
CREATE INDEX IF NOT EXISTS idx_clubs_created_at ON clubs(created_at);

-- Club members association table
CREATE TABLE IF NOT EXISTS club_members (
    club_id INTEGER REFERENCES clubs(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES app_users(id) ON DELETE CASCADE,
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_admin BOOLEAN DEFAULT false,
    PRIMARY KEY (club_id, user_id)
);

-- Club discussions table
CREATE TABLE IF NOT EXISTS club_discussions (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    author_id INTEGER REFERENCES app_users(id),
    club_id INTEGER REFERENCES clubs(id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT true,
    upvotes INTEGER DEFAULT 0,
    downvotes INTEGER DEFAULT 0,
    views INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes for club discussions
CREATE INDEX IF NOT EXISTS idx_club_discussions_author_id ON club_discussions(author_id);
CREATE INDEX IF NOT EXISTS idx_club_discussions_club_id ON club_discussions(club_id);
CREATE INDEX IF NOT EXISTS idx_club_discussions_created_at ON club_discussions(created_at);
CREATE INDEX IF NOT EXISTS idx_club_discussions_updated_at ON club_discussions(updated_at);

-- Club comments table
CREATE TABLE IF NOT EXISTS club_comments (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    author_id INTEGER REFERENCES app_users(id),
    discussion_id INTEGER REFERENCES club_discussions(id) ON DELETE CASCADE,
    parent_id INTEGER REFERENCES club_comments(id),
    upvotes INTEGER DEFAULT 0,
    downvotes INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for club comments
CREATE INDEX IF NOT EXISTS idx_club_comments_discussion_id ON club_comments(discussion_id);
CREATE INDEX IF NOT EXISTS idx_club_comments_author_id ON club_comments(author_id);
CREATE INDEX IF NOT EXISTS idx_club_comments_parent_id ON club_comments(parent_id);
CREATE INDEX IF NOT EXISTS idx_club_comments_created_at ON club_comments(created_at);

-- Discussion votes table
CREATE TABLE IF NOT EXISTS discussion_votes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES app_users(id) ON DELETE CASCADE,
    discussion_id INTEGER REFERENCES club_discussions(id) ON DELETE CASCADE,
    vote_type VARCHAR(10) NOT NULL, -- 'up' or 'down'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, discussion_id)
);

-- Create indexes for discussion votes
CREATE INDEX IF NOT EXISTS idx_discussion_votes_user_id ON discussion_votes(user_id);
CREATE INDEX IF NOT EXISTS idx_discussion_votes_discussion_id ON discussion_votes(discussion_id);

-- Comment votes table
CREATE TABLE IF NOT EXISTS comment_votes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES app_users(id) ON DELETE CASCADE,
    comment_id INTEGER REFERENCES club_comments(id) ON DELETE CASCADE,
    vote_type VARCHAR(10) NOT NULL, -- 'up' or 'down'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, comment_id)
);

-- Create indexes for comment votes
CREATE INDEX IF NOT EXISTS idx_comment_votes_user_id ON comment_votes(user_id);
CREATE INDEX IF NOT EXISTS idx_comment_votes_comment_id ON comment_votes(comment_id);

-- Debates table
CREATE TABLE IF NOT EXISTS debates (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    status VARCHAR(50) DEFAULT 'active',
    created_by INTEGER REFERENCES app_users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes for debates
CREATE INDEX IF NOT EXISTS idx_debates_creator_id ON debates(created_by);
CREATE INDEX IF NOT EXISTS idx_debates_status ON debates(status);
CREATE INDEX IF NOT EXISTS idx_debates_created_at ON debates(created_at);

-- Arguments table
CREATE TABLE IF NOT EXISTS arguments (
    id SERIAL PRIMARY KEY,
    text TEXT NOT NULL,
    side VARCHAR(10) NOT NULL,
    author_id INTEGER REFERENCES app_users(id),
    debate_id INTEGER REFERENCES debates(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Battle rooms table
CREATE TABLE IF NOT EXISTS battle_rooms (
    id SERIAL PRIMARY KEY,
    debate_id INTEGER REFERENCES debates(id) ON DELETE CASCADE,
    pro_user_id INTEGER REFERENCES app_users(id),
    con_user_id INTEGER REFERENCES app_users(id),
    status VARCHAR(50) DEFAULT 'waiting',
    current_round INTEGER DEFAULT 1,
    max_rounds INTEGER DEFAULT 3,
    round_time_limit INTEGER DEFAULT 300,
    
    -- Enhanced battle timing
    started_at TIMESTAMP WITH TIME ZONE,
    round_started_at TIMESTAMP WITH TIME ZONE,
    round_ends_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Battle results
    winner_side VARCHAR(10),
    winner_user_id INTEGER REFERENCES app_users(id)
);

-- Votes table
CREATE TABLE IF NOT EXISTS votes (
    id SERIAL PRIMARY KEY,
    battle_room_id INTEGER REFERENCES battle_rooms(id) ON DELETE CASCADE,
    voter_id INTEGER REFERENCES app_users(id),
    side VARCHAR(10) NOT NULL,
    
    -- Enhanced voting criteria
    reasoning TEXT,
    confidence INTEGER DEFAULT 5,
    argument_quality INTEGER DEFAULT 5,
    clarity INTEGER DEFAULT 5,
    persuasiveness INTEGER DEFAULT 5,
    evidence INTEGER DEFAULT 5,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(battle_room_id, voter_id)
);

-- Battle rounds table
CREATE TABLE IF NOT EXISTS battle_rounds (
    id SERIAL PRIMARY KEY,
    battle_room_id INTEGER REFERENCES battle_rooms(id) ON DELETE CASCADE,
    round_number INTEGER NOT NULL,
    status VARCHAR(50) DEFAULT 'waiting',
    
    -- Round arguments
    pro_argument TEXT,
    con_argument TEXT,
    pro_submitted_at TIMESTAMP WITH TIME ZONE,
    con_submitted_at TIMESTAMP WITH TIME ZONE,
    
    -- Round timing
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(battle_room_id, round_number)
);

-- AI Argument Scores table
CREATE TABLE IF NOT EXISTS ai_argument_scores (
    id SERIAL PRIMARY KEY,
    battle_round_id INTEGER REFERENCES battle_rounds(id) ON DELETE CASCADE,
    side VARCHAR(10) NOT NULL, -- "pro" or "con"
    
    -- AI scoring criteria (1-10 scale)
    logical_coherence INTEGER DEFAULT 5,
    evidence_quality INTEGER DEFAULT 5,
    clarity INTEGER DEFAULT 5,
    relevance INTEGER DEFAULT 5,
    counter_effectiveness INTEGER DEFAULT 5,
    
    -- Overall score and analysis
    overall_score INTEGER DEFAULT 5,
    strengths TEXT,
    weaknesses TEXT,
    detailed_feedback TEXT,
    
    -- Status tracking
    score_status VARCHAR(50) DEFAULT 'pending', -- "pending", "completed", "failed"
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,

    -- Calibration tracking
    community_average_score INTEGER,
    score_deviation INTEGER,
    calibration_status VARCHAR(50) DEFAULT 'pending', -- "pending", "calibrated"

    -- Metadata
    model_used VARCHAR(100),
    scored_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for AI argument scores
CREATE INDEX IF NOT EXISTS idx_ai_argument_scores_battle_round_id ON ai_argument_scores(battle_round_id);
CREATE INDEX IF NOT EXISTS idx_ai_argument_scores_side ON ai_argument_scores(side);

-- Add new columns to existing ai_argument_scores table if missing
ALTER TABLE ai_argument_scores ADD COLUMN IF NOT EXISTS score_status VARCHAR(50) DEFAULT 'pending';
ALTER TABLE ai_argument_scores ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;
ALTER TABLE ai_argument_scores ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE ai_argument_scores ADD COLUMN IF NOT EXISTS community_average_score INTEGER;
ALTER TABLE ai_argument_scores ADD COLUMN IF NOT EXISTS score_deviation INTEGER;
ALTER TABLE ai_argument_scores ADD COLUMN IF NOT EXISTS calibration_status VARCHAR(50) DEFAULT 'pending';

-- AI Battle Results table
CREATE TABLE IF NOT EXISTS ai_battle_results (
    id SERIAL PRIMARY KEY,
    battle_room_id INTEGER REFERENCES battle_rooms(id) ON DELETE CASCADE,
    
    -- Final scores
    pro_total_score INTEGER DEFAULT 0,
    con_total_score INTEGER DEFAULT 0,
    winner_side VARCHAR(10),
    confidence INTEGER DEFAULT 5,
    
    -- Detailed breakdown
    pro_strengths TEXT,
    pro_weaknesses TEXT,
    con_strengths TEXT,
    con_weaknesses TEXT,
    overall_analysis TEXT,
    
    -- Round-by-round breakdown
    round_breakdown JSONB,
    
    -- Processing status
    status VARCHAR(50) DEFAULT 'pending',
    error_message TEXT,
    
    -- Metadata
    model_used VARCHAR(100),
    processing_started_at TIMESTAMP WITH TIME ZONE,
    processing_completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for AI battle results
CREATE INDEX IF NOT EXISTS idx_ai_battle_results_battle_room_id ON ai_battle_results(battle_room_id);
CREATE INDEX IF NOT EXISTS idx_ai_battle_results_status ON ai_battle_results(status);
CREATE INDEX IF NOT EXISTS idx_ai_battle_results_winner_side ON ai_battle_results(winner_side);

-- Elo history table
CREATE TABLE IF NOT EXISTS elo_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES app_users(id) ON DELETE CASCADE,
    battle_room_id INTEGER REFERENCES battle_rooms(id) ON DELETE SET NULL,
    old_elo INTEGER NOT NULL,
    new_elo INTEGER NOT NULL,
    elo_change INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for elo history
CREATE INDEX IF NOT EXISTS idx_elo_history_user_id ON elo_history(user_id);

-- Friend requests table
CREATE TABLE IF NOT EXISTS friend_requests (
    id SERIAL PRIMARY KEY,
    sender_id INTEGER REFERENCES app_users(id) ON DELETE CASCADE,
    receiver_id INTEGER REFERENCES app_users(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'pending',
    message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Friends table
CREATE TABLE IF NOT EXISTS friends (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES app_users(id) ON DELETE CASCADE,
    friend_id INTEGER REFERENCES app_users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, friend_id),
    CHECK (user_id != friend_id)
);

-- Create indexes for friends
CREATE INDEX IF NOT EXISTS idx_friends_user_id ON friends(user_id);
CREATE INDEX IF NOT EXISTS idx_friends_friend_id ON friends(friend_id);

-- Notifications table
CREATE TABLE IF NOT EXISTS notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES app_users(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT,
    data JSONB,
    is_read BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for notifications
CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON notifications(created_at);
CREATE INDEX IF NOT EXISTS idx_notifications_is_read ON notifications(is_read);

-- Reports table
CREATE TABLE IF NOT EXISTS reports (
    id SERIAL PRIMARY KEY,
    reporter_id INTEGER REFERENCES app_users(id) NOT NULL,
    reported_user_id INTEGER REFERENCES app_users(id) NOT NULL,
    target_type VARCHAR NOT NULL,
    target_id INTEGER NOT NULL,
    reason VARCHAR NOT NULL,
    description TEXT,
    status VARCHAR DEFAULT 'pending',
    resolved_by INTEGER REFERENCES app_users(id),
    resolution VARCHAR,
    resolution_note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE
);

-- Create indexes for reports
CREATE INDEX IF NOT EXISTS idx_reports_id ON reports(id);
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);
CREATE INDEX IF NOT EXISTS idx_reports_reported_user_id ON reports(reported_user_id);

-- User bans table
CREATE TABLE IF NOT EXISTS user_bans (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES app_users(id) NOT NULL,
    banned_by INTEGER REFERENCES app_users(id) NOT NULL,
    reason TEXT NOT NULL,
    ban_type VARCHAR DEFAULT 'mute',
    is_active BOOLEAN DEFAULT true,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    lifted_at TIMESTAMP WITH TIME ZONE,
    lifted_by INTEGER REFERENCES app_users(id)
);

-- Create indexes for user bans
CREATE INDEX IF NOT EXISTS idx_user_bans_id ON user_bans(id);
CREATE INDEX IF NOT EXISTS idx_user_bans_user_id ON user_bans(user_id);
CREATE INDEX IF NOT EXISTS idx_user_bans_is_active ON user_bans(is_active);

-- Additional performance indexes
CREATE INDEX IF NOT EXISTS idx_battle_rooms_status ON battle_rooms(status);
CREATE INDEX IF NOT EXISTS idx_battle_rooms_debate ON battle_rooms(debate_id);
CREATE INDEX IF NOT EXISTS idx_votes_battle_room ON votes(battle_room_id);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
DROP TRIGGER IF EXISTS update_users_updated_at ON app_users CASCADE;
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON app_users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_clubs_updated_at ON clubs CASCADE;
CREATE TRIGGER update_clubs_updated_at BEFORE UPDATE ON clubs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_club_discussions_updated_at ON club_discussions CASCADE;
CREATE TRIGGER update_club_discussions_updated_at BEFORE UPDATE ON club_discussions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_debates_updated_at ON debates CASCADE;
CREATE TRIGGER update_debates_updated_at BEFORE UPDATE ON debates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_friend_requests_updated_at ON friend_requests CASCADE;
CREATE TRIGGER update_friend_requests_updated_at BEFORE UPDATE ON friend_requests
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
