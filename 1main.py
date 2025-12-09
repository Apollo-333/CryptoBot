import os
import psycopg
import logging
from datetime import datetime, timedelta
import random
import aiohttp
import asyncio
import time
import sys
import telegram.error

# ================== FIX ДЛЯ IMGHDR ==================
try:
    import imghdr
except ImportError:
    class ImghdrStub:
        @staticmethod
        def what(file, h=None):
            return None
    sys.modules['imghdr'] = ImghdrStub()

# ================== ЛОГИРОВАНИЕ ==================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ================== КОНФИГ ==================
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# CoinGecko API
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"

# ================== СПИСОК МОНЕТ ==================
COINGECKO_IDS = {
    'BTC': 'bitcoin',
    'ETH': 'ethereum',
    # ... (оставьте ваш список монет как есть)
}

# ================== УТИЛИТЫ ДЛЯ АСИНХРОНА ==================
def run_async(coro):
    """Безопасный запуск корутины внутри синхронных хендлеров."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

# ================== БАЗА ДАННЫХ ==================
class UserDatabase:
    def __init__(self):
        database_url = os.getenv("DATABASE_URL")
        
        if not database_url:
            print("⚠️ DATABASE_URL не найден, использую фиктивную базу в памяти")
            self.conn = None
            self.cursor = None
            self.use_dummy_db = True
            self.users = {}
            return
        
        try:
            self.conn = psycopg.connect(database_url)
            self.cursor = self.conn.cursor()
            self.use_dummy_db = False
            self.init_db()
            print("✅ Подключение к PostgreSQL установлено")
        except Exception as e:
            print(f"❌ Ошибка подключения к БД: {e}")
            print("⚠️ Использую фиктивную базу в памяти")
            self.conn = None
            self.cursor = None
            self.use_dummy_db = True
            self.users = {}

    def init_db(self):
        if self.use_dummy_db:
            return
        try:
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    is_premium BOOLEAN DEFAULT FALSE,
                    signals_today INTEGER DEFAULT 0,
                    last_reset_date TEXT,
                    premium_expiry TEXT
                )
            ''')
            self.conn.commit()
            print("✅ PostgreSQL база инициализирована")
        except Exception as e:
            print(f"❌ Ошибка при инициализации БД: {e}")

    def add_user(self, user_id):
        if self.use_dummy_db:
            if user_id not in self.users:
                self.users[user_id] = {
                    'is_premium': False,
                    'signals_today': 0,
                    'last_reset_date': datetime.now().date().isoformat(),
                    'premium_expiry': None
                }
            return
        
        try:
            self.cursor.execute('''
                INSERT INTO users (user_id, is_premium, signals_today, last_reset_date)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id) DO NOTHING
            ''', (user_id, False, 0, datetime.now().date().isoformat()))
            self.conn.commit()
        except Exception as e:
            print(f"❌ Ошибка при добавлении пользователя: {e}")

    def get_user(self, user_id):
        if self.use_dummy_db:
            if user_id not in self.users:
                self.add_user(user_id)
            user_data = self.users[user_id]
            return (
                user_id,
                user_data['is_premium'],
                user_data['signals_today'],
                user_data['last_reset_date'],
                user_data['premium_expiry']
            )
        
        try:
            self.cursor.execute('''
                SELECT user_id, is_premium, signals_today, last_reset_date, premium_expiry
                FROM users WHERE user_id = %s
            ''', (user_id,))
            result = self.cursor.fetchone()
            if result:
                return result
            else:
                self.add_user(user_id)
                return (user_id, False, 0, datetime.now().date().isoformat(), None)
        except Exception as e:
            print(f"❌ Ошибка при получении пользователя: {e}")
            return (user_id, False, 0, datetime.now().date().isoformat(), None)

    def can_send_signal(self, user_id):
        try:
            user_id, is_premium, signals_today, last_reset_date, _ = self.get_user(user_id)
            today = datetime.now().date().isoformat()
            if last_reset_date != today:
                if self.use_dummy_db:
                    self.users[user_id]['signals_today'] = 0
                    self.users[user_id]['last_reset_date'] = today
                else:
                    self.cursor.execute('''
                        UPDATE users SET signals_today = 0, last_reset_date = %s WHERE user_id = %s
                    ''', (today, user_id))
                    self.conn.commit()
                signals_today = 0
            limit = 1000 if is_premium else 1
            return signals_today < limit
        except Exception as e:
            print(f"❌ Ошибка проверки лимита сигналов: {e}")
            return True

    def increment_signal_count(self, user_id):
        if self.use_dummy_db:
            if user_id in self.users:
                self.users[user_id]['signals_today'] += 1
            return
        
        try:
            self.cursor.execute('''
                UPDATE users SET signals_today = signals_today + 1 WHERE user_id = %s
            ''', (user_id,))
            self.conn.commit()
        except Exception as e:
            print(f"❌ Ошибка увеличения счетчика: {e}")

    def activate_premium(self, user_id, duration_days=30):
        expiry_date = (datetime.now() + timedelta(days=duration_days)).isoformat()
        
        if self.use_dummy_db:
            if user_id in self.users:
                self.users[user_id]['is_premium'] = True
                self.users[user_id]['premium_expiry'] = expiry_date
            return True
        
        try:
            self.cursor.execute('''
                UPDATE users SET is_premium = TRUE, premium_expiry = %s WHERE user_id = %s
            ''', (expiry_date, user_id))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Ошибка активации премиума: {e}")
            return False

    def deactivate_premium(self, user_id):
        if self.use_dummy_db:
            if user_id in self.users:
                self.users[user_id]['is_premium'] = False
                self.users[user_id]['premium_expiry'] = None
            return True
        
        try:
            self.cursor.execute('''
                UPDATE users SET is_premium = FALSE, premium_expiry = NULL WHERE user_id = %s
            ''', (user_id,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Ошибка деактивации премиума: {e}")
            return False

    def check_premium_status(self, user_id):
        """Возвращает True/False — активен ли премиум у пользователя."""
        if self.use_dummy_db:
            if user_id not in self.users:
                return False
            user_data = self.users[user_id]
            if not user_data['is_premium']:
                return False
            if user_data['premium_expiry']:
                try:
                    return datetime.fromisoformat(user_data['premium_expiry']) > datetime.now()
                except Exception:
                    return True
            return True
        
        try:
            self.cursor.execute('SELECT is_premium, premium_expiry FROM users WHERE user_id = %s', (user_id,))
            row = self.cursor.fetchone()
            if not row:
                return False
            is_premium, premium_expiry = row
            if not is_premium:
                return False
            if premium_expiry:
                try:
                    return datetime.fromisoformat(premium_expiry) > datetime.now()
                except Exception:
                    return True
            return True
        except Exception as e:
            print(f"❌ Ошибка проверки статуса премиума: {e}")
            return False

    def get_premium_users(self):
        """Возвращает список (user_id, premium_expiry) активных премиум пользователей."""
        if self.use_dummy_db:
            return [(uid, data['premium_expiry']) for uid, data in self.users.items() 
                   if data['is_premium']]
        
        try:
            self.cursor.execute('SELECT user_id, premium_expiry FROM users WHERE is_premium = TRUE')
            rows = self.cursor.fetchall() or []
            result = []
            for user_id, expiry in rows:
                result.append((user_id, expiry))
            return result
        except Exception as e:
            print(f"❌ Ошибка получения списка премиум: {e}")
            return []

# Глобальный экземпляр БД
user_db = UserDatabase()

# ================== ПРАВА АДМИНА ==================
def is_admin(user_id):
    return user_id == ADMIN_ID

# ================== РАБОТА С API COINGECKO ==================
async def get_crypto_price(symbol):
    """Получить текущую цену криптовалюты с CoinGecko."""
    try:
        coin_id = COINGECKO_IDS.get(symbol)
        if not coin_id:
            return None

        async with aiohttp.ClientSession() as session:
            url = f"{COINGECKO_API_URL}/simple/price"
            params = {
                'ids': coin_id,
                'vs_currencies': 'usd',
                'include_24hr_change': 'true',
                'include_24hr_vol': 'true'
            }

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if coin_id in data:
                        price_data = data[coin_id]
                        return {
                            'price': price_data.get('usd', 0),
                            'change_24h': price_data.get('usd_24h_change', 0),
                            'volume': price_data.get('usd_24h_vol', 0)
                        }
                return None

    except Exception as e:
        print(f"❌ Ошибка получения цены для {symbol}: {e}")
        return None

async def get_multiple_prices(symbols):
    """Получить цены для нескольких символов одновременно."""
    tasks = [get_crypto_price(symbol) for symbol in symbols]
    results = await asyncio.gather(*tasks)
    return dict(zip(symbols, results))

# ================== ЛОГИКА СИГНАЛОВ ==================
def calculate_signal_parameters(current_price, change_24h, volume):
    """Рассчитать параметры сигнала на основе рыночных данных."""
    if change_24h > 5:
        action = "BUY" if random.random() > 0.3 else "HOLD"
        target_percent = random.uniform(3, 8)
        stop_loss_percent = random.uniform(2, 4)
        confidence = random.randint(75, 90)
    elif change_24h < -5:
        action = "SELL" if random.random() > 0.3 else "HOLD"
        target_percent = random.uniform(3, 8)
        stop_loss_percent = random.uniform(2, 4)
        confidence = random.randint(70, 85)
    else:
        action = random.choice(["BUY", "SELL", "HOLD"])
        target_percent = random.uniform(2, 6)
        stop_loss_percent = random.uniform(1.5, 3)
        confidence = random.randint(65, 80)

    if volume > 1_000_000_000:
        confidence = min(95, confidence + 10)
    elif volume < 100_000_000:
        confidence = max(60, confidence - 5)

    if action == "BUY":
        target_price = current_price * (1 + target_percent / 100)
        stop_loss_price = current_price * (1 - stop_loss_percent / 100)
    elif action == "SELL":
        target_price = current_price * (1 - target_percent / 100)
        stop_loss_price = current_price * (1 + stop_loss_percent / 100)
    else:
        target_price = current_price
        stop_loss_price = current_price

    volatility = abs(change_24h)
    if volatility > 10:
        leverage = "2x"
    elif volatility > 5:
        leverage = "3x"
    else:
        leverage = "5x"

    return {
        'action': action,
        'target_price': target_price,
        'stop_loss_price': stop_loss_price,
        'leverage': leverage,
        'confidence': f"{confidence}%"
    }

async def generate_real_signals():
    """Генерация реальных торговых сигналов на основе текущих цен."""
    try:
        symbols = list(COINGECKO_IDS.keys())[:100]
        selected_symbols = random.sample(symbols, min(5, len(symbols)))
        print(f"🔍 Анализируем символы: {selected_symbols}")

        prices_data = await get_multiple_prices(selected_symbols)
        signals = []

        for symbol in selected_symbols:
            price_data = prices_data.get(symbol)
            if not price_data or not price_data.get('price'):
                continue

            current_price = price_data['price']
            change_24h = price_data.get('change_24h', 0)
            volume = price_data.get('volume', 0)

            signal_params = calculate_signal_parameters(current_price, change_24h, volume)

            if signal_params['action'] == 'HOLD':
                continue

            signal_text = f"""
