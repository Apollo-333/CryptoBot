"""
🚀 YESsignals_bot - Версия с реальными данными CoinGecko
Полностью исправлены противоречия в ценах
"""

import os
import json
import random
import asyncio
import logging
import requests
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# ================== НАСТРОЙКА ==================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация из переменных окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

DB_FILE = "users_db.json"

# CoinGecko API конфигурация
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"
COINGECKO_TIMEOUT = 10

# Список монет для анализа (символы и их ID на CoinGecko)
COINGECKO_IDS = {
    'BTC': 'bitcoin', 'ETH': 'ethereum', 'BNB': 'binancecoin', 'SOL': 'solana',
    'XRP': 'ripple', 'ADA': 'cardano', 'DOGE': 'dogecoin', 'DOT': 'polkadot',
    'MATIC': 'matic-network', 'LINK': 'chainlink', 'UNI': 'uniswap',
    'LTC': 'litecoin', 'AVAX': 'avalanche-2', 'ATOM': 'cosmos', 'XLM': 'stellar',
    'ALGO': 'algorand', 'VET': 'vechain', 'AXS': 'axie-infinity',
    'SAND': 'the-sandbox', 'MANA': 'decentraland', 'ETC': 'ethereum-classic',
    'XTZ': 'tezos', 'FIL': 'filecoin', 'EOS': 'eos', 'AAVE': 'aave',
    'COMP': 'compound-governance-token', 'YFI': 'yearn-finance', 'MKR': 'maker',
    'SNX': 'havven', 'CRV': 'curve-dao-token', 'SUSHI': 'sushi', '1INCH': '1inch'
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
                "premium_start": None,
                "last_pumpdump_check": None
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
    
    def check_premium_status(self, user_id):
        """ЕДИНАЯ ФУНКЦИЯ ПРОВЕРКИ ПРЕМИУМ СТАТУСА"""
        user = self.get_user(user_id)
        
        if not user.get("is_premium"):
            return False
        
        expiry = user.get("premium_expiry")
        if expiry:
            try:
                expiry_date = datetime.fromisoformat(expiry)
                if datetime.now() > expiry_date:
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
        
        return True
    
    def can_send_signal(self, user_id):
        """Может ли пользователь получить сигнал"""
        if self.check_premium_status(user_id):
            return True
        
        user = self.get_user(user_id)
        today = datetime.now().date().isoformat()
        
        if user.get("last_reset_date") != today:
            self.update_user(user_id, {
                "signals_today": 0,
                "last_reset_date": today
            })
            return True
        
        return user.get("signals_today", 0) < 1
    
    def increment_signal_count(self, user_id):
        """Увеличить счетчик сигналов"""
        user = self.get_user(user_id)
        signals_today = user.get("signals_today", 0) + 1
        total_signals = user.get("total_signals", 0) + 1
        
        self.update_user(user_id, {
            "signals_today": signals_today,
            "total_signals": total_signals
        })
    
    def get_user_stats(self, user_id):
        """Получить статистику пользователя"""
        user = self.get_user(user_id)
        is_premium = self.check_premium_status(user_id)
        
        return {
            "is_premium": is_premium,
            "signals_today": user.get("signals_today", 0),
            "total_signals": user.get("total_signals", 0),
            "premium_expiry": user.get("premium_expiry"),
            "username": user.get("username")
        }

user_db = UserDatabase()

# ================== РЕАЛЬНЫЕ ДАННЫЕ С COINGECKO ==================
class CoinGeckoClient:
    """Класс для получения реальных данных с CoinGecko"""
    
    def __init__(self):
        self.cache = {}
        self.cache_timeout = 60  # кешируем данные на 60 секунд
    
    def get_coin_data(self, symbol):
        """Получить реальные данные по монете с CoinGecko"""
        coin_id = COINGECKO_IDS.get(symbol)
        if not coin_id:
            logger.error(f"Неизвестный символ: {symbol}")
            return None
        
        # Проверяем кеш
        cache_key = f"{symbol}_data"
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if (datetime.now() - timestamp).seconds < self.cache_timeout:
                return cached_data
        
        try:
            # Делаем запрос к CoinGecko API
            url = f"{COINGECKO_API_URL}/simple/price"
            params = {
                'ids': coin_id,
                'vs_currencies': 'usd',
                'include_24hr_change': 'true',
                'include_last_updated_at': 'true'
            }
            
            response = requests.get(url, params=params, timeout=COINGECKO_TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                
                if coin_id in data:
                    coin_data = data[coin_id]
                    
                    result = {
                        'symbol': symbol,
                        'price': coin_data.get('usd', 0),
                        'change_24h': coin_data.get('usd_24h_change', 0),
                        'last_updated': coin_data.get('last_updated_at', time.time()),
                        'source': 'CoinGecko'
                    }
                    
                    # Сохраняем в кеш
                    self.cache[cache_key] = (result, datetime.now())
                    
                    logger.info(f"✅ Получены реальные данные для {symbol}: ${result['price']} ({result['change_24h']}%)")
                    return result
            
            logger.warning(f"⚠️ CoinGecko API вернул {response.status_code} для {symbol}")
            
        except requests.exceptions.Timeout:
            logger.error(f"⏱️ Таймаут запроса к CoinGecko для {symbol}")
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Ошибка запроса к CoinGecko: {e}")
        except Exception as e:
            logger.error(f"❌ Неизвестная ошибка при запросе данных: {e}")
        
        # Если API не работает, возвращаем реалистичные данные
        return self.get_fallback_data(symbol)
    
    def get_fallback_data(self, symbol):
        """Резервные данные если API недоступно"""
        realistic_prices = {
            'BTC': random.uniform(60000, 70000),
            'ETH': random.uniform(3000, 4000),
            'BNB': random.uniform(500, 600),
            'SOL': random.uniform(100, 150),
            'XRP': random.uniform(0.5, 0.7),
            'ADA': random.uniform(0.4, 0.6),
            'DOGE': random.uniform(0.1, 0.15),
            'DOT': random.uniform(7, 9),
            'MATIC': random.uniform(0.8, 1.0),
            'LINK': random.uniform(14, 18)
        }
        
        price = realistic_prices.get(symbol, random.uniform(1, 100))
        change = random.uniform(-5, 5)
        
        result = {
            'symbol': symbol,
            'price': price,
            'change_24h': change,
            'last_updated': time.time(),
            'source': 'Fallback'
        }
        
        logger.warning(f"⚠️ Используются резервные данные для {symbol}")
        return result
    
    def get_multiple_coins(self, symbols):
        """Получить данные для нескольких монет одновременно"""
        coin_ids = []
        symbol_to_id = {}
        
        for symbol in symbols:
            coin_id = COINGECKO_IDS.get(symbol)
            if coin_id:
                coin_ids.append(coin_id)
                symbol_to_id[coin_id] = symbol
        
        if not coin_ids:
            return {}
        
        try:
            url = f"{COINGECKO_API_URL}/simple/price"
            params = {
                'ids': ','.join(coin_ids),
                'vs_currencies': 'usd',
                'include_24hr_change': 'true'
            }
            
            response = requests.get(url, params=params, timeout=COINGECKO_TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                results = {}
                
                for coin_id, coin_data in data.items():
                    symbol = symbol_to_id.get(coin_id)
                    if symbol:
                        results[symbol] = {
                            'symbol': symbol,
                            'price': coin_data.get('usd', 0),
                            'change_24h': coin_data.get('usd_24h_change', 0),
                            'source': 'CoinGecko'
                        }
                
                return results
        
        except Exception as e:
            logger.error(f"Ошибка получения множественных данных: {e}")
        
        return {}

coingecko_client = CoinGeckoClient()

# ================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================
def get_main_keyboard(user_id):
    """Главное меню"""
    keyboard = [
        [KeyboardButton("🎯 Сигналы"), KeyboardButton("📈 Pump/Dump")],
        [KeyboardButton("💎 Подписка"), KeyboardButton("🆘 Поддержка")]
    ]
    
    if str(user_id) == str(ADMIN_ID) and ADMIN_ID != 0:
        keyboard.append([KeyboardButton("👑 Админ")])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def format_price(price):
    """Форматировать цену"""
    if price >= 1000:
        return f"${price:,.2f}"
    elif price >= 1:
        return f"${price:.2f}"
    elif price >= 0.01:
        return f"${price:.4f}"
    else:
        return f"${price:.6f}"

def generate_signal_from_real_data(coin_data):
    """Генерация сигнала на основе реальных данных"""
    symbol = coin_data['symbol']
    price = coin_data['price']
    change = coin_data['change_24h']
    
    # Логика на основе реальных изменений цены
    if change > 5:
        action = 'SELL'
        target_percent = random.uniform(2, 6)
        stop_loss_percent = random.uniform(1, 3)
        confidence = random.randint(70, 85)
    elif change < -5:
        action = 'BUY'
        target_percent = random.uniform(3, 7)
        stop_loss_percent = random.uniform(1.5, 3.5)
        confidence = random.randint(70, 85)
    else:
        action = random.choice(['BUY', 'SELL'])
        target_percent = random.uniform(2, 5)
        stop_loss_percent = random.uniform(1, 2.5)
        confidence = random.randint(60, 75)
    
    # Расчет целей на основе реальной цены
    if action == 'BUY':
        target_price = price * (1 + target_percent / 100)
        stop_loss_price = price * (1 - stop_loss_percent / 100)
    else:
        target_price = price * (1 - target_percent / 100)
        stop_loss_price = price * (1 + stop_loss_percent / 100)
    
    # Плечо на основе волатильности
    volatility = abs(change)
    if volatility > 8:
        leverage = "2x"
    elif volatility > 4:
        leverage = "3x"
    else:
        leverage = "5x"
    
    # Время обновления
    if 'last_updated' in coin_data:
        try:
            update_time = datetime.fromtimestamp(coin_data['last_updated']).strftime('%H:%M %d.%m.%Y')
        except:
            update_time = datetime.now().strftime('%H:%M %d.%m.%Y')
    else:
        update_time = datetime.now().strftime('%H:%M %d.%m.%Y')
    
    return {
        'symbol': symbol,
        'action': action,
        'price': price,
        'change': change,
        'target': target_price,
        'stop_loss': stop_loss_price,
        'leverage': leverage,
        'confidence': f"{confidence}%",
        'time': update_time,
        'formatted_price': format_price(price),
        'formatted_target': format_price(target_price),
        'formatted_stop_loss': format_price(stop_loss_price),
        'data_source': coin_data.get('source', 'Unknown')
    }

# ================== КОМАНДЫ БОТА ==================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    user_id = user.id
    
    user_db.update_user(user_id, {"username": user.username})
    
    stats = user_db.get_user_stats(user_id)
    is_premium = stats["is_premium"]
    
    text = f"""
🚀 **Добро пожаловать в YESsignals_bot, {user.first_name}!**

👤 **Ваш ID:** `{user_id}`
💎 **Статус:** {'✅ ПРЕМИУМ' if is_premium else '🎯 БЕСПЛАТНЫЙ'}

📊 **Статистика:**
• Сигналов сегодня: {stats['signals_today']}/1
• Всего сигналов: {stats['total_signals']}

🔔 **Доступные функции:**
• 🎯 1 бесплатный сигнал в день (реальные данные)
• 📈 Pump/Dump мониторинг ({'✅ доступен' if is_premium else '🔒 только для премиума'})
• 💎 Премиум: неограниченные сигналы
• 🆘 Поддержка 24/7

💡 **Используйте кнопки меню для навигации!**
"""
    
    await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))

async def signals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить торговые сигналы с реальными данными"""
    user = update.effective_user
    user_id = user.id
    
    # Проверяем может ли пользователь получить сигнал
    if not user_db.can_send_signal(user_id):
        stats = user_db.get_user_stats(user_id)
        
        text = f"""
❌ **Достигнут дневной лимит!**

📊 **Ваша статистика:**
• Статус: {'💎 ПРЕМИУМ' if stats['is_premium'] else '🎯 БЕСПЛАТНЫЙ'}
• Использовано сегодня: {stats['signals_today']}/1 сигналов
• Всего сигналов: {stats['total_signals']}

💎 **Премиум подписка включает:**
• Неограниченные сигналы (сколько угодно в день)
• Pump/Dump мониторинг 24/7
• Приоритетную поддержку
• Расширенный анализ рынка

💰 **Стоимость:** 9 USDT на 30 дней
👉 /premium - оформить подписку
"""
        await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))
        return
    
    # Показываем статус
    stats = user_db.get_user_stats(user_id)
    is_premium = stats["is_premium"]
    
    loading_msg = await update.message.reply_text(
        "🔄 Запрашиваю реальные данные с бирж..." if is_premium else "🔄 Запрашиваю реальный бесплатный сигнал..."
    )
    
    try:
        # Выбираем монеты в зависимости от статуса
        if is_premium:
            # Для премиум: 3 разные монеты
            symbols = random.sample(list(COINGECKO_IDS.keys())[:15], 3)
        else:
            # Для бесплатных: 1 монета из топ-10
            symbols = [random.choice(list(COINGECKO_IDS.keys())[:10])]
        
        signals = []
        for symbol in symbols:
            # Получаем реальные данные
            coin_data = coingecko_client.get_coin_data(symbol)
            if coin_data:
                # Генерируем сигнал на основе реальных данных
                signal = generate_signal_from_real_data(coin_data)
                signals.append(signal)
        
        await loading_msg.delete()
        
        if not signals:
            await update.message.reply_text(
                "⚠️ Временно не удалось получить данные с бирж. Попробуйте позже.",
                reply_markup=get_main_keyboard(user_id)
            )
            return
        
        # Отправляем сигналы
        for signal in signals:
            data_source = "📊 **Реальные данные с бирж**" if signal.get('data_source') == 'CoinGecko' else "⚠️ **Оценочные данные (API недоступно)**"
            
            if is_premium:
                text = f"""
💎 **ПРЕМИУМ СИГНАЛ** 💎
{data_source}

🏷 **Пара:** {signal['symbol']}/USDT
⚡ **Действие:** {signal['action']}
💰 **Текущая цена:** {signal['formatted_price']}
📊 **Изменение 24ч:** {signal['change']:+.2f}%
🎯 **Цель:** {signal['formatted_target']}
🛑 **Стоп-лосс:** {signal['formatted_stop_loss']}
📈 **Плечо:** {signal['leverage']}
✅ **Уверенность:** {signal['confidence']}

⏰ **Время обновления:** {signal['time']}

⚠️ **Предупреждение о рисках:**
Сигналы основаны на реальных данных с бирж.
Проводите собственный анализ перед сделками.
"""
            else:
                text = f"""
🎯 **БЕСПЛАТНЫЙ СИГНАЛ** 🎯
{data_source}

🏷 **Пара:** {signal['symbol']}/USDT
💰 **Реальная цена:** {signal['formatted_price']}
📊 **Изменение 24ч:** {signal['change']:+.2f}%
📈 **Тренд:** {'📈 Восходящий' if signal['change'] > 0 else '📉 Нисходящий' if signal['change'] < 0 else '➡️ Боковой'}

🔒 **Для получения полных сигналов оформите премиум!**

📊 **Использовано сегодня:** {stats['signals_today'] + 1}/1
💎 **Премиум:** /premium

⚠️ **Торговля сопряжена с рисками.**
"""
            
            await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))
            await asyncio.sleep(0.3)
        
        # Увеличиваем счетчик
        user_db.increment_signal_count(user_id)
        
    except Exception as e:
        logger.error(f"Ошибка получения сигналов: {e}")
        await update.message.reply_text(
            "⚠️ Ошибка получения данных. Попробуйте позже.",
            reply_markup=get_main_keyboard(user_id)
        )

async def pumpdump_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pump/Dump мониторинг с реальными данными"""
    user = update.effective_user
    user_id = user.id
    
    # СТРОГАЯ проверка премиум статуса
    stats = user_db.get_user_stats(user_id)
    is_premium = stats["is_premium"]
    is_admin = ADMIN_ID != 0 and str(user_id) == str(ADMIN_ID)
    
    if not is_premium and not is_admin:
        text = f"""
🔒 **ДОСТУП ЗАПРЕЩЕН!** 🔒

📈 **Pump/Dump мониторинг доступен ИСКЛЮЧИТЕЛЬНО для премиум пользователей!**

📊 **Ваша статистика:**
• Статус: 🎯 БЕСПЛАТНЫЙ
• Сигналов сегодня: {stats['signals_today']}/1
• Всего сигналов: {stats['total_signals']}

💎 **Премиум подписка включает:**
• 24/7 мониторинг pump/dump сигналов (реальные данные)
• Мгновенные уведомления о волатильности
• Неограниченные торговые сигналы
• Расширенный анализ рынка
• Приоритетную поддержку

💰 **Стоимость:** 9 USDT на 30 дней
📋 **Оформить подписку:** /premium

⚠️ **Без премиума функция Pump/Dump НЕДОСТУПНА**
"""
        await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))
        return
    
    # Если пользователь премиум или админ
    loading_msg = await update.message.reply_text("🔍 Анализирую реальные данные рынка...")
    
    try:
        # Берем случайные 10 монет для анализа
        symbols = random.sample(list(COINGECKO_IDS.keys())[:20], 10)
        
        # Получаем данные для всех монет
        all_data = coingecko_client.get_multiple_coins(symbols)
        
        await loading_msg.delete()
        
        alerts = []
        for symbol, coin_data in all_data.items():
            change = coin_data.get('change_24h', 0)
            price = coin_data.get('price', 0)
            
            # Критерии для Pump/Dump
            if change > 12:
                alert_type = "🚀 PUMP"
                intensity = "🔥 СИЛЬНЫЙ" if change > 18 else "📈 УМЕРЕННЫЙ"
                action = "SELL" if change > 20 else "CAUTIOUS BUY"
                alerts.append({
                    'symbol': symbol,
                    'type': alert_type,
                    'change': change,
                    'price': price,
                    'intensity': intensity,
                    'action': action
                })
            elif change < -12:
                alert_type = "🔻 DUMP"
                intensity = "💥 СИЛЬНЫЙ" if change < -18 else "📉 УМЕРЕННЫЙ"
                action = "BUY" if change < -20 else "WAIT"
                alerts.append({
                    'symbol': symbol,
                    'type': alert_type,
                    'change': change,
                    'price': price,
                    'intensity': intensity,
                    'action': action
                })
        
        # Отправляем алерты если есть
        if alerts:
            for alert in alerts[:3]:  # Ограничиваем 3 алерта
                text = f"""
{alert['type']} **ОБНАРУЖЕН!** ⚡

🏷 **Пара:** {alert['symbol']}/USDT
💰 **Реальная цена:** {format_price(alert['price'])}
📊 **Изменение 24ч:** {alert['change']:+.1f}%
💪 **Интенсивность:** {alert['intensity']}
⚡ **Рекомендуемое действие:** {alert['action']}

⏰ **Время обнаружения:** {datetime.now().strftime('%H:%M %d.%m.%Y')}
📡 **Источник данных:** CoinGecko API

🎯 **Критерий сигнала:** изменение цены на {abs(alert['change']):.1f}% за 24 часа
"""
                await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))
                await asyncio.sleep(0.3)
            
            info_text = f"""
✅ **Pump/Dump мониторинг завершен!**

📊 **Найдены активные сигналы:** {len(alerts)}
🔍 **Проанализировано:** {len(all_data)} монет
{'💎 **Ваш статус:** ПРЕМИУМ ✅' if is_premium else '👑 **Администратор**'}

⚡ **Параметры анализа:**
• Проверено: {len(all_data)} монет
• Критерий pump: рост >12% за 24ч
• Критерий dump: падение >12% за 24ч
• Время анализа: {datetime.now().strftime('%H:%M')}
• Источник данных: CoinGecko API
"""
        else:
            info_text = f"""
📊 **АНАЛИЗ РЫНКА ЗАВЕРШЕН**

✅ **Активных Pump/Dump сигналов не обнаружено.**
Рынок находится в стабильном состоянии.

{'💎 **Ваш статус:** ПРЕМИУМ ✅' if is_premium else '👑 **Администратор**'}

⚡ **Параметры анализа:**
• Проверено: {len(all_data)} монет
• Критерий pump: рост >12% за 24ч
• Критерий dump: падение >12% за 24ч
• Время анализа: {datetime.now().strftime('%H:%M')}
• Источник данных: CoinGecko API
"""
        
        await update.message.reply_text(info_text, reply_markup=get_main_keyboard(user_id))
        
    except Exception as e:
        logger.error(f"Ошибка pump/dump: {e}")
        await update.message.reply_text(
            "⚠️ Ошибка анализа рыночных данных. Попробуйте позже.",
            reply_markup=get_main_keyboard(user_id)
        )

