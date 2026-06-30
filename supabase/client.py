"""
Supabase client configuration and initialization.
Provides both admin and anon clients for different use cases.
"""
from supabase import create_client, Client
from app.config import settings

# Admin client with service role key (bypasses RLS)
# Use for backend operations that need full access
supabase_admin: Client = None

# Anon client with anon key (respects RLS)
# Use for client-facing operations
supabase_client: Client = None

def init_supabase():
    """Initialize Supabase clients."""
    global supabase_admin, supabase_client
    
    if settings.supabase_url and settings.supabase_service_role_key:
        supabase_admin = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key
        )
    
    if settings.supabase_url and settings.supabase_anon_key:
        supabase_client = create_client(
            settings.supabase_url,
            settings.supabase_anon_key
        )

def get_supabase_admin() -> Client:
    """Get the admin Supabase client."""
    if not supabase_admin:
        init_supabase()
    return supabase_admin

def get_supabase_client() -> Client:
    """Get the anon Supabase client."""
    if not supabase_client:
        init_supabase()
    return supabase_client

# Initialize on import
init_supabase()
