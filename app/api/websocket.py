from fastapi import WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
from typing import Dict, List, Optional, Any
import json
import asyncio
import logging
from datetime import datetime

from app.database import get_db
from app.services.debate_service import DebateService
from app.core.security import verify_token

logger = logging.getLogger(__name__)

class WebSocketManager:
    """Manages WebSocket connections for real-time battle communication"""
    
    def __init__(self):
        # battle_room_id -> {user_id: WebSocket}
        self.battle_connections: Dict[int, Dict[int, WebSocket]] = {}
        # user_id -> {battle_room_id: WebSocket}
        self.user_connections: Dict[int, Dict[int, WebSocket]] = {}
        # battle_room_id -> List of system messages
        self.battle_message_history: Dict[int, List[Dict[str, Any]]] = {}
        # Active battle timers
        self.battle_timers: Dict[int, asyncio.Task] = {}

    async def connect_to_battle(self, websocket: WebSocket, battle_room_id: int, user_id: int, db: Session):
        """Connect a user to a specific battle room"""
        await websocket.accept()
        
        # Verify user is part of this battle
        debate_service = DebateService(db)
        battle = debate_service.get_battle_room(battle_room_id)
        
        if not battle or user_id not in [battle.pro_user_id, battle.con_user_id]:
            await websocket.send_text(json.dumps({
                "type": "error",
                "data": {"message": "You are not part of this battle"},
                "timestamp": datetime.utcnow().isoformat()
            }))
            await websocket.close()
            return False
        
        # Add connection
        if battle_room_id not in self.battle_connections:
            self.battle_connections[battle_room_id] = {}
            self.battle_message_history[battle_room_id] = []
        
        self.battle_connections[battle_room_id][user_id] = websocket
        
        if user_id not in self.user_connections:
            self.user_connections[user_id] = {}
        self.user_connections[user_id][battle_room_id] = websocket
        
        # Send current battle state
        rounds = debate_service.get_battle_rounds(battle_room_id)
        votes = debate_service.get_battle_votes(battle_room_id)
        
        await websocket.send_text(json.dumps({
            "type": "battle_state",
            "data": {
                "battle": {
                    "id": battle.id,
                    "status": battle.status,
                    "current_round": battle.current_round,
                    "max_rounds": battle.max_rounds,
                    "round_time_limit": battle.round_time_limit,
                    "started_at": battle.started_at.isoformat() if battle.started_at else None,
                    "round_started_at": battle.round_started_at.isoformat() if battle.round_started_at else None,
                    "round_ends_at": battle.round_ends_at.isoformat() if battle.round_ends_at else None,
                    "completed_at": battle.completed_at.isoformat() if battle.completed_at else None,
                    "winner_side": battle.winner_side,
                    "winner_user_id": battle.winner_user_id,
                    "pro_user_id": battle.pro_user_id,
                    "con_user_id": battle.con_user_id
                },
                "rounds": [
                    {
                        "id": round_obj.id,
                        "round_number": round_obj.round_number,
                        "status": round_obj.status,
                        "pro_argument": round_obj.pro_argument,
                        "con_argument": round_obj.con_argument,
                        "pro_submitted_at": round_obj.pro_submitted_at.isoformat() if round_obj.pro_submitted_at else None,
                        "con_submitted_at": round_obj.con_submitted_at.isoformat() if round_obj.con_submitted_at else None,
                        "started_at": round_obj.started_at.isoformat() if round_obj.started_at else None,
                        "completed_at": round_obj.completed_at.isoformat() if round_obj.completed_at else None
                    }
                    for round_obj in rounds
                ],
                "votes": [
                    {
                        "id": vote.id,
                        "voter_id": vote.voter_id,
                        "side": vote.side,
                        "reasoning": vote.reasoning,
                        "confidence": vote.confidence,
                        "argument_quality": vote.argument_quality,
                        "clarity": vote.clarity,
                        "persuasiveness": vote.persuasiveness,
                        "evidence": vote.evidence,
                        "created_at": vote.created_at.isoformat()
                    }
                    for vote in votes
                ]
            },
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        # Send message history
        if self.battle_message_history[battle_room_id]:
            await websocket.send_text(json.dumps({
                "type": "message_history",
                "data": {"messages": self.battle_message_history[battle_room_id][-20:]},  # Last 20 messages
                "timestamp": datetime.utcnow().isoformat()
            }))
        
        # Notify other participant
        await self.broadcast_to_battle(battle_room_id, {
            "type": "user_joined",
            "data": {
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat()
            },
            "timestamp": datetime.utcnow().isoformat()
        }, exclude_user_id=user_id)
        
        # Auto-start battle if both users are connected and battle is in waiting state
        if battle.status == "waiting":
            connected_users = len(self.battle_connections.get(battle_room_id, {}))
            if connected_users == 2:
                try:
                    await self._handle_battle_start(battle_room_id, user_id, db)
                except Exception as e:
                    logger.error(f"Error auto-starting battle: {e}")
        
        return True

    async def disconnect_from_battle(self, battle_room_id: int, user_id: int):
        """Disconnect a user from a battle room"""
        # Remove from battle connections
        if battle_room_id in self.battle_connections:
            if user_id in self.battle_connections[battle_room_id]:
                del self.battle_connections[battle_room_id][user_id]
            
            # Clean up empty battle rooms
            if not self.battle_connections[battle_room_id]:
                del self.battle_connections[battle_room_id]
                if battle_room_id in self.battle_message_history:
                    del self.battle_message_history[battle_room_id]
                if battle_room_id in self.battle_timers:
                    self.battle_timers[battle_room_id].cancel()
                    del self.battle_timers[battle_room_id]
        
        # Remove from user connections
        if user_id in self.user_connections:
            if battle_room_id in self.user_connections[user_id]:
                del self.user_connections[user_id][battle_room_id]
            
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]

    async def send_to_user(self, user_id: int, message: Dict[str, Any]):
        """Send a message to a specific user"""
        if user_id in self.user_connections:
            for battle_id, websocket in self.user_connections[user_id].items():
                try:
                    await websocket.send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"Error sending message to user {user_id}: {e}")
                    await self.disconnect_from_battle(battle_id, user_id)

    async def broadcast_to_battle(self, battle_room_id: int, message: Dict[str, Any], exclude_user_id: Optional[int] = None):
        """Broadcast a message to all users in a battle room"""
        if battle_room_id not in self.battle_connections:
            return
        
        # Add to message history
        if battle_room_id in self.battle_message_history:
            self.battle_message_history[battle_room_id].append(message)
            # Keep only last 50 messages
            if len(self.battle_message_history[battle_room_id]) > 50:
                self.battle_message_history[battle_room_id] = self.battle_message_history[battle_room_id][-50:]
        
        # Send to all connected users
        disconnected_users = []
        for user_id, websocket in self.battle_connections[battle_room_id].items():
            if exclude_user_id and user_id == exclude_user_id:
                continue
            
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error broadcasting to user {user_id} in battle {battle_room_id}: {e}")
                disconnected_users.append(user_id)
        
        # Clean up disconnected users
        for user_id in disconnected_users:
            await self.disconnect_from_battle(battle_room_id, user_id)

    async def handle_websocket_message(self, websocket: WebSocket, battle_room_id: int, user_id: int, message: Dict[str, Any], db: Session):
        """Handle incoming WebSocket message"""
        message_type = message.get("type")
        data = message.get("data", {})
        
        debate_service = DebateService(db)
        
        try:
            if message_type == "chat":
                # Handle chat message
                await self._handle_chat_message(battle_room_id, user_id, data, db)
            
            elif message_type == "submit_argument":
                # Handle argument submission
                await self._handle_argument_submission(battle_room_id, user_id, data, db)
            
            elif message_type == "start_battle":
                # Handle battle start
                await self._handle_battle_start(battle_room_id, user_id, db)
            
            elif message_type == "heartbeat":
                # Handle heartbeat
                await websocket.send_text(json.dumps({
                    "type": "heartbeat_response",
                    "timestamp": datetime.utcnow().isoformat()
                }))
            
            elif message_type == "get_battle_state":
                # Send current battle state
                battle = debate_service.get_battle_room(battle_room_id)
                rounds = debate_service.get_battle_rounds(battle_room_id)
                votes = debate_service.get_battle_votes(battle_room_id)
                
                await websocket.send_text(json.dumps({
                    "type": "battle_state",
                    "data": {
                        "battle": {
                            "id": battle.id,
                            "status": battle.status,
                            "current_round": battle.current_round,
                            "max_rounds": battle.max_rounds,
                            "round_time_limit": battle.round_time_limit,
                            "started_at": battle.started_at.isoformat() if battle.started_at else None,
                            "round_started_at": battle.round_started_at.isoformat() if battle.round_started_at else None,
                            "round_ends_at": battle.round_ends_at.isoformat() if battle.round_ends_at else None,
                            "completed_at": battle.completed_at.isoformat() if battle.completed_at else None,
                            "winner_side": battle.winner_side,
                            "winner_user_id": battle.winner_user_id,
                            "pro_user_id": battle.pro_user_id,
                            "con_user_id": battle.con_user_id
                        },
                        "rounds": [
                            {
                                "id": round_obj.id,
                                "round_number": round_obj.round_number,
                                "status": round_obj.status,
                                "pro_argument": round_obj.pro_argument,
                                "con_argument": round_obj.con_argument,
                                "pro_submitted_at": round_obj.pro_submitted_at.isoformat() if round_obj.pro_submitted_at else None,
                                "con_submitted_at": round_obj.con_submitted_at.isoformat() if round_obj.con_submitted_at else None,
                                "started_at": round_obj.started_at.isoformat() if round_obj.started_at else None,
                                "completed_at": round_obj.completed_at.isoformat() if round_obj.completed_at else None
                            }
                            for round_obj in rounds
                        ],
                        "votes": [
                            {
                                "id": vote.id,
                                "voter_id": vote.voter_id,
                                "side": vote.side,
                                "reasoning": vote.reasoning,
                                "confidence": vote.confidence,
                                "argument_quality": vote.argument_quality,
                                "clarity": vote.clarity,
                                "persuasiveness": vote.persuasiveness,
                                "evidence": vote.evidence,
                                "created_at": vote.created_at.isoformat()
                            }
                            for vote in votes
                        ]
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }))
            
            else:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "data": {"message": f"Unknown message type: {message_type}"},
                    "timestamp": datetime.utcnow().isoformat()
                }))
        
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
            await websocket.send_text(json.dumps({
                "type": "error",
                "data": {"message": "Internal server error"},
                "timestamp": datetime.utcnow().isoformat()
            }))

    async def _handle_chat_message(self, battle_room_id: int, user_id: int, data: Dict[str, Any], db: Session):
        """Handle chat message"""
        message_content = data.get("message", "").strip()
        
        if not message_content:
            return
        
        # Get user info
        from app.models.user import User
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return
        
        # Create message
        message = {
            "type": "chat",
            "data": {
                "user_id": user_id,
                "username": user.username,
                "message": message_content,
                "timestamp": datetime.utcnow().isoformat()
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Broadcast to battle room
        await self.broadcast_to_battle(battle_room_id, message)

    async def _handle_argument_submission(self, battle_room_id: int, user_id: int, data: Dict[str, Any], db: Session):
        """Handle argument submission"""
        debate_service = DebateService(db)
        
        try:
            argument = data.get("argument", "").strip()
            round_number = data.get("round_number", 1)
            
            if not argument:
                await self.send_to_user(user_id, {
                    "type": "error",
                    "data": {"message": "Argument cannot be empty"},
                    "timestamp": datetime.utcnow().isoformat()
                })
                return
            
            # Submit argument
            round_obj = debate_service.submit_round_argument(battle_room_id, round_number, argument, user_id)
            
            # Determine user's side
            battle = debate_service.get_battle_room(battle_room_id)
            user_side = "pro" if user_id == battle.pro_user_id else "con"
            
            # Broadcast argument submission
            await self.broadcast_to_battle(battle_room_id, {
                "type": "argument_submitted",
                "data": {
                    "round_number": round_number,
                    "side": user_side,
                    "argument": argument,
                    "submitted_at": datetime.utcnow().isoformat()
                },
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Check if round is complete
            if round_obj.status == "completed":
                await self.broadcast_to_battle(battle_room_id, {
                    "type": "round_completed",
                    "data": {
                        "round_number": round_number,
                        "next_round": battle.current_round if battle.status == "active" else None
                    },
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            # If battle is completed, broadcast completion
            if battle.status == "completed":
                await self.broadcast_to_battle(battle_room_id, {
                    "type": "battle_completed",
                    "data": {
                        "winner_side": battle.winner_side,
                        "winner_user_id": battle.winner_user_id,
                        "completed_at": battle.completed_at.isoformat() if battle.completed_at else None
                    },
                    "timestamp": datetime.utcnow().isoformat()
                })
        
        except ValueError as e:
            await self.send_to_user(user_id, {
                "type": "error",
                "data": {"message": str(e)},
                "timestamp": datetime.utcnow().isoformat()
            })

    async def _handle_battle_start(self, battle_room_id: int, user_id: int, db: Session):
        """Handle battle start"""
        debate_service = DebateService(db)
        
        try:
            battle = debate_service.start_battle(battle_room_id)
            
            # Broadcast battle start
            await self.broadcast_to_battle(battle_room_id, {
                "type": "battle_started",
                "data": {
                    "battle_id": battle_room_id,
                    "status": battle.status,
                    "current_round": battle.current_round,
                    "round_time_limit": battle.round_time_limit,
                    "started_at": battle.started_at.isoformat() if battle.started_at else None,
                    "round_ends_at": battle.round_ends_at.isoformat() if battle.round_ends_at else None
                },
                "timestamp": datetime.utcnow().isoformat()
            })
        
        except ValueError as e:
            await self.send_to_user(user_id, {
                "type": "error",
                "data": {"message": str(e)},
                "timestamp": datetime.utcnow().isoformat()
            })

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        total_connections = sum(len(connections) for connections in self.battle_connections.values())
        active_battles = len(self.battle_connections)
        active_timers = len(self.battle_timers)
        
        return {
            "total_connections": total_connections,
            "active_battles": active_battles,
            "active_timers": active_timers,
            "battle_connections": {battle_id: len(users) for battle_id, users in self.battle_connections.items()}
        }

# Global WebSocket manager
websocket_manager = WebSocketManager()
