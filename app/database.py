from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Configure connection pooling for production
# Supabase free tier limits: 15 concurrent connections in session mode
engine = create_engine(
    settings.database_url,
    pool_size=10,           # Number of connections to keep in pool (reduced for Supabase limits)
    max_overflow=5,         # Additional connections allowed beyond pool_size (reduced for Supabase limits)
    pool_pre_ping=True,      # Verify connections before using
    pool_recycle=3600,       # Recycle connections after 1 hour
    echo=False               # Set to True for SQL query logging in development
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
