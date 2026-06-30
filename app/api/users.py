from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
from app.database import get_db
from app.schemas.user import UserList, UserStats, UserUpdate, UserSettings, PasswordChange
from app.services.user_service import UserService
from app.models.user import User
from app.models.debate import EloHistory
from app.core.dependencies import get_current_user
from app.core.security import verify_password, get_password_hash
from app.services.telegram_service import telegram_service
import os
import uuid
from pathlib import Path

router = APIRouter(prefix="/api/users", tags=["users"])

@router.get("/debaters", response_model=List[UserList])
def get_top_debaters(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    user_service = UserService(db)
    return user_service.get_top_debaters(skip=skip, limit=limit)

@router.get("/me")
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "bio": current_user.bio,
        "avatar_url": current_user.avatar_url,
        "elo_rating": current_user.elo_rating or 400,
        "language": current_user.language,
        "notifications_enabled": current_user.notifications_enabled,
        "email_alerts": current_user.email_alerts,
        "sound_effects": current_user.sound_effects,
        "privacy": current_user.privacy,
        "telegram_chat_id": current_user.telegram_chat_id,
        "telegram_username": current_user.telegram_username
    }

@router.get("/stats")
def get_user_stats(db: Session = Depends(get_db)):
    user_service = UserService(db)
    return user_service.get_stats()

@router.get("/username/{username}")
def find_user_by_username(username: str, db: Session = Depends(get_db)):
    """Find a user by their username"""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "bio": user.bio,
        "avatar_url": user.avatar_url,
        "elo_rating": user.elo_rating or 400,
        "created_at": user.created_at.isoformat() if user.created_at else None
    }

@router.get("/search")
def search_users(q: str, db: Session = Depends(get_db)):
    """Search users by username"""
    users = db.query(User).filter(User.username.ilike(f"%{q}%")).limit(10).all()
    return [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "elo_rating": getattr(user, 'elo_rating', 400)
        }
        for user in users
    ]

@router.get("/online")
def get_online_users(db: Session = Depends(get_db)):
    """Get list of online users (simplified version)"""
    # In production, this would use a proper online tracking system
    users = db.query(User).limit(20).all()
    
    return [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "elo_rating": getattr(user, 'elo_rating', 400),
            "is_online": True  # Simplified - in production track actual online status
        }
        for user in users
    ]

