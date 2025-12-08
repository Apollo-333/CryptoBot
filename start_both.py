import os
import time
import threading
import subprocess
import sys

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
    # Используем waitress для production
    from waitress import serve
    serve(app, host="0.0.0.0", port=port)

# Запускаем Flask в отдельном процессе
Thread(target=run_flask, daemon=True).start()
time.sleep(2)

def run_bot(bot_name, module_name):
    """Запуск бота в отдельном процессе"""
    print(f"🤖 Запускаю {bot_name}...")
    
    # Запускаем каждый бот в отдельном процессе
    result = subprocess.run(
        [sys.executable, "-c", f"from {module_name} import main; main()"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"❌ {bot_name} завершился с ошибкой:")
        print(result.stderr)
    else:
        print(f"✅ {bot_name} завершился")

def main():
    """Основная функция запуска"""
    # Запускаем оба бота в отдельных потоках
    threads = []
    
    # Основной бот
    t1 = threading.Thread(
        target=run_bot,
        args=("Основной бот", "main"),
        daemon=True
    )
    
    # Бот поддержки (только если есть токен)
    if os.environ.get("SUPPORT_BOT_TOKEN"):
        t2 = threading.Thread(
            target=run_bot,
            args=("Бот поддержки", "support_bot"),
            daemon=True
        )
        threads.append(t2)
    
    threads.append(t1)
    
    # Запускаем все потоки
    for t in threads:
        t.start()
    
    print("=" * 60)
    print("✅ Система запущена!")
    print(f"🤖 Основной бот: активен")
    if os.environ.get("SUPPORT_BOT_TOKEN"):
        print(f"🆘 Бот поддержки: активен")
    print("🌐 Статус: https://cryptobot-sebz.onrender.com")
    print("=" * 60)
    
    # Держим основной поток живым
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Остановка...")

if __name__ == "__main__":
    main()
