from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List
from pydantic import Field

class DiscussionList(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    title: str
    category: Optional[str] = None
    author: str
    author_id: int
    club_id: Optional[int] = None
    club_name: Optional[str] = None
    replies: int = 0
    views: int = 0
    last_activity: Optional[datetime] = None
    is_pinned: bool = False
    is_hot: bool = False
    tags: List[str] = []
    upvotes: int = 0
    downvotes: int = 0
    user_vote: Optional[str] = None  # 'up', 'down', or None

class DiscussionStats(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    total_discussions: int
    total_replies: int
    active_discussions: int

class DiscussionCreate(BaseModel):
    title: str
    content: str
    club_id: Optional[int] = None
    tags: List[str] = []

class DiscussionDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    title: str
    content: str
    author: str
    author_id: int
    club_id: Optional[int] = None
    club_name: Optional[str] = None
    upvotes: int = 0
    downvotes: int = 0
    user_vote: Optional[str] = None  # 'up', 'down', or None
    created_at: datetime
    updated_at: Optional[datetime] = None
    tags: List[str] = []
    comments: List['Comment'] = []

class CommentCreate(BaseModel):
    content: str
    parent_id: Optional[int] = None

class Comment(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    content: str
    author: str
    author_id: int
    discussion_id: int
    parent_id: Optional[int] = None
    upvotes: int = 0
    downvotes: int = 0
    created_at: datetime
    user_vote: Optional[str] = None  # 'up', 'down', or None
    replies: List['Comment'] = []

class VoteRequest(BaseModel):
    vote_type: str  # 'up' or 'down'
