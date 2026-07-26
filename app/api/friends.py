from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.schemas.friend import (
    FriendRequestCreate,
    FriendRequestResponse,
    FriendResponse,
    UserSearchResult
)
from app.models.user import User
from app.models.friend import Friend, FriendRequest
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/api/friends", tags=["friends"])

async def send_friend_request_notification(receiver_id: int, requester_username: str, requester_id: int, request_id: int, db: Session):
    """Send notification for friend request in background"""
    from app.services.notification_service import NotificationService
    from app.schemas.notification import NotificationCreate
    import json
    
    notification_service = NotificationService(db)
    
    # Create notification
    notification = notification_service.create_notification(
        NotificationCreate(
            user_id=receiver_id,
            type="friend_request",
            title="New Friend Request",
            message=f"{requester_username} wants to be your friend!",
            data=json.dumps({
                "requester_username": requester_username,
                "requester_id": requester_id,
                "request_id": request_id
            })
        )
    )
    
    # Send Telegram notification
    try:
        user = db.query(User).filter(User.id == receiver_id).first()
        await notification_service._send_telegram_notification(notification, user)
    except Exception as e:
        print(f"Failed to send Telegram notification: {e}")

@router.get("/search")
def search_users(
    q: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search users by username"""
    users = db.query(User).filter(
        User.username.ilike(f"%{q}%"),
        User.id != current_user.id
    ).limit(20).all()
    
    results = []
    for user in users:
        # Check if already friends
        existing_friend = db.query(Friend).filter(
            Friend.user_id == current_user.id,
            Friend.friend_id == user.id
        ).first()
        
        # Check if request sent
        request_sent = db.query(FriendRequest).filter(
            FriendRequest.sender_id == current_user.id,
            FriendRequest.receiver_id == user.id,
            FriendRequest.status == "pending"
        ).first()
        
        # Check if request received
        request_received = db.query(FriendRequest).filter(
            FriendRequest.sender_id == user.id,
            FriendRequest.receiver_id == current_user.id,
            FriendRequest.status == "pending"
        ).first()
        
        results.append({
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "avatar_url": user.avatar_url,
            "elo_rating": user.elo_rating or 400,
            "is_friend": bool(existing_friend),
            "friend_request_sent": bool(request_sent),
            "friend_request_received": bool(request_received)
        })
    
    return results

@router.post("/request")
def send_friend_request(
    request_data: FriendRequestCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a friend request"""
    # Check if receiver exists
    receiver = db.query(User).filter(User.id == request_data.receiver_id).first()
    if not receiver:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if already friends
    existing_friend = db.query(Friend).filter(
        Friend.user_id == current_user.id,
        Friend.friend_id == request_data.receiver_id
    ).first()
    if existing_friend:
        raise HTTPException(status_code=400, detail="Already friends")
    
    # Check if request already exists
    existing_request = db.query(FriendRequest).filter(
        FriendRequest.sender_id == current_user.id,
        FriendRequest.receiver_id == request_data.receiver_id,
        FriendRequest.status == "pending"
    ).first()
    if existing_request:
        raise HTTPException(status_code=400, detail="Friend request already sent")
    
    # Create friend request
    friend_request = FriendRequest(
        sender_id=current_user.id,
        receiver_id=request_data.receiver_id,
        message=request_data.message,
        status="pending"
    )
    db.add(friend_request)
    db.commit()
    db.refresh(friend_request)
    
    # Send notification in background
    background_tasks.add_task(
        send_friend_request_notification,
        request_data.receiver_id,
        current_user.username,
        current_user.id,
        friend_request.id,
        db
    )
    
    return {"message": "Friend request sent", "request_id": friend_request.id}

@router.get("/requests/sent")
def get_sent_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get sent friend requests"""
    requests = db.query(FriendRequest).filter(
        FriendRequest.sender_id == current_user.id,
        FriendRequest.status == "pending"
    ).all()
    
    results = []
    for req in requests:
        receiver = db.query(User).filter(User.id == req.receiver_id).first()
        if receiver:
            results.append({
                "id": req.id,
                "sender_id": req.sender_id,
                "sender_username": current_user.username,
                "sender_full_name": current_user.full_name,
                "sender_avatar_url": current_user.avatar_url,
                "receiver_id": req.receiver_id,
                "status": req.status,
                "message": req.message,
                "created_at": req.created_at
            })
    
    return results

@router.get("/requests/received")
def get_received_requests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get received friend requests"""
    requests = db.query(FriendRequest).filter(
        FriendRequest.receiver_id == current_user.id,
        FriendRequest.status == "pending"
    ).all()
    
    results = []
    for req in requests:
        sender = db.query(User).filter(User.id == req.sender_id).first()
        if sender:
            results.append({
                "id": req.id,
                "sender_id": req.sender_id,
                "sender_username": sender.username,
                "sender_full_name": sender.full_name,
                "sender_avatar_url": sender.avatar_url,
                "receiver_id": req.receiver_id,
                "status": req.status,
                "message": req.message,
                "created_at": req.created_at
            })
    
    return results

@router.post("/requests/{request_id}/accept")
def accept_friend_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Accept a friend request"""
    friend_request = db.query(FriendRequest).filter(
        FriendRequest.id == request_id,
        FriendRequest.receiver_id == current_user.id,
        FriendRequest.status == "pending"
    ).first()
    
    if not friend_request:
        raise HTTPException(status_code=404, detail="Friend request not found")
    
    # Update request status
    friend_request.status = "accepted"
    
    # Create friendship (both directions)
    friend1 = Friend(user_id=current_user.id, friend_id=friend_request.sender_id)
    friend2 = Friend(user_id=friend_request.sender_id, friend_id=current_user.id)
    db.add(friend1)
    db.add(friend2)
    db.commit()
    
    return {"message": "Friend request accepted"}

@router.post("/requests/{request_id}/reject")
def reject_friend_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reject a friend request"""
    friend_request = db.query(FriendRequest).filter(
        FriendRequest.id == request_id,
        FriendRequest.receiver_id == current_user.id,
        FriendRequest.status == "pending"
    ).first()
    
    if not friend_request:
        raise HTTPException(status_code=404, detail="Friend request not found")
    
    friend_request.status = "rejected"
    db.commit()
    
    return {"message": "Friend request rejected"}

@router.get("")
def get_friends(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of friends"""
    friends = db.query(Friend).filter(Friend.user_id == current_user.id).all()
    
    results = []
    for friend in friends:
        friend_user = db.query(User).filter(User.id == friend.friend_id).first()
        if friend_user:
            results.append({
                "id": friend.id,
                "user_id": friend.user_id,
                "friend_id": friend.friend_id,
                "friend_username": friend_user.username,
                "friend_full_name": friend_user.full_name,
                "friend_avatar_url": friend_user.avatar_url,
                "friend_elo_rating": friend_user.elo_rating or 400,
                "created_at": friend.created_at
            })
    
    return results

@router.delete("/{friend_id}")
def remove_friend(
    friend_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove a friend"""
    # Remove friendship (both directions)
    db.query(Friend).filter(
        Friend.user_id == current_user.id,
        Friend.friend_id == friend_id
    ).delete()
    
    db.query(Friend).filter(
        Friend.user_id == friend_id,
        Friend.friend_id == current_user.id
    ).delete()
    
    db.commit()
    
    return {"message": "Friend removed"}
