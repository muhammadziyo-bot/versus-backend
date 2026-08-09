from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.schemas.club import (
    ClubCreate, ClubUpdate, ClubResponse, ClubList, ClubSearchResult
)
from app.services.club_service import ClubService
from app.models.user import User
from app.models.club import Club, ClubDiscussion, ClubComment, club_members
from app.core.dependencies import get_current_user, get_current_user_optional, get_current_unmuted_user
from app.core.content_filter import contains_prohibited_content, get_filter_error_message
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

class ClubMessageCreate(BaseModel):
    content: str
    parent_id: int = None

router = APIRouter(prefix="/api/clubs", tags=["clubs"])
limiter = Limiter(key_func=get_remote_address)

async def send_club_join_notification(club_founder_id: int, new_member_username: str, club_name: str, db: Session):
    """Send club join notification in background"""
    from app.services.notification_service import NotificationService
    from app.schemas.notification import NotificationCreate
    import json

    notification_service = NotificationService(db)

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


@router.get("/", response_model=ClubSearchResult)
@limiter.limit("60/minute")
def get_clubs(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_optional),
):
    club_service = ClubService(db)
    return club_service.get_clubs(
        skip=skip,
        limit=limit,
        user_id=current_user.id if current_user else None,
    )


@router.get("/search", response_model=ClubSearchResult)
@limiter.limit("60/minute")
def search_clubs(
    request: Request,
    q: str = None,
    category: str = None,
    sort_by: str = "newest",
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_optional),
):
    club_service = ClubService(db)
    return club_service.search_clubs(
        query=q,
        category=category,
        user_id=current_user.id if current_user else None,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
    )


@router.get("/my", response_model=List[ClubList])
def get_my_clubs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    club_service = ClubService(db)
    return club_service.get_user_clubs(current_user.id)


@router.get("/stats/overview")
@limiter.limit("30/minute")
def get_club_stats(request: Request, db: Session = Depends(get_db)):
    club_service = ClubService(db)
    return club_service.get_stats()


@router.get("/{club_id}", response_model=ClubResponse)
@limiter.limit("60/minute")
def get_club(
    request: Request,
    club_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_optional),
):
    club_service = ClubService(db)
    club = club_service.get_club(club_id, user_id=current_user.id if current_user else None)
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


@router.patch("/{club_id}", response_model=ClubResponse)
def update_club(
    club_id: int,
    updates: ClubUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_unmuted_user)
):
    club_service = ClubService(db)
    try:
        club = club_service.update_club(club_id, updates, current_user.id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    return club_service.get_club(club_id, user_id=current_user.id)


@router.delete("/{club_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_club(
    club_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_unmuted_user)
):
    club_service = ClubService(db)
    try:
        deleted = club_service.delete_club(club_id, current_user.id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail="Club not found")
    return None


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

    # Sort: founders first, then admins, then members
    order = {"is_founder": 0, "is_admin": 1}
    members.sort(key=lambda m: order.get(m["is_founder"], 2) if m["is_founder"] else order.get(m["is_admin"], 2))

    return members


def _is_member(db: Session, club_id: int, user_id: int) -> bool:
    return db.execute(
        club_members.select().where(
            (club_members.c.club_id == club_id) &
            (club_members.c.user_id == user_id)
        )
    ).first() is not None


def _serialize_message(db: Session, message: ClubDiscussion) -> dict:
    replies = db.query(ClubComment).filter(
        ClubComment.discussion_id == message.id,
        ClubComment.parent_id.is_(None)
    ).order_by(ClubComment.created_at.asc()).all()
    return {
        "id": message.id,
        "content": message.content,
        "author_id": message.author_id,
        "author": message.author.username if message.author else "Unknown",
        "avatar_url": message.author.avatar_url if message.author else None,
        "created_at": message.created_at.isoformat() if message.created_at else None,
        "replies": [_serialize_reply(db, r) for r in replies]
    }


def _serialize_reply(db: Session, reply: ClubComment) -> dict:
    return {
        "id": reply.id,
        "content": reply.content,
        "author_id": reply.author_id,
        "author": reply.author.username if reply.author else "Unknown",
        "avatar_url": reply.author.avatar_url if reply.author else None,
        "parent_id": reply.parent_id,
        "created_at": reply.created_at.isoformat() if reply.created_at else None,
        "replies": [
            _serialize_reply(db, r) for r in db.query(ClubComment).filter(
                ClubComment.parent_id == reply.id
            ).order_by(ClubComment.created_at.asc()).all()
        ]
    }


@router.get("/{club_id}/chat")
@limiter.limit("60/minute")
def get_club_chat(
    request: Request,
    club_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the casual chat feed for a club (members only)."""
    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    if not _is_member(db, club_id, current_user.id):
        raise HTTPException(status_code=403, detail="Must be a member to view club chat")

    messages = db.query(ClubDiscussion).filter(
        ClubDiscussion.club_id == club_id,
        ClubDiscussion.is_active == True
    ).order_by(ClubDiscussion.created_at.asc()).all()

    return [_serialize_message(db, m) for m in messages]


@router.post("/{club_id}/chat")
@limiter.limit("20/minute")
def post_club_message(
    request: Request,
    club_id: int,
    payload: ClubMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_unmuted_user)
):
    """Post a message to the club chat (members only)."""
    if contains_prohibited_content(payload.content):
        raise HTTPException(status_code=400, detail=get_filter_error_message())

    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    if not _is_member(db, club_id, current_user.id):
        raise HTTPException(status_code=403, detail="Must be a member to post in club chat")

    # Auto-generate a hidden title so the row fits the shared model
    title = payload.content.strip().splitlines()[0][:60] or "Message"
    new_message = ClubDiscussion(
        title=title,
        content=payload.content,
        author_id=current_user.id,
        club_id=club_id
    )
    db.add(new_message)
    db.commit()
    db.refresh(new_message)

    return {
        "id": new_message.id,
        "content": new_message.content,
        "author_id": new_message.author_id,
        "author": current_user.username,
        "avatar_url": current_user.avatar_url,
        "created_at": new_message.created_at.isoformat() if new_message.created_at else None,
        "replies": []
    }


@router.post("/{club_id}/chat/{message_id}/reply")
@limiter.limit("20/minute")
def reply_to_club_message(
    request: Request,
    club_id: int,
    message_id: int,
    payload: ClubMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_unmuted_user)
):
    """Reply to a message in the club chat (members only)."""
    if contains_prohibited_content(payload.content):
        raise HTTPException(status_code=400, detail=get_filter_error_message())

    club = db.query(Club).filter(Club.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found")
    if not _is_member(db, club_id, current_user.id):
        raise HTTPException(status_code=403, detail="Must be a member to reply in club chat")

    message = db.query(ClubDiscussion).filter(
        ClubDiscussion.id == message_id,
        ClubDiscussion.club_id == club_id
    ).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    new_reply = ClubComment(
        content=payload.content,
        author_id=current_user.id,
        discussion_id=message_id,
        parent_id=payload.parent_id
    )
    db.add(new_reply)
    db.commit()
    db.refresh(new_reply)

    return {
        "id": new_reply.id,
        "content": new_reply.content,
        "author_id": new_reply.author_id,
        "author": current_user.username,
        "avatar_url": current_user.avatar_url,
        "parent_id": new_reply.parent_id,
        "created_at": new_reply.created_at.isoformat() if new_reply.created_at else None,
        "replies": []
    }
