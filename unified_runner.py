"""
🚀 ЕДИНСТВЕННЫЙ БОТ ДЛЯ RENDER
Запускает: ТОЛЬКО ОСНОВНОЙ БОТ + Веб-сервер
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
SUPPORT_BOT_TOKEN = os.getenv("SUPPORT_BOT_TOKEN", "")  # Опционально

print("=" * 60)
print("🤖 CRYPTO SIGNALS BOT")
print("=" * 60)
print(f"Основной бот: {'✅' if TELEGRAM_TOKEN else '❌'}")
if SUPPORT_BOT_TOKEN:
    print(f"Бот поддержки: ✅ (будет запущен позже)")
else:
    print(f"Бот поддержки: ⚠️ Нет токена")
print("=" * 60)

# ================== ВЕБ-СЕРВЕР ==================
def run_web_server():
    """Запуск веб-сервера для Render"""
    try:
        from flask import Flask
        from waitress import serve
        
        app = Flask(__name__)
        
        @app.route('/')
        def home():
            return f"""
            <html>
                <head>
                    <title>Crypto Signals Bot</title>
                    <meta http-equiv="refresh" content="30">
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 40px; }}
                        .status {{ padding: 15px; margin: 10px 0; border-radius: 8px; }}
                        .ok {{ background: #d4edda; color: #155724; border: 2px solid #c3e6cb; }}
                        .warning {{ background: #fff3cd; color: #856404; border: 2px solid #ffeaa7; }}
                        .container {{ max-width: 800px; margin: 0 auto; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>🤖 Crypto Signals Bot</h1>
                        <p>Торговые сигналы в реальном времени</p>
                        
                        <div class="status ok">
                            <h3>✅ Система активна</h3>
                            <p><strong>Время:</strong> {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}</p>
                            <p><strong>Статус:</strong> Основной бот работает</p>
                            <p><strong>Telegram:</strong> @CryptoSignalsProBot</p>
                        </div>
                        
                        <div class="status {'ok' if SUPPORT_BOT_TOKEN else 'warning'}">
                            <h3>{'✅' if SUPPORT_BOT_TOKEN else '⚠️'} Бот поддержки</h3>
                            <p>{'Активен' if SUPPORT_BOT_TOKEN else 'Не настроен'}</p>
                            <p><strong>ID для поддержки:</strong> Отправьте /start в боте</p>
                        </div>
                        
                        <p><a href="/health">Проверка здоровья системы</a></p>
                    </div>
                </body>
            </html>
            """
        
        @app.route('/health')
        def health():
            return "OK", 200
        
        @app.route('/ping')
        def ping():
            return "pong", 200
        
        port = int(os.environ.get('PORT', 10000))
        logger.info(f"🌐 Веб-сервер запущен на порту {port}")
        
        # Запускаем в основном потоке (блокирующий)
        serve(app, host="0.0.0.0", port=port)
        
    except Exception as e:
        logger.error(f"❌ Веб-сервер: {e}")
        raise

# ================== ОСНОВНОЙ БОТ ==================
def run_main_bot():
    """Запуск ОСНОВНОГО бота торговых сигналов"""
    time.sleep(5)  # Ждем запуск веб-сервера
    
    if not TELEGRAM_TOKEN:
        logger.error("❌ Нет TELEGRAM_TOKEN!")
        return
    
    try:
        from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
        
        logger.info("🚀 Запуск основного бота...")
        
        # Создаем бота
        updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
        
        # КРИТИЧЕСКИ ВАЖНО: сбрасываем ВСЕ предыдущие обновления
        try:
            logger.info("🔄 Сброс offset...")
            updater.bot.get_updates(offset=-1)
            time.sleep(2)
        except Exception as e:
            logger.warning(f"Ошибка сброса offset: {e}")
        
        # Команды
        def start_command(update, context):
            user = update.effective_user
            update.message.reply_text(
                f"🚀 Привет, {user.first_name}!\n\n"
                "Я Crypto Signals Bot - ваш помощник в торговле криптовалютой.\n\n"
                "📊 Доступные команды:\n"
                "/signals - Получить торговые сигналы\n"
                "/subscription - Информация о подписке\n"
                "/support - Техническая поддержка"
            )
        
        def signals_command(update, context):
            update.message.reply_text(
                "📈 **Генерация сигналов...**\n\n"
                "Анализирую рынок...\n"
                "Пожалуйста, подождите 10-15 секунд.",
                parse_mode='Markdown'
            )
        
        def support_command(update, context):
            user_id = update.effective_user.id
            update.message.reply_text(
                f"🆘 **Техническая поддержка**\n\n"
                f"Ваш ID: `{user_id}`\n"
                "Для связи с поддержкой:\n"
                "1. Напишите @CryptoSignalsSupportBot\n"
                "2. Укажите ваш ID выше\n"
                "3. Опишите проблему\n\n"
                "⏰ Время ответа: до 24 часов",
                parse_mode='Markdown'
            )
        
        # Регистрация обработчиков
        dispatcher = updater.dispatcher
        dispatcher.add_handler(CommandHandler("start", start_command))
        dispatcher.add_handler(CommandHandler("signals", signals_command))
        dispatcher.add_handler(CommandHandler("support", support_command))
        dispatcher.add_handler(CommandHandler("help", start_command))
        
        # Запускаем polling
        logger.info("✅ Бот готов к работе!")
        updater.start_polling(
            poll_interval=2.0,
            timeout=20,
            drop_pending_updates=True,
            allowed_updates=['message', 'callback_query']
        )
        
        logger.info("🤖 Бот начал слушать сообщения...")
        
        # Бесконечный цикл
        while True:
            time.sleep(10)
            
    except Exception as e:
        logger.error(f"❌ Ошибка бота: {e}")
        # Не перезапускаем - лучше упасть чем конфликтовать

# ================== ГЛАВНЫЙ ЗАПУСК ==================
def main():
    """Основная функция - запуск ВСЕГО в правильном порядке"""
    logger.info("=" * 60)
    logger.info("🚀 НАЧАЛО РАБОТЫ СИСТЕМЫ")
    logger.info("=" * 60)
    
    # Проверка токена
    if not TELEGRAM_TOKEN:
        logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: TELEGRAM_TOKEN не установлен!")
        logger.error("💡 Добавьте в Render Dashboard:")
        logger.error("   TELEGRAM_TOKEN = ваш_токен_от_BotFather")
        return
    
    # Запускаем в отдельных потоках
    threads = []
    
    # 1. Веб-сервер (главный поток)
    web_thread = threading.Thread(target=run_web_server, daemon=True, name="WebServer")
    web_thread.start()
    threads.append(web_thread)
    
    # Ждем запуска веб-сервера
    time.sleep(3)
    
    # 2. Основной бот
    bot_thread = threading.Thread(target=run_main_bot, daemon=True, name="MainBot")
    bot_thread.start()
    threads.append(bot_thread)
    
    logger.info("✅ Все компоненты запущены!")
    logger.info(f"🌐 Веб-интерфейс: https://crypto-bot-612m.onrender.com")
    logger.info(f"🤖 Бот Telegram: @CryptoSignalsProBot")
    logger.info("=" * 60)
    
    # Мониторинг
    try:
        counter = 0
        while True:
            time.sleep(60)
            counter += 1
            logger.info(f"⏱ Система активна {counter} мин: {datetime.now().strftime('%H:%M:%S')}")
            
    except KeyboardInterrupt:
        logger.info("\n🛑 Остановка по команде...")
    except Exception as e:
        logger.error(f"❌ Непредвиденная ошибка: {e}")

# ================== ЗАПУСК ==================
if __name__ == "__main__":
    """Точка входа - без лишних проверок"""
    print("=" * 60)
    print("🚀 ЗАПУСК CRYPTO SIGNALS BOT")
    print("=" * 60)
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Остановка по команде пользователя")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