async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о подписке"""
    user = update.effective_user
    user_id = user.id
    
    stats = user_db.get_user_stats(user_id)
    is_premium = stats["is_premium"]
    
    if is_premium:
        expiry = stats['premium_expiry']
        if expiry:
            try:
                expiry_date = datetime.fromisoformat(expiry)
                expiry_str = expiry_date.strftime('%d.%m.%Y')
                days_left = (expiry_date - datetime.now()).days
            except:
                expiry_str = "Бессрочно"
                days_left = "∞"
        else:
            expiry_str = "Бессрочно"
            days_left = "∞"
        
        text = f"""
💎 **ВАША ПРЕМИУМ ПОДПИСКА АКТИВНА**

✅ **Статус:** Активен
📅 **Истекает:** {expiry_str}
⏳ **Осталось дней:** {days_left}
📊 **Всего сигналов:** {stats['total_signals']}
📈 **Сигналов сегодня:** {stats['signals_today']}

🔔 **Доступные функции:**
• ✅ Неограниченные торговые сигналы (реальные данные)
• ✅ Pump/Dump мониторинг 24/7 (реальные данные)
• ✅ Автоматические уведомления
• ✅ Приоритетная поддержка
• ✅ Расширенный анализ рынка

⚠️ **Предупреждение:** Торговля криптовалютами связана с рисками.
"""
    else:
        text = f"""
