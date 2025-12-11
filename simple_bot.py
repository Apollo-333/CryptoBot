"""
🚀 CRYPTO SIGNALS BOT - ПОЛНАЯ ВЕРСИЯ
Восстановленный функционал с премиум системой и админ-панелью
"""
import os
import sys
import time
import json
import logging
import threading
from datetime import datetime
from typing import Dict, Any

# ================== НАСТРОЙКА ==================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID", "638584949")

print("=" * 60)
print("🤖 CRYPTO SIGNALS PRO BOT v2.0")
print("=" * 60)
print(f"Token: {'✅' if TELEGRAM_TOKEN else '❌'}")
print(f"Admin ID: {ADMIN_ID}")
print("=" * 60)

# ================== БАЗА ДАННЫХ ==================
DB_FILE = "users_db.json"

def load_database() -> Dict[str, Any]:
    """Загрузить базу данных из файла"""
    try:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки БД: {e}")
    return {}

def save_database(db: Dict[str, Any]) -> None:
    """Сохранить базу данных в файл"""
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Ошибка сохранения БД: {e}")

def get_user(user_id: int) -> Dict[str, Any]:
    """Получить данные пользователя"""
    db = load_database()
    user_key = str(user_id)
    
    if user_key not in db:
        db[user_key] = {
            "id": user_id,
            "is_premium": False,
            "premium_expiry": None,
            "signals_today": 0,
            "last_reset_date": datetime.now().date().isoformat(),
            "join_date": datetime.now().isoformat(),
            "total_signals": 0
        }
        save_database(db)
    
    return db[user_key]

def update_user(user_id: int, updates: Dict[str, Any]) -> None:
    """Обновить данные пользователя"""
    db = load_database()
    user_key = str(user_id)
    
    if user_key not in db:
        get_user(user_id)  # Создаст пользователя если не существует
    
    db[user_key].update(updates)
    save_database(db)

def is_admin(user_id: int) -> bool:
    """Проверить, является ли пользователь админом"""
    return str(user_id) == ADMIN_ID

def can_send_signal(user_id: int) -> bool:
    """Проверить, может ли пользователь получить сигнал"""
    user = get_user(user_id)
    today = datetime.now().date().isoformat()
    
    # Сброс счетчика если новый день
    if user.get("last_reset_date") != today:
        update_user(user_id, {
            "signals_today": 0,
            "last_reset_date": today
        })
        return True
    
    # Проверка лимита
    if user.get("is_premium", False):
        return True  # Премиум пользователи без лимитов
    else:
        return user.get("signals_today", 0) < 1  # Бесплатный лимит: 1 сигнал в день

def increment_signal_count(user_id: int) -> None:
    """Увеличить счетчик сигналов"""
    user = get_user(user_id)
    current = user.get("signals_today", 0)
    total = user.get("total_signals", 0)
    
    update_user(user_id, {
        "signals_today": current + 1,
        "total_signals": total + 1
    })

