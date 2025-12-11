"""
🚀 CRYPTO SIGNALS BOT - ИСПРАВЛЕННАЯ ВЕРСИЯ
Без ошибок Markdown
"""
import os
import sys
import time
import json
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, Any

# ================== НАСТРОЙКА ==================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID", "638584949")

print("=" * 60)
print("🤖 CRYPTO SIGNALS PRO BOT")
print("=" * 60)

# ================== БАЗА ДАННЫХ ==================
DB_FILE = "users_db.json"

def load_db():
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_db(db):
    with open(DB_FILE, 'w') as f:
        json.dump(db, f, indent=2)

def get_user(user_id):
    db = load_db()
    key = str(user_id)
    if key not in db:
        db[key] = {
            "id": user_id,
            "is_premium": False,
            "premium_expiry": None,
            "signals_today": 0,
            "last_reset_date": datetime.now().date().isoformat(),
            "join_date": datetime.now().isoformat(),
            "total_signals": 0
        }
        save_db(db)
    return db[key]

def update_user(user_id, updates):
    db = load_db()
    key = str(user_id)
    if key not in db:
        get_user(user_id)
    db[key].update(updates)
    save_db(db)

def is_admin(user_id):
    return str(user_id) == ADMIN_ID

# ================== КОМАНДЫ ==================
async def start_command(update, context):
    user = update.effective_user
    user_id = user.id
    user_data = get_user(user_id)
    
    status = "✅ ПРЕМИУМ" if user_data.get('is_premium') else "🎯 БЕСПЛАТНЫЙ"
    
    text = f"""🚀 Добро пожаловать в Crypto Signals Pro, {user.first_name}!

👤 Ваш ID: {user_id}
💎 Статус: {status}

📊 Доступные команды:
• /signals - Получить торговые сигналы
• /premium - Информация о подписке
• /mystatus - Мой статус и статистика
• /support - Техническая поддержка
• /help - Помощь по командам"""
    
    if is_admin(user_id):
        text += "\n\n👑 Админ-команды:\n• /activate <user_id> [дней]\n• /users"
    
    text += "\n\n💡 Начните с команды /signals!"
    
    await update.message.reply_text(text)

async def signals_command(update, context):
    user = update.effective_user
    user_id = user.id
    user_data = get_user(user_id)
    
    today = datetime.now().date().isoformat()
    if user_data.get('last_reset_date') != today:
        update_user(user_id, {"signals_today": 0, "last_reset_date": today})
        user_data['signals_today'] = 0
    
    # Проверка лимита
    if not user_data.get('is_premium') and user_data.get('signals_today', 0) >= 1:
        await update.message.reply_text(
            f"❌ Достигнут дневной лимит!\n\n"
            f"Вы использовали {user_data.get('signals_today', 0)}/1 бесплатных сигналов сегодня.\n\n"
            f"💎 Премиум подписка включает неограниченные сигналы.\n"
            f"Оформите подписку: /premium"
        )
        return
    
    # Генерация сигнала
    if user_data.get('is_premium'):
        price = 42000 + int(time.time() % 1000)
        target = 43000 + int(time.time() % 1500)
        signal = f"""💎 ПРЕМИУМ СИГНАЛ 💎

Пара: BTC/USDT
Действие: {'BUY' if time.time() % 2 == 0 else 'SELL'}
Цена: ${price:,}
Цель: ${target:,}
Уверенность: {75 + int(time.time() % 20)}%

Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}"""
    else:
        update_user(user_id, {
            "signals_today": user_data.get('signals_today', 0) + 1,
            "total_signals": user_data.get('total_signals', 0) + 1
        })
        signal = f"""🎯 БЕСПЛАТНЫЙ СИГНАЛ 🎯

Пара: BTC/USDT
Ситуация: Анализ рынка...
Рекомендация: Ожидание подтверждения тренда

Использовано сигналов: {user_data.get('signals_today', 0) + 1}/1 сегодня

💎 Для детальных сигналов: /premium"""
    
    await update.message.reply_text(signal)

