from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, field_serializer
from datetime import datetime

from app.database import get_db
from app.services.debate_service import DebateService
from app.services.ai_scoring_service import AIScoringService
from app.core.dependencies import get_current_active_user
from app.models.user import User
from app.models.debate import Debate
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter(prefix="/api/battles", tags=["battles"])
limiter = Limiter(key_func=get_remote_address)

def send_battle_invitation_notification(opponent_id: int, inviter_username: str, topic_title: str, battle_id: int, db: Session):
    """Send battle invitation notification in background"""
    from app.services.notification_service import NotificationService
    from app.schemas.notification import NotificationCreate
    from app.models.user import User
    import json
    import asyncio
    
    notification_service = NotificationService(db)
    
    # Create notification
    notification = notification_service.create_notification(
        NotificationCreate(
            user_id=opponent_id,
            type="battle_invitation",
            title="Battle Invitation",
            message=f"{inviter_username} has invited you to a battle on '{topic_title}'!",
            data=json.dumps({
                "inviter_username": inviter_username,
                "topic_title": topic_title,
                "battle_id": battle_id
            })
        )
    )
    
    # Send Telegram notification
    try:
        user = db.query(User).filter(User.id == opponent_id).first()
        asyncio.run(notification_service._send_telegram_notification(notification, user))
    except Exception as e:
        print(f"Failed to send Telegram notification: {e}")

def send_battle_result_notification(user_id: int, opponent_username: str, topic_title: str, won: bool, battle_id: int, db: Session):
    """Send battle result notification in background"""
    from app.services.notification_service import NotificationService
    from app.schemas.notification import NotificationCreate
    from app.models.user import User
    import json
    import asyncio
    
    notification_service = NotificationService(db)
    
    # Create notification
    notification = notification_service.create_notification(
        NotificationCreate(
            user_id=user_id,
            type="battle_result",
            title="Battle Result",
            message=f"You {'won' if won else 'lost'} the battle against {opponent_username} on '{topic_title}'!",
            data=json.dumps({
                "opponent_username": opponent_username,
                "topic_title": topic_title,
                "won": won,
                "battle_id": battle_id
            })
        )
    )
    
    # Send Telegram notification
    try:
        user = db.query(User).filter(User.id == user_id).first()
        asyncio.run(notification_service._send_telegram_notification(notification, user))
    except Exception as e:
        print(f"Failed to send Telegram notification: {e}")

# Pydantic schemas for battle operations
class BattleRoomCreate(BaseModel):
    debate_id: int
    opponent_id: int

class SideSelection(BaseModel):
    side: str  # 'pro' or 'con'

class ArgumentSubmit(BaseModel):
    round_number: int
    argument: str

class VoteCast(BaseModel):
    side: str
    reasoning: Optional[str] = None
    confidence: int = 5
    argument_quality: int = 5
    clarity: int = 5
    persuasiveness: int = 5
    evidence: int = 5

class UserInfo(BaseModel):
    id: int
    username: str
    email: str
    
    class Config:
        from_attributes = True

class BattleRoomResponse(BaseModel):
    id: int
    debate_id: int
    pro_user_id: int
    con_user_id: int
    pro_user: Optional[UserInfo] = None
    con_user: Optional[UserInfo] = None
    status: str
    current_round: int
    max_rounds: int
    round_time_limit: int
    started_at: Optional[datetime] = None
    round_started_at: Optional[datetime] = None
    round_ends_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    winner_side: Optional[str] = None
    winner_user_id: Optional[int] = None
    created_at: datetime

    @field_serializer('started_at', 'round_started_at', 'round_ends_at', 'completed_at', 'created_at')
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        return value.isoformat()

    class Config:
        from_attributes = True

class BattleRoundResponse(BaseModel):
    id: int
    battle_room_id: int
    round_number: int
    status: str
    pro_argument: Optional[str] = None
    con_argument: Optional[str] = None
    pro_submitted_at: Optional[datetime] = None
    con_submitted_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    @field_serializer('pro_submitted_at', 'con_submitted_at', 'started_at', 'completed_at', 'created_at')
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        return value.isoformat()

    class Config:
        from_attributes = True

class VoteResponse(BaseModel):
    id: int
    battle_room_id: int
    voter_id: int
    side: str
    reasoning: Optional[str] = None
    confidence: int
    argument_quality: int
    clarity: int
    persuasiveness: int
    evidence: int
    created_at: datetime

    @field_serializer('created_at')
    def serialize_datetime(self, value: datetime) -> str:
        return value.isoformat()

    class Config:
        from_attributes = True

