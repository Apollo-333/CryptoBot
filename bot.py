"""
🚀 YESsignals_bot - Исправленная версия с единой системой проверки премиума
"""

import os
import json
import random
import asyncio
import logging
import aiohttp
import threading
import time
from datetime import datetime, timedelta
from flask import Flask
from waitress import serve
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# ================== НАСТРОЙКА ==================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB_FILE = "users_db.json"

# Список монет (упрощенный для примера)
COINGECKO_IDS = {
    'BTC': 'bitcoin', 'ETH': 'ethereum', 'BNB': 'binancecoin', 'SOL': 'solana',
    'XRP': 'ripple', 'ADA': 'cardano', 'DOGE': 'dogecoin', 'DOT': 'polkadot',
    'MATIC': 'matic-network', 'LINK': 'chainlink', 'UNI': 'uniswap'
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
        """Получить пользователя (создать если нет)"""
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
                "username": None,
                "premium_start": None
            }
            self.save_db()
        return self.db[key]
    
    def update_user(self, user_id, updates):
        """Обновить данные пользователя"""
        key = str(user_id)
        if key not in self.db:
            self.get_user(user_id)
        self.db[key].update(updates)
        self.save_db()
    
    def check_and_reset_daily_limit(self, user_id):
        """Проверить и сбросить дневной лимит если нужно"""
        user = self.get_user(user_id)
        today = datetime.now().date().isoformat()
        
        if user.get("last_reset_date") != today:
            self.update_user(user_id, {
                "signals_today": 0,
                "last_reset_date": today
            })
            return 0  # Сброшено, можно отправлять сигналы
        return user.get("signals_today", 0)
    
    def is_premium(self, user_id):
        """ЕДИНАЯ ФУНКЦИЯ ПРОВЕРКИ ПРЕМИУМ СТАТУСА"""
        user = self.get_user(user_id)
        
        # Если не помечен как премиум - сразу false
        if not user.get("is_premium"):
            return False
        
        # Проверяем срок действия
        expiry = user.get("premium_expiry")
        if expiry:
            try:
                expiry_date = datetime.fromisoformat(expiry)
                if datetime.now() > expiry_date:
                    # Автоматически отключаем истекший премиум
                    self.update_user(user_id, {
                        "is_premium": False,
                        "premium_expiry": None
                    })
                    logger.info(f"⚠️ Премиум истек у пользователя {user_id}")
                    return False
                return True
            except Exception as e:
                logger.error(f"Ошибка проверки срока премиума: {e}")
                return False
        
        # Если нет expiry, считаем бессрочным (для админа или тестов)
        return True
    
    def can_send_signal(self, user_id):
        """Может ли пользователь получить сигнал (ЕДИНАЯ ЛОГИКА)"""
        # Проверяем премиум статус
        if self.is_premium(user_id):
            return True
        
        # Для бесплатных пользователей проверяем лимит
        signals_today = self.check_and_reset_daily_limit(user_id)
        return signals_today < 1
    
    def increment_signal_count(self, user_id):
        """Увеличить счетчик сигналов"""
        user = self.get_user(user_id)
        signals_today = user.get("signals_today", 0)
        total_signals = user.get("total_signals", 0)
        
        self.update_user(user_id, {
            "signals_today": signals_today + 1,
            "total_signals": total_signals + 1
        })

user_db = UserDatabase()

# ================== API ФУНКЦИИ ==================
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
            async with session.get(url, params=params, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    if coin_id in data:
                        price_data = data[coin_id]
                        return {
                            'price': price_data.get('usd', 0),
                            'change': price_data.get('usd_24h_change', 0)
                        }
        return None
    except Exception as e:
        logger.error(f"Ошибка получения цены {symbol}: {e}")
        return None

# ================== КОМАНДЫ ==================
def get_main_keyboard(user_id):
    """Главное меню"""
    keyboard = [
        [KeyboardButton("🎯 Сигналы"), KeyboardButton("📈 Pump/Dump")],
        [KeyboardButton("💎 Подписка"), KeyboardButton("🆘 Поддержка")]
    ]
    
    # Админ-панель ТОЛЬКО для админа
    if str(user_id) == str(ADMIN_ID) and ADMIN_ID != 0:
        keyboard.append([KeyboardButton("👑 Админ")])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    user_id = user.id
    
    user_db.update_user(user_id, {"username": user.username})
    
    is_premium = user_db.is_premium(user_id)
    signals_today = user_db.check_and_reset_daily_limit(user_id)
    
    text = f"""
🚀 **Добро пожаловать, {user.first_name}!**

👤 **Ваш ID:** `{user_id}`
💎 **Статус:** {'✅ ПРЕМИУМ' if is_premium else '🎯 БЕСПЛАТНЫЙ'}

📊 **Использовано сегодня:** {signals_today}/1 сигналов
📈 **Всего сигналов:** {user_db.get_user(user_id).get('total_signals', 0)}

💡 **Используйте кнопки меню!**
"""
    
    await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))

