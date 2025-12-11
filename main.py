# main.py
import asyncio
from telegram.ext import Application
from config import TELEGRAM_BOT_TOKEN
from bot.bot_handler import setup_handlers
from telegram import Update
def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    setup_handlers(application)
    print("=" * 40)
    print("Bot Initialized")
    print("=" * 40)
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()