class AIArgumentScoreResponse(BaseModel):
    id: int
    battle_round_id: int
    side: str
    logical_coherence: int
    evidence_quality: int
    clarity: int
    relevance: int
    counter_effectiveness: int
    overall_score: int
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    detailed_feedback: Optional[str] = None
    model_used: Optional[str] = None
    scored_at: datetime

    @field_serializer('scored_at')
    def serialize_datetime(self, value: datetime) -> str:
        return value.isoformat()

    class Config:
        from_attributes = True

class AIBattleResultResponse(BaseModel):
    id: int
    battle_room_id: int
    pro_total_score: int
    con_total_score: int
    winner_side: Optional[str] = None
    confidence: int
    pro_strengths: Optional[str] = None
    pro_weaknesses: Optional[str] = None
    con_strengths: Optional[str] = None
    con_weaknesses: Optional[str] = None
    overall_analysis: Optional[str] = None
    round_breakdown: Optional[dict] = None
    status: str
    error_message: Optional[str] = None
    model_used: Optional[str] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    created_at: datetime

    @field_serializer('processing_started_at', 'processing_completed_at', 'created_at')
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        return value.isoformat()

    class Config:
        from_attributes = True

@router.post("/", response_model=BattleRoomResponse)
@limiter.limit("10/minute")
def create_battle_room(
    request: Request,
    battle_create: BattleRoomCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new battle room"""
    from app.models.debate import BattleRoom
    from sqlalchemy.orm import joinedload
    
    debate_service = DebateService(db)
    
    try:
        battle_room = debate_service.create_battle_room(
            debate_id=battle_create.debate_id,
            pro_user_id=current_user.id,
            con_user_id=battle_create.opponent_id
        )
        
        # Get debate topic title
        debate = db.query(Debate).filter(Debate.id == battle_create.debate_id).first()
        topic_title = debate.title if debate else "Unknown topic"
        
        # Send battle invitation notification to opponent
        background_tasks.add_task(
            send_battle_invitation_notification,
            battle_create.opponent_id,
            current_user.username,
            topic_title,
            battle_room.id,
            db
        )
        
        # Eagerly load user relationships for response
        battle_room_with_users = db.query(BattleRoom).options(
            joinedload(BattleRoom.pro_user),
            joinedload(BattleRoom.con_user)
        ).filter(BattleRoom.id == battle_room.id).first()
        
        return battle_room_with_users
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/{battle_id}/start", response_model=BattleRoomResponse)
@limiter.limit("20/minute")
def start_battle(
    request: Request,
    battle_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Start a battle"""
    debate_service = DebateService(db)
    
    try:
        battle_room = debate_service.start_battle(battle_id)
        
        # Verify user is part of this battle
        if current_user.id not in [battle_room.pro_user_id, battle_room.con_user_id]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not part of this battle"
            )
        
        return battle_room
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/{battle_id}/select-side", response_model=BattleRoomResponse)
@limiter.limit("20/minute")
def select_side(
    request: Request,
    battle_id: int,
    side_selection: SideSelection,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Select a side for the battle (pro or con)"""
    from app.models.debate import BattleRoom
    from sqlalchemy.orm import joinedload
    
    debate_service = DebateService(db)
    
    try:
        battle_room = debate_service.select_battle_side(battle_id, current_user.id, side_selection.side)
        
        # Eagerly load user relationships for response
        battle_room_with_users = db.query(BattleRoom).options(
            joinedload(BattleRoom.pro_user),
            joinedload(BattleRoom.con_user)
        ).filter(BattleRoom.id == battle_room.id).first()
        
        return battle_room_with_users
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/{battle_id}/rounds/submit", response_model=BattleRoundResponse)
@limiter.limit("30/minute")
def submit_round_argument(
    request: Request,
    battle_id: int,
    argument_data: ArgumentSubmit,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Submit an argument for a specific round"""
    debate_service = DebateService(db)
    
    try:
        round_obj = debate_service.submit_round_argument(
            battle_room_id=battle_id,
            round_number=argument_data.round_number,
            argument=argument_data.argument,
            user_id=current_user.id
        )
        return round_obj
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/{battle_id}", response_model=BattleRoomResponse)
@limiter.limit("60/minute")
def get_battle_room(
    request: Request,
    battle_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get a specific battle room"""
    from app.models.debate import BattleRoom
    from sqlalchemy.orm import joinedload
    
    # Eagerly load user relationships
    battle_room = db.query(BattleRoom).options(
        joinedload(BattleRoom.pro_user),
        joinedload(BattleRoom.con_user)
    ).filter(BattleRoom.id == battle_id).first()
    
    if not battle_room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Battle room not found"
        )
    
    # Verify user is part of this battle
    if current_user.id not in [battle_room.pro_user_id, battle_room.con_user_id]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not part of this battle"
        )
    
    return battle_room

@router.get("/{battle_id}/rounds", response_model=List[BattleRoundResponse])
def get_battle_rounds(
    battle_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all rounds for a battle"""
    debate_service = DebateService(db)
    
    # Verify battle exists and user is part of it
    battle_room = debate_service.get_battle_room(battle_id)
    if not battle_room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Battle room not found"
        )
    
    if current_user.id not in [battle_room.pro_user_id, battle_room.con_user_id]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not part of this battle"
        )
    
    rounds = debate_service.get_battle_rounds(battle_id)
    return rounds