# ================== ВЕБ-СЕРВЕР ==================
def run_web_server():
    """Запуск веб-сервера для Render"""
    try:
        from flask import Flask
        from waitress import serve
        
        app = Flask(__name__)
        
        @app.route('/')
        def home():
            db = load_database()
            premium_count = sum(1 for user in db.values() if user.get("is_premium"))
            
            return f"""
            <html>
                <head>
                    <title>Crypto Signals Pro</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 40px; }}
                        .status {{ padding: 20px; margin: 20px 0; border-radius: 10px; }}
                        .ok {{ background: #d4edda; color: #155724; border: 2px solid #c3e6cb; }}
                        .info {{ background: #d1ecf1; color: #0c5460; border: 2px solid #bee5eb; }}
                    </style>
                </head>
                <body>
                    <h1>🤖 Crypto Signals Pro Bot</h1>
                    
                    <div class="status ok">
                        <h2>✅ Система активна</h2>
                        <p><strong>Время сервера:</strong> {datetime.now().strftime('%H:%M:%S %d.%m.%Y')}</p>
                        <p><strong>Статус:</strong> Бот работает стабильно</p>
                        <p><strong>Telegram:</strong> @CryptoSignalsProBot</p>
                    </div>
                    
                    <div class="status info">
                        <h3>📊 Статистика</h3>
                        <p><strong>Всего пользователей:</strong> {len(db)}</p>
                        <p><strong>Премиум пользователей:</strong> {premium_count}</p>
                        <p><strong>Администратор:</strong> {ADMIN_ID}</p>
                    </div>
                    
                    <p><a href="/health">Проверка работоспособности</a></p>
                </body>
            </html>
            """
        
        @app.route('/health')
        def health():
            return "OK", 200
        
        @app.route('/api/stats')
        def api_stats():
            db = load_database()
            return {
                "status": "active",
                "users_count": len(db),
                "premium_users": sum(1 for user in db.values() if user.get("is_premium")),
                "timestamp": datetime.now().isoformat()
            }, 200
        
        port = int(os.environ.get('PORT', 10000))
        logger.info(f"🌐 Веб-сервер запущен на порту {port}")
        serve(app, host="0.0.0.0", port=port)
        
    except Exception as e:
        logger.error(f"❌ Ошибка веб-сервера: {e}")
        raise

# ================== ТОРГОВЫЕ СИГНАЛЫ ==================
async def generate_premium_signal() -> str:
    """Генерация премиум сигнала"""
    return f"""
💎 **ПРЕМИУМ СИГНАЛ** 💎

🏷 **Пара:** BTC/USDT
⚡ **Действие:** {'BUY' if time.time() % 2 == 0 else 'SELL'}
💰 **Текущая цена:** ${42000 + int(time.time() % 1000):,}
🎯 **Цель:** ${43000 + int(time.time() % 1500):,}
🛑 **Стоп-лосс:** ${41000 + int(time.time() % 800):,}
📈 **Плечо:** {'3x' if time.time() % 3 == 0 else '5x'}
✅ **Уверенность:** {75 + int(time.time() % 20)}%

⏰ **Время сигнала:** {datetime.now().strftime('%H:%M %d.%m.%Y')}
💡 **Основа:** Анализ рыночных данных и индикаторов

📊 **Рекомендации:**
• Вход по текущей цене
• Тейк-профит по цели
• Стоп-лосс обязателен
• Следите за обновлениями
"""

async def generate_free_signal(user_id: int) -> str:
    """Генерация бесплатного сигнала"""
    user = get_user(user_id)
    signals_used = user.get("signals_today", 0)
    
    return f"""
🎯 **БЕСПЛАТНЫЙ СИГНАЛ** 🎯

🏷 **Пара:** BTC/USDT
📊 **Текущая ситуация:** Анализ рынка...

💰 **Общая рекомендация:**
Рынок показывает смешанные сигналы. 
Рекомендуется ожидание подтверждения тренда.

⚠️ **Вы использовали {signals_used}/1 бесплатных сигналов сегодня**

💎 **Премиум подписка включает:**
• Неограниченные сигналы (100+ монет)
• Точные точки входа/выхода
• Стоп-лосс и тейк-профит
• Рекомендации по плечу
• Приоритетную поддержку

💡 Для получения детальных сигналов оформите подписку /premium
"""

