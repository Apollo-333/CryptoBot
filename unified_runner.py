"""
🚀 УНИФИЦИРОВАННЫЙ ЗАПУСК ДЛЯ RENDER
Запускает: Основной бот + Бот поддержки + Веб-сервер
БЕЗ КОНФЛИКТОВ!
"""
import os
import sys
import time
import logging
import threading
from datetime import datetime

# ================== НАСТРОЙКА ==================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SUPPORT_BOT_TOKEN = os.getenv("SUPPORT_BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

print("=" * 60)
print("🤖 ЗАПУСК CRYPTO SIGNALS SYSTEM")
print("=" * 60)
print(f"Основной бот: {'✅' if TELEGRAM_TOKEN else '❌'}")
print(f"Бот поддержки: {'✅' if SUPPORT_BOT_TOKEN else '❌'}")
print(f"Админ ID: {ADMIN_ID or 'Не установлен'}")
print("=" * 60)

# ================== ГЛОБАЛЬНЫЕ ФЛАГИ ==================
bot_instances = {}
bot_lock = threading.Lock()

# ================== ВЕБ-СЕРВЕР ==================
def run_web_server():
    """Запуск веб-сервера для Render (ОБЯЗАТЕЛЬНО)"""
    try:
        from flask import Flask
        import json
        from waitress import serve
        
        app = Flask(__name__)
        
        @app.route('/')
        def home():
            status = {
                "main_bot": "active" if TELEGRAM_TOKEN else "missing_token",
                "support_bot": "active" if SUPPORT_BOT_TOKEN else "missing_token",
                "web_server": "active",
                "timestamp": datetime.now().isoformat(),
                "url": "https://crypto-bot-612m.onrender.com"
            }
            
            return f"""
            <html>
                <head>
                    <title>Crypto Signals System</title>
                    <meta http-equiv="refresh" content="30">
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 40px; }}
                        .status {{ padding: 10px; margin: 10px 0; border-radius: 5px; }}
                        .ok {{ background: #d4edda; color: #155724; }}
                        .error {{ background: #f8d7da; color: #721c24; }}
                        .warning {{ background: #fff3cd; color: #856404; }}
                    </style>
                </head>
                <body>
                    <h1>🤖 Crypto Signals System</h1>
                    <div class="status {'ok' if TELEGRAM_TOKEN else 'error'}">
                        <strong>Основной бот:</strong> {'✅ Активен' if TELEGRAM_TOKEN else '❌ Нет токена'}
                    </div>
                    <div class="status {'ok' if SUPPORT_BOT_TOKEN else 'warning'}">
                        <strong>Бот поддержки:</strong> {'✅ Активен' if SUPPORT_BOT_TOKEN else '⚠️ Не настроен'}
                    </div>
                    <div class="status ok">
                        <strong>Веб-сервер:</strong> ✅ Активен
                    </div>
                    <p><strong>Время:</strong> {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}</p>
                    <p><strong>Telegram:</strong> @CryptoSignalsProBot</p>
                </body>
            </html>
            """
        
        @app.route('/health')
        def health():
            return json.dumps({"status": "OK", "time": datetime.now().isoformat()}), 200
        
        @app.route('/api/status')
        def api_status():
            return json.dumps({
                "status": "running",
                "services": {
                    "web_server": "active",
                    "main_bot": "active" if TELEGRAM_TOKEN else "inactive",
                    "support_bot": "active" if SUPPORT_BOT_TOKEN else "inactive"
                }
            }), 200
        
        port = int(os.environ.get('PORT', 8080))
        logger.info(f"🌐 Запуск веб-сервера на порту {port}")
        serve(app, host="0.0.0.0", port=port)
        
    except Exception as e:
        logger.error(f"❌ Ошибка веб-сервера: {e}")
        # Падаем если веб-сервер не запустился
        raise

# ================== ОСНОВНОЙ БОТ ==================
def run_main_bot():
    """Запуск основного бота с задержкой и защитой от конфликтов"""
    logger.info("⏳ Задержка 10 секунд перед запуском основного бота...")
    time.sleep(10)  # Ждем дольше
    
    if not TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN не найден!")
        return
    
    try:
        from telegram.ext import Updater, CommandHandler
        
        logger.info("🤖 Инициализация основного бота...")
        
        # Создаем экземпляр
        updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
        
        # КРИТИЧЕСКИ ВАЖНО: сбросить offset
        try:
            logger.info("🔄 Сбрасываю offset для основного бота...")
            updater.bot.get_updates(offset=-1)
            time.sleep(1)
        except Exception as e:
            logger.warning(f"⚠️ Не удалось сбросить offset: {e}")
        
        # Регистрируем команды
        def start(update, context):
            update.message.reply_text("🚀 Crypto Signals Bot активен! Используйте /signals")
        
        def signals(update, context):
            update.message.reply_text("📈 Сигналы: функция в разработке")
        
        dispatcher = updater.dispatcher
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("signals", signals))
        
        # Запускаем с уникальными параметрами
        logger.info("✅ Запускаю polling основного бота...")
        updater.start_polling(
            poll_interval=2.0,  # Уникальный интервал
            timeout=15,
            drop_pending_updates=True,
            allowed_updates=['message', 'callback_query']
        )
        
        # Сохраняем экземпляр
        with bot_lock:
            bot_instances['main'] = updater
        
        logger.info("✅ Основной бот успешно запущен!")
        
        # Держим активным
        while True:
            time.sleep(30)
            logger.debug("Основной бот: активен")
            
    except Exception as e:
        logger.error(f"❌ Ошибка основного бота: {e}")
        # Не перезапускаем автоматически - пусть упадет

