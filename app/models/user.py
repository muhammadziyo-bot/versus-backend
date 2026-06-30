from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    bio = Column(Text)
    avatar_url = Column(String)
    elo_rating = Column(Integer, default=400)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # User settings
    language = Column(String, default="english")
    notifications_enabled = Column(Boolean, default=True)
    email_alerts = Column(Boolean, default=False)
    sound_effects = Column(Boolean, default=True)
    privacy = Column(String, default="public")
    telegram_username = Column(String, unique=True, index=True)
    telegram_chat_id = Column(String, unique=True, index=True)
    
    # Security fields
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    debates = relationship("Debate", back_populates="creator")
    clubs = relationship("Club", secondary="club_members", back_populates="members")
