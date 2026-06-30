"""
Script to start the Telegram bot
Run this separately from the main FastAPI server
"""
import asyncio
import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.telegram_bot_handler import bot_handler
from app.services.telegram_service import telegram_service

async def main():
    print("Starting Telegram Bot...")
    
    if not telegram_service.is_enabled():
        print("ERROR: TELEGRAM_BOT_TOKEN not set in .env file")
        print("Please add your bot token to the .env file and try again")
        return
    
    try:
        await bot_handler.start()
        print("Telegram bot is running. Press Ctrl+C to stop.")
        
        # Keep the bot running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping Telegram Bot...")
        await bot_handler.stop()
        print("Telegram Bot stopped.")
    except Exception as e:
        print(f"Error starting bot: {e}")
        await bot_handler.stop()

if __name__ == "__main__":
    asyncio.run(main())
