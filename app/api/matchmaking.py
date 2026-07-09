from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import asyncio
import time
import json
from datetime import datetime, timedelta

from app.database import get_db
from app.models.user import User
from app.core.dependencies import get_current_active_user
from app.core.redis_client import redis_client

router = APIRouter(prefix="/api/matchmaking", tags=["matchmaking"])

# Redis keys
MATCHMAKING_QUEUE_KEY = "matchmaking:queue"
ACTIVE_MATCHES_KEY = "matchmaking:active_matches"
USER_QUEUES_KEY = "matchmaking:user_queues"

class MatchmakingRequest(BaseModel):
    debate_id: int
    preferences: dict = {}

class QueueStatus(BaseModel):
    queue_size: int
    position: Optional[int]
    estimated_wait_time: Optional[str]
    users_waiting: List[str]
    match_found: bool
    battle: Optional[dict] = None

def cleanup_stale_users():
    """Remove users who have been in queue for more than 5 minutes using Redis"""
    current_time = datetime.now()
    stale_threshold = timedelta(minutes=5)
    
    try:
        # Get current queue from Redis
        queue_data = redis_client.get(MATCHMAKING_QUEUE_KEY)
        if not queue_data:
            return
        
        matchmaking_queue = json.loads(queue_data) if isinstance(queue_data, str) else queue_data
        
        # Remove stale users from queue
        original_queue_size = len(matchmaking_queue)
        matchmaking_queue[:] = [
            entry for entry in matchmaking_queue 
            if datetime.fromisoformat(entry["joined_at"]) > current_time - stale_threshold
        ]
        
        # Update queue in Redis
        redis_client.set(MATCHMAKING_QUEUE_KEY, matchmaking_queue, expire=300)
        
        # Clean up user queues
        user_queues_data = redis_client.get(USER_QUEUES_KEY)
        if user_queues_data:
            user_queues = json.loads(user_queues_data) if isinstance(user_queues_data, str) else user_queues_data
            queue_user_ids = {entry["user_id"] for entry in matchmaking_queue}
            stale_user_ids = set(user_queues.keys()) - queue_user_ids
            
            for user_id in stale_user_ids:
                del user_queues[user_id]
                # Also remove from active matches if exists
                active_matches_data = redis_client.get(ACTIVE_MATCHES_KEY)
                if active_matches_data:
                    active_matches = json.loads(active_matches_data) if isinstance(active_matches_data, str) else active_matches_data
                    if user_id in active_matches:
                        del active_matches[user_id]
                    redis_client.set(ACTIVE_MATCHES_KEY, active_matches, expire=3600)
            
            redis_client.set(USER_QUEUES_KEY, user_queues, expire=300)
        
        if len(matchmaking_queue) != original_queue_size:
            print(f"🧹 Cleaned up {original_queue_size - len(matchmaking_queue)} stale users from matchmaking queue")
    
    except Exception as e:
        print(f"Error cleaning up stale users: {e}")

