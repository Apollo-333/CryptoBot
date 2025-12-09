"""
🚀 УНИФИЦИРОВАННЫЙ ЗАПУСК ДЛЯ RENDER
Запускает: Основной бот + Бот поддержки + Веб-сервер
"""
import os
import sys
import time
import logging
import threading
from datetime import datetime

# ================== НАСТРОЙКА ==================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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

# ================== ВЕБ-СЕРВЕР ==================
def run_web_server():
    """Запуск веб-сервера для Render (ОБЯЗАТЕЛЬНО)"""
    try:
        from flask import Flask
        from waitress import serve
        
        app = Flask(__name__)
        
        @app.route('/')
        def home():
            return f"""
            <html>
                <head>
                    <title>Crypto Signals System</title>
                    <meta http-equiv="refresh" content="30">
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
                        .container {{ max-width: 800px; margin: 0 auto; }}
                        .status {{ padding: 10px; margin: 10px 0; border-radius: 5px; }}
                        .ok {{ background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
                        .error {{ background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }}
                        .warning {{ background: #fff3cd; color: #856404; border: 1px solid #ffeaa7; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>🤖 Crypto Signals System</h1>
                        <p>Система управления торговыми сигналами</p>
                        
                        <div class="status {'ok' if TELEGRAM_TOKEN else 'error'}">
                            <strong>Основной бот:</strong> {'✅ Активен' if TELEGRAM_TOKEN else '❌ Не настроен'}
                        </div>
                        
                        <div class="status {'ok' if SUPPORT_BOT_TOKEN else 'warning'}">
                            <strong>Бот поддержки:</strong> {'✅ Активен' if SUPPORT_BOT_TOKEN else '⚠️ Не настроен'}
                        </div>
                        
                        <div class="status ok">
                            <strong>Веб-сервер:</strong> ✅ Активен
                        </div>
                        
                        <p><strong>Время сервера:</strong> {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}</p>
                        <p><strong>Telegram:</strong> @CryptoSignalsProBot</p>
                        <p><strong>Поддержка:</strong> @CryptoSignalsSupportBot</p>
                    </div>
                </body>
            </html>
            """
        
        @app.route('/health')
        def health():
            return json.dumps({
                "status": "OK",
                "main_bot": bool(TELEGRAM_TOKEN),
                "support_bot": bool(SUPPORT_BOT_TOKEN),
                "timestamp": datetime.now().isoformat()
            }), 200, {'Content-Type': 'application/json'}
        
        @app.route('/ping')
        def ping():
            return "pong"
        
        port = int(os.environ.get('PORT', 8080))
        logger.info(f"🌐 Запуск веб-сервера на порту {port}")
        serve(app, host="0.0.0.0", port=port)
        
    except Exception as e:
        logger.error(f"❌ Ошибка веб-сервера: {e}")

# ================== ОСНОВНОЙ БОТ ==================
def run_main_bot():
    """Запуск основного бота с сигналами"""
    logger.info("🤖 Инициализация основного бота...")
    time.sleep(5)  # Даем время веб-серверу запуститься
    
    try:
        # Импортируем основные модули
        import telegram
        from telegram.ext import Updater
        
        if not TELEGRAM_TOKEN:
            logger.error("❌ TELEGRAM_TOKEN не найден!")
            return
        
        updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
        
        # Сброс offset чтобы избежать конфликтов
        try:
            updater.bot.get_updates(offset=-1)
            logger.info("✅ Offset сброшен")
        except:
            pass
        
        # Простые команды для теста
        def start(update, context):
            update.message.reply_text("🚀 Crypto Signals Bot активен! Используйте /signals для получения сигналов.")
        
        def signals(update, context):
            update.message.reply_text("📈 Сигналы генерируются... (функционал в разработке)")
        
        dispatcher = updater.dispatcher
        dispatcher.add_handler(telegram.ext.CommandHandler("start", start))
        dispatcher.add_handler(telegram.ext.CommandHandler("signals", signals))
        
        # Запускаем с уникальными параметрами
        updater.start_polling(
            poll_interval=2.0,
            timeout=20,
            drop_pending_updates=True,
            allowed_updates=['message', 'callback_query']
        )
        
        logger.info("✅ Основной бот запущен и слушает команды")
        
        # Держим активным
        while True:
            time.sleep(10)
            logger.debug("Основной бот: активен")
            
    except telegram.error.Conflict as e:
        logger.error(f"⚠️ Конфликт основного бота: {e}")
        logger.info("🔄 Перезапуск через 30 секунд...")
        time.sleep(30)
        run_main_bot()  # Рекурсивный перезапуск
    except Exception as e:
        logger.error(f"❌ Критическая ошибка основного бота: {e}")
        logger.exception(e)

