import os
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from typing import Optional
import logging
import requests
from app.config import settings

logger = logging.getLogger(__name__)

class TelegramService:
    def __init__(self):
        self.bot_token = settings.telegram_bot_token
        self.bot = None
        if self.bot_token:
            self.bot = Bot(token=self.bot_token)
    
    def is_enabled(self) -> bool:
        """Check if Telegram bot is configured"""
        return self.bot_token is not None and self.bot is not None
    
    async def resolve_username_to_chat_id(self, username: str) -> Optional[str]:
        """
        Resolve a Telegram username to a chat ID
        Note: This only works for public usernames and requires the bot to be in the same chat
        For private users, we need them to start a conversation with the bot first
        """
        try:
            # Try to get chat info from username
            # This is limited - Telegram API doesn't easily allow resolving usernames to chat IDs
            # The best approach is to have users start a conversation with the bot
            # Then we capture their chat_id when they use the /link command
            
            # For now, we'll return None and rely on the chat_id from the bot interaction
            logger.warning(f"Username resolution not directly supported via API. Username: {username}")
            return None
        except Exception as e:
            logger.error(f"Error resolving username: {e}")
            return None
    
    async def send_notification(
        self,
        chat_id: str,
        title: str,
        message: str,
        action_url: Optional[str] = None,
        action_text: str = "View on Website"
    ) -> bool:
        """
        Send a notification to a user via Telegram
        
        Args:
            chat_id: User's Telegram chat ID
            title: Notification title
            message: Notification message content
            action_url: Optional URL for the action button
            action_text: Text for the action button
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.is_enabled():
            logger.warning("Telegram bot is not configured")
            return False
        
        if not chat_id:
            logger.warning("No chat ID provided")
            return False
        
        try:
            # Format the message
            formatted_message = f"🔔 *{title}*\n\n{message}"
            
            # Create inline keyboard if action URL is provided
            reply_markup = None
            if action_url:
                keyboard = [[InlineKeyboardButton(action_text, url=action_url)]]
                reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Send the message
            await self.bot.send_message(
                chat_id=chat_id,
                text=formatted_message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
            logger.info(f"Telegram notification sent to chat_id: {chat_id}")
            return True
            
        except TelegramError as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False
    
    async def send_battle_invitation(
        self,
        chat_id: str,
        inviter_username: str,
        topic_title: str,
        battle_url: str
    ) -> bool:
        """Send a battle invitation notification"""
        message = (
            f"👤 {inviter_username} has invited you to a battle!\n\n"
            f"⚔️ Topic: {topic_title}\n\n"
            f"Click the button below to accept the challenge and start battling!"
        )
        return await self.send_notification(
            chat_id=chat_id,
            title="Battle Invitation",
            message=message,
            action_url=battle_url,
            action_text="⚔️ Join Battle"
        )
    
    async def send_friend_request(
        self,
        chat_id: str,
        requester_username: str,
        profile_url: str
    ) -> bool:
        """Send a friend request notification"""
        message = (
            f"👤 {requester_username} wants to be your friend!\n\n"
            f"Click the button below to view their profile and accept the request."
        )
        return await self.send_notification(
            chat_id=chat_id,
            title="Friend Request",
            message=message,
            action_url=profile_url,
            action_text="👤 View Profile"
        )
    
    async def send_comment_notification(
        self,
        chat_id: str,
        commenter_username: str,
        topic_title: str,
        comment_preview: str,
        topic_url: str
    ) -> bool:
        """Send a notification when someone comments on your topic"""
        message = (
            f"👤 {commenter_username} commented on your topic\n\n"
            f"📝 Topic: {topic_title}\n"
            f"💬 Comment: {comment_preview[:100]}...\n\n"
            f"Click the button to view the discussion."
        )
        return await self.send_notification(
            chat_id=chat_id,
            title="New Comment",
            message=message,
            action_url=topic_url,
            action_text="💬 View Comment"
        )
    
    async def send_battle_result(
        self,
        chat_id: str,
        opponent_username: str,
        topic_title: str,
        won: bool,
        battle_url: str
    ) -> bool:
        """Send battle result notification"""
        result_emoji = "🏆" if won else "😔"
        result_text = "won" if won else "lost"
        message = (
            f"{result_emoji} You {result_text} the battle against {opponent_username}!\n\n"
            f"⚔️ Topic: {topic_title}\n\n"
            f"Click the button to view the battle details."
        )
        return await self.send_notification(
            chat_id=chat_id,
            title=f"Battle {result_text.title()}!",
            message=message,
            action_url=battle_url,
            action_text="📊 View Battle"
        )

# Singleton instance
telegram_service = TelegramService()
