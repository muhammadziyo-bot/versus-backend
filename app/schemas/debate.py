from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import List, Optional
import re

class ArgumentBase(BaseModel):
    text: str
    side: str  # pro, con
    
    @field_validator('text')
    @classmethod
    def validate_text(cls, v):
        if len(v) < 10:
            raise ValueError('Argument must be at least 10 characters long')
        if len(v) > 5000:
            raise ValueError('Argument must not exceed 5000 characters')
        return v
    
    @field_validator('side')
    @classmethod
    def validate_side(cls, v):
        if v not in ['pro', 'con']:
            raise ValueError('Side must be either "pro" or "con"')
        return v

class ArgumentCreate(ArgumentBase):
    pass

class Argument(ArgumentBase):
    id: int
    author_id: int
    debate_id: int
    score: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class DebateBase(BaseModel):
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    
    @field_validator('title')
    @classmethod
    def validate_title(cls, v):
        if len(v) < 5:
            raise ValueError('Title must be at least 5 characters long')
        if len(v) > 200:
            raise ValueError('Title must not exceed 200 characters')
        return v
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v):
        if v and len(v) > 2000:
            raise ValueError('Description must not exceed 2000 characters')
        return v
    
    @field_validator('category')
    @classmethod
    def validate_category(cls, v):
        if v and len(v) > 50:
            raise ValueError('Category must not exceed 50 characters')
        return v

class DebateCreate(DebateBase):
    pass

class Debate(DebateBase):
    id: int
    created_by: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class DebateList(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    status: str
    created_at: datetime
    pro_count: int = 0
    con_count: int = 0
    total_arguments: int = 0
    
    class Config:
        from_attributes = True

class DebateResponse(Debate):
    arguments: List[Argument] = []
    pro_count: int = 0
    con_count: int = 0
    total_arguments: int = 0