# ================== БОТ ПОДДЕРЖКИ ==================
def run_support_bot():
    """Запуск бота технической поддержки"""
    logger.info("🆘 Инициализация бота поддержки...")
    time.sleep(10)  # Ждем дольше чем основной бот
    
    try:
        import telegram
        from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
        
        if not SUPPORT_BOT_TOKEN:
            logger.warning("⚠️ SUPPORT_BOT_TOKEN не найден, пропускаем бота поддержки")
            return
        
        updater = Updater(token=SUPPORT_BOT_TOKEN, use_context=True)
        
        # Сброс offset
        try:
            updater.bot.get_updates(offset=-1)
            logger.info("✅ Offset сброшен (поддержка)")
        except:
            pass
        
        def support_start(update, context):
            user = update.effective_user
            update.message.reply_text(
                f"🤖 Здравствуйте, {user.first_name}!\n"
                "Я бот поддержки Crypto Signals.\n"
                "Отправьте ваш вопрос, и я передам его администратору."
            )
        
        def forward_message(update, context):
            user = update.effective_user
            logger.info(f"📨 Сообщение от {user.id} ({user.first_name}): {update.message.text}")
            update.message.reply_text("✅ Ваше сообщение получено! Администратор ответит в течение 24 часов.")
        
        dispatcher = updater.dispatcher
        dispatcher.add_handler(CommandHandler("start", support_start))
        dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, forward_message))
        
        # Другой polling интервал
        updater.start_polling(
            poll_interval=3.0,
            timeout=20,
            drop_pending_updates=True,
            allowed_updates=['message']
        )
        
        logger.info("✅ Бот поддержки запущен")
        
        while True:
            time.sleep(15)
            logger.debug("Бот поддержки: активен")
            
    except telegram.error.Conflict as e:
        logger.error(f"⚠️ Конфликт бота поддержки: {e}")
        logger.info("🔄 Перезапуск через 45 секунд...")
        time.sleep(45)
        run_support_bot()
    except Exception as e:
        logger.error(f"❌ Ошибка бота поддержки: {e}")

# ================== ГЛАВНАЯ ФУНКЦИЯ ==================
def main():
    """Основная функция запуска"""
    logger.info("🚀 Запуск всех компонентов системы...")
    
    # Проверка обязательных переменных
    if not TELEGRAM_TOKEN:
        logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: TELEGRAM_TOKEN не установлен!")
        logger.info("💡 Установите в Render: TELEGRAM_TOKEN=ваш_токен")
        return
    
    # Запускаем ВСЕ в отдельных потоках
    threads = []
    
    # 1. Веб-сервер (ОБЯЗАТЕЛЬНО для Render)
    web_thread = threading.Thread(target=run_web_server, daemon=True, name="WebServer")
    web_thread.start()
    threads.append(web_thread)
    time.sleep(2)  # Даем веб-серверу запуститься первым
    
    # 2. Основной бот
    main_bot_thread = threading.Thread(target=run_main_bot, daemon=True, name="MainBot")
    main_bot_thread.start()
    threads.append(main_bot_thread)
    time.sleep(3)
    
    # 3. Бот поддержки (если есть токен)
    if SUPPORT_BOT_TOKEN:
        support_bot_thread = threading.Thread(target=run_support_bot, daemon=True, name="SupportBot")
        support_bot_thread.start()
        threads.append(support_bot_thread)
    
    logger.info("✅ Все компоненты запущены успешно!")
    logger.info(f"📊 Активных потоков: {threading.active_count()}")
    
    # Бесконечный цикл главного потока
    try:
        while True:
            time.sleep(60)
            # Периодический лог статуса
            logger.info(f"⏰ Система активна: {datetime.now().strftime('%H:%M:%S')}")
            logger.info(f"📊 Потоков: {threading.active_count()}")
            
    except KeyboardInterrupt:
        logger.info("\n🛑 Остановка системы...")
    except Exception as e:
        logger.error(f"❌ Непредвиденная ошибка: {e}")

# ================== ЗАПУСК ==================
if __name__ == "__main__":
    # Добавляем обработку JSON
    import json
    
    main()
