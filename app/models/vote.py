from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class DiscussionVote(Base):
    __tablename__ = "discussion_votes"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    discussion_id = Column(Integer, ForeignKey("club_discussions.id"), nullable=False)
    vote_type = Column(String, nullable=False)  # 'up' or 'down'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (UniqueConstraint('user_id', 'discussion_id', name='unique_user_discussion_vote'),)
    
    # Relationships
    user = relationship("User")
    discussion = relationship("ClubDiscussion")

class CommentVote(Base):
    __tablename__ = "comment_votes"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    comment_id = Column(Integer, ForeignKey("club_comments.id"), nullable=False)
    vote_type = Column(String, nullable=False)  # 'up' or 'down'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (UniqueConstraint('user_id', 'comment_id', name='unique_user_comment_vote'),)
    
    # Relationships
    user = relationship("User")
    comment = relationship("ClubComment")