@router.post("/join")
async def join_matchmaking(
    request: MatchmakingRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Join matchmaking queue"""
    # First cleanup any stale users
    cleanup_stale_users()
    
    user_id = current_user.id
    
    # Check if user is already in queue using Redis
    user_queues_data = redis_client.get(USER_QUEUES_KEY)
    user_queues = json.loads(user_queues_data) if user_queues_data else {}
    
    if str(user_id) in user_queues:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already in matchmaking queue"
        )
    
    # Add user to queue
    queue_entry = {
        "user_id": user_id,
        "username": current_user.username,
        "debate_id": request.debate_id,
        "preferences": request.preferences,
        "joined_at": datetime.now().isoformat(),
        "elo_rating": getattr(current_user, 'elo_rating', 400)
    }
    
    # Get current queue from Redis
    queue_data = redis_client.get(MATCHMAKING_QUEUE_KEY)
    matchmaking_queue = json.loads(queue_data) if queue_data else []
    
    matchmaking_queue.append(queue_entry)
    
    # Update Redis
    redis_client.set(MATCHMAKING_QUEUE_KEY, matchmaking_queue, expire=300)
    user_queues[str(user_id)] = queue_entry
    redis_client.set(USER_QUEUES_KEY, user_queues, expire=300)
    
    # Try to find immediate match
    match = await find_match(user_id, request.debate_id, db)
    
    if match:
        return {
            "message": "Match found immediately!",
            "match_found": True,
            "battle": match
        }
    
    # Return queue status
    position = len(matchmaking_queue)
    estimated_wait = f"{position * 30} seconds"
    
    return {
        "message": "Joined matchmaking queue",
        "match_found": False,
        "queue_size": len(matchmaking_queue),
        "position": position,
        "estimated_wait_time": estimated_wait
    }

@router.get("/status")
async def get_queue_status(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current queue status"""
    # Cleanup stale users periodically
    cleanup_stale_users()
    
    user_id = current_user.id
    
    # Get user queues from Redis
    user_queues_data = redis_client.get(USER_QUEUES_KEY)
    user_queues = json.loads(user_queues_data) if user_queues_data else {}
    
    if str(user_id) not in user_queues:
        # Get queue size
        queue_data = redis_client.get(MATCHMAKING_QUEUE_KEY)
        matchmaking_queue = json.loads(queue_data) if queue_data else []
        
        return {
            "queue_size": len(matchmaking_queue),
            "position": None,
            "estimated_wait_time": None,
            "users_waiting": [],
            "match_found": False
        }
    
    # Check if user has a match
    active_matches_data = redis_client.get(ACTIVE_MATCHES_KEY)
    active_matches = json.loads(active_matches_data) if active_matches_data else {}
    
    if str(user_id) in active_matches:
        queue_data = redis_client.get(MATCHMAKING_QUEUE_KEY)
        matchmaking_queue = json.loads(queue_data) if queue_data else []
        
        return {
            "queue_size": len(matchmaking_queue),
            "position": None,
            "estimated_wait_time": None,
            "users_waiting": [],
            "match_found": True,
            "battle": active_matches[str(user_id)]
        }
    
    # Get queue position
    queue_data = redis_client.get(MATCHMAKING_QUEUE_KEY)
    matchmaking_queue = json.loads(queue_data) if queue_data else []
    
    position = None
    for i, entry in enumerate(matchmaking_queue):
        if entry["user_id"] == user_id:
            position = i + 1
            break
    
    estimated_wait = f"{position * 30} seconds" if position else None
    
    return {
        "queue_size": len(matchmaking_queue),
        "position": position,
        "estimated_wait_time": estimated_wait,
        "users_waiting": [entry["username"] for entry in matchmaking_queue],
        "match_found": False
    }

@router.post("/leave")
async def leave_matchmaking(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Leave matchmaking queue"""
    user_id = current_user.id
    
    # Get user queues from Redis
    user_queues_data = redis_client.get(USER_QUEUES_KEY)
    user_queues = json.loads(user_queues_data) if user_queues_data else {}
    
    if str(user_id) not in user_queues:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not in matchmaking queue"
        )
    
    # Remove from queue
    queue_data = redis_client.get(MATCHMAKING_QUEUE_KEY)
    matchmaking_queue = json.loads(queue_data) if queue_data else []
    
    matchmaking_queue[:] = [entry for entry in matchmaking_queue if entry["user_id"] != user_id]
    redis_client.set(MATCHMAKING_QUEUE_KEY, matchmaking_queue, expire=300)
    
    del user_queues[str(user_id)]
    redis_client.set(USER_QUEUES_KEY, user_queues, expire=300)
    
    # Remove from active matches if exists
    active_matches_data = redis_client.get(ACTIVE_MATCHES_KEY)
    active_matches = json.loads(active_matches_data) if active_matches_data else {}
    
    if str(user_id) in active_matches:
        del active_matches[str(user_id)]
        redis_client.set(ACTIVE_MATCHES_KEY, active_matches, expire=3600)
    
    return {"message": "Left matchmaking queue"}

async def find_match(user_id: int, debate_id: int, db: Session) -> Optional[dict]:
    """Find a compatible match for the user using Redis"""
    # Get current queue from Redis
    queue_data = redis_client.get(MATCHMAKING_QUEUE_KEY)
    matchmaking_queue = json.loads(queue_data) if queue_data else []
    
    user_entry = None
    for entry in matchmaking_queue:
        if entry["user_id"] == user_id:
            user_entry = entry
            break
    
    if not user_entry:
        return None
    
    # Find compatible opponent
    for opponent in matchmaking_queue:
        if opponent["user_id"] == user_id:
            continue
        
        # Check compatibility
        if is_compatible(user_entry, opponent):
            # Create real battle room in database
            from app.services.debate_service import DebateService
            debate_service = DebateService(db)
            
            # Assign sides randomly
            if time.time() % 2 < 1:
                pro_user_id = user_id
                con_user_id = opponent["user_id"]
            else:
                pro_user_id = opponent["user_id"]
                con_user_id = user_id
            
            # Create battle room in database
            battle_room = debate_service.create_battle_room(debate_id, pro_user_id, con_user_id)
            
            # Create match data for response
            match_data = {
                "battle_id": battle_room.id,
                "debate_id": debate_id,
                "user1_id": user_id,
                "user2_id": opponent["user_id"],
                "user1_username": user_entry["username"],
                "user2_username": opponent["username"],
                "pro_user_id": pro_user_id,
                "con_user_id": con_user_id,
                "created_at": datetime.now().isoformat(),
                "status": "waiting"
            }
            
            # Remove both users from queue
            matchmaking_queue[:] = [
                entry for entry in matchmaking_queue 
                if entry["user_id"] not in [user_id, opponent["user_id"]]
            ]
            
            # Update queue in Redis
            redis_client.set(MATCHMAKING_QUEUE_KEY, matchmaking_queue, expire=300)
            
            # Update user queues in Redis
            user_queues_data = redis_client.get(USER_QUEUES_KEY)
            user_queues = json.loads(user_queues_data) if user_queues_data else {}
            
            if str(user_id) in user_queues:
                del user_queues[str(user_id)]
            if str(opponent["user_id"]) in user_queues:
                del user_queues[str(opponent["user_id"])]
            
            redis_client.set(USER_QUEUES_KEY, user_queues, expire=300)
            
            # Store active matches in Redis
            active_matches_data = redis_client.get(ACTIVE_MATCHES_KEY)
            active_matches = json.loads(active_matches_data) if active_matches_data else {}
            
            active_matches[str(user_id)] = match_data
            active_matches[str(opponent["user_id"])] = match_data
            
            redis_client.set(ACTIVE_MATCHES_KEY, active_matches, expire=3600)
            
            return match_data
    
    return None

def is_compatible(user1: dict, user2: dict) -> bool:
    """Check if two users are compatible for matching"""
    # ELO rating compatibility (within 300 points)
    elo_diff = abs(user1.get("elo_rating", 400) - user2.get("elo_rating", 400))
    if elo_diff > 300:
        return False
    
    return True

@router.get("/online")
async def get_online_users(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get list of online users (simplified version)"""
    # In production, this would use a proper online tracking system
    users = db.query(User).filter(User.id != current_user.id).limit(20).all()
    
    return [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "elo_rating": getattr(user, 'elo_rating', 400),
            "is_online": True  # Simplified - in production track actual online status
        }
        for user in users
    ]

@router.get("/search")
async def search_users(
    q: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Search users by username"""
    users = db.query(User).filter(
        User.username.ilike(f"%{q}%"),
        User.id != current_user.id
    ).limit(10).all()
    
    return [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "elo_rating": getattr(user, 'elo_rating', 400)
        }
        for user in users
    ]
