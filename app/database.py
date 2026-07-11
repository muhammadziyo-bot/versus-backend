from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Configure connection pooling for production
# Supabase free tier limits: 15 concurrent connections in session mode
# Use null pool to avoid connection pooling issues with limited connections
engine = create_engine(
    settings.database_url,
    pool_size=5,            # Number of connections to keep in pool (very conservative)
    max_overflow=2,         # Additional connections allowed beyond pool_size
    pool_pre_ping=True,      # Verify connections before using
    pool_recycle=1800,       # Recycle connections after 30 minutes
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