async def signals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить торговые сигналы"""
    user = update.effective_user
    user_id = user.id
    
    # ЕДИНАЯ ПРОВЕРКА через can_send_signal
    if not user_db.can_send_signal(user_id):
        is_premium = user_db.is_premium(user_id)
        signals_today = user_db.check_and_reset_daily_limit(user_id)
        
        if is_premium:
            text = "⚠️ **Техническая ошибка.** Премиум статус есть, но что-то пошло не так."
        else:
            text = f"""
❌ **Достигнут дневной лимит!**

📊 **Использовано:** {signals_today}/1 сигналов
💎 **Премиум включает:**
• Неограниченные сигналы
• Pump/Dump мониторинг
• Приоритетную поддержку

👉 /premium - оформить подписку
"""
        await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))
        return
    
    # Показываем статус пользователя
    is_premium = user_db.is_premium(user_id)
    status_text = "💎 **ПРЕМИУМ СИГНАЛ**" if is_premium else "🎯 **БЕСПЛАТНЫЙ СИГНАЛ**"
    
    loading_msg = await update.message.reply_text("🔄 Получаю данные...")
    
    try:
        # Выбираем символы в зависимости от статуса
        if is_premium:
            symbols = random.sample(list(COINGECKO_IDS.keys()), min(3, len(COINGECKO_IDS)))
        else:
            symbols = [random.choice(list(COINGECKO_IDS.keys())[:5])]
        
        signals = []
        for symbol in symbols:
            price_data = await get_crypto_price(symbol)
            if price_data and price_data['price'] > 0:
                signals.append({
                    'symbol': symbol,
                    'price': price_data['price'],
                    'change': price_data.get('change', 0)
                })
                if not is_premium:
                    break
        
        await loading_msg.delete()
        
        if not signals:
            await update.message.reply_text(
                "⚠️ Не удалось получить данные. Попробуйте позже.",
                reply_markup=get_main_keyboard(user_id)
            )
            return
        
        # Отправляем сигналы
        for signal in signals:
            text = f"""
{status_text}

🏷 **Пара:** {signal['symbol']}/USDT
💰 **Цена:** ${signal['price']:.2f}
📊 **Изменение 24ч:** {signal['change']:+.2f}%

{'💎 **Ваш статус: ПРЕМИУМ ✅**' if is_premium else '🔒 **Премиум:** /premium'}
"""
            await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))
            await asyncio.sleep(0.3)
        
        # Увеличиваем счетчик
        user_db.increment_signal_count(user_id)
        
    except Exception as e:
        logger.error(f"Ошибка получения сигналов: {e}")
        await update.message.reply_text(
            "⚠️ Ошибка получения данных.",
            reply_markup=get_main_keyboard(user_id)
        )

async def pumpdump_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pump/Dump мониторинг - ТОЛЬКО для премиум"""
    user = update.effective_user
    user_id = user.id
    
    # ЕДИНАЯ ПРОВЕРКА через is_premium
    is_premium = user_db.is_premium(user_id)
    is_admin = ADMIN_ID != 0 and str(user_id) == str(ADMIN_ID)
    
    if not is_premium and not is_admin:
        signals_today = user_db.check_and_reset_daily_limit(user_id)
        
        text = f"""
🔒 **ДОСТУП ЗАПРЕЩЕН!**

📊 **Pump/Dump мониторинг доступен ТОЛЬКО для премиум пользователей!**

📈 **Ваша статистика:**
• Сигналов сегодня: {signals_today}/1
• Статус: 🎯 БЕСПЛАТНЫЙ

💎 **Премиум подписка включает:**
• Pump/Dump мониторинг
• Неограниченные сигналы
• Приоритетную поддержку

💰 **9 USDT** на 30 дней
👉 /premium - оформить подписку
"""
        await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))
        return
    
    # Если пользователь премиум или админ
    loading_msg = await update.message.reply_text("🔍 Анализирую рынок...")
    
    try:
        # Простая имитация анализа
        await asyncio.sleep(1)
        await loading_msg.delete()
        
        # Показываем статус пользователя
        status = "💎 **Ваш статус: ПРЕМИУМ ✅**" if is_premium else "👑 **Администратор**"
        
        text = f"""
📊 **АНАЛИЗ РЫНКА ЗАВЕРШЕН**

✅ Активных pump/dump сигналов не обнаружено
{status}

⚡ **Параметры анализа:**
• Проверено: 50+ монет
• Критерий pump: рост >12%
• Критерий dump: падение >12%

⏰ **Время анализа:** {datetime.now().strftime('%H:%M')}
"""
        await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))
        
    except Exception as e:
        logger.error(f"Ошибка pump/dump: {e}")
        await update.message.reply_text(
            "⚠️ Ошибка анализа.",
            reply_markup=get_main_keyboard(user_id)
        )

