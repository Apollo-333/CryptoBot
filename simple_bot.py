# simple_bot.py - исправленный для PTB 20.x
import os
import sys
import time
import logging
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# ================== ВЕБ-СЕРВЕР ==================
def run_web():
    from flask import Flask
    from waitress import serve
    
    app = Flask(__name__)
    
    @app.route('/')
    def home():
        return "🤖 Crypto Bot - ACTIVE ✅"
    
    @app.route('/health')
    def health():
        return "OK", 200
    
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🌐 Web server on port {port}")
    serve(app, host="0.0.0.0", port=port)

# ================== БОТ (для PTB 20.x) ==================
def run_bot():
    time.sleep(3)
    
    if not TELEGRAM_TOKEN:
        logger.error("❌ No token!")
        return
    
    try:
        # НОВЫЙ API для PTB 20.x
        from telegram.ext import Application, CommandHandler, ContextTypes
        from telegram import Update
        
        logger.info("🤖 Creating bot instance...")
        
        # Создаем Application (новый стиль)
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Команды (должны быть async)
        async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await update.message.reply_text("🚀 Bot is working!")
        
        async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await update.message.reply_text("🤖 Commands: /start, /help, /ping")
        
        async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await update.message.reply_text("🏓 Pong!")
        
        # Регистрируем команды
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_cmd))
        application.add_handler(CommandHandler("ping", ping))
        
        # Запускаем polling
        logger.info("✅ Starting polling...")
        application.run_polling(
            poll_interval=3.0,
            timeout=25,
            drop_pending_updates=True
        )
        
    except Exception as e:
        logger.error(f"❌ Bot error: {e}")
        import traceback
        traceback.print_exc()

# ================== ГЛАВНЫЙ ЗАПУСК ==================
def main():
    import threading
    
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    time.sleep(2)
    run_bot()

if __name__ == "__main__":
    print("🚀 Starting bot...")
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Stopped")
    except Exception as e:
        print(f"❌ Critical: {e}")
        sys.exit(1)
