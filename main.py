# main.py
import asyncio
from telegram.ext import Application
from config import TELEGRAM_BOT_TOKEN
from bot.bot_handler import setup_handlers
from database.postgres import check_and_fix_columns
from telegram import Update
def main():
    check_and_fix_columns()  
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    setup_handlers(application)

    print("Bot iniciado e pronto para uso!")
    print("=" * 40)
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()