import threading
from main import updater as main_updater
from support_bot import updater as support_updater

def run_main():
    try:
        print("🚀 Запуск основного бота...")
        main_updater.start_polling()
        main_updater.idle()
    except Exception as e:
        print(f"❌ Ошибка основного бота: {e}")

def run_support():
    try:
        print("🚀 Запуск бота поддержки...")
        support_updater.start_polling()
        support_updater.idle()
    except Exception as e:
        print(f"❌ Ошибка бота поддержки: {e}")

if __name__ == "__main__":
    threading.Thread(target=run_main).start()
    threading.Thread(target=run_support).start()
    print("✅ Оба бота запущены в одном процессе")