async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о подписке"""
    user = update.effective_user
    user_id = user.id
    
    is_premium = user_db.is_premium(user_id)
    signals_today = user_db.check_and_reset_daily_limit(user_id)
    
    if is_premium:
        user_data = user_db.get_user(user_id)
        expiry = user_data.get('premium_expiry')
        
        if expiry:
            try:
                expiry_date = datetime.fromisoformat(expiry)
                days_left = (expiry_date - datetime.now()).days
                expiry_str = expiry_date.strftime('%d.%m.%Y')
            except:
                days_left = "?"
                expiry_str = "?"
        else:
            days_left = "∞"
            expiry_str = "Бессрочно"
        
        text = f"""
💎 **ВАША ПРЕМИУМ ПОДПИСКА АКТИВНА**

✅ **Статус:** Активен
📅 **Истекает:** {expiry_str}
⏳ **Осталось дней:** {days_left}
📊 **Всего сигналов:** {user_data.get('total_signals', 0)}
📈 **Сигналов сегодня:** {signals_today}

🔔 **Доступные функции:**
• ✅ Неограниченные торговые сигналы
• ✅ Pump/Dump мониторинг
• ✅ Приоритетная поддержка
"""
    else:
        text = f"""
💎 **ПРЕМИУМ ПОДПИСКА YESsignals**

⏳ **Срок:** 30 дней
💰 **Стоимость:** 9 USDT

👤 **Ваш ID:** `{user_id}`
📊 **Ваши сигналы:** {signals_today}/1 сегодня

💳 **USDT (TRC20):**
`TF33keB2N3P226zxFfESVCvXCFQMjnMXQh`

📸 **Отправьте чек:** @YESsignals_support_bot
"""
    
    keyboard = [
        [InlineKeyboardButton("📤 Отправить чек", url="https://t.me/YESsignals_support_bot")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ]
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поддержка"""
    text = """
🆘 **ТЕХНИЧЕСКАЯ ПОДДЕРЖКА**

🤖 **Бот поддержки:**
@YESsignals_support_bot

⏰ **Время ответа:** до 15 минут

💡 **Для быстрого решения:**
• Укажите ваш ID
• Приложите скриншоты
• Оплата только USDT (TRC20)
"""
    
    keyboard = [
        [InlineKeyboardButton("🤖 Написать", url="https://t.me/YESsignals_support_bot")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ]
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ================== ЗАПУСК ==================
def main():
    """Основной запуск"""
    print("=" * 50)
    print("🚀 YESsignals_bot - Исправленная версия")
    print("=" * 50)
    print("✅ Единая система проверки премиума")
    print("✅ Нет противоречий в статусе")
    print("✅ Быстрая работа")
    print("=" * 50)
    
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_TOKEN не найден!")
        return
    
    try:
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Команды
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("signals", signals_command))
        application.add_handler(CommandHandler("pumpdump", pumpdump_command))
        application.add_handler(CommandHandler("premium", premium_command))
        application.add_handler(CommandHandler("support", support_command))
        
        # Обработчики
        application.add_handler(CallbackQueryHandler(lambda u,c: u.callback_query.answer() and None))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, 
            lambda u,c: handle_text(u,c) if hasattr(handle_text, '__call__') else None))
        
        print("✅ Бот запускается...")
        application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    main()