@router.post("/{battle_id}/vote", response_model=VoteResponse)
@limiter.limit("10/minute")
def cast_vote(
    request: Request,
    battle_id: int,
    vote_data: VoteCast,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Cast a vote for a completed battle"""
    debate_service = DebateService(db)
    
    try:
        vote = debate_service.cast_vote(
            battle_room_id=battle_id,
            voter_id=current_user.id,
            side=vote_data.side,
            reasoning=vote_data.reasoning,
            confidence=vote_data.confidence,
            argument_quality=vote_data.argument_quality,
            clarity=vote_data.clarity,
            persuasiveness=vote_data.persuasiveness,
            evidence=vote_data.evidence
        )
        
        # Get battle room details for notifications
        from app.models.battle import BattleRoom
        battle_room = db.query(BattleRoom).filter(BattleRoom.id == battle_id).first()
        if battle_room:
            debate = db.query(Debate).filter(Debate.id == battle_room.debate_id).first()
            topic_title = debate.title if debate else "Unknown topic"
            
            # Get opponent usernames
            pro_user = db.query(User).filter(User.id == battle_room.pro_user_id).first()
            con_user = db.query(User).filter(User.id == battle_room.con_user_id).first()
            
            # Send result notifications to both participants
            if pro_user:
                background_tasks.add_task(
                    send_battle_result_notification,
                    pro_user.id,
                    con_user.username if con_user else "Unknown",
                    topic_title,
                    vote_data.side == "pro",  # pro won if vote is for pro
                    battle_id,
                    db
                )
            if con_user:
                background_tasks.add_task(
                    send_battle_result_notification,
                    con_user.id,
                    pro_user.username if pro_user else "Unknown",
                    topic_title,
                    vote_data.side == "con",  # con won if vote is for con
                    battle_id,
                    db
                )
        
        return vote
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/{battle_id}/votes", response_model=List[VoteResponse])
def get_battle_votes(
    battle_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all votes for a battle"""
    debate_service = DebateService(db)
    
    # Verify battle exists
    battle_room = debate_service.get_battle_room(battle_id)
    if not battle_room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Battle room not found"
        )
    
    votes = debate_service.get_battle_votes(battle_id)
    return votes

@router.get("/user/{user_id}", response_model=List[BattleRoomResponse])
def get_user_battles(
    user_id: int,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get battles for a specific user"""
    debate_service = DebateService(db)
    
    # Users can only see their own battles
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own battles"
        )
    
    battles = debate_service.get_user_battles(user_id, status)
    return battles

@router.get("/stats/overview")
def get_battle_stats(
    db: Session = Depends(get_db)
):
    """Get battle statistics (placeholder for now)"""
    # This would be enhanced with real battle statistics
    return {
        "total_battles": 0,
        "active_battles": 0,
        "completed_battles": 0,
        "message": "Battle statistics coming soon!"
    }

@router.get("/{battle_id}/ai-result", response_model=AIBattleResultResponse)
def get_ai_battle_result(
    battle_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get AI battle result for a completed battle"""
    # Verify battle exists and user is part of it
    debate_service = DebateService(db)
    battle_room = debate_service.get_battle_room(battle_id)
    if not battle_room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Battle room not found"
        )
    
    if current_user.id not in [battle_room.pro_user_id, battle_room.con_user_id]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not part of this battle"
        )
    
    ai_service = AIScoringService(db)
    ai_result = ai_service.get_battle_result(battle_id)
    
    if not ai_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI result not available yet"
        )
    
    return ai_result

@router.get("/{battle_id}/rounds/{round_id}/ai-scores", response_model=List[AIArgumentScoreResponse])
def get_round_ai_scores(
    battle_id: int,
    round_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get AI scores for a specific round"""
    # Verify battle exists and user is part of it
    debate_service = DebateService(db)
    battle_room = debate_service.get_battle_room(battle_id)
    if not battle_room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Battle room not found"
        )
    
    if current_user.id not in [battle_room.pro_user_id, battle_room.con_user_id]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not part of this battle"
        )
    
    ai_service = AIScoringService(db)
    scores = ai_service.get_argument_scores(round_id)
    
    return scores
