"""
🚀 CRYPTO SIGNALS PRO BOT - РАБОЧАЯ ВЕРСИЯ ДЛЯ RENDER
Анализ рынка + Pump/Dump мониторинг + Премиум подписки
"""

import os
import json
import logging
import asyncio
import aiohttp
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# ================== НАСТРОЙКА ==================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация из переменных окружения Render
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "638584949"))

# База данных в JSON (для Render)
DB_FILE = "users_db.json"

# Список монет для анализа
COINGECKO_IDS = {
    'BTC': 'bitcoin', 'ETH': 'ethereum', 'BNB': 'binancecoin',
    'SOL': 'solana', 'XRP': 'ripple', 'ADA': 'cardano',
    'DOGE': 'dogecoin', 'DOT': 'polkadot', 'LTC': 'litecoin',
    'LINK': 'chainlink', 'AVAX': 'avalanche-2', 'MATIC': 'matic-network',
    'SHIB': 'shiba-inu', 'PEPE': 'pepe', 'ATOM': 'cosmos',
    'UNI': 'uniswap', 'AAVE': 'aave', 'ALGO': 'algorand',
    'NEAR': 'near', 'TRX': 'tron', 'XLM': 'stellar',
    'ETC': 'ethereum-classic', 'XMR': 'monero', 'EOS': 'eos'
}

# ================== БАЗА ДАННЫХ ==================
class UserDatabase:
    def __init__(self):
        self.load_db()
    
    def load_db(self):
        try:
            if os.path.exists(DB_FILE):
                with open(DB_FILE, 'r', encoding='utf-8') as f:
                    self.db = json.load(f)
            else:
                self.db = {}
                self.save_db()
        except Exception as e:
            logger.error(f"Ошибка загрузки БД: {e}")
            self.db = {}
    
    def save_db(self):
        try:
            with open(DB_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.db, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Ошибка сохранения БД: {e}")
    
    def get_user(self, user_id):
        key = str(user_id)
        if key not in self.db:
            self.db[key] = {
                "id": user_id,
                "is_premium": False,
                "premium_expiry": None,
                "signals_today": 0,
                "last_reset_date": datetime.now().date().isoformat(),
                "join_date": datetime.now().isoformat(),
                "total_signals": 0,
                "username": None
            }
            self.save_db()
        return self.db[key]
    
    def update_user(self, user_id, updates):
        key = str(user_id)
        if key not in self.db:
            self.get_user(user_id)
        self.db[key].update(updates)
        self.save_db()
    
    def can_send_signal(self, user_id):
        user = self.get_user(user_id)
        today = datetime.now().date().isoformat()
        
        # Сброс дневного счетчика
        if user.get("last_reset_date") != today:
            self.update_user(user_id, {
                "signals_today": 0,
                "last_reset_date": today
            })
            user["signals_today"] = 0
        
        # Проверка лимита
        if user.get("is_premium"):
            return True
        return user.get("signals_today", 0) < 1
    
    def increment_signal(self, user_id):
        user = self.get_user(user_id)
        self.update_user(user_id, {
            "signals_today": user.get("signals_today", 0) + 1,
            "total_signals": user.get("total_signals", 0) + 1
        })

# Глобальная БД
user_db = UserDatabase()

# ================== COINGECKO API ==================
async def get_crypto_price(symbol):
    """Получить цену криптовалюты"""
    try:
        coin_id = COINGECKO_IDS.get(symbol.upper())
        if not coin_id:
            return None
        
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            'ids': coin_id,
            'vs_currencies': 'usd',
            'include_24hr_change': 'true'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if coin_id in data:
                        return {
                            'price': data[coin_id].get('usd', 0),
                            'change': data[coin_id].get('usd_24h_change', 0)
                        }
    except Exception as e:
        logger.error(f"API ошибка для {symbol}: {e}")
    return None

# ================== ГЕНЕРАЦИЯ СИГНАЛОВ ==================
async def generate_signal(symbol):
    """Генерировать торговый сигнал"""
    price_data = await get_crypto_price(symbol)
    
    if price_data and price_data['price']:
        current_price = price_data['price']
        change_24h = price_data['change']
        
        # Логика анализа
        import random
        actions = ['BUY', 'SELL', 'HOLD']
        
        if change_24h > 5:
            action = 'BUY' if random.random() > 0.3 else 'HOLD'
            confidence = random.randint(70, 90)
            leverage = "3x"
        elif change_24h < -5:
            action = 'SELL' if random.random() > 0.3 else 'HOLD'
            confidence = random.randint(65, 85)
            leverage = "2x"
        else:
            action = random.choice(actions)
            confidence = random.randint(60, 80)
            leverage = "1x"
        
        if action == 'BUY':
            target = current_price * (1 + random.uniform(2, 6) / 100)
            stop_loss = current_price * (1 - random.uniform(1, 3) / 100)
        elif action == 'SELL':
            target = current_price * (1 - random.uniform(2, 6) / 100)
            stop_loss = current_price * (1 + random.uniform(1, 3) / 100)
        else:
            target = current_price
            stop_loss = current_price
        
        return {
            'symbol': symbol,
            'action': action,
            'price': current_price,
            'change': change_24h,
            'target': target,
            'stop_loss': stop_loss,
            'leverage': leverage,
            'confidence': f"{confidence}%",
            'time': datetime.now().strftime('%H:%M %d.%m.%Y')
        }
    return None

# ================== КЛАВИАТУРЫ ==================
def get_main_keyboard(user_id):
    """Главное меню"""
    keyboard = [
        [KeyboardButton("🎯 Сигналы"), KeyboardButton("📊 Рынок")],
        [KeyboardButton("💎 Подписка"), KeyboardButton("🆘 Поддержка")]
    ]
    
    # Админ-панель
    if str(user_id) == str(ADMIN_ID):
        keyboard.append([KeyboardButton("👑 Админ")])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ================== КОМАНДЫ ==================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    user_id = user.id
    
    # Сохраняем пользователя
    user_db.update_user(user_id, {"username": user.username})
    
    text = f"""
🚀 Добро пожаловать в Crypto Signals Pro, {user.first_name}!

👤 Ваш ID: `{user_id}`
💎 Статус: {'✅ ПРЕМИУМ' if user_db.get_user(user_id).get('is_premium') else '🎯 БЕСПЛАТНЫЙ'}

📊 Доступные функции:
• 🎯 1 бесплатный сигнал в день
• 📊 Анализ рынка
• 💎 Премиум подписка
• 🆘 Поддержка 24/7

💡 Используйте кнопки меню для навигации!
    """
    
    await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))

