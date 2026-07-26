from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.schemas.club import ClubCreate, ClubResponse, ClubList
from app.services.club_service import ClubService
from app.models.user import User
from app.models.club import ClubDiscussion, ClubComment
from app.core.dependencies import get_current_user, get_current_unmuted_user
from app.core.content_filter import contains_prohibited_content, get_filter_error_message
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

class ClubDiscussionCreate(BaseModel):
    title: str
    content: str

class ClubCommentCreate(BaseModel):
    content: str
    parent_id: int = None

router = APIRouter(prefix="/api/clubs", tags=["clubs"])
limiter = Limiter(key_func=get_remote_address)

async def send_club_join_notification(club_founder_id: int, new_member_username: str, club_name: str, db: Session):
    """Send club join notification in background"""
    from app.services.notification_service import NotificationService
    from app.schemas.notification import NotificationCreate
    from app.models.user import User
    import json
    
    notification_service = NotificationService(db)
    
    # Create notification
    notification = notification_service.create_notification(
        NotificationCreate(
            user_id=club_founder_id,
            type="comment",  # Using comment type for now, can create club type later
            title="New Club Member",
            message=f"{new_member_username} has joined your club '{club_name}'!",
            data=json.dumps({
                "new_member_username": new_member_username,
                "club_name": club_name
            })
        )
    )
    
    # Send Telegram notification
    try:
        user = db.query(User).filter(User.id == club_founder_id).first()
        await notification_service._send_telegram_notification(notification, user)
    except Exception as e:
        print(f"Failed to send Telegram notification: {e}")

@router.get("/", response_model=List[ClubList])
@limiter.limit("60/minute")
def get_clubs(request: Request, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    club_service = ClubService(db)
    return club_service.get_clubs(skip=skip, limit=limit)

@router.get("/{club_id}", response_model=ClubResponse)
@limiter.limit("60/minute")
def get_club(
    request: Request,
    club_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    club_service = ClubService(db)
    club = club_service.get_club(club_id, user_id=current_user.id)
    if not club:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Club not found"
        )
    return club

@router.post("/", response_model=ClubResponse)
@limiter.limit("10/minute")
def create_club(
    request: Request,
    club: ClubCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_unmuted_user)
):
    if contains_prohibited_content(club.name) or (club.description and contains_prohibited_content(club.description)):
        raise HTTPException(status_code=400, detail=get_filter_error_message())
    club_service = ClubService(db)
    return club_service.create_club(club, founder_id=current_user.id)

@router.get("/stats/overview")
@limiter.limit("30/minute")
def get_club_stats(request: Request, db: Session = Depends(get_db)):
    club_service = ClubService(db)
    return club_service.get_stats()

@router.post("/{club_id}/join")
@limiter.limit("20/minute")
def join_club(
    request: Request,
    club_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_unmuted_user)
):
    """Join a club"""
    from app.models.club import club_members, Club
    
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    
    # Check if already a member
    existing_member = db.execute(
        club_members.select().where(
            (club_members.c.club_id == club_id) & 
            (club_members.c.user_id == current_user.id)
        )
    ).first()
    
    if existing_member:
        raise HTTPException(status_code=400, detail="Already a member of this club")
    
    # Add user to club
    db.execute(
        club_members.insert().values(
            club_id=club_id,
            user_id=current_user.id,
            is_admin=False
        )
    )
    db.commit()
    
    # Send notification to club founder about new member
    if club.founder_id != current_user.id:  # Don't notify if founder joins their own club
        background_tasks.add_task(
            send_club_join_notification,
            club.founder_id,
            current_user.username,
            club.name,
            db
        )
    
    return {"message": "Successfully joined the club"}

