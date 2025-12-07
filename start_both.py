import os
import threading
import time

os.environ['PYTHONUNBUFFERED'] = '1'

def run_main_bot():
    """Запуск основного бота (версия 13.15)"""
    try:
        print("=" * 60)
        print("🚀 ЗАПУСК CRYPTO SIGNALS PRO BOT")
        print("=" * 60)
        
        # Импортируем здесь чтобы избежать конфликтов
        from main import BOT_TOKEN
        
        from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
        from main import (
            start_command, signals_command, subscription_command, 
            pumpdump_command, support_command, admin_panel,
            activate_premium_command, deactivate_premium_command,
            check_premium_command, list_premium_command,
            button_handler, handle_message, get_main_keyboard
        )
        
        print("📊 Реальные данные с CoinGecko API")
        print(f"💰 Анализ монет")
        print(f"🤖 Бот поддержки: @CryptoSignalsSupportBot")
        print(f"💎 Цена подписки: 9 USDT")
        print("=" * 60)
        
        updater = Updater(token=BOT_TOKEN, use_context=True)
        dispatcher = updater.dispatcher
        
        # Команды пользователя
        dispatcher.add_handler(CommandHandler("start", start_command))
        dispatcher.add_handler(CommandHandler("signals", signals_command))
        dispatcher.add_handler(CommandHandler("subscription", subscription_command))
        dispatcher.add_handler(CommandHandler("pumpdump", pumpdump_command))
        dispatcher.add_handler(CommandHandler("support", support_command))
        
        # Админ-команды
        dispatcher.add_handler(CommandHandler("activate_premium", activate_premium_command))
        dispatcher.add_handler(CommandHandler("deactivate_premium", deactivate_premium_command))
        dispatcher.add_handler(CommandHandler("check_premium", check_premium_command))
        dispatcher.add_handler(CommandHandler("list_premium", list_premium_command))
        
        # Callback и сообщения
        dispatcher.add_handler(CallbackQueryHandler(button_handler))
        dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
        
        print("✅ Основной бот готов к работе!")
        print("💎 Система премиум подписок активна")
        print("=" * 60)
        
        updater.start_polling()
        updater.idle()
        
    except Exception as e:
        print(f"❌ Ошибка основного бота: {e}")
        import traceback
        traceback.print_exc()

def run_support_bot():
    """Запуск бота поддержки (версия 13.15)"""
    try:
        print("🤖 ЗАПУСК БОТА ПОДДЕРЖКИ")
        print("=" * 60)
        
        # Импортируем здесь чтобы избежать конфликтов
        from support_bot import SUPPORT_BOT_TOKEN, ADMIN_ID
        
        from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
        from support_bot import (
            start_command, forward_to_admin, handle_photo,
            admin_reply_command, handle_payment_info, handle_faq,
            handle_message
        )
        
        if not SUPPORT_BOT_TOKEN:
            print("⚠️ SUPPORT_BOT_TOKEN не найден")
            return
        
        updater = Updater(SUPPORT_BOT_TOKEN, use_context=True)
        dp = updater.dispatcher
        
        dp.add_handler(CommandHandler("start", start_command))
        dp.add_handler(CommandHandler("reply", admin_reply_command))
        dp.add_handler(CallbackQueryHandler(handle_payment_info, pattern="payment_info"))
        dp.add_handler(CallbackQueryHandler(handle_faq, pattern="faq"))
        dp.add_handler(CallbackQueryHandler(handle_faq, pattern="tech_issues"))
        dp.add_handler(MessageHandler(Filters.photo, handle_photo))
        dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
        
        print("✅ Бот поддержки запущен...")
        print(f"👨‍💻 ADMIN_ID: {ADMIN_ID}")
        print("👨‍💻 Для ответа: /reply <user_id> <сообщение>")
        print("=" * 60)
        
        updater.start_polling()
        updater.idle()
        
    except Exception as e:
        print(f"❌ Ошибка бота поддержки: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 ЗАПУСК ДВУХ БОТОВ В ОДНОМ ПРОЦЕССЕ (v13.15)")
    print("=" * 60)
    
    # Запускаем ботов в отдельных потоках с задержкой
    thread1 = threading.Thread(target=run_main_bot, daemon=True)
    thread2 = threading.Thread(target=run_support_bot, daemon=True)
    
    thread1.start()
    time.sleep(5)  # Ждем 5 секунд перед запуском второго бота
    thread2.start()
    
    print("✅ Оба бота запущены в разных потоках")
    print("📊 Основной бот: @CryptoSignalsPro777_bot")
    print("🆘 Бот поддержки: @CryptoSignalsSupportBot")
    print("=" * 60)
    
    # Держим основной поток живым
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Остановка ботов...")
