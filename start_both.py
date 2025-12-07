import os
import threading
import time
from keep_alive import keep_alive
keep_alive()

os.environ['PYTHONUNBUFFERED'] = '1'

def run_main_bot():
    """Запуск основного бота без idle()"""
    try:
        print("=" * 60)
        print("🚀 ЗАПУСК CRYPTO SIGNALS PRO BOT")
        print("=" * 60)
        
        # Импортируем здесь чтобы избежать конфликтов
        from main import BOT_TOKEN, main
        
        print("📊 Реальные данные с CoinGecko API")
        print(f"💰 Анализ монет")
        print(f"🤖 Бот поддержки: @CryptoSignalsSupportBot")
        print(f"💎 Цена подписки: 9 USDT")
        print("=" * 60)
        
        # Запускаем main() из main.py
        main()
        
    except Exception as e:
        print(f"❌ Ошибка основного бота: {e}")
        import traceback
        traceback.print_exc()

def run_support_bot():
    """Запуск бота поддержки без idle()"""
    try:
        print("🤖 ЗАПУСК БОТА ПОДДЕРЖКИ")
        print("=" * 60)
        
        # Импортируем здесь чтобы избежать конфликтов
        from support_bot import main
        
        print("✅ Бот поддержки запущен...")
        print("👨‍💻 Для ответа: /reply <user_id> <сообщение>")
        print("=" * 60)
        
        # Запускаем main() из support_bot.py
        main()
        
    except Exception as e:
        print(f"❌ Ошибка бота поддержки: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 ЗАПУСК ДВУХ БОТОВ В ОДНОМ ПРОЦЕССЕ")
    print("=" * 60)
    
    # Запускаем ботов в отдельных потоках с задержкой
    thread1 = threading.Thread(target=run_main_bot, daemon=True)
    thread2 = threading.Thread(target=run_support_bot, daemon=True)
    
    thread1.start()
    time.sleep(10)  # Ждем 10 секунд перед запуском второго бота
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
