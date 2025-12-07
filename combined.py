import threading
import main
import support_bot

def run_main():
    try:
        print("🚀 Запуск основного бота...")
        main.main()   # вызываем функцию main() из main.py
    except Exception as e:
        print(f"❌ Ошибка основного бота: {e}")

def run_support():
    try:
        print("🚀 Запуск бота поддержки...")
        support_bot.main()   # вызываем функцию main() из support_bot.py
    except Exception as e:
        print(f"❌ Ошибка бота поддержки: {e}")

if __name__ == "__main__":
    # Запускаем оба бота параллельно в потоках
    threading.Thread(target=run_main).start()
    threading.Thread(target=run_support).start()

    print("✅ Оба бота запущены в одном процессе")
