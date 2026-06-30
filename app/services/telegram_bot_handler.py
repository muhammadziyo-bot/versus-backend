import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.user import User
from app.config import settings
import secrets

logger = logging.getLogger(__name__)

class TelegramBotHandler:
    def __init__(self):
        self.bot_token = settings.telegram_bot_token
        self.application = None
    
    async def start(self):
        """Start the Telegram bot"""
        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not set, bot not starting")
            return
        
        self.application = Application.builder().token(self.bot_token).build()
        
        # Register command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("link", self.link_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("unlink", self.unlink_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Start the bot
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        
        logger.info("Telegram bot started successfully")
    
    async def stop(self):
        """Stop the Telegram bot"""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("Telegram bot stopped")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_message = (
            "🎮 Welcome to Digital Arena Bot!\n\n"
            "This bot will send you notifications about:\n"
            "⚔️ Battle invitations\n"
            "👥 Friend requests\n"
            "💬 Comments on your topics\n"
            "🏆 Battle results\n\n"
            "Commands:\n"
            "/link - Link your Telegram account to Digital Arena\n"
            "/unlink - Unlink your account\n"
            "/help - Show this help message"
        )
        await update.message.reply_text(welcome_message)
    
    async def link_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /link command - Generate a linking token"""
        chat_id = str(update.effective_chat.id)
        username = update.effective_user.username
        
        # Generate a unique linking token
        linking_token = secrets.token_urlsafe(16)
        
        db: Session = SessionLocal()
        try:
            # Check if this chat_id is already linked
            existing_user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
            if existing_user:
                await update.message.reply_text(
                    f"✅ Your Telegram account is already linked to: {existing_user.username}\n\n"
                    "Use /unlink to disconnect if you want to link a different account."
                )
                return
            
            # Show the user their chat ID and token
            link_message = (
                "🔗 Link Your Account\n\n"
                f"📱 Your Chat ID: {chat_id}\n"
                f"🔑 Your Token: {linking_token}\n\n"
                "Steps to link:\n"
                "1. Go to Digital Arena website\n"
                "2. Navigate to Settings → Telegram Integration\n"
                "3. Click 'Bot Link' tab\n"
                "4. Enter the Token above\n"
                "5. Enter the Chat ID above\n"
                f"6. (Optional) Enter your username: @{username if username else 'your_username'}\n\n"
                "⚠️ This token will expire in 10 minutes."
            )
            await update.message.reply_text(link_message)
            
        finally:
            db.close()
    
    async def unlink_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /unlink command"""
        chat_id = str(update.effective_chat.id)
        
        db: Session = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_chat_id == chat_id).first()
            if user:
                user.telegram_chat_id = None
                user.telegram_username = None
                db.commit()
                await update.message.reply_text("✅ Your account has been unlinked successfully.")
            else:
                await update.message.reply_text("❌ Your account is not linked to any Digital Arena account.")
        finally:
            db.close()
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_message = (
            "📚 Digital Arena Bot Help\n\n"
            "Commands:\n"
            "/start - Show welcome message\n"
            "/link - Link your Telegram account\n"
            "/unlink - Unlink your account\n"
            "/help - Show this help message\n\n"
            "For support, contact us at support@digitalarena.uz"
        )
        await update.message.reply_text(help_message)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle non-command messages"""
        # If someone sends a message, we can respond or just ignore
        # For now, let's provide a helpful response
        await update.message.reply_text(
            "I'm the Digital Arena notification bot! 🎮\n\n"
            "Use /help to see available commands."
        )

# Global bot handler instance
bot_handler = TelegramBotHandler()