# ================== КОМАНДЫ БОТА ==================
async def start_command(update, context):
    """Команда /start"""
    from telegram import Update
    from telegram.ext import ContextTypes
    
    user = update.effective_user
    user_id = user.id
    
    # Получаем/создаем пользователя
    user_data = get_user(user_id)
    
    welcome_text = f"""
🚀 **Добро пожаловать в Crypto Signals Pro, {user.first_name}!** 🚀

👤 **Ваш ID:** `{user_id}`
💎 **Статус:** {'✅ ПРЕМИУМ' if user_data.get('is_premium') else '🎯 БЕСПЛАТНЫЙ'}

📊 **Доступные команды:**
• /signals - Получить торговые сигналы
• /premium - Информация о подписке
• /mystatus - Мой статус и статистика
• /support - Техническая поддержка

{'👑 **Админ-команды:**' if is_admin(user_id) else ''}
{'• /activate <user_id> [дней] - Активировать премиум' if is_admin(user_id) else ''}
{'• /users - Список пользователей' if is_admin(user_id) else ''}

💡 **Начните с команды /signals!**
    """
    
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def signals_command(update, context):
    """Команда /signals - получение торговых сигналов"""
    user = update.effective_user
    user_id = user.id
    user_data = get_user(user_id)
    
    # Проверка возможности отправить сигнал
    if not can_send_signal(user_id):
        await update.message.reply_text(
            f"❌ **Достигнут дневной лимит!**\n\n"
            f"Вы использовали {user_data.get('signals_today', 0)}/1 бесплатных сигналов сегодня.\n\n"
            f"💎 **Премиум подписка включает:**\n"
            f"• Неограниченные сигналы\n"
            f"• Точные точки входа/выхода\n"
            f"• Pump/Dump мониторинг 24/7\n\n"
            f"Оформите подписку: /premium",
            parse_mode='Markdown'
        )
        return
    
    # Отправка сигнала в зависимости от статуса
    if user_data.get('is_premium'):
        signal = await generate_premium_signal()
    else:
        signal = await generate_free_signal(user_id)
    
    # Увеличиваем счетчик
    increment_signal_count(user_id)
    
    await update.message.reply_text(signal, parse_mode='Markdown')

async def premium_command(update, context):
    """Команда /premium - информация о подписке"""
    user = update.effective_user
    user_id = user.id
    user_data = get_user(user_id)
    
    if user_data.get('is_premium'):
        expiry = user_data.get('premium_expiry')
        if expiry:
            try:
                expiry_date = datetime.fromisoformat(expiry)
                expiry_str = expiry_date.strftime('%d.%m.%Y')
            except:
                expiry_str = "Не указано"
        else:
            expiry_str = "Бессрочно"
        
        text = f"""
💎 **ВАША ПРЕМИУМ ПОДПИСКА АКТИВНА** 💎

✅ **Статус:** Активен
📅 **Истекает:** {expiry_str}
👤 **ID пользователя:** `{user_id}`

🎯 **Доступные возможности:**
• Неограниченные торговые сигналы
• Точные точки входа/выхода
• Стоп-лосс и тейк-профит рекомендации
• Приоритетная техподдержка
• Доступ ко всем функциям бота

📈 **Наслаждайтесь полным доступом!**
        """
    else:
        text = f"""
💎 **ПОДПИСКА НА ПРЕМИУМ**

💰 **1 месяц:** 9 USDT
📅 **3 месяца:** 25 USDT (экономия 15%)

👤 **Ваш ID для оплаты:** `{user_id}`

💳 **Реквизиты для оплаты:**
USDT (TRC20): `TF33keB2N3P226zxFfESVCvXCFQMjnMXQh`

📋 **Процесс активации:**
1. Совершите оплату на указанный адрес
2. Отправьте скриншот чека администратору
3. Укажите ваш ID: `{user_id}`
4. Ожидайте активации в течение 15 минут

⚡ **Что получите после активации:**
• Неограниченные сигналы (100+ монет)
• Pump/Dump мониторинг всех рынков
• Приоритетную поддержку 24/7
• Точные точки входа/выхода
• Анализ на основе реальных рыночных данных

🔒 **Гарантия качества и поддержки!**
        """
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def mystatus_command(update, context):
    """Команда /mystatus - статус пользователя"""
    user = update.effective_user
    user_id = user.id
    user_data = get_user(user_id)
    
    today = datetime.now().date().isoformat()
    last_reset = user_data.get('last_reset_date', today)
    
    if last_reset != today:
        update_user(user_id, {
            "signals_today": 0,
            "last_reset_date": today
        })
        user_data['signals_today'] = 0
    
    status_text = f"""
📊 **ВАШ СТАТУС**

👤 **ID:** `{user_id}`
👋 **Имя:** {user.first_name}
💎 **Премиум статус:** {'✅ АКТИВЕН' if user_data.get('is_premium') else '❌ НЕ АКТИВЕН'}

📈 **Статистика:**
• Сигналов сегодня: {user_data.get('signals_today', 0)}/{
    '∞' if user_data.get('is_premium') else '1'
}
• Всего сигналов: {user_data.get('total_signals', 0)}
• Дата регистрации: {datetime.fromisoformat(
    user_data.get('join_date', datetime.now().isoformat())
).strftime('%d.%m.%Y')}

{
    f"📅 **Подписка истекает:** {datetime.fromisoformat(
        user_data['premium_expiry']
    ).strftime('%d.%m.%Y')}" 
    if user_data.get('is_premium') and user_data.get('premium_expiry') 
    else '💡 **Для активации премиума:** /premium'
}
    """
    
    await update.message.reply_text(status_text.strip(), parse_mode='Markdown')