@router.post("/{club_id}/leave")
@limiter.limit("20/minute")
def leave_club(
    request: Request,
    club_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Leave a club"""
    from app.models.club import club_members, Club
    
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    
    # Check if user is the founder
    if club.founder_id == current_user.id:
        raise HTTPException(status_code=400, detail="Club founder cannot leave the club")
    
    # Remove user from club
    result = db.execute(
        club_members.delete().where(
            (club_members.c.club_id == club_id) & 
            (club_members.c.user_id == current_user.id)
        )
    )
    
    if result.rowcount == 0:
        raise HTTPException(status_code=400, detail="Not a member of this club")
    
    db.commit()
    
    return {"message": "Successfully left the club"}

@router.get("/{club_id}/members")
def get_club_members(club_id: int, db: Session = Depends(get_db)):
    """Get detailed member list for a club"""
    from app.models.club import club_members, Club
    from app.models.user import User
    
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    
    # Get all members with their details
    members_data = db.execute(
        club_members.select().where(club_members.c.club_id == club_id)
    ).all()
    
    members = []
    for member_data in members_data:
        user = db.query(User).filter(User.id == member_data.user_id).first()
        if user:
            members.append({
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "avatar_url": user.avatar_url,
                "elo_rating": user.elo_rating or 400,
                "joined_at": member_data.joined_at.isoformat() if member_data.joined_at else None,
                "is_admin": member_data.is_admin,
                "is_founder": club.founder_id == user.id
            })
    
    return members

@router.get("/{club_id}/discussions")
def get_club_discussions(club_id: int, db: Session = Depends(get_db)):
    """Get all discussions for a club"""
    from app.models.club import Club
    
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    
    discussions = db.query(ClubDiscussion).filter(
        ClubDiscussion.club_id == club_id,
        ClubDiscussion.is_active == True
    ).order_by(ClubDiscussion.created_at.desc()).all()
    
    return [
        {
            "id": discussion.id,
            "title": discussion.title,
            "content": discussion.content,
            "author_id": discussion.author_id,
            "author": discussion.author.username if discussion.author else "Unknown",
            "upvotes": discussion.upvotes,
            "downvotes": discussion.downvotes,
            "created_at": discussion.created_at.isoformat() if discussion.created_at else None
        }
        for discussion in discussions
    ]

@router.post("/{club_id}/discussions")
@limiter.limit("20/minute")
def create_club_discussion(
    request: Request,
    club_id: int,
    discussion: ClubDiscussionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_unmuted_user)
):
    """Create a new discussion in a club"""
    if contains_prohibited_content(discussion.title) or contains_prohibited_content(discussion.content):
        raise HTTPException(status_code=400, detail=get_filter_error_message())
    from app.models.club import Club, club_members
    
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    
    # Check if user is a member
    is_member = db.execute(
        club_members.select().where(
            (club_members.c.club_id == club_id) & 
            (club_members.c.user_id == current_user.id)
        )
    ).first()
    
    if not is_member:
        raise HTTPException(status_code=403, detail="Must be a member to create discussions")
    
    new_discussion = ClubDiscussion(
        title=discussion.title,
        content=discussion.content,
        author_id=current_user.id,
        club_id=club_id
    )
    
    db.add(new_discussion)
    db.commit()
    db.refresh(new_discussion)
    
    return {
        "id": new_discussion.id,
        "title": new_discussion.title,
        "content": new_discussion.content,
        "author_id": new_discussion.author_id,
        "created_at": new_discussion.created_at.isoformat() if new_discussion.created_at else None
    }

@router.post("/{club_id}/discussions/{discussion_id}/comments")
@limiter.limit("30/minute")
def create_club_comment(
    request: Request,
    club_id: int,
    discussion_id: int,
    comment: ClubCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_unmuted_user)
):
    """Create a comment on a club discussion"""
    if contains_prohibited_content(comment.content):
        raise HTTPException(status_code=400, detail=get_filter_error_message())
    from app.models.club import Club, ClubDiscussion, club_members
    
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    
    discussion = db.query(ClubDiscussion).filter(
        ClubDiscussion.id == discussion_id,
        ClubDiscussion.club_id == club_id
    ).first()
    
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    
    # Check if user is a member
    is_member = db.execute(
        club_members.select().where(
            (club_members.c.club_id == club_id) & 
            (club_members.c.user_id == current_user.id)
        )
    ).first()
    
    if not is_member:
        raise HTTPException(status_code=403, detail="Must be a member to comment")
    
    new_comment = ClubComment(
        content=comment.content,
        author_id=current_user.id,
        discussion_id=discussion_id,
        parent_id=comment.parent_id
    )
    
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    
    return {
        "id": new_comment.id,
        "content": new_comment.content,
        "author_id": new_comment.author_id,
        "discussion_id": new_comment.discussion_id,
        "created_at": new_comment.created_at.isoformat() if new_comment.created_at else None
    }