🎯 **СИГНАЛ** 🎯

🏷 **Пара:** {symbol}/USDT
⚡ **Действие:** {signal_params['action']}
💰 **Текущая цена:** ${current_price:,.2f}
📊 **Изменение 24ч:** {change_24h:+.2f}%
🎯 **Цель:** ${signal_params['target_price']:,.2f}
🛑 **Стоп-лосс:** ${signal_params['stop_loss_price']:,.2f}
📈 **Плечо:** {signal_params['leverage']}
✅ **Уверенность:** {signal_params['confidence']}

⏰ **Время сигнала:** {datetime.now().strftime('%H:%M %d.%m.%Y')}
💡 **Основа:** Анализ рыночных данных
            """
            signals.append(signal_text)

        if not signals:
            fallback_symbol = random.choice(list(COINGECKO_IDS.keys())[:50])
            price_data = await get_crypto_price(fallback_symbol)

            if price_data and price_data.get('price'):
                current_price = price_data['price']
                signal_params = calculate_signal_parameters(current_price, 0, 0)

                signal_text = f"""
🎯 **СИГНАЛ** 🎯

🏷 **Пара:** {fallback_symbol}/USDT
⚡ **Действие:** {signal_params['action']}
💰 **Текущая цена:** ${current_price:,.2f}
🎯 **Цель:** ${signal_params['target_price']:,.2f}
🛑 **Стоп-лосс:** ${signal_params['stop_loss_price']:,.2f}
📈 **Плечо:** {signal_params['leverage']}
✅ **Уверенность:** {signal_params['confidence']}

