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
    
    # Cloud Storage (Optional)
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: Optional[str] = None
    aws_s3_bucket: Optional[str] = None
    
    # Email Configuration (Optional)
    smtp_host: Optional[str] = None
    smtp_port: Optional[str] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None
    
    # Groq AI Configuration
    groq_api_key: Optional[str] = None
    groq_model: str = "llama-3.3-70b-versatile"
    
    class Config:
        env_file = ".env"

settings = Settings()
