from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import List, Optional
import re

class ClubBase(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    badge: str = "🤖"
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if len(v) < 3:
            raise ValueError('Club name must be at least 3 characters long')
        if len(v) > 100:
            raise ValueError('Club name must not exceed 100 characters')
        if not re.match(r'^[a-zA-Z0-9\s\-_]+$', v):
            raise ValueError('Club name can only contain letters, numbers, spaces, hyphens, and underscores')
        return v
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v):
        if v and len(v) > 1000:
            raise ValueError('Description must not exceed 1000 characters')
        return v
    
    @field_validator('category')
    @classmethod
    def validate_category(cls, v):
        if v and len(v) > 50:
            raise ValueError('Category must not exceed 50 characters')
        return v
    
    @field_validator('badge')
    @classmethod
    def validate_badge(cls, v):
        if len(v) > 10:
            raise ValueError('Badge must not exceed 10 characters')
        return v

class ClubCreate(ClubBase):
    pass

class Club(ClubBase):
    id: int
    founder_id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class ClubMember(BaseModel):
    id: int
    username: str
    full_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class ClubList(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    badge: str
    member_count: int = 0
    active_battles: int = 0
    is_member: bool = False
    founder: str
    
    class Config:
        from_attributes = True

class ClubResponse(Club):
    members: List[ClubMember] = []
    member_count: int = 0
    active_battles: int = 0
    is_member: bool = False
