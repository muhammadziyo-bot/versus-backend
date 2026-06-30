from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.schemas.discussion import DiscussionList, DiscussionStats, DiscussionCreate, DiscussionDetail, CommentCreate, Comment, VoteRequest
from app.services.discussion_service import DiscussionService
from app.core.dependencies import get_current_user, get_current_user_optional
from app.models.user import User
from app.models.club import ClubDiscussion

router = APIRouter(prefix="/api/discussions", tags=["discussions"])
comments_router = APIRouter(prefix="/api/comments", tags=["comments"])

def send_comment_notification(discussion_author_id: int, commenter_username: str, topic_title: str, comment_preview: str, topic_id: int, db: Session):
    """Send comment notification in background"""
    from app.services.notification_service import NotificationService
    from app.schemas.notification import NotificationCreate
    from app.models.user import User
    import json
    import asyncio
    
    notification_service = NotificationService(db)
    
    # Create notification
    notification = notification_service.create_notification(
        NotificationCreate(
            user_id=discussion_author_id,
            type="comment",
            title="New Comment",
            message=f"{commenter_username} commented on '{topic_title}'!",
            data=json.dumps({
                "commenter_username": commenter_username,
                "topic_title": topic_title,
                "comment_preview": comment_preview,
                "topic_id": topic_id
            })
        )
    )
    
    # Send Telegram notification
    try:
        user = db.query(User).filter(User.id == discussion_author_id).first()
        asyncio.run(notification_service._send_telegram_notification(notification, user))
    except Exception as e:
        print(f"Failed to send Telegram notification: {e}")

def send_reply_notification(parent_comment_author_id: int, replier_username: str, topic_title: str, reply_preview: str, topic_id: int, db: Session):
    """Send reply notification in background"""
    from app.services.notification_service import NotificationService
    from app.schemas.notification import NotificationCreate
    from app.models.user import User
    import json
    import asyncio
    
    notification_service = NotificationService(db)
    
    # Create notification
    notification = notification_service.create_notification(
        NotificationCreate(
            user_id=parent_comment_author_id,
            type="comment",
            title="New Reply",
            message=f"{replier_username} replied to your comment on '{topic_title}'!",
            data=json.dumps({
                "commenter_username": replier_username,
                "topic_title": topic_title,
                "comment_preview": reply_preview,
                "topic_id": topic_id
            })
        )
    )
    
    # Send Telegram notification
    try:
        user = db.query(User).filter(User.id == parent_comment_author_id).first()
        asyncio.run(notification_service._send_telegram_notification(notification, user))
    except Exception as e:
        print(f"Failed to send Telegram notification: {e}")

def send_comment_like_notification(comment_author_id: int, voter_username: str, topic_title: str, vote_type: str, topic_id: int, db: Session):
    """Send comment like/dislike notification in background"""
    from app.services.notification_service import NotificationService
    from app.schemas.notification import NotificationCreate
    from app.models.user import User
    import json
    import asyncio
    
    notification_service = NotificationService(db)
    
    # Create notification
    notification = notification_service.create_notification(
        NotificationCreate(
            user_id=comment_author_id,
            type="comment",
            title=f"Comment {vote_type}d" if vote_type == "up" else "Comment disliked",
            message=f"{voter_username} {'liked' if vote_type == 'up' else 'disliked'} your comment on '{topic_title}'!",
            data=json.dumps({
                "commenter_username": voter_username,
                "topic_title": topic_title,
                "vote_type": vote_type,
                "topic_id": topic_id
            })
        )
    )
    
    # Send Telegram notification
    try:
        user = db.query(User).filter(User.id == comment_author_id).first()
        asyncio.run(notification_service._send_telegram_notification(notification, user))
    except Exception as e:
        print(f"Failed to send Telegram notification: {e}")

@router.get("/", response_model=List[DiscussionList])
def get_discussions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_optional)):
    discussion_service = DiscussionService(db)
    return discussion_service.get_discussions(skip=skip, limit=limit, user_id=current_user.id if current_user else None)

@router.get("/stats")
def get_discussion_stats(db: Session = Depends(get_db)):
    discussion_service = DiscussionService(db)
    return discussion_service.get_stats()

@router.get("/{discussion_id}", response_model=DiscussionDetail)
def get_discussion(discussion_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user_optional)):
    discussion_service = DiscussionService(db)
    discussion = discussion_service.get_discussion_by_id(discussion_id, user_id=current_user.id if current_user else None)
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    return discussion

@router.post("/", response_model=DiscussionDetail, status_code=status.HTTP_201_CREATED)
def create_discussion(
    discussion: DiscussionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        discussion_service = DiscussionService(db)
        return discussion_service.create_discussion(discussion, current_user.id)
    except Exception as e:
        print(f"Error creating discussion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{discussion_id}/comments", response_model=Comment, status_code=status.HTTP_201_CREATED)
def create_comment(
    discussion_id: int,
    comment: CommentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    discussion_service = DiscussionService(db)
    new_comment = discussion_service.create_comment(discussion_id, comment, current_user.id)
    
    # Get discussion details for notification
    discussion = db.query(ClubDiscussion).filter(ClubDiscussion.id == discussion_id).first()
    
    # Check if this is a reply to another comment
    if comment.parent_id:
        from app.models.club import ClubComment
        parent_comment = db.query(ClubComment).filter(ClubComment.id == comment.parent_id).first()
        if parent_comment and parent_comment.author_id != current_user.id:  # Don't notify if replying to own comment
            # Send reply notification to parent comment author
            background_tasks.add_task(
                send_reply_notification,
                parent_comment.author_id,
                current_user.username,
                discussion.title if discussion else "Unknown topic",
                comment.content[:100] + "..." if len(comment.content) > 100 else comment.content,
                discussion_id,
                db
            )
    elif discussion and discussion.author_id != current_user.id:  # Top-level comment, notify discussion author
        # Send comment notification to discussion author
        background_tasks.add_task(
            send_comment_notification,
            discussion.author_id,
            current_user.username,
            discussion.title,
            comment.content[:100] + "..." if len(comment.content) > 100 else comment.content,
            discussion_id,
            db
        )
    
    return new_comment

@router.post("/{discussion_id}/vote", response_model=DiscussionDetail)
def vote_discussion(
    discussion_id: int,
    vote: VoteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    discussion_service = DiscussionService(db)
    discussion = discussion_service.vote_discussion(discussion_id, vote.vote_type, current_user.id)
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")
    return discussion

@router.get("/votes/my")
def get_my_votes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.vote import DiscussionVote
    votes = db.query(DiscussionVote).filter(
        DiscussionVote.user_id == current_user.id
    ).all()
    return {
        vote.discussion_id: vote.vote_type
        for vote in votes
    }

@comments_router.post("/{comment_id}/vote", response_model=Comment)
def vote_comment(
    comment_id: int,
    vote: VoteRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    discussion_service = DiscussionService(db)
    comment = discussion_service.vote_comment(comment_id, vote.vote_type, current_user.id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    # Get discussion details for notification
    discussion = db.query(ClubDiscussion).filter(ClubDiscussion.id == comment.discussion_id).first()
    # Only send like notification for comments (no dislike button in UI for nested comments)
    if comment.author_id != current_user.id and vote.vote_type == 'up':  # Don't notify if voting on own comment or if unliking
        # Send like notification to comment author
        background_tasks.add_task(
            send_comment_like_notification,
            comment.author_id,
            current_user.username,
            discussion.title if discussion else "Unknown topic",
            vote.vote_type,
            comment.discussion_id,
            db
        )
    
    return comment
