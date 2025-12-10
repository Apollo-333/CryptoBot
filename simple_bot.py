"""
🚀 MINIMAL WORKING BOT - NO APSCHEDULER, NO CONFLICTS
"""
import os
import sys
import time
import logging

# ================== НАСТРОЙКА ==================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID", "0")

print("=" * 60)
print("🤖 MINIMAL CRYPTO BOT")
print(f"Token: {'✅' if TELEGRAM_TOKEN else '❌'}")
print(f"Admin: {ADMIN_ID}")
print("=" * 60)

# ================== ВЕБ-СЕРВЕР ==================
def run_web():
    """Простой веб-сервер"""
    try:
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
    except Exception as e:
        logger.error(f"Web error: {e}")

# ================== БОТ ==================
def run_bot():
    """Минимальный бот без APScheduler"""
    time.sleep(3)
    
    if not TELEGRAM_TOKEN:
        logger.error("❌ No token!")
        return
    
    try:
        # Импортируем ТОЛЬКО необходимые модули
        from telegram import Bot
        import telegram.ext
        
        logger.info("🤖 Creating bot instance...")
        
        # Создаем вручную без APScheduler
        from telegram.ext import Updater, CommandHandler
        
        # 1. Создаем Updater
        updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
        
        # 2. ВАЖНО: Полностью сбрасываем offset
        try:
            logger.info("🔄 FULL offset reset...")
            # Получаем все обновления и отмечаем их как обработанные
            updater.bot.get_updates(offset=-1)
            time.sleep(2)
        except Exception as e:
            logger.warning(f"Offset warning: {e}")
        
        # 3. Простые команды
        def start(update, context):
            update.message.reply_text("🚀 Bot is working!")
        
        def help_cmd(update, context):
            update.message.reply_text("🤖 Commands: /start, /help, /ping")
        
        def ping(update, context):
            update.message.reply_text("🏓 Pong!")
        
        # 4. Регистрируем команды
        dp = updater.dispatcher
        dp.add_handler(CommandHandler("start", start))
        dp.add_handler(CommandHandler("help", help_cmd))
        dp.add_handler(CommandHandler("ping", ping))
        
        # 5. Запускаем polling с параметрами для избежания конфликтов
        logger.info("✅ Starting polling...")
        updater.start_polling(
            poll_interval=3.0,  # Увеличиваем интервал
            timeout=25,
            drop_pending_updates=True,
            allowed_updates=['message']
        )
        
        logger.info("✅ Bot started successfully!")
        
        # 6. Бесконечный цикл
        while True:
            time.sleep(30)
            logger.info("🤖 Bot heartbeat...")
            
    except Exception as e:
        logger.error(f"❌ Bot error: {e}")
        import traceback
        traceback.print_exc()

# ================== ГЛАВНЫЙ ЗАПУСК ==================
def main():
    """Запуск всего"""
    import threading
    
    # Запускаем веб в отдельном потоке
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    
    # Даем вебу время запуститься
    time.sleep(2)
    
    # Запускаем бота в основном потоке
    run_bot()

# ================== ТОЧКА ВХОДА ==================
if __name__ == "__main__":
    print("🚀 Starting minimal bot...")
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Stopped")
    except Exception as e:
        print(f"❌ Critical: {e}")
        sys.exit(1)