⏰ **Время сигнала:** {datetime.now().strftime('%H:%M %d.%m.%Y')}
💡 **Основа:** Рыночный анализ
                """
                signals.append(signal_text)

        return signals

    except Exception as e:
        print(f"❌ Ошибка генерации реальных сигналов: {e}")
        return []

async def generate_free_signals():
    """Генерация сигналов для бесплатных пользователей."""
    try:
        btc_data = await get_crypto_price('BTC')

        if btc_data and btc_data.get('price'):
            btc_price = btc_data['price']
            btc_change = btc_data.get('change_24h', 0)
            trend = "📈 Восходящий" if btc_change > 0 else "📉 Нисходящий" if btc_change < 0 else "➡️ Боковой"

            return [f"""
🎯 **БЕСПЛАТНЫЙ СИГНАЛ** 🎯

🏷 **Пара:** BTC/USDT
💰 **Текущая цена:** ${btc_price:,.2f}
📊 **Изменение 24ч:** {btc_change:+.2f}%
📈 **Тренд:** {trend}

💡 **Анализ рынка:**
{get_market_analysis(btc_change)}

🔒 **Для получения точных сигналов с точками входа/выхода оформите премиум-подписку!**

💎 **Премиум включает:**
✓ Неограниченные сигналы (100+ монет)
✓ Точные точки входа/выхода
✓ Стоп-лосс и тейк-профит
✓ Рекомендации по плечу
✓ Приоритетную поддержку
✓ Pump/Dump мониторинг 24/7
✓ Анализ всех топовых монет
            """]

    except Exception as e:
        print(f"❌ Ошибка генерации бесплатных сигналов: {e}")

    return ["""
