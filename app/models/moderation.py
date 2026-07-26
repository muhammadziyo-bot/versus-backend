from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(Integer, ForeignKey("app_users.id"), nullable=False)
    reported_user_id = Column(Integer, ForeignKey("app_users.id"), nullable=False)
    target_type = Column(String, nullable=False)
    target_id = Column(Integer, nullable=False)
    reason = Column(String, nullable=False)
    description = Column(Text)
    status = Column(String, default="pending")
    resolved_by = Column(Integer, ForeignKey("app_users.id"), nullable=True)
    resolution = Column(String, nullable=True)
    resolution_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    reporter = relationship("User", foreign_keys=[reporter_id])
    reported_user = relationship("User", foreign_keys=[reported_user_id])
    resolver = relationship("User", foreign_keys=[resolved_by])


class UserBan(Base):
    __tablename__ = "user_bans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("app_users.id"), nullable=False)
    banned_by = Column(Integer, ForeignKey("app_users.id"), nullable=False)
    reason = Column(Text, nullable=False)
    ban_type = Column(String, default="mute")
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    lifted_at = Column(DateTime(timezone=True), nullable=True)
    lifted_by = Column(Integer, ForeignKey("app_users.id"), nullable=True)

    user = relationship("User", foreign_keys=[user_id])
    banned_by_user = relationship("User", foreign_keys=[banned_by])
    lifted_by_user = relationship("User", foreign_keys=[lifted_by])