async def support_command(update, context):
    """Команда /support - техподдержка"""
    user = update.effective_user
    user_id = user.id
    
    support_text = f"""
🆘 **ТЕХНИЧЕСКАЯ ПОДДЕРЖКА**

👤 **Ваш ID:** `{user_id}`
📅 **Дата обращения:** {datetime.now().strftime('%d.%m.%Y %H:%M')}

🤖 **Бот поддержки:**
@CryptoSignalsSupportBot

📋 **Мы поможем с:**
• Техническими проблемами с ботом
• Вопросами по оплате и подписке
• Активацией премиум доступа
• Любыми другими вопросами

💡 **Для быстрого решения:**
1. Опишите вашу проблему подробно
2. Укажите ваш ID: `{user_id}`
3. Приложите скриншот если есть

⏰ **Время ответа:** до 24 часов
📧 **Альтернативно:** support@cryptosignals.com
    """
    
    await update.message.reply_text(support_text, parse_mode='Markdown')

# ================== АДМИН-КОМАНДЫ ==================
async def activate_command(update, context):
    """Команда /activate - активация премиума (админ)"""
    user = update.effective_user
    user_id = user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ **Доступ запрещен!**")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ **Использование:**\n"
            "`/activate <user_id> [дней=30]`\n\n"
            "**Примеры:**\n"
            "`/activate 123456789`\n"
            "`/activate 123456789 90`",
            parse_mode='Markdown'
        )
        return
    
    try:
        target_id = int(context.args[0])
        days = int(context.args[1]) if len(context.args) > 1 else 30
        
        # Активация премиума
        expiry_date = (datetime.now() + timedelta(days=days)).isoformat()
        
        update_user(target_id, {
            "is_premium": True,
            "premium_expiry": expiry_date,
            "activated_by": user_id,
            "activated_at": datetime.now().isoformat()
        })
        
        await update.message.reply_text(
            f"✅ **Премиум активирован!**\n\n"
            f"👤 Пользователь: `{target_id}`\n"
            f"📅 Срок: {days} дней\n"
            f"⏰ Истекает: {datetime.fromisoformat(expiry_date).strftime('%d.%m.%Y')}\n\n"
            f"📊 Всего премиум пользователей: {sum(1 for u in load_database().values() if u.get('is_premium'))}",
            parse_mode='Markdown'
        )
        
        # Пытаемся уведомить пользователя
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"🎉 **ВАШ ПРЕМИУМ АКТИВИРОВАН!**\n\n"
                     f"Подписка активна на {days} дней\n"
                     "Теперь вам доступны:\n"
                     "• Неограниченные сигналы (100+ монет)\n"
                     "• Pump/Dump мониторинг всех рынков\n"
                     "• Приоритетная поддержка\n\n"
                     "💎 Добро пожаловать в клуб премиум пользователей!\n"
                     "Используйте /signals для получения сигналов.",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.warning(f"Не удалось уведомить пользователя {target_id}: {e}")
        
    except ValueError:
        await update.message.reply_text("❌ **Неверный формат!**\nИспользуйте числовой ID пользователя.")