🎯 **БЕСПЛАТНЫЙ СИГНАЛ** 🎯

🏷 **Пара:** BTC/USDT
💡 **Текущая ситуация:** Анализ рыночных данных

📊 **Общий тренд:** Смешанный
💰 **Рекомендация:** Ожидайте подтверждения тренда

🔒 **Для получения точных сигналов с точками входа/выхода оформите премиум-подписку!**

💎 **Премиум включает:**
✓ Неограниченное количество сигналов
✓ Точные точки входа/выхода
✓ Стоп-лосс и тейк-профит
✓ Рекомендации по плечу
✓ Приоритетную поддержку
✓ Pump/Dump мониторинг 24/7
    """]

def get_market_analysis(btc_change):
    """Анализ рынка на основе изменения BTC."""
    if btc_change > 5:
        return "Сильный бычий тренд. Рынок показывает уверенный рост. Рекомендуется следить за альткойнами."
    elif btc_change > 2:
        return "Умеренный бычий тренд. Рынок в позитивной зоне. Возможны коррекции."
    elif btc_change > -2:
        return "Боковое движение. Рынок в неопределенности. Ожидайте пробоя уровня."
    elif btc_change > -5:
        return "Умеренный медвежий тренд. Рынок под давлением. Будьте осторожны."
    else:
        return "Сильный медвежий тренд. Рынок в коррекции. Рассмотрите короткие позиции."

async def generate_comprehensive_signals(user_id):
    """Генерация торговых сигналов с учетом статуса пользователя."""
    try:
        if is_admin(user_id):
            print(f"👑 Администратор {user_id} запросил сигналы")
            signals = await generate_real_signals()
            return signals, None

        user_id_, is_premium, _, _, _ = user_db.get_user(user_id)

        if not is_premium or not user_db.check_premium_status(user_id):
            print(f"👤 Бесплатный пользователь {user_id} запросил сигналы")
            if not user_db.can_send_signal(user_id):
                user_data = user_db.get_user(user_id)
                signals_used = user_data[2]
                return None, f"""❌ **Достигнут дневной лимит!**

Вы использовали {signals_used}/1 бесплатных сигналов сегодня.

💎 **Премиум подписка включает:**
• Неограниченное количество сигналов (100+ монет)
• Точные точки входа/выхода
• Pump/Dump мониторинг 24/7
• Приоритетную поддержку
• Анализ всех топовых монет

