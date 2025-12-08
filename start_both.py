import os
import time
import threading

os.environ['PYTHONUNBUFFERED'] = '1'

print("=" * 60)
print("🚀 ЗАПУСК ДВУХ БОТОВ НА RENDER")
print("=" * 60)

# Keep-alive сервер для Render
from flask import Flask
from threading import Thread

app = Flask('')
@app.route('/')
def home():
    return "✅ Crypto Bots are ALIVE"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    print(f"🌐 Keep-alive сервер на порту {port}")
    app.run(host='0.0.0.0', port=port)

# Запускаем Flask
Thread(target=run_flask, daemon=True).start()
time.sleep(2)

def check_token(token_name):
    """Проверяет что токен установлен"""
    token = os.environ.get(token_name)
    if not token:
        print(f"❌ {token_name} не найден в переменных окружения!")
        return False
    # Проверяем что токен не пустой и имеет правильный формат
    if len(token) < 10:
        print(f"❌ {token_name} слишком короткий!")
        return False
    return True

def run_main_bot():
    """Запуск основного бота"""
    print("🤖 Проверяю основной бот...")
    
    # Проверяем токен
    if not check_token('TELEGRAM_TOKEN'):
        print("⚠️  Основной бот не будет запущен")
        return
    
    print("✅ Токен найден, запускаю основной бот...")
    time.sleep(5)  # Даем время Flask запуститься
    
    try:
        from main import main as main_bot_main
        main_bot_main()
    except Exception as e:
        print(f"❌ Ошибка основного бота: {e}")
        import traceback
        traceback.print_exc()

def run_support_bot():
    """Запуск бота поддержки"""
    print("🆘 Проверяю бот поддержки...")
    
    # Проверяем токен
    if not check_token('SUPPORT_BOT_TOKEN'):
        print("⚠️  Бот поддержки не будет запущен")
        return
    
    print("✅ Токен найден, запускаю бот поддержки...")
    time.sleep(10)  # Ждем дольше перед запуском второго бота
    
    try:
        from support_bot import main as support_bot_main
        support_bot_main()
    except Exception as e:
        print(f"❌ Ошибка бота поддержки: {e}")
        import traceback
        traceback.print_exc()

# Запускаем проверку токенов
print("🔐 Проверка токенов...")
main_token_ok = check_token('TELEGRAM_TOKEN')
support_token_ok = check_token('SUPPORT_BOT_TOKEN')

if not main_token_ok and not support_token_ok:
    print("❌ Ни один токен не найден! Проверь переменные окружения на Render.")
    print("💡 Добавь TELEGRAM_TOKEN и SUPPORT_BOT_TOKEN в настройках сервиса")
    exit(1)

# Запускаем ботов в отдельных потоках
print("🔄 Запускаю ботов...")
t1 = threading.Thread(target=run_main_bot, daemon=True)
t2 = threading.Thread(target=run_support_bot, daemon=True)

t1.start()
t2.start()

print("=" * 60)
print("✅ Система запущена!")
if main_token_ok:
    print("🤖 Основной бот: @CryptoSignalsPro777_bot")
if support_token_ok:
    print("🆘 Бот поддержки: @CryptoSignalsSupportBot")
print("🌐 Статус: https://cryptobot-sebz.onrender.com")
print("=" * 60)

# Держим основной поток живым
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n🛑 Остановка...")
