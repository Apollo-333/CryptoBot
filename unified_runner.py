"""
🚀 ОКОНЧАТЕЛЬНАЯ ВЕРСИЯ БОТА ДЛЯ RENDER
С админ-командами и премиум системой
"""
import os
import sys
import time
import threading
import logging
from datetime import datetime

# ================== НАСТРОЙКА ==================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID", "0")

print("=" * 60)
print("🤖 CRYPTO SIGNALS PRO BOT")
print(f"Токен: {'✅' if TELEGRAM_TOKEN else '❌'}")
print(f"Админ ID: {ADMIN_ID}")
print("=" * 60)

# ================== ИМИТАЦИЯ БАЗЫ ДАННЫХ ==================
# Простая база в памяти для демо
users_db = {}

def is_admin(user_id):
    """Проверка, является ли пользователь админом"""
    return str(user_id) == ADMIN_ID

def get_user(user_id):
    """Получить данные пользователя"""
    if user_id not in users_db:
        users_db[user_id] = {
            'is_premium': False,
            'premium_expiry': None,
            'signals_today': 0
        }
    return users_db[user_id]

def activate_premium(user_id, days=30):
    """Активировать премиум для пользователя"""
    users_db[user_id] = {
        'is_premium': True,
        'premium_expiry': time.time() + (days * 86400),
        'signals_today': 0
    }
    return True

# ================== ВЕБ-СЕРВЕР ==================
def run_web_server():
    """Веб-сервер для Render"""
    from flask import Flask
    from waitress import serve
    
    app = Flask(__name__)
    
    @app.route('/')
    def home():
        return f"""
        <html>
            <head>
                <title>Crypto Signals Pro</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; }}
                    .status {{ padding: 20px; margin: 20px 0; border-radius: 10px; }}
                    .ok {{ background: #d4edda; color: #155724; }}
                    .info {{ background: #d1ecf1; color: #0c5460; }}
                </style>
            </head>
            <body>
                <h1>🤖 Crypto Signals Pro</h1>
                <div class="status ok">
                    <h3>✅ Система активна</h3>
                    <p><strong>Время сервера:</strong> {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}</p>
                    <p><strong>Пользователей:</strong> {len(users_db)}</p>
                    <p><strong>Премиум пользователей:</strong> {sum(1 for u in users_db.values() if u['is_premium'])}</p>
                </div>
                <div class="status info">
                    <h3>📊 Статистика</h3>
                    <p>Бот работает стабильно</p>
                    <p>Telegram: @CryptoSignalsProBot</p>
                    <p>Админ ID: {ADMIN_ID}</p>
                </div>
            </body>
        </html>
        """
    
    @app.route('/health')
    def health():
        return "OK", 200
    
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🌐 Веб-сервер на порту {port}")
    serve(app, host="0.0.0.0", port=port)