Нажмите «💎 Подписка» для оформления!"""
            free_signals = await generate_free_signals()
            user_db.increment_signal_count(user_id)
            return free_signals, None

        print(f"💎 Премиум пользователь {user_id} запросил сигналы")
        signals = await generate_real_signals()
        user_db.increment_signal_count(user_id)
        return signals, None

    except Exception as e:
        print(f"❌ Ошибка генерации сигналов: {e}")
        return None, "⚠️ Произошла ошибка при генерации сигналов"

# ================== КЛАВИАТУРЫ ==================
def get_main_keyboard(user_id):
    keyboard = [
        [KeyboardButton("🎯 Сигналы"), KeyboardButton("📈 Pump/Dump")],
        [KeyboardButton("💎 Подписка"), KeyboardButton("🆘 Поддержка")]
    ]
    if is_admin(user_id):
        keyboard.append([KeyboardButton("👨‍💻 Админ-панель")])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ================== ХЕНДЛЕРЫ (СИНХРОННЫЕ) ==================
def start_command(update, context):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    user_db.add_user(user_id)

    welcome_text = f"""
🚀 **Добро пожаловать в Crypto Signals Pro, {user_name}!** 🚀

💡 **Ваш ID:** `{user_id}`
📊 **Доступные функции:**
• 🎯 1 бесплатный сигнал в сутки
• 📈 Pump/Dump мониторинг (премиум)
• 💎 Премиум подписка
• 🆘 Поддержка 24/7

🎯 **Начните с кнопки "Сигналы"!**
    """
    update.message.reply_text(welcome_text, parse_mode='Markdown', reply_markup=get_main_keyboard(user_id))

def signals_command(update, context):
    user_id = update.effective_user.id
    try:
        loading_msg = update.message.reply_text(
            "**ПОЛУЧАЮ АКТУАЛЬНЫЕ СИГНАЛЫ...**\nЗапрашиваю рыночные данные...",
            reply_markup=get_main_keyboard(user_id)
        )

        signals, error = run_async(generate_comprehensive_signals(user_id))
        loading_msg.delete()

        if error:
            update.message.reply_text(error, reply_markup=get_main_keyboard(user_id))
            return

        for signal in signals:
            update.message.reply_text(signal, parse_mode='Markdown', reply_markup=get_main_keyboard(user_id))

    except Exception as e:
        print(f"❌ Ошибка в signals_command: {e}")
        update.message.reply_text(
            "⚠️ Произошла ошибка при получении сигналов",
            reply_markup=get_main_keyboard(user_id)
        )

def subscription_command(update, context):
    user_id = update.effective_user.id

    subscription_text = f"""
💎 **ПОДПИСКА НА ПРЕМИУМ**

**1 месяц: 9 USDT**

**Что получите:**  
• Неограниченные сигналы (100+ монет)  
• Pump/Dump мониторинг всех рынков  
• Приоритетную поддержку  
• Точные точки входа/выхода
• Анализ на основе реальных рыночных данных

**Оплата:**  
USDT (TRC20): `TF33keB2N3P226zxFfESVCvXCFQMjnMXQh`

**После оплаты:**  
Отправьте скриншот @CryptoSignalsSupportBot  
Ваш ID: `{user_id}`

**Активация в течение 15 минут!**
    """

    keyboard = [
        [InlineKeyboardButton("📤 Отправить квитанцию", url="https://t.me/CryptoSignalsSupportBot")],
        [InlineKeyboardButton("🆘 Поддержка", callback_data="support")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(subscription_text, parse_mode='Markdown', reply_markup=reply_markup)

def pumpdump_command(update, context):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        user_data = user_db.get_user(user_id)
        if not user_db.check_premium_status(user_id):
            update.message.reply_text(
                "🔒 **Pump/Dump мониторинг доступен только для премиум пользователей!**\n\n"
                "💎 Оформите подписку для доступа к эксклюзивным данным.",
                reply_markup=get_main_keyboard(user_id)
            )
            return

    try:
        loading_msg = update.message.reply_text(
            "🔍 **АНАЛИЗИРУЮ РЫНОК...**\nПолучаю актуальные данные...",
            reply_markup=get_main_keyboard(user_id)
        )
        loading_msg.delete()
        
        update.message.reply_text(
            "📊 **Pump/Dump мониторинг временно недоступен**\n\n"
            "Функция будет доступна в ближайшее время.\n"
            "Следите за обновлениями!",
            reply_markup=get_main_keyboard(user_id)
        )

    except Exception as e:
        print(f"❌ Ошибка в pumpdump_command: {e}")
        update.message.reply_text("⚠️ Ошибка получения данных Pump/Dump", reply_markup=get_main_keyboard(user_id))

def support_command(update, context):
    support_text = """