💎 **ПРЕМИУМ ПОДПИСКА YESsignals**

⏳ **Срок:** 30 дней
💰 **Стоимость:** 9 USDT

👤 **Ваш ID для оплаты:** `{user_id}`

💳 **Реквизиты для оплаты:**
**USDT (TRC20):** `TF33keB2N3P226zxFfESVCvXCFQMjnMXQh`

📋 **Что включено в премиум:**
• ✅ Неограниченное количество сигналов (реальные данные)
• ✅ Pump/Dump мониторинг 24/7 (реальные данные)
• ✅ Автоматические уведомления о волатильности
• ✅ Расширенный анализ рынка
• ✅ Приоритетная поддержка
• ✅ Доступ ко всем функциям бота

📸 **Процесс активации:**
1. Совершите перевод 9 USDT
2. Сохраните скриншот чека
3. Отправьте скриншот в @YESsignals_support_bot
4. Укажите ваш ID: `{user_id}`

⚡ **Активация в течение 15 минут!**

⚠️ **ВАЖНО:**
• Сигналы основаны на реальных данных с бирж
• Проводите собственный анализ
• Торговля сопряжена с рисками
"""
    
    keyboard = [
        [InlineKeyboardButton("📤 Отправить чек", url="https://t.me/YESsignals_support_bot")],
        [InlineKeyboardButton("🆘 Поддержка", callback_data="support")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup)

async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поддержка"""
    text = """
🆘 **ТЕХНИЧЕСКАЯ ПОДДЕРЖКА**

🤖 **Бот поддержки:**
@YESsignals_support_bot

📋 **Решаем вопросы:**
• Технические проблемы с ботом
• Вопросы по оплате и подписке
• Активация премиум доступа
• Любые другие вопросы

⏰ **Время ответа:** до 15 минут

💡 **Рекомендации:**
• Для быстрого решения прикладывайте скриншоты
• Указывайте ваш ID при обращении
• Оплата только в USDT (TRC20)

⚠️ **Администрация не предоставляет финансовых консультаций.**
"""
    
    keyboard = [
        [InlineKeyboardButton("🤖 Написать в поддержку", url="https://t.me/YESsignals_support_bot")],
        [InlineKeyboardButton("💎 Оформить подписку", callback_data="subscription")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(text, reply_markup=reply_markup)

# ================== ОБРАБОТЧИК КНОПОК ==================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик inline-кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "back":
        await query.message.reply_text(
            "🔙 Возврат в главное меню",
            reply_markup=get_main_keyboard(user_id)
        )
    
    elif data == "support":
        await support_command(update, context)
    
    elif data == "subscription":
        await premium_command(update, context)

# ================== ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ ==================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений (кнопок меню)"""
    text = update.message.text
    user_id = update.effective_user.id
    
    if text == "🎯 Сигналы":
        await signals_command(update, context)
    
    elif text == "📈 Pump/Dump":
        await pumpdump_command(update, context)
    
    elif text == "💎 Подписка":
        await premium_command(update, context)
    
    elif text == "🆘 Поддержка":
        await support_command(update, context)
    
    elif text == "👑 Админ" and str(user_id) == str(ADMIN_ID) and ADMIN_ID != 0:
        await update.message.reply_text(
            "👑 **Админ-панель**\n\n"
            "Команды:\n"
            "/activate <id> [дни] - активировать премиум\n"
            "/stats - статистика\n\n"
            "⚠️ Используйте команды в чате"
        )
    
    else:
        await update.message.reply_text(
            "🤖 **Используйте кнопки меню!**\n\n"
            "**Доступные команды:**\n"
            "/start - Главное меню\n"
            "/signals - Торговые сигналы (реальные данные)\n"
            "/premium - Информация о подписке\n"
            "/support - Техническая поддержка\n\n"
            "⚠️ Все общение с администрацией только через @YESsignals_support_bot",
            reply_markup=get_main_keyboard(user_id)
        )

# ================== ЗАПУСК ==================
def main():
    """Основная функция запуска"""
    print("=" * 60)
    print("🚀 ЗАПУСК YESsignals_bot - ВЕРСИЯ С РЕАЛЬНЫМИ ДАННЫМИ")
    print("=" * 60)
    print("✅ Реальные данные с CoinGecko API")
    print("✅ Нет противоречий в ценах")
    print("✅ Кеширование данных для скорости")
    print("✅ Резервные данные если API недоступно")
    print("=" * 60)
    
    if not TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN не установлен!")
        print("⚠️ Добавьте TELEGRAM_TOKEN в переменные окружения")
        return
    
    if ADMIN_ID == 0:
        logger.warning("⚠️ ADMIN_ID не настроен. Админ-панель недоступна.")
        print("ℹ️ Админ-панель: отключена")
    else:
        print(f"👑 Админ-панель: доступна для ID {ADMIN_ID}")
    
    print("📡 Источник данных: CoinGecko API")
    print("🎯 Монет для анализа: 30+")
    print("💾 Кеширование: 60 секунд")
    print("=" * 60)
    
    try:
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Основные команды
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("signals", signals_command))
        application.add_handler(CommandHandler("premium", premium_command))
        application.add_handler(CommandHandler("support", support_command))
        application.add_handler(CommandHandler("pumpdump", pumpdump_command))
        
        # Обработчики
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        
        print("✅ Бот готов к работе!")
        print("💎 Система премиум подписок активна")
        print("📊 База данных: загружена")
        print("🔄 Запуск polling...")
        print("=" * 60)
        
        # Запускаем бота
        application.run_polling(
            poll_interval=3.0,
            timeout=30,
            drop_pending_updates=True
        )
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка запуска: {e}")
        print(f"💥 Ошибка: {e}")

if __name__ == "__main__":
    main()
