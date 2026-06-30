from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

# Association table for club members
club_members = Table(
    'club_members',
    Base.metadata,
    Column('club_id', Integer, ForeignKey('clubs.id'), primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('joined_at', DateTime(timezone=True), server_default=func.now()),
    Column('is_admin', Boolean, default=False)
)

class Club(Base):
    __tablename__ = "clubs"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    category = Column(String)
    badge = Column(String, default="🤖")
    founder_id = Column(Integer, ForeignKey("users.id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    founder = relationship("User")
    members = relationship("User", secondary=club_members, back_populates="clubs")
    discussions = relationship("ClubDiscussion", back_populates="club")

class ClubDiscussion(Base):
    __tablename__ = "club_discussions"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"))
    club_id = Column(Integer, ForeignKey("clubs.id"))
    is_active = Column(Boolean, default=True)
    upvotes = Column(Integer, default=0)
    downvotes = Column(Integer, default=0)
    views = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    author = relationship("User")
    club = relationship("Club", back_populates="discussions")
    comments = relationship("ClubComment", back_populates="discussion")

class ClubComment(Base):
    __tablename__ = "club_comments"
    
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"))
    discussion_id = Column(Integer, ForeignKey("club_discussions.id"))
    parent_id = Column(Integer, ForeignKey("club_comments.id"), nullable=True)
    upvotes = Column(Integer, default=0)
    downvotes = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    author = relationship("User")
    discussion = relationship("ClubDiscussion", back_populates="comments")
    parent = relationship("ClubComment", remote_side=[id], backref="replies")