🆘 **ПОДДЕРЖКА**

🤖 **Единый бот поддержки:**
@CryptoSignalsSupportBot

📋 **Решаем все вопросы:**
• Техническая поддержка
• Вопросы по оплате
• Активация премиум подписки
• Проблемы с ботом
    """

    keyboard = [
        [InlineKeyboardButton("🤖 Написать в поддержку", url="https://t.me/CryptoSignalsSupportBot")],
        [InlineKeyboardButton("💎 Оформить подписку", callback_data="subscription")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(support_text, parse_mode='Markdown', reply_markup=reply_markup)

def admin_panel(update, context):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        update.message.reply_text("❌ Доступ запрещен")
        return

    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("🎯 Тест сигналов", callback_data="admin_test_signals")],
        [InlineKeyboardButton("💎 Управление премиум", callback_data="admin_manage_premium")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text("👨‍💻 **ПАНЕЛЬ АДМИНИСТРАТОРА**\n\nВыберите действие:", parse_mode='Markdown', reply_markup=reply_markup)

# ================== АДМИН-КОМАНДЫ ==================
def activate_premium_command(update, context):
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("❌ Доступ запрещен")
        return

    if not context.args:
        update.message.reply_text("❌ Использование: /activate_premium <user_id> [дней=30]")
        return

    try:
        target_user_id = int(context.args[0])
        days = int(context.args[1]) if len(context.args) > 1 else 30

        if user_db.activate_premium(target_user_id, days):
            update.message.reply_text(f"✅ Премиум активирован для пользователя {target_user_id} на {days} дней")
            try:
                context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"🎉 **ВАШ ПРЕМИУМ АКТИВИРОВАН!**\n\n"
                         f"Подписка активна на {days} дней\n"
                         "Теперь вам доступны:\n"
                         "• Неограниченные сигналы (100+ монет)\n"
                         "• Pump/Dump мониторинг всех рынков\n"
                         "• Приоритетная поддержка\n\n"
                         "💎 Добро пожаловать в клуб премиум пользователей!",
                    parse_mode='Markdown'
                )
            except Exception:
                print(f"Не удалось уведомить пользователя {target_user_id}")
        else:
            update.message.reply_text("❌ Ошибка активации премиума")

    except ValueError:
        update.message.reply_text("❌ Неверный формат. Использование: /activate_premium <user_id> [дней]")

def deactivate_premium_command(update, context):
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("❌ Доступ запрещен")
        return

    if not context.args:
        update.message.reply_text("❌ Использование: /deactivate_premium <user_id>")
        return

    try:
        target_user_id = int(context.args[0])

        if user_db.deactivate_premium(target_user_id):
            update.message.reply_text(f"✅ Премиум деактивирован для пользователя {target_user_id}")
            try:
                context.bot.send_message(
                    chat_id=target_user_id,
                    text="ℹ️ **ВАША ПРЕМИУМ ПОДПИСКА ЗАВЕРШЕНА**\n\n"
                         "Спасибо что пользовались нашим сервисом!\n"
                         "Для возобновления доступа оформите новую подписку.",
                    parse_mode='Markdown'
                )
            except Exception:
                print(f"Не удалось уведомить пользователя {target_user_id}")
        else:
            update.message.reply_text("❌ Ошибка деактивации премиума")

    except ValueError:
        update.message.reply_text("❌ Неверный user_id")

def check_premium_command(update, context):
    user_id = update.effective_user.id

    if not is_admin(user_id) and not context.args:
        user_data = user_db.get_user(user_id)
        if user_db.check_premium_status(user_id):
            update.message.reply_text("✅ У вас активна премиум подписка!")
        else:
            update.message.reply_text("❌ У вас нет активной премиум подписки")
        return

    if not context.args:
        update.message.reply_text("❌ Использование: /check_premium [user_id]")
        return

    try:
        target_user_id = int(context.args[0])
        is_premium = user_db.check_premium_status(target_user_id)

        if is_premium:
            update.message.reply_text(f"✅ Пользователь {target_user_id} имеет активную премиум подписку")
        else:
            update.message.reply_text(f"❌ Пользователь {target_user_id} не имеет активной премиум подписки")

    except ValueError:
        update.message.reply_text("❌ Неверный user_id")

def list_premium_command(update, context):
    user_id = update.effective_user.id

    if not is_admin(user_id):
        update.message.reply_text("❌ Доступ запрещен")
        return

    premium_users = user_db.get_premium_users()

    if not premium_users:
        update.message.reply_text("📊 Нет активных премиум пользователей")
        return

    message = "📊 **АКТИВНЫЕ ПРЕМИУМ ПОЛЬЗОВАТЕЛИ:**\n\n"
    for idx, (uid, expiry_date) in enumerate(premium_users[:50], 1):
        try:
            expiry = datetime.fromisoformat(expiry_date).strftime('%d.%m.%Y') if expiry_date else "Бессрочно"
            message += f"{idx}. ID: `{uid}` - Истекает: {expiry}\n"
        except Exception:
            message += f"{idx}. ID: `{uid}`\n"

    if len(premium_users) > 50:
        message += f"\n... и еще {len(premium_users) - 50} пользователей"

    update.message.reply_text(message, parse_mode='Markdown')

# ================== CALLBACK И СООБЩЕНИЯ ==================
def button_handler(update, context):
    query = update.callback_query
    query.answer()

    user_id = query.from_user.id
    data = query.data

    if data == "back_to_main":
        query.message.reply_text("🔙 Возврат в главное меню", reply_markup=get_main_keyboard(user_id))

    elif data == "subscription":
        subscription_command(update, context)

    elif data == "support":
        support_command(update, context)

    elif data == "admin_stats":
        if is_admin(user_id):
            stats_text = """