# ================== ОСНОВНОЙ БОТ ==================
def run_main_bot():
    """Запуск основного бота со всеми функциями"""
    time.sleep(5)
    
    if not TELEGRAM_TOKEN:
        logger.error("❌ Нет TELEGRAM_TOKEN!")
        return
    
    try:
        from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
        
        logger.info("🚀 Запуск основного бота...")
        
        updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
        dispatcher = updater.dispatcher
        
        # ================== КОМАНДЫ ==================
        def start(update, context):
            user = update.effective_user
            user_id = user.id
            
            # Добавляем пользователя в базу
            get_user(user_id)
            
            welcome_text = f"""
🚀 **Добро пожаловать, {user.first_name}!** 🚀

Ваш ID: `{user_id}`
Статус: {'💎 ПРЕМИУМ' if users_db[user_id]['is_premium'] else '🎯 БЕСПЛАТНЫЙ'}

📊 **Доступные команды:**
/signals - Получить торговые сигналы
/subscription - Информация о подписке
/mystatus - Мой статус

👑 **Админ-команды** (если вы админ):
/activate_premium <user_id> - Активировать премиум
/list_users - Список пользователей
            """
            
            keyboard = [
                [InlineKeyboardButton("🎯 Сигналы", callback_data="signals")],
                [InlineKeyboardButton("💎 Подписка", callback_data="subscription")],
                [InlineKeyboardButton("📊 Мой статус", callback_data="mystatus")]
            ]
            
            if is_admin(user_id):
                keyboard.append([InlineKeyboardButton("👑 Админ-панель", callback_data="admin")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            update.message.reply_text(
                welcome_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
        
        def signals_command(update, context):
            user_id = update.effective_user.id
            user_data = get_user(user_id)
            
            if user_data['is_premium']:
                signal_text = """
💎 **ПРЕМИУМ СИГНАЛ** 💎

🏷 Пара: BTC/USDT
⚡ Действие: BUY
💰 Цена: $42,150
🎯 Цель: $43,500
🛑 Стоп-лосс: $41,200
📈 Плечо: 3x
✅ Уверенность: 85%

⏰ Время: сейчас
💡 Анализ: Сильный бычий тренд
                """
            else:
                user_data['signals_today'] += 1
                signal_text = f"""
🎯 **БЕСПЛАТНЫЙ СИГНАЛ** 🎯

🏷 Пара: BTC/USDT
💰 Цена: Анализируем рынок...
📊 Тренд: Смешанный

💡 **Вы использовали {user_data['signals_today']}/1 бесплатных сигналов сегодня**

💎 **Премиум включает:**
• Неограниченные сигналы
• Точные точки входа/выхода
• Рекомендации по плечу
                """
            
            update.message.reply_text(signal_text, parse_mode=ParseMode.MARKDOWN)
        
        def subscription_command(update, context):
            user_id = update.effective_user.id
            user_data = get_user(user_id)
            
            if user_data['is_premium']:
                expiry = datetime.fromtimestamp(user_data['premium_expiry']).strftime('%d.%m.%Y') if user_data['premium_expiry'] else "Бессрочно"
                text = f"""
💎 **ВАША ПРЕМИУМ ПОДПИСКА АКТИВНА**

✅ Статус: Активен
📅 Истекает: {expiry}

📊 Премиум возможности:
• Неограниченные сигналы
• Приоритетная поддержка
• Все функции разблокированы
                """
            else:
                text = f"""
💎 **ПРЕМИУМ ПОДПИСКА**

💰 1 месяц: 9 USDT
📅 3 месяца: 25 USDT (экономия 15%)

💳 **Оплата:**
USDT (TRC20): `TF33keB2N3P226zxFfESVCvXCFQMjnMXQh`

📋 **После оплаты:**
1. Отправьте скриншот
2. Ваш ID: `{user_id}`
3. Ожидайте активации (до 15 минут)

⚡ **Что получите:**
• Неограниченные сигналы
• Pump/Dump мониторинг
• Точные точки входа/выхода
• Приоритетную поддержку
                """
            
            update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        
        # ================== АДМИН-КОМАНДЫ ==================
        def activate_premium_cmd(update, context):
            """Активация премиума (админ)"""
            user_id = update.effective_user.id
            
            if not is_admin(user_id):
                update.message.reply_text("❌ Доступ запрещен")
                return
            
            if not context.args:
                update.message.reply_text("❌ Использование: /activate_premium <user_id> [дней=30]")
                return
            
            try:
                target_user_id = int(context.args[0])
                days = int(context.args[1]) if len(context.args) > 1 else 30
                
                activate_premium(target_user_id, days)
                
                update.message.reply_text(
                    f"✅ Премиум активирован для пользователя {target_user_id} на {days} дней\n\n"
                    f"Теперь ему доступны все премиум функции!"
                )
                
                # Отправляем уведомление пользователю
                try:
                    context.bot.send_message(
                        chat_id=target_user_id,
                        text=f"🎉 **ВАША ПРЕМИУМ ПОДПИСКА АКТИВИРОВАНА!**\n\n"
                             f"Спасибо за покупку! Теперь вам доступны все премиум функции на {days} дней.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass
                
            except ValueError:
                update.message.reply_text("❌ Неверный формат")
        
        def list_users_cmd(update, context):
            """Список пользователей (админ)"""
            user_id = update.effective_user.id
            
            if not is_admin(user_id):
                update.message.reply_text("❌ Доступ запрещен")
                return
            
            if not users_db:
                update.message.reply_text("📊 База пользователей пуста")
                return
            
            text = "📊 **СПИСОК ПОЛЬЗОВАТЕЛЕЙ:**\n\n"
            for uid, data in users_db.items():
                status = "💎 ПРЕМИУМ" if data['is_premium'] else "🎯 БЕСПЛАТНЫЙ"
                text += f"ID: `{uid}` - {status}\n"
            
            text += f"\n📈 Всего: {len(users_db)} пользователей"
            text += f"\n💎 Премиум: {sum(1 for u in users_db.values() if u['is_premium'])}"
            
            update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        
        def my_status(update, context):
            """Мой статус"""
            user_id = update.effective_user.id
            user_data = get_user(user_id)
            
            status_text = f"""
📊 **ВАШ СТАТУС**

👤 ID: `{user_id}`
💎 Статус: {'✅ ПРЕМИУМ' if user_data['is_premium'] else '🎯 БЕСПЛАТНЫЙ'}
📈 Сигналов сегодня: {user_data['signals_today']}

{'📅 Подписка истекает: ' + datetime.fromtimestamp(user_data['premium_expiry']).strftime('%d.%m.%Y') if user_data['is_premium'] and user_data['premium_expiry'] else ''}
            """
            
            update.message.reply_text(status_text.strip(), parse_mode=ParseMode.MARKDOWN)
        
        # ================== РЕГИСТРАЦИЯ КОМАНД ==================
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("signals", signals_command))
        dispatcher.add_handler(CommandHandler("subscription", subscription_command))
        dispatcher.add_handler(CommandHandler("mystatus", my_status))
        
        # Админ-команды
        dispatcher.add_handler(CommandHandler("activate_premium", activate_premium_cmd))
        dispatcher.add_handler(CommandHandler("list_users", list_users_cmd))
        
        # Кнопки
        def button_handler(update, context):
            query = update.callback_query
            query.answer()
            
            user_id = query.from_user.id
            
            if query.data == "signals":
                signals_command(update, context)
            elif query.data == "subscription":
                subscription_command(update, context)
            elif query.data == "mystatus":
                my_status(update, context)
            elif query.data == "admin" and is_admin(user_id):
                query.message.reply_text(
                    "👑 **АДМИН-ПАНЕЛЬ**\n\n"
                    "Доступные команды:\n"
                    "• /activate_premium <user_id> [дней]\n"
                    "• /list_users\n\n"
                    "Для активации премиума:\n"
                    "`/activate_premium 123456789 30`",
                    parse_mode=ParseMode.MARKDOWN
                )
        
        dispatcher.add_handler(CallbackQueryHandler(button_handler))
        
        # ================== ЗАПУСК ==================
        logger.info("✅ Бот инициализирован")
        
        # Запускаем polling
        updater.start_polling(
            poll_interval=2.0,
            timeout=20,
            drop_pending_updates=True
        )
        
        logger.info("🤖 Бот слушает сообщения...")
        
        while True:
            time.sleep(10)
            
    except Exception as e:
        logger.error(f"❌ Ошибка бота: {e}")
        import traceback
        traceback.print_exc()

# ================== ГЛАВНЫЙ ЗАПУСК ==================
def main():
    """Основная функция"""
    logger.info("🚀 Начало работы системы...")
    
    if not TELEGRAM_TOKEN:
        logger.error("❌ Нет TELEGRAM_TOKEN!")
        return
    
    # Запускаем веб-сервер в отдельном потоке
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    
    time.sleep(2)
    
    # Запускаем бота в основном потоке
    run_main_bot()

# ================== ТОЧКА ВХОДА ==================
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Остановка...")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
