-- Initial database schema for Versus
-- Run this in Supabase SQL Editor after creating your project

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Users table
CREATE TABLE users (
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
    locked_until TIMESTAMP WITH TIME ZONE
);

-- Create indexes for users
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_telegram_username ON users(telegram_username);
CREATE INDEX idx_users_telegram_chat_id ON users(telegram_chat_id);

-- Clubs table
CREATE TABLE clubs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    badge VARCHAR(10) DEFAULT '🤖',
    founder_id INTEGER REFERENCES users(id),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Club members association table
CREATE TABLE club_members (
    club_id INTEGER REFERENCES clubs(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_admin BOOLEAN DEFAULT false,
    PRIMARY KEY (club_id, user_id)
);

-- Club discussions table
CREATE TABLE club_discussions (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    author_id INTEGER REFERENCES users(id),
    club_id INTEGER REFERENCES clubs(id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT true,
    upvotes INTEGER DEFAULT 0,
    downvotes INTEGER DEFAULT 0,
    views INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Club comments table
CREATE TABLE club_comments (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    author_id INTEGER REFERENCES users(id),
    discussion_id INTEGER REFERENCES club_discussions(id) ON DELETE CASCADE,
    parent_id INTEGER REFERENCES club_comments(id),
    upvotes INTEGER DEFAULT 0,
    downvotes INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Debates table
CREATE TABLE debates (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    status VARCHAR(50) DEFAULT 'active',
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Arguments table
CREATE TABLE arguments (
    id SERIAL PRIMARY KEY,
    text TEXT NOT NULL,
    side VARCHAR(10) NOT NULL,
    author_id INTEGER REFERENCES users(id),
    debate_id INTEGER REFERENCES debates(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Battle rooms table
CREATE TABLE battle_rooms (
    id SERIAL PRIMARY KEY,
    debate_id INTEGER REFERENCES debates(id) ON DELETE CASCADE,
    pro_user_id INTEGER REFERENCES users(id),
    con_user_id INTEGER REFERENCES users(id),
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
    winner_user_id INTEGER REFERENCES users(id)
);

-- Votes table
CREATE TABLE votes (
    id SERIAL PRIMARY KEY,
    battle_room_id INTEGER REFERENCES battle_rooms(id) ON DELETE CASCADE,
    voter_id INTEGER REFERENCES users(id),
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
CREATE TABLE battle_rounds (
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

-- Elo history table
CREATE TABLE elo_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    battle_room_id INTEGER REFERENCES battle_rooms(id) ON DELETE SET NULL,
    old_elo INTEGER NOT NULL,
    new_elo INTEGER NOT NULL,
    elo_change INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Friends table
CREATE TABLE friends (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    friend_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(user_id, friend_id),
    CHECK (user_id != friend_id)
);

-- Notifications table
CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT,
    data JSONB,
    is_read BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX idx_battle_rooms_status ON battle_rooms(status);
CREATE INDEX idx_battle_rooms_debate ON battle_rooms(debate_id);
CREATE INDEX idx_votes_battle_room ON votes(battle_room_id);
CREATE INDEX idx_notifications_user ON notifications(user_id);
CREATE INDEX idx_notifications_read ON notifications(is_read);
CREATE INDEX idx_friends_user ON friends(user_id);
CREATE INDEX idx_friends_friend ON friends(friend_id);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_clubs_updated_at BEFORE UPDATE ON clubs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_club_discussions_updated_at BEFORE UPDATE ON club_discussions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_debates_updated_at BEFORE UPDATE ON debates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