📊 **СТАТИСТИКА СИСТЕМЫ**

👥 **Пользователи:**
• Всего: собираем данные...
• Премиум: собираем данные...
• Активные: собираем данные...

📈 **Сигналы за сегодня:**
• Отправлено: собираем данные...
• Успешных: собираем данные...

⚡ **Система:** Работает стабильно
🔗 **API CoinGecko:** Активно
            """
            query.message.edit_text(stats_text, parse_mode='Markdown')

    elif data == "admin_test_signals":
        if is_admin(user_id):
            signals = run_async(generate_real_signals())
            if signals:
                for signal in signals:
                    query.message.reply_text(signal, parse_mode='Markdown')
            else:
                query.message.reply_text("❌ Ошибка генерации сигналов")

    elif data == "admin_manage_premium":
        if is_admin(user_id):
            keyboard = [
                [InlineKeyboardButton("➕ Активировать премиум", callback_data="admin_activate_premium")],
                [InlineKeyboardButton("➖ Деактивировать премиум", callback_data="admin_deactivate_premium")],
                [InlineKeyboardButton("📋 Список премиум", callback_data="admin_list_premium")],
                [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            query.message.edit_text("💎 **УПРАВЛЕНИЕ ПРЕМИУМ ПОДПИСКАМИ**\n\nВыберите действие:", parse_mode='Markdown', reply_markup=reply_markup)

    elif data == "admin_activate_premium":
        if is_admin(user_id):
            query.message.edit_text(
                "➕ **АКТИВАЦИЯ ПРЕМИУМ**\n\n"
                "Используйте команду:\n"
                "`/activate_premium <user_id> [дней=30]`\n\n"
                "Примеры:\n"
                "`/activate_premium 123456789`\n"
                "`/activate_premium 123456789 90`",
                parse_mode='Markdown'
            )

    elif data == "admin_deactivate_premium":
        if is_admin(user_id):
            query.message.edit_text(
                "➖ **ДЕАКТИВАЦИЯ ПРЕМИУМ**\n\n"
                "Используйте команду:\n"
                "`/deactivate_premium <user_id>`\n\n"
                "Пример:\n"
                "`/deactivate_premium 123456789`",
                parse_mode='Markdown'
            )

    elif data == "admin_list_premium":
        if is_admin(user_id):
            list_premium_command(update, context)

    elif data == "admin_back":
        if is_admin(user_id):
            admin_panel(update, context)

def handle_message(update, context):
    text = update.message.text
    user_id = update.effective_user.id

    admin_commands = [
        '/activate_premium', '/deactivate_premium',
        '/list_premium', '/check_premium', '/check_expired',
        '/expiring_premiums'
    ]

    if any(text.startswith(cmd) for cmd in admin_commands) and not is_admin(user_id):
        update.message.reply_text("❓ Неизвестная команда. Используйте кнопки меню.", reply_markup=get_main_keyboard(user_id))
        return

    if text == "🎯 Сигналы":
        signals_command(update, context)
    elif text == "📈 Pump/Dump":
        pumpdump_command(update, context)
    elif text == "💎 Подписка":
        subscription_command(update, context)
    elif text == "🆘 Поддержка":
        support_command(update, context)
    elif text == "👨‍💻 Админ-панель":
        admin_panel(update, context)
    else:
        update.message.reply_text("🤖 Используйте кнопки меню для навигации", reply_markup=get_main_keyboard(user_id))

# ================== ОСНОВНАЯ ФУНКЦИЯ С ПОВТОРНЫМИ ПОПЫТКАМИ ==================
def start_bot_with_retry():
    """Запуск бота с повторными попытками при конфликте"""
    max_retries = 3
    retry_delay = 30  # секунд
    
    for attempt in range(max_retries):
        try:
            print("=" * 60)
            print(f"🚀 ПОПЫТКА {attempt + 1}/{max_retries} ЗАПУСКА ОСНОВНОГО БОТА")
            print("=" * 60)
            
            from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
            
            updater = Updater(token=BOT_TOKEN, use_context=True)
            
            # КРИТИЧЕСКИ ВАЖНО: сбросить offset перед стартом
            print("🔄 Сбрасываю offset для основного бота...")
            try:
                updater.bot.get_updates(offset=-1)
                print("✅ Offset сброшен успешно")
            except Exception as e:
                print(f"⚠️ Ошибка сброса offset: {e}")
            
            dispatcher = updater.dispatcher
            
            # Все обработчики
            dispatcher.add_handler(CommandHandler("start", start_command))
            dispatcher.add_handler(CommandHandler("signals", signals_command))
            dispatcher.add_handler(CommandHandler("subscription", subscription_command))
            dispatcher.add_handler(CommandHandler("pumpdump", pumpdump_command))
            dispatcher.add_handler(CommandHandler("support", support_command))
            
            # Админ-команды
            dispatcher.add_handler(CommandHandler("activate_premium", activate_premium_command))
            dispatcher.add_handler(CommandHandler("deactivate_premium", deactivate_premium_command))
            dispatcher.add_handler(CommandHandler("check_premium", check_premium_command))
            dispatcher.add_handler(CommandHandler("list_premium", list_premium_command))
            
            # Callback и сообщения
            dispatcher.add_handler(CallbackQueryHandler(button_handler))
            dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
            
            print("✅ Бот готов к работе!")
            print("💎 Система премиум подписок активна")
            print("🔔 Pump/Dump мониторинг доступен премиум пользователям")
            print("=" * 60)
            
            # Запускаем polling с УНИКАЛЬНЫМИ параметрами
            updater.start_polling(
                poll_interval=2.0,  # 2 секунды - УНИКАЛЬНЫЙ интервал
                timeout=20,
                drop_pending_updates=True,
                allowed_updates=['message', 'callback_query']
            )
            
            print("✅ Polling запущен успешно!")
            
            # Бесконечный цикл
            while True:
                time.sleep(1)
                
        except telegram.error.Conflict as e:
            print(f"⚠️ Конфликт обнаружен: {e}")
            if attempt < max_retries - 1:
                print(f"⏳ Жду {retry_delay} секунд перед повторной попыткой...")
                time.sleep(retry_delay)
            else:
                print("❌ Достигнут лимит попыток. Останавливаю бота.")
                break
        except Exception as e:
            print(f"❌ Критическая ошибка: {e}")
            import traceback
            traceback.print_exc()
            break

def main():
    """Основная функция запуска"""
    # Ждем 5 секунд перед запуском (дать время другим сервисам)
    print("⏳ Жду 5 секунд перед запуском основного бота...")
    time.sleep(5)
    
    start_bot_with_retry()

if __name__ == '__main__':
    main()
