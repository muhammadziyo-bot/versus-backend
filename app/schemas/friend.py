from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class FriendRequestBase(BaseModel):
    receiver_id: int
    message: Optional[str] = None

class FriendRequestCreate(FriendRequestBase):
    pass

class FriendRequest(FriendRequestBase):
    id: int
    sender_id: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class FriendRequestResponse(BaseModel):
    id: int
    sender_id: int
    sender_username: str
    sender_full_name: Optional[str] = None
    sender_avatar_url: Optional[str] = None
    receiver_id: int
    status: str
    message: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class FriendBase(BaseModel):
    friend_id: int

class FriendCreate(FriendBase):
    pass

class Friend(FriendBase):
    id: int
    user_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class FriendResponse(BaseModel):
    id: int
    user_id: int
    friend_id: int
    friend_username: str
    friend_full_name: Optional[str] = None
    friend_avatar_url: Optional[str] = None
    friend_rank: str
    friend_total_battles: int
    friend_win_rate: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class UserSearchResult(BaseModel):
    id: int
    username: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    rank: str
    total_battles: int
    win_rate: int
    is_friend: bool = False
    friend_request_sent: bool = False
    friend_request_received: bool = False
    
    class Config:
        from_attributes = True