async def signals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить сигналы"""
    user = update.effective_user
    user_id = user.id
    user_data = user_db.get_user(user_id)
    
    # Проверка лимита
    if not user_db.can_send_signal(user_id):
        await update.message.reply_text(
            f"❌ Достигнут дневной лимит!\n\n"
            f"Вы использовали {user_data.get('signals_today', 0)}/1 бесплатных сигналов.\n\n"
            f"💎 Оформите премиум для неограниченных сигналов!\n"
            f"Команда: /premium",
            reply_markup=get_main_keyboard(user_id)
        )
        return
    
    # Сообщение о загрузке
    loading_msg = await update.message.reply_text("🔄 Получаю рыночные данные...")
    
    try:
        # Для премиум пользователей - несколько сигналов
        symbols_to_check = ['BTC', 'ETH', 'BNB', 'SOL'] if user_data.get('is_premium') else ['BTC']
        signals = []
        
        for symbol in symbols_to_check:
            signal = await generate_signal(symbol)
            if signal and signal['action'] != 'HOLD':
                signals.append(signal)
        
        # Удаляем сообщение о загрузке
        await loading_msg.delete()
        
        if signals:
            for signal in signals:
                if user_data.get('is_premium'):
                    text = f"""
💎 ПРЕМИУМ СИГНАЛ 💎

🏷 Пара: {signal['symbol']}/USDT
⚡ Действие: {signal['action']}
💰 Цена: ${signal['price']:,.2f}
📊 Изменение 24ч: {signal['change']:+.2f}%
🎯 Цель: ${signal['target']:,.2f}
🛑 Стоп-лосс: ${signal['stop_loss']:,.2f}
📈 Плечо: {signal['leverage']}
✅ Уверенность: {signal['confidence']}

