from pydantic_settings import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    # Database (PostgreSQL - works with Supabase)
    database_url: str
    
    # Supabase Configuration
    supabase_url: Optional[str] = None
    supabase_anon_key: Optional[str] = None
    supabase_service_role_key: Optional[str] = None
    
    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 600  # 10 hours
    
    # App
    debug: bool = False
    cors_origins: List[str] = ["http://localhost:5173"]
    
    # Services
    telegram_bot_token: Optional[str] = None
    redis_url: str = "redis://localhost:6379/0"
    sentry_dsn: Optional[str] = None
    
    class Config:
        env_file = ".env"

settings = Settings()