async def premium_command(update, context):
    user = update.effective_user
    user_id = user.id
    user_data = get_user(user_id)
    
    if user_data.get('is_premium'):
        expiry = user_data.get('premium_expiry')
        if expiry:
            try:
                expiry_str = datetime.fromisoformat(expiry).strftime('%d.%m.%Y')
            except:
                expiry_str = "Не указано"
        else:
            expiry_str = "Бессрочно"
        
        text = f"""💎 ВАША ПРЕМИУМ ПОДПИСКА АКТИВНА 💎

Статус: Активен
Истекает: {expiry_str}
ID пользователя: {user_id}

🎯 Наслаждайтесь полным доступом!"""
    else:
        text = f"""💎 ПОДПИСКА НА ПРЕМИУМ

1 месяц: 9 USDT
3 месяца: 25 USDT (экономия 15%)

Ваш ID для оплаты: {user_id}

💳 Реквизиты:
USDT (TRC20): TF33keB2N3P226zxFfESVCvXCFQMjnMXQh

📋 После оплаты отправьте скриншот администратору."""
    
    await update.message.reply_text(text)

async def activate_command(update, context):
    user = update.effective_user
    user_id = user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Доступ запрещен!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Использование: /activate <user_id> [дней=30]")
        return
    
    try:
        target_id = int(context.args[0])
        days = int(context.args[1]) if len(context.args) > 1 else 30
        
        expiry_date = (datetime.now() + timedelta(days=days)).isoformat()
        
        update_user(target_id, {
            "is_premium": True,
            "premium_expiry": expiry_date
        })
        
        expiry_str = datetime.fromisoformat(expiry_date).strftime('%d.%m.%Y')
        
        await update.message.reply_text(
            f"✅ Премиум активирован!\n\n"
            f"Пользователь: {target_id}\n"
            f"Срок: {days} дней\n"
            f"Истекает: {expiry_str}"
        )
        
    except ValueError:
        await update.message.reply_text("❌ Неверный формат ID")

# ================== ВЕБ-СЕРВЕР ==================
def run_web():
    from flask import Flask
    from waitress import serve
    
    app = Flask(__name__)
    
    @app.route('/')
    def home():
        db = load_db()
        premium = sum(1 for u in db.values() if u.get('is_premium'))
        return f"""
        <h1>🤖 Crypto Signals Pro Bot</h1>
        <p>Статус: ✅ Активен</p>
        <p>Время: {datetime.now().strftime('%H:%M:%S')}</p>
        <p>Пользователей: {len(db)}</p>
        <p>Премиум: {premium}</p>
        """
    
    @app.route('/health')
    def health():
        return "OK", 200
    
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🌐 Веб-сервер на порту {port}")
    serve(app, host="0.0.0.0", port=port)

# ================== ЗАПУСК БОТА ==================
def run_bot():
    time.sleep(3)
    
    if not TELEGRAM_TOKEN:
        logger.error("❌ Нет токена!")
        return
    
    try:
        from telegram import Update
        from telegram.ext import Application, CommandHandler, ContextTypes
        
        logger.info("🤖 Запуск бота...")
        
        app = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Команды
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("signals", signals_command))
        app.add_handler(CommandHandler("premium", premium_command))
        app.add_handler(CommandHandler("activate", activate_command))
        app.add_handler(CommandHandler("mystatus", start_command))  # временно
        app.add_handler(CommandHandler("support", start_command))   # временно
        app.add_handler(CommandHandler("help", start_command))      # временно
        app.add_handler(CommandHandler("users", start_command))     # временно
        
        logger.info("✅ Бот готов...")
        app.run_polling(
            poll_interval=2.0,
            timeout=20,
            drop_pending_updates=True
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")

# ================== ГЛАВНЫЙ ЗАПУСК ==================
def main():
    logger.info("🚀 Запуск системы...")
    
    if not TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN не установлен!")
        return
    
    # Веб в потоке
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    
    time.sleep(2)
    
    # Бот в основном потоке
    run_bot()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Остановка...")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)