@router.put("/profile")
def update_profile(
    profile_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update user profile"""
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update fields if provided
    if profile_data.full_name is not None:
        user.full_name = profile_data.full_name
    if profile_data.bio is not None:
        user.bio = profile_data.bio
    if profile_data.avatar_url is not None:
        user.avatar_url = profile_data.avatar_url
    
    db.commit()
    db.refresh(user)
    
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "bio": user.bio,
        "avatar_url": user.avatar_url,
        "elo_rating": user.elo_rating or 400
    }

@router.put("/settings")
def update_settings(
    settings: UserSettings,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update user settings"""
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update settings
    user.language = settings.language
    user.notifications_enabled = settings.notifications_enabled
    user.email_alerts = settings.email_alerts
    user.sound_effects = settings.sound_effects
    user.privacy = settings.privacy
    
    db.commit()
    db.refresh(user)
    
    return {
        "language": user.language,
        "notifications_enabled": user.notifications_enabled,
        "email_alerts": user.email_alerts,
        "sound_effects": user.sound_effects,
        "privacy": user.privacy
    }

@router.put("/password")
def change_password(
    password_data: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Change user password"""
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify current password
    if not verify_password(password_data.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    # Update password
    user.hashed_password = get_password_hash(password_data.new_password)
    db.commit()
    
    return {"message": "Password updated successfully"}

@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload profile picture"""
    # Validate file type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Create uploads directory if it doesn't exist
    upload_dir = Path("uploads/avatars")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    file_extension = file.filename.split(".")[-1]
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = upload_dir / unique_filename
    
    # Save file
    try:
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")
    
    # Update user avatar URL
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Delete old avatar if exists
    if user.avatar_url:
        old_avatar_path = Path(user.avatar_url.replace("http://localhost:8000/", ""))
        if old_avatar_path.exists():
            try:
                old_avatar_path.unlink()
            except:
                pass
    
    # Set new avatar URL
    user.avatar_url = f"http://localhost:8000/uploads/avatars/{unique_filename}"
    db.commit()
    db.refresh(user)
    
    return {"avatar_url": user.avatar_url}

class TelegramLinkRequest(BaseModel):
    chat_id: str | None = None
    username: str | None = None
    token: str | None = None

@router.post("/telegram/link")
async def link_telegram(
    request: TelegramLinkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Link Telegram account to user profile"""
    if not telegram_service.is_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram service is not configured"
        )
    
    # Determine linking method
    if request.token:
        # Token-based linking (from Telegram bot)
        # In production, validate the token from a cache/Redis
        # For now, we'll accept any token and require chat_id to be provided separately
        if not request.chat_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token linking requires chat_id from bot interaction"
            )
        chat_id = request.chat_id
        username = request.username
    elif request.username:
        # Username-based linking
        # Note: We still need the chat_id, which should come from bot interaction
        if not request.chat_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username linking requires chat_id. Please use the Telegram bot /link command first"
            )
        chat_id = request.chat_id
        username = request.username
    elif request.chat_id:
        # Direct chat_id linking (old method, kept for backward compatibility)
        chat_id = request.chat_id
        username = None
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either chat_id, username, or token"
        )
    
    # Check if chat_id is already linked to another user
    existing_user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
    if existing_user and existing_user.id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This Telegram account is already linked to another user"
        )
    
    # Check if username is already linked to another user
    if username:
        existing_username_user = db.query(User).filter(User.telegram_username == username).first()
        if existing_username_user and existing_username_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This Telegram username is already linked to another user"
            )
    
    # Update user's telegram fields
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.telegram_chat_id = chat_id
    if username:
        user.telegram_username = username
    db.commit()
    db.refresh(user)
    
    # Send a test notification to confirm the link
    try:
        await telegram_service.send_notification(
            chat_id=chat_id,
            title="Account Linked Successfully",
            message=f"Your Telegram account has been successfully linked to Digital Arena!\n\nYou will now receive notifications for battle invitations, friend requests, and more."
        )
    except Exception as e:
        # Don't fail the link if test notification fails
        print(f"Failed to send test notification: {e}")
    
    return {"message": "Telegram account linked successfully"}

@router.delete("/telegram/unlink")
def unlink_telegram(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Unlink Telegram account from user profile"""
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.telegram_chat_id = None
    user.telegram_username = None
    db.commit()
    
    return {"message": "Telegram account unlinked successfully"}

class LeaderboardEntry(BaseModel):
    rank: int
    id: int
    username: str
    full_name: Optional[str] = None
    elo_rating: int
    elo_gained: int = 0

@router.get("/leaderboard")
def get_leaderboard(
    period: str = "all",  # "weekly", "monthly", "all"
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get leaderboard with weekly, monthly, or all-time rankings"""
    
    if period == "all":
        # All-time: Sort by current ELO rating
        users = db.query(User).order_by(
            (User.elo_rating or 400).desc()
        ).offset(skip).limit(limit).all()
        
        result = []
        for index, user in enumerate(users):
            result.append(LeaderboardEntry(
                rank=skip + index + 1,
                id=user.id,
                username=user.username,
                full_name=user.full_name,
                elo_rating=user.elo_rating or 400,
                elo_gained=0
            ))
        return result
    
    elif period == "weekly":
        # Weekly: Calculate ELO gained in the last 7 days
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        # Get ELO history for the last week
        elo_changes = db.query(
            EloHistory.user_id,
            func.sum(EloHistory.elo_change).label('elo_gained')
        ).filter(
            EloHistory.created_at >= week_ago
        ).group_by(
            EloHistory.user_id
        ).all()
        
        # Create a map of user_id to elo_gained
        elo_gained_map = {row.user_id: row.elo_gained or 0 for row in elo_changes}
        
        # Get all users and calculate their current ELO
        users = db.query(User).all()
        
        leaderboard_data = []
        for user in users:
            gained = elo_gained_map.get(user.id, 0)
            leaderboard_data.append({
                'user': user,
                'elo_rating': user.elo_rating or 400,
                'elo_gained': gained
            })
        
        # Sort by ELO gained (descending), then by current ELO
        leaderboard_data.sort(key=lambda x: (x['elo_gained'], x['elo_rating']), reverse=True)
        
        # Apply pagination
        paginated_data = leaderboard_data[skip:skip + limit]
        
        result = []
        for index, data in enumerate(paginated_data):
            result.append(LeaderboardEntry(
                rank=skip + index + 1,
                id=data['user'].id,
                username=data['user'].username,
                full_name=data['user'].full_name,
                elo_rating=data['elo_rating'],
                elo_gained=data['elo_gained']
            ))
        return result
    
    elif period == "monthly":
        # Monthly: Calculate ELO gained in the last 30 days
        month_ago = datetime.utcnow() - timedelta(days=30)
        
        # Get ELO history for the last month
        elo_changes = db.query(
            EloHistory.user_id,
            func.sum(EloHistory.elo_change).label('elo_gained')
        ).filter(
            EloHistory.created_at >= month_ago
        ).group_by(
            EloHistory.user_id
        ).all()
        
        # Create a map of user_id to elo_gained
        elo_gained_map = {row.user_id: row.elo_gained or 0 for row in elo_changes}
        
        # Get all users and calculate their current ELO
        users = db.query(User).all()
        
        leaderboard_data = []
        for user in users:
            gained = elo_gained_map.get(user.id, 0)
            leaderboard_data.append({
                'user': user,
                'elo_rating': user.elo_rating or 400,
                'elo_gained': gained
            })
        
        # Sort by ELO gained (descending), then by current ELO
        leaderboard_data.sort(key=lambda x: (x['elo_gained'], x['elo_rating']), reverse=True)
        
        # Apply pagination
        paginated_data = leaderboard_data[skip:skip + limit]
        
        result = []
        for index, data in enumerate(paginated_data):
            result.append(LeaderboardEntry(
                rank=skip + index + 1,
                id=data['user'].id,
                username=data['user'].username,
                full_name=data['user'].full_name,
                elo_rating=data['elo_rating'],
                elo_gained=data['elo_gained']
            ))
        return result
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid period. Must be 'weekly', 'monthly', or 'all'"
        )
