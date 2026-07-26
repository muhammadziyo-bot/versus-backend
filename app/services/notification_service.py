from sqlalchemy.orm import Session
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationCreate, NotificationUpdate
from typing import List
from app.services.telegram_service import telegram_service
from app.config import settings
import json

class NotificationService:
    def __init__(self, db: Session):
        self.db = db

    def get_user_notifications(self, user_id: int, skip: int = 0, limit: int = 100) -> List[Notification]:
        return self.db.query(Notification).filter(
            Notification.user_id == user_id
        ).order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()

    def get_unread_count(self, user_id: int) -> int:
        return self.db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).count()

    def create_notification(self, notification: NotificationCreate) -> Notification:
        db_notification = Notification(**notification.dict())
        self.db.add(db_notification)
        self.db.commit()
        self.db.refresh(db_notification)
        
        return db_notification
    
    async def _send_telegram_notification(self, notification: Notification, user: User):
        """Send notification via Telegram based on notification type"""
        if not telegram_service.is_enabled():
            return
        
        try:
            # Parse data from JSON string
            data = {}
            if notification.data:
                try:
                    data = json.loads(notification.data)
                except:
                    data = {}
            
            # Base URL for the website (from config, defaults to localhost:5173 in dev)
            base_url = settings.frontend_url
            
            # Send appropriate notification based on type
            if notification.type == "battle_invitation":
                battle_id = data.get("battle_id", "")
                await telegram_service.send_battle_invitation(
                    chat_id=user.telegram_chat_id,
                    inviter_username=data.get("inviter_username", "Someone"),
                    topic_title=data.get("topic_title", "Unknown topic"),
                    battle_url=f"{base_url}/battle/room/{battle_id}" if battle_id else base_url
                )
            elif notification.type == "friend_request":
                requester_username = data.get("requester_username", "Someone")
                await telegram_service.send_friend_request(
                    chat_id=user.telegram_chat_id,
                    requester_username=requester_username,
                    profile_url=f"{base_url}/profile/{requester_username}" if requester_username else base_url
                )
            elif notification.type == "comment":
                topic_id = data.get("topic_id", "")
                await telegram_service.send_comment_notification(
                    chat_id=user.telegram_chat_id,
                    commenter_username=data.get("commenter_username", "Someone"),
                    topic_title=data.get("topic_title", "Unknown topic"),
                    comment_preview=data.get("comment_preview", ""),
                    topic_url=f"{base_url}/discussions/{topic_id}" if topic_id else base_url
                )
            elif notification.type == "battle_result":
                battle_id = data.get("battle_id", "")
                await telegram_service.send_battle_result(
                    chat_id=user.telegram_chat_id,
                    opponent_username=data.get("opponent_username", "Someone"),
                    topic_title=data.get("topic_title", "Unknown topic"),
                    won=data.get("won", False),
                    battle_url=f"{base_url}/battle/room/{battle_id}" if battle_id else base_url
                )
            else:
                # Generic notification
                await telegram_service.send_notification(
                    chat_id=user.telegram_chat_id,
                    title=notification.title,
                    message=notification.message,
                    action_url=base_url
                )
        except Exception as e:
            # Log error but don't fail the notification creation
            print(f"Failed to send Telegram notification: {e}")

    def mark_as_read(self, notification_id: int, user_id: int) -> Notification:
        notification = self.db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == user_id
        ).first()
        
        if notification:
            notification.is_read = True
            self.db.commit()
            self.db.refresh(notification)
        
        return notification

    def mark_all_as_read(self, user_id: int) -> int:
        count = self.db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).update({"is_read": True})
        self.db.commit()
        return count

    def delete_notification(self, notification_id: int, user_id: int) -> bool:
        notification = self.db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == user_id
        ).first()
        
        if notification:
            self.db.delete(notification)
            self.db.commit()
            return True
        
        return False