# ================== БОТ ПОДДЕРЖКИ ==================
def run_support_bot():
    """Запуск бота поддержки с большой задержкой"""
    logger.info("⏳ Задержка 20 секунд перед запуском бота поддержки...")
    time.sleep(20)  # Ждем еще дольше
    
    if not SUPPORT_BOT_TOKEN:
        logger.warning("⚠️ SUPPORT_BOT_TOKEN не найден, пропускаем")
        return
    
    try:
        from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
        
        logger.info("🆘 Инициализация бота поддержки...")
        
        # Создаем экземпляр
        updater = Updater(token=SUPPORT_BOT_TOKEN, use_context=True)
        
        # Сброс offset
        try:
            logger.info("🔄 Сбрасываю offset для бота поддержки...")
            updater.bot.get_updates(offset=-1)
            time.sleep(1)
        except Exception as e:
            logger.warning(f"⚠️ Не удалось сбросить offset: {e}")
        
        # Команды
        def support_start(update, context):
            update.message.reply_text("🤖 Бот поддержки активен. Отправьте ваш вопрос.")
        
        def echo(update, context):
            update.message.reply_text(f"✅ Получено: {update.message.text}")
        
        dispatcher = updater.dispatcher
        dispatcher.add_handler(CommandHandler("start", support_start))
        dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))
        
        # ДРУГОЙ интервал polling
        logger.info("✅ Запускаю polling бота поддержки...")
        updater.start_polling(
            poll_interval=3.0,  # Другой интервал!
            timeout=15,
            drop_pending_updates=True,
            allowed_updates=['message']
        )
        
        # Сохраняем экземпляр
        with bot_lock:
            bot_instances['support'] = updater
        
        logger.info("✅ Бот поддержки успешно запущен!")
        
        while True:
            time.sleep(30)
            logger.debug("Бот поддержки: активен")
            
    except Exception as e:
        logger.error(f"❌ Ошибка бота поддержки: {e}")
        # Проверяем токен
        if "Invalid token" in str(e):
            logger.error("❌ НЕВЕРНЫЙ ТОКЕН бота поддержки! Проверьте SUPPORT_BOT_TOKEN")

# ================== ГЛАВНАЯ ФУНКЦИЯ ==================
def main():
    """Основная функция запуска с защитой от конфликтов"""
    logger.info("🚀 Начинаю запуск системы...")
    
    # ВАЖНО: Проверяем переменные
    if not TELEGRAM_TOKEN:
        logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: TELEGRAM_TOKEN не установлен!")
        logger.info("💡 Установите в Render Dashboard:")
        logger.info("   TELEGRAM_TOKEN = ваш_токен_от_BotFather")
        return
    
    # Запускаем компоненты ПО ОЧЕРЕДИ с задержками
    
    # 1. Веб-сервер ПЕРВЫМ
    logger.info("1. Запуск веб-сервера...")
    web_thread = threading.Thread(target=run_web_server, daemon=True, name="WebServer")
    web_thread.start()
    time.sleep(3)  # Ждем запуска
    
    # 2. Основной бот
    logger.info("2. Подготовка основного бота...")
    main_bot_thread = threading.Thread(target=run_main_bot, daemon=True, name="MainBot")
    main_bot_thread.start()
    
    # 3. Бот поддержки (если есть токен)
    if SUPPORT_BOT_TOKEN:
        logger.info("3. Подготовка бота поддержки...")
        support_bot_thread = threading.Thread(target=run_support_bot, daemon=True, name="SupportBot")
        support_bot_thread.start()
    else:
        logger.info("3. Бот поддержки пропущен (нет токена)")
    
    logger.info("✅ Все компоненты инициализированы!")
    logger.info(f"🌐 Веб-интерфейс: https://crypto-bot-612m.onrender.com")
    logger.info(f"🤖 Основной бот: {'✅' if TELEGRAM_TOKEN else '❌'}")
    logger.info(f"🆘 Бот поддержки: {'✅' if SUPPORT_BOT_TOKEN else '❌'}")
    
    # Мониторинг
    try:
        while True:
            time.sleep(60)
            logger.info(f"⏰ Система активна: {datetime.now().strftime('%H:%M:%S')}")
            logger.info(f"📊 Активных потоков: {threading.active_count()}")
            
    except KeyboardInterrupt:
        logger.info("\n🛑 Остановка системы...")
    except Exception as e:
        logger.error(f"❌ Непредвиденная ошибка: {e}")

# ================== ЗАПУСК ==================
if __name__ == "__main__":
    # КРИТИЧЕСКИ ВАЖНО: Убедитесь что старые боты не запускаются
    # Переименуйте main.py и support_bot.py чтобы они не запускались автоматически!
    
    main()
