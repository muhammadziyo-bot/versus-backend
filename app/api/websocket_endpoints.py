from fastapi import WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
import json
import logging
from datetime import datetime

from app.database import get_db
from app.api.websocket import websocket_manager
from app.core.security import verify_token

logger = logging.getLogger(__name__)

async def get_current_user_websocket(
    token: Optional[str] = Query(...),
    db: Session = Depends(get_db)
):
    """Authenticate WebSocket connection"""
    if not token:
        return None
    
    try:
        email = verify_token(token)
        if email:
            from app.models.user import User
            user = db.query(User).filter(User.email == email).first()
            return user
    except Exception as e:
        logger.error(f"WebSocket authentication error: {e}")
    
    return None

async def websocket_endpoint(
    websocket: WebSocket,
    battle_room_id: int,
    token: Optional[str] = Query(...),
    db: Session = Depends(get_db)
):
    """WebSocket endpoint for real-time battle communication"""
    # Authenticate user
    user = await get_current_user_websocket(token, db)
    if not user:
        await websocket.close(code=4001, reason="Authentication required")
        return
    
    # Connect to battle room
    connected = await websocket_manager.connect_to_battle(websocket, battle_room_id, user.id, db)
    if not connected:
        return
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                await websocket_manager.handle_websocket_message(websocket, battle_room_id, user.id, message, db)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "data": {"message": "Invalid JSON format"},
                    "timestamp": datetime.utcnow().isoformat()
                }))
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "data": {"message": "Error processing message"},
                    "timestamp": datetime.utcnow().isoformat()
                }))
    
    except WebSocketDisconnect:
        await websocket_manager.disconnect_from_battle(battle_room_id, user.id)
        logger.info(f"User {user.id} disconnected from battle {battle_room_id}")
    
    except Exception as e:
        logger.error(f"WebSocket error for battle {battle_room_id}: {e}")
        await websocket_manager.disconnect_from_battle(battle_room_id, user.id)