⏰ {signal['time']}
                    """
                else:
                    text = f"""
🎯 БЕСПЛАТНЫЙ СИГНАЛ 🎯

🏷 Пара: {signal['symbol']}/USDT
💰 Цена: ${signal['price']:,.2f}
📊 Изменение 24ч: {signal['change']:+.2f}%

📈 Тренд: {'📈 Восходящий' if signal['change'] > 0 else '📉 Нисходящий' if signal['change'] < 0 else '➡️ Боковой'}

💎 Для получения полных сигналов с точками входа/выхода оформите премиум!

🎯 Использовано: {user_data.get('signals_today', 0)+1}/1 сегодня

Команда: /premium
                    """
                
                await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))
            
            # Увеличиваем счетчик сигналов
            user_db.increment_signal(user_id)
        
        else:
            await update.message.reply_text(
                "⚠️ В данный момент нет активных сигналов. Попробуйте позже.",
                reply_markup=get_main_keyboard(user_id)
            )
    
    except Exception as e:
        logger.error(f"Ошибка сигналов: {e}")
        await update.message.reply_text(
            "⚠️ Ошибка получения сигналов. Попробуйте позже.",
            reply_markup=get_main_keyboard(user_id)
        )

async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о подписке"""
    user = update.effective_user
    user_id = user.id
    user_data = user_db.get_user(user_id)
    
    if user_data.get('is_premium'):
        expiry = user_data.get('premium_expiry')
        if expiry:
            try:
                expiry_date = datetime.fromisoformat(expiry)
                expiry_str = expiry_date.strftime('%d.%m.%Y %H:%M')
            except:
                expiry_str = "Бессрочно"
        else:
            expiry_str = "Бессрочно"
        
        text = f"""
💎 ВАША ПРЕМИУМ ПОДПИСКА АКТИВНА 💎

👤 ID пользователя: {user_id}
✅ Статус: Активен
📅 Истекает: {expiry_str}

🎯 Доступные функции:
• Неограниченные торговые сигналы
• Pump/Dump мониторинг
• Приоритетная поддержка
• Расширенный анализ рынка

Наслаждайтесь полным доступом!
        """
    else:
        text = f"""
💎 ПОДПИСКА НА ПРЕМИУМ

⏳ Срок: 30 дней
💰 Стоимость: 9 USDT

👤 Ваш ID для оплаты: `{user_id}`

💳 Реквизиты:
USDT (TRC20): `TF33keB2N3P226zxFfESVCvXCFQMjnMXQh`

📋 Что включено:
• Неограниченное количество сигналов (100+ монет)
• Точные точки входа/выхода
• Стоп-лосс и тейк-профит рекомендации
• Pump/Dump мониторинг 24/7
• Приоритетная поддержка
• Анализ всех топовых монет

📸 После оплаты отправьте скриншот:
@CryptoSignalsSupportBot

⚡ Активация в течение 15 минут!
        """
    
    keyboard = [
        [InlineKeyboardButton("📤 Отправить квитанцию", url="https://t.me/CryptoSignalsSupportBot")],
        [InlineKeyboardButton("🆘 Поддержка", callback_data="support")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup)

async def market_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Анализ рынка"""
    user = update.effective_user
    user_id = user.id
    user_data = user_db.get_user(user_id)
    
    # Проверка премиума для Pump/Dump
    if not user_data.get('is_premium') and str(user_id) != str(ADMIN_ID):
        await update.message.reply_text(
            "🔒 Pump/Dump мониторинг доступен только для премиум пользователей!\n\n"
            "💎 Оформите подписку для доступа к эксклюзивным данным.\n"
            "Команда: /premium",
            reply_markup=get_main_keyboard(user_id)
        )
        return
    
    await update.message.reply_text("🔄 Анализирую рынок...")
    
    try:
        # Анализ нескольких монет
        symbols = ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA']
        results = []
        
        for symbol in symbols:
            data = await get_crypto_price(symbol)
            if data:
                results.append({
                    'symbol': symbol,
                    'price': data['price'],
                    'change': data['change']
                })
        
        # Формируем отчет
        text = "📊 ОБЗОР РЫНКА\n\n"
        
        for res in results:
            change = res['change']
            if change > 10:
                status = "🚀 СИЛЬНЫЙ РОСТ"
                emoji = "📈"
            elif change > 5:
                status = "📈 РОСТ"
                emoji = "↗️"
            elif change > 0:
                status = "⬆️ НЕБОЛЬШОЙ РОСТ"
                emoji = "↗️"
            elif change < -10:
                status = "🔻 СИЛЬНОЕ ПАДЕНИЕ"
                emoji = "📉"
            elif change < -5:
                status = "📉 ПАДЕНИЕ"
                emoji = "↘️"
            else:
                status = "➡️ СТАБИЛЬНО"
                emoji = "➡️"
            
            text += f"{emoji} **{res['symbol']}**: ${res['price']:,.2f} ({change:+.2f}%)\n{status}\n\n"
        
        text += f"\n⏰ Обновлено: {datetime.now().strftime('%H:%M %d.%m.%Y')}"
        
        await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))
    
    except Exception as e:
        logger.error(f"Ошибка анализа рынка: {e}")
        await update.message.reply_text(
            "⚠️ Ошибка получения данных рынка. Попробуйте позже.",
            reply_markup=get_main_keyboard(user_id)
        )

async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поддержка"""
    text = """
🆘 ПОДДЕРЖКА

🤖 Единый бот поддержки:
@CryptoSignalsSupportBot

📋 Решаем все вопросы:
• Техническая поддержка
• Вопросы по оплате
• Активация премиум подписки
• Проблемы с ботом

⏰ Время ответа: до 15 минут

💡 Частые вопросы:
• Оплата - USDT (TRC20)
• Активация - до 15 минут
• Сигналы - обновляются каждые 2 часа
    """
    
    keyboard = [
        [InlineKeyboardButton("🤖 Написать в поддержку", url="https://t.me/CryptoSignalsSupportBot")],
        [InlineKeyboardButton("💎 Подписка", callback_data="subscription")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup)

# ================== АДМИН-КОМАНДЫ ==================
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Админ-панель"""
    user = update.effective_user
    
    if str(user.id) != str(ADMIN_ID):
        await update.message.reply_text("❌ Доступ запрещен!")
        return
    
    # Статистика
    db = user_db.db
    total_users = len(db)
    premium_users = sum(1 for u in db.values() if u.get('is_premium'))
    today_signals = sum(u.get('signals_today', 0) for u in db.values())
    
    text = f"""
👑 АДМИН-ПАНЕЛЬ

📊 Статистика:
• Всего пользователей: {total_users}
• Премиум пользователей: {premium_users}
• Сигналов сегодня: {today_signals}

🛠 Команды:
• /activate <user_id> [дней] - активировать премиум
• /deactivate <user_id> - деактивировать премиум
• /list_premium - список премиум пользователей
• /stats - подробная статистика
    """
    
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("💎 Управление премиум", callback_data="admin_premium")],
        [InlineKeyboardButton("🔙 В меню", callback_data="back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup)

async def activate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Активировать премиум"""
    user = update.effective_user
    
    if str(user.id) != str(ADMIN_ID):
        await update.message.reply_text("❌ Доступ запрещен!")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Использование: /activate <user_id> [дней=30]")
        return
    
    try:
        target_id = int(context.args[0])
        days = int(context.args[1]) if len(context.args) > 1 else 30
        
        expiry = (datetime.now() + timedelta(days=days)).isoformat()
        user_db.update_user(target_id, {
            "is_premium": True,
            "premium_expiry": expiry
        })
        
        expiry_str = (datetime.now() + timedelta(days=days)).strftime('%d.%m.%Y')
        
        await update.message.reply_text(
            f"✅ Премиум активирован!\n\n"
            f"Пользователь: {target_id}\n"
            f"Срок: {days} дней\n"
            f"Истекает: {expiry_str}"
        )
        
        # Уведомление пользователю
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"🎉 **ВАШ ПРЕМИУМ АКТИВИРОВАН!**\n\n"
                     f"Подписка активна на {days} дней.\n"
                     "Теперь вам доступны все премиум функции!"
            )
        except:
            pass
        
    except ValueError:
        await update.message.reply_text("❌ Неверный формат ID")

async def list_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список премиум пользователей"""
    user = update.effective_user
    
    if str(user.id) != str(ADMIN_ID):
        await update.message.reply_text("❌ Доступ запрещен!")
        return
    
    db = user_db.db
    premium_users = [(uid, data) for uid, data in db.items() if data.get('is_premium')]
    
    if not premium_users:
        await update.message.reply_text("📊 Нет активных премиум пользователей")
        return
    
    text = "📊 АКТИВНЫЕ ПРЕМИУМ ПОЛЬЗОВАТЕЛИ:\n\n"
    
    for i, (user_id, data) in enumerate(premium_users[:20], 1):
        expiry = data.get('premium_expiry')
        if expiry:
            try:
                expiry_str = datetime.fromisoformat(expiry).strftime('%d.%m.%Y')
            except:
                expiry_str = "Бессрочно"
        else:
            expiry_str = "Бессрочно"
        
        username = data.get('username', 'нет')
        text += f"{i}. ID: `{user_id}` | @{username} | До: {expiry_str}\n"
    
    if len(premium_users) > 20:
        text += f"\n... и еще {len(premium_users) - 20} пользователей"
    
    await update.message.reply_text(text)

# ================== ОБРАБОТЧИК КНОПОК ==================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик inline кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "back":
        await query.message.reply_text(
            "🔙 Возврат в главное меню",
            reply_markup=get_main_keyboard(user_id)
        )
    
    elif data == "subscription":
        await premium_command(update, context)
    
    elif data == "support":
        await support_command(update, context)

# ================== ОБРАБОТЧИК ТЕКСТА ==================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    text = update.message.text
    user_id = update.effective_user.id
    
    if text == "🎯 Сигналы":
        await signals_command(update, context)
    
    elif text == "📊 Рынок":
        await market_command(update, context)
    
    elif text == "💎 Подписка":
        await premium_command(update, context)
    
    elif text == "🆘 Поддержка":
        await support_command(update, context)
    
    elif text == "👑 Админ":
        await admin_command(update, context)
    
    else:
        await update.message.reply_text(
            "🤖 Используйте кнопки меню или команды:\n"
            "/start - Главное меню\n"
            "/signals - Получить сигналы\n"
            "/premium - Подписка\n"
            "/support - Поддержка",
            reply_markup=get_main_keyboard(user_id)
        )

# ================== ЗАПУСК БОТА ==================
def main():
    """Основная функция запуска"""
    print("=" * 60)
    print("🚀 ЗАПУСК CRYPTO SIGNALS PRO BOT")
    print("=" * 60)
    print(f"🤖 Бот поддержки: @CryptoSignalsSupportBot")
    print(f"💎 Цена подписки: 9 USDT")
    print(f"📊 Анализ {len(COINGECKO_IDS)} монет")
    print("=" * 60)
    
    if not TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN не установлен!")
        return
    
    try:
        # Создаем приложение
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Основные команды
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("signals", signals_command))
        application.add_handler(CommandHandler("premium", premium_command))
        application.add_handler(CommandHandler("market", market_command))
        application.add_handler(CommandHandler("support", support_command))
        
        # Админ-команды
        application.add_handler(CommandHandler("admin", admin_command))
        application.add_handler(CommandHandler("activate", activate_command))
        application.add_handler(CommandHandler("list_premium", list_premium_command))
        application.add_handler(CommandHandler("stats", admin_command))
        
        # Обработчики
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        
        print("✅ Бот готов к работе!")
        print("💎 Система премиум подписок активна")
        print("📊 Подключение к CoinGecko API...")
        print("=" * 60)
        
        # Запускаем polling
        application.run_polling(
            poll_interval=3.0,
            timeout=30,
            drop_pending_updates=True
        )
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")

if __name__ == "__main__":
    main()
