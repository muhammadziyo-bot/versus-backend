# Supabase Integration Guide

This directory contains Supabase-related configuration and migrations for the Versus backend.

## Directory Structure

```
supabase/
├── client.py              # Supabase client initialization
├── migrations/            # SQL migration files
│   └── 001_initial_schema.sql
└── rls_policies/          # Row Level Security policies (to be added)
```

## Setup Instructions

### 1. Create Supabase Project

1. Go to [supabase.com](https://supabase.com)
2. Create a new project named "versus"
3. Choose a region closest to your users
4. Generate and save your database password
5. Wait for the project to be ready (~2 minutes)

### 2. Get Supabase Credentials

From your Supabase project dashboard:

1. Go to Settings → API
2. Copy the following:
   - **Project URL**: `https://xxx.supabase.co`
   - **anon/public key**: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`
   - **service_role key**: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` (keep this secret!)

### 3. Run Database Migrations

1. Go to the Supabase SQL Editor
2. Open `supabase/migrations/001_initial_schema.sql`
3. Copy and run the entire script
4. This will create all required tables, indexes, and triggers

### 4. Configure Environment Variables

Add the following to your `.env` file:

```bash
# Database URL (Supabase PostgreSQL)
DATABASE_URL=postgresql://postgres:[password]@db.xxx.supabase.co:5432/postgres

# Supabase Configuration
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=your_anon_key_here
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
```

### 5. Test Connection

```python
from supabase import client

# Test admin client
supabase_admin = client.get_supabase_admin()
result = supabase_admin.table('users').select('*').limit(1).execute()
print(result)
```

## Usage

### Using the Admin Client

The admin client bypasses Row Level Security (RLS) and should be used for:

- Backend operations that need full access
- Administrative tasks
- Data migrations

```python
from supabase.client import get_supabase_admin

supabase = get_supabase_admin()
result = supabase.table('users').select('*').execute()
```

### Using the Anon Client

The anon client respects RLS and should be used for:

- Client-facing operations
- User-specific data access
- Public data queries

```python
from supabase.client import get_supabase_client

supabase = get_supabase_client()
result = supabase.table('users').select('*').eq('id', user_id).execute()
```

## Database Schema

The initial schema includes:

- **users**: User accounts and profiles
- **clubs**: Debate clubs
- **club_members**: Club membership
- **club_discussions**: Club discussion threads
- **club_comments**: Comments on discussions
- **debates**: Debate topics
- **arguments**: Arguments within debates
- **battle_rooms**: Real-time battle sessions
- **votes**: Voting on battle results
- **battle_rounds**: Individual battle rounds
- **elo_history**: ELO rating history
- **friends**: Friend relationships
- **notifications**: User notifications

## Row Level Security (RLS)

RLS policies should be added to the `rls_policies/` directory. Example policies:

```sql
-- Enable RLS on users table
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Users can view their own profile
CREATE POLICY "Users can view own profile" ON users
    FOR SELECT USING (auth.uid()::text = id::text);

-- Users can update their own profile
CREATE POLICY "Users can update own profile" ON users
    FOR UPDATE USING (auth.uid()::text = id::text);
```

## Migration Management

When making schema changes:

1. Create a new migration file: `002_add_new_feature.sql`
2. Write the SQL changes
3. Run in Supabase SQL Editor
4. Commit the migration file

## Deployment

### Render Deployment

The backend is configured to deploy to Render using `render.yaml`. The configuration includes:

- Automatic database connection
- Health check endpoint at `/health`
- Keep-alive endpoint at `/keep-alive` (to prevent spin-downs)

### Keep-Alive Setup

To prevent Render free tier from spinning down after 15 minutes of inactivity:

1. Use a cron service (cron-job.org, EasyCron)
2. Set up a job to hit `https://versus-backend.onrender.com/keep-alive` every 10 minutes
3. This keeps the instance warm and reduces cold start times

## Troubleshooting

### Connection Issues

If you can't connect to Supabase:

1. Check your DATABASE_URL format
2. Verify your Supabase credentials
3. Ensure your IP is not blocked by Supabase
4. Check Supabase status page

### Migration Errors

If migrations fail:

1. Check for existing tables that conflict
2. Run migrations in order (001, 002, etc.)
3. Check Supabase logs for detailed errors

### RLS Issues

If RLS is blocking queries:

1. Check if RLS is enabled on the table
2. Verify your policies are correct
3. Use the admin client to bypass RLS for admin tasks

## Additional Resources

- [Supabase Documentation](https://supabase.com/docs)
- [Supabase Python Client](https://supabase.com/docs/reference/python)
- [Render Deployment Guide](https://render.com/docs/deploy-fastapi)