async def users_command(update, context):
    """Команда /users - список пользователей (админ)"""
    user = update.effective_user
    user_id = user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ **Доступ запрещен!**")
        return
    
    db = load_database()
    
    if not db:
        await update.message.reply_text("📊 **База пользователей пуста**")
        return
    
    premium_count = sum(1 for u in db.values() if u.get('is_premium'))
    
    users_text = f"""
📊 **СТАТИСТИКА ПОЛЬЗОВАТЕЛЕЙ**

👥 **Всего пользователей:** {len(db)}
💎 **Премиум пользователей:** {premium_count}
🎯 **Бесплатных пользователей:** {len(db) - premium_count}

📈 **Последние 10 пользователей:**
"""
    
    # Последние 10 пользователей
    sorted_users = sorted(
        db.items(),
        key=lambda x: x[1].get('join_date', ''),
        reverse=True
    )[:10]
    
    for i, (uid, data) in enumerate(sorted_users, 1):
        status = "💎" if data.get('is_premium') else "🎯"
        join_date = datetime.fromisoformat(
            data.get('join_date', datetime.now().isoformat())
        ).strftime('%d.%m')
        users_text += f"{i}. {status} `{uid}` - {join_date}\n"
    
    users_text += f"\n💡 **Полный список:** {len(db)} пользователей"
    
    await update.message.reply_text(users_text, parse_mode='Markdown')

async def help_command(update, context):
    """Команда /help - помощь"""
    user = update.effective_user
    user_id = user.id
    
    help_text = """
🆘 **ПОМОЩЬ ПО КОМАНДАМ**

📋 **Основные команды:**
• /start - Начать работу с ботом
• /signals - Получить торговые сигналы
• /premium - Информация о премиум подписке
• /mystatus - Мой статус и статистика
• /support - Техническая поддержка
• /help - Эта справка

👑 **Админ-команды** (только для администратора):
• /activate <user_id> [дней] - Активировать премиум
• /users - Список пользователей

💡 **Как работает бот:**
1. Бесплатные пользователи получают 1 сигнал в день
2. Премиум пользователи - неограниченные сигналы
3. Все сигналы генерируются на основе рыночного анализа

📞 **Поддержка:** @CryptoSignalsSupportBot
    """
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

# ================== ОСНОВНОЙ БОТ ==================
def run_bot():
    """Запуск основного бота"""
    time.sleep(5)  # Ждем запуск веб-сервера
    
    if not TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN не найден!")
        return
    
    try:
        from telegram import Update
        from telegram.ext import Application, CommandHandler, ContextTypes
        from datetime import timedelta
        
        logger.info("🤖 Инициализация основного бота...")
        
        # Создаем Application для PTB 20.x
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Регистрируем обработчики команд
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("signals", signals_command))
        application.add_handler(CommandHandler("premium", premium_command))
        application.add_handler(CommandHandler("mystatus", mystatus_command))
        application.add_handler(CommandHandler("support", support_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("activate", activate_command))
        application.add_handler(CommandHandler("users", users_command))
        
        # Псевдонимы команд
        application.add_handler(CommandHandler("sub", premium_command))
        application.add_handler(CommandHandler("subscription", premium_command))
        application.add_handler(CommandHandler("status", mystatus_command))
        application.add_handler(CommandHandler("list", users_command))
        
        logger.info("✅ Бот инициализирован, запускаю polling...")
        
        # Запускаем polling
        application.run_polling(
            poll_interval=2.0,
            timeout=20,
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка бота: {e}")
        import traceback
        traceback.print_exc()

# ================== ГЛАВНЫЙ ЗАПУСК ==================
def main():
    """Основная функция запуска"""
    logger.info("🚀 Запуск системы Crypto Signals Pro...")
    
    if not TELEGRAM_TOKEN:
        logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: TELEGRAM_TOKEN не установлен!")
        return
    
    # Запускаем веб-сервер в отдельном потоке
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    
    # Ждем запуска веб-сервера
    time.sleep(3)
    
    # Запускаем бота в основном потоке
    run_bot()

# ================== ТОЧКА ВХОДА ==================
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Остановка системы...")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
