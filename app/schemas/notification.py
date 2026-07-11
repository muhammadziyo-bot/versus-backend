from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional, Union, Dict, Any
import json

class NotificationBase(BaseModel):
    type: str
    title: str
    message: Optional[str] = None
    data: Optional[str] = None

class NotificationCreate(NotificationBase):
    user_id: int

class Notification(NotificationBase):
    id: int
    user_id: int
    is_read: bool
    created_at: datetime
    
    # Allow data to be either string or dict for flexibility
    data: Optional[Union[str, Dict[str, Any]]] = None
    
    @field_validator('data', mode='before')
    @classmethod
    def parse_data(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except:
                return v
        return v
    
    class Config:
        from_attributes = True

class NotificationUpdate(BaseModel):
    is_read: bool
