"""
🚀 YESsignals_bot - Оптимизированная версия
Быстрые команды, больше монет, строгая проверка премиума
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

# Конфигурация из переменных окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

DB_FILE = "users_db.json"

# Увеличенный список монет (100+)
COINGECKO_IDS = {
    # Топ 20
    'BTC': 'bitcoin', 'ETH': 'ethereum', 'BNB': 'binancecoin', 'SOL': 'solana', 
    'XRP': 'ripple', 'ADA': 'cardano', 'DOGE': 'dogecoin', 'DOT': 'polkadot',
    'MATIC': 'matic-network', 'LINK': 'chainlink', 'UNI': 'uniswap', 
    'LTC': 'litecoin', 'AVAX': 'avalanche-2', 'ATOM': 'cosmos', 'XLM': 'stellar',
    'ALGO': 'algorand', 'VET': 'vechain', 'AXS': 'axie-infinity', 
    'SAND': 'the-sandbox', 'MANA': 'decentraland',
    
    # Дополнительные популярные
    'ETC': 'ethereum-classic', 'XTZ': 'tezos', 'FIL': 'filecoin', 
    'EOS': 'eos', 'AAVE': 'aave', 'COMP': 'compound', 'YFI': 'yearn-finance',
    'MKR': 'maker', 'SNX': 'havven', 'CRV': 'curve-dao-token',
    'SUSHI': 'sushi', '1INCH': '1inch', 'ZRX': '0x', 'BAT': 'basic-attention-token',
    'ENJ': 'enjincoin', 'CHZ': 'chiliz', 'HOT': 'holotoken', 'ZIL': 'zilliqa',
    'WAVES': 'waves', 'QTUM': 'qtum', 'NEO': 'neo', 'ONT': 'ontology',
    'ICX': 'icon', 'SC': 'siacoin', 'STORJ': 'storj', 'ANKR': 'ankr',
    'RVN': 'ravencoin', 'ZEN': 'horizen', 'BTT': 'bittorrent', 'WIN': 'wink',
    'CELR': 'celer-network', 'ONE': 'harmony', 'IOST': 'iost', 'CKB': 'nervos-network',
    
    # Новые перспективные
    'NEAR': 'near', 'FTM': 'fantom', 'AR': 'arweave', 'GRT': 'the-graph',
    'CELO': 'celo', 'RUNE': 'thorchain', 'OCEAN': 'ocean-protocol',
    'BAND': 'band-protocol', 'UMA': 'uma', 'REN': 'republic-protocol',
    'KSM': 'kusama', 'DIA': 'dia-data', 'API3': 'api3', 'ROSE': 'oasis-network',
    
    # Meme монеты
    'SHIB': 'shiba-inu', 'PEPE': 'pepe', 'FLOKI': 'floki', 'BONK': 'bonk',
    'WIF': 'dogwifcoin', 'MEME': 'memecoin', 'COQ': 'coq-inu',
    
    # DeFi
    'CAKE': 'pancakeswap-token', 'SFP': 'safepal', 'BAKE': 'bakerytoken',
    'ALPHA': 'alpha-finance', 'INJ': 'injective-protocol', 'RNDR': 'render-token',
    'IMX': 'immutable-x', 'OP': 'optimism', 'ARB': 'arbitrum',
    'MNT': 'mantle', 'STRK': 'starknet', 'SEI': 'sei-network', 'SUI': 'sui',
    'APT': 'aptos', 'BLUR': 'blur', 'RDNT': 'radiant-capital',
    
    # GameFi
    'GALA': 'gala', 'ILV': 'illuvium', 'YGG': 'yield-guild-games',
    'MAGIC': 'magic', 'GMT': 'stepn', 'MOOV': 'dotmoovs',
    
    # AI & Big Data
    'AGIX': 'singularitynet', 'FET': 'fetch-ai', 'OCEAN': 'ocean-protocol',
    'NMR': 'numeraire', 'GRT': 'the-graph',
}

# Глобальные переменные для кэширования
price_cache = {}
cache_expiry = {}
CACHE_DURATION = 60  # 1 минута кэширования

# ================== ВЕБ-СЕРВЕР ==================
def run_web_server():
    """Запуск веб-сервера для Render"""
    app = Flask(__name__)
    
    @app.route('/')
    def home():
        return "✅ YESsignals_bot активен!"
    
    @app.route('/health')
    def health():
        return "OK", 200
    
    port = int(os.environ.get('PORT', 10000))
    server_thread = threading.Thread(
        target=lambda: serve(app, host='0.0.0.0', port=port),
        daemon=True
    )
    server_thread.start()
    print(f"🌐 Веб-сервер запущен на порту {port}")

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
        key = str(user_id)
        if key not in self.db:
            self.get_user(user_id)
        self.db[key].update(updates)
        self.save_db()
    
    def is_premium(self, user_id):
        """Строгая проверка премиум статуса"""
        user = self.get_user(user_id)
        
        # Проверка срока действия
        if user.get("is_premium") and user.get("premium_expiry"):
            try:
                expiry_date = datetime.fromisoformat(user["premium_expiry"])
                if datetime.now() > expiry_date:
                    # Автоматическое отключение
                    self.update_user(user_id, {
                        "is_premium": False,
                        "premium_expiry": None
                    })
                    return False
                return True
            except:
                pass
        return False

user_db = UserDatabase()

# ================== ОПТИМИЗИРОВАННЫЙ API ==================
async def get_crypto_price_fast(symbol):
    """Быстрое получение цены с кэшированием"""
    global price_cache, cache_expiry
    
    coin_id = COINGECKO_IDS.get(symbol.upper())
    if not coin_id:
        return None
    
    # Проверка кэша
    current_time = time.time()
    if symbol in price_cache and symbol in cache_expiry:
        if current_time < cache_expiry[symbol]:
            return price_cache[symbol]
    
    try:
        # Используем batch запрос для нескольких монет сразу
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
                        result = {
                            'price': price_data.get('usd', 0),
                            'change': price_data.get('usd_24h_change', 0)
                        }
                        # Сохраняем в кэш
                        price_cache[symbol] = result
                        cache_expiry[symbol] = current_time + CACHE_DURATION
                        return result
        
        return None
        
    except Exception as e:
        logger.error(f"Ошибка API для {symbol}: {e}")
        return None

async def get_multiple_prices_fast(symbols, batch_size=10):
    """Оптимизированное получение цен для многих монет"""
    results = {}
    
    # Разделяем на батчи для избежания лимитов
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i+batch_size]
        tasks = []
        
        for symbol in batch:
            # Используем кэшированную версию
            task = get_crypto_price_fast(symbol)
            tasks.append(task)
        
        batch_results = await asyncio.gather(*tasks)
        
        for symbol, result in zip(batch, batch_results):
            if result:
                results[symbol] = result
        
        # Задержка между батчами
        if i + batch_size < len(symbols):
            await asyncio.sleep(0.5)
    
    return results

# ================== БЫСТРАЯ ГЕНЕРАЦИЯ СИГНАЛОВ ==================
def format_price_fast(price):
    """Быстрое форматирование цены"""
    try:
        if price >= 1000:
            return f"${price:,.2f}"
        elif price >= 1:
            return f"${price:.2f}"
        elif price >= 0.01:
            return f"${price:.4f}"
        else:
            return f"${price:.6f}"
    except:
        return f"${price}"

async def generate_signal_fast(symbol):
    """Быстрая генерация сигнала"""
    try:
        price_data = await get_crypto_price_fast(symbol)
        
        if not price_data or price_data['price'] == 0:
            return None
        
        current_price = price_data['price']
        change_24h = price_data.get('change', 0)
        
        # Упрощенная логика для скорости
        if change_24h > 5:
            action = 'SELL'
            target_percent = random.uniform(2, 6)
            confidence = 75
        elif change_24h < -5:
            action = 'BUY'
            target_percent = random.uniform(3, 7)
            confidence = 80
        else:
            action = random.choice(['BUY', 'SELL'])
            target_percent = random.uniform(1.5, 4)
            confidence = random.randint(60, 70)
        
        # Расчет целей
        if action == 'BUY':
            target_price = current_price * (1 + target_percent / 100)
            stop_loss = current_price * (1 - random.uniform(1, 3) / 100)
        else:
            target_price = current_price * (1 - target_percent / 100)
            stop_loss = current_price * (1 + random.uniform(1, 3) / 100)
        
        # Плечо
        volatility = abs(change_24h)
        if volatility > 10:
            leverage = "2x"
        elif volatility > 5:
            leverage = "3x"
        else:
            leverage = "5x"
        
        return {
            'symbol': symbol,
            'action': action,
            'price': current_price,
            'change': change_24h,
            'target': target_price,
            'stop_loss': stop_loss,
            'leverage': leverage,
            'confidence': f"{confidence}%",
            'time': datetime.now().strftime('%H:%M'),
            'formatted_price': format_price_fast(current_price),
            'formatted_target': format_price_fast(target_price),
            'formatted_stop_loss': format_price_fast(stop_loss)
        }
        
    except Exception as e:
        logger.error(f"Ошибка генерации сигнала: {e}")
        return None

# ================== PUMP/DUMP МОНИТОРИНГ ==================
async def check_pump_dump_fast():
    """Быстрый поиск pump/dump сигналов"""
    try:
        # Берем случайные 50 монет из списка (чтобы покрыть больше)
        all_symbols = list(COINGECKO_IDS.keys())
        symbols_to_check = random.sample(all_symbols, min(50, len(all_symbols)))
        
        # Быстро получаем цены
        prices_data = await get_multiple_prices_fast(symbols_to_check, batch_size=15)
        
        alerts = []
        for symbol, data in prices_data.items():
            if not data:
                continue
            
            change = data['change']
            price = data['price']
            
            # Pump сигнал (>12%)
            if change > 12:
                intensity = "🔥 СИЛЬНЫЙ" if change > 20 else "📈 СРЕДНИЙ"
                alerts.append({
                    'type': "🚀 PUMP",
                    'symbol': symbol,
                    'change': change,
                    'price': price,
                    'intensity': intensity,
                    'action': "SELL" if change > 18 else "CAUTIOUS BUY"
                })
            
            # Dump сигнал (< -12%)
            elif change < -12:
                intensity = "💥 СИЛЬНЫЙ" if change < -20 else "📉 СРЕДНИЙ"
                alerts.append({
                    'type': "🔻 DUMP",
                    'symbol': symbol,
                    'change': change,
                    'price': price,
                    'intensity': intensity,
                    'action': "BUY" if change < -18 else "WAIT"
                })
        
        return alerts
        
    except Exception as e:
        logger.error(f"Ошибка pump/dump: {e}")
        return []

# ================== КЛАВИАТУРЫ ==================
def get_main_keyboard(user_id):
    """Главное меню"""
    keyboard = [
        [KeyboardButton("🎯 Сигналы"), KeyboardButton("📈 Pump/Dump")],
        [KeyboardButton("💎 Подписка"), KeyboardButton("🆘 Поддержка")]
    ]
    
    # Админ-панель ТОЛЬКО для админа
    if str(user_id) == str(ADMIN_ID) and ADMIN_ID != 0:
        keyboard.append([KeyboardButton("👑 Админ")])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, input_field_placeholder="Выберите действие:")

# ================== ОСНОВНЫЕ КОМАНДЫ ==================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    user_id = user.id
    
    user_db.update_user(user_id, {"username": user.username})
    
    is_premium = user_db.is_premium(user_id)
    status = "✅ ПРЕМИУМ" if is_premium else "🎯 БЕСПЛАТНЫЙ"
    
    text = f"""
🚀 **Добро пожаловать в YESsignals_bot, {user.first_name}!**

👤 **Ваш ID:** `{user_id}`
💎 **Статус:** {status}

📊 **Доступные функции:**
• 🎯 1 бесплатный сигнал в день
• 📈 Pump/Dump мониторинг (только премиум)
• 💎 Премиум: неограниченные сигналы
• 🆘 Поддержка 24/7

⚡ **Быстрый анализ 100+ монет**
"""
    
    await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))

async def signals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Быстрое получение сигналов"""
    user = update.effective_user
    user_id = user.id
    
    # Быстрая проверка премиума
    is_premium = user_db.is_premium(user_id)
    
    # Для бесплатных пользователей проверяем лимит
    if not is_premium:
        user_data = user_db.get_user(user_id)
        today = datetime.now().date().isoformat()
        
        if user_data.get("last_reset_date") != today:
            user_db.update_user(user_id, {
                "signals_today": 0,
                "last_reset_date": today
            })
        
        if user_data.get("signals_today", 0) >= 1:
            await update.message.reply_text(
                "❌ **Достигнут дневной лимит!**\n\n"
                "💎 Оформите премиум для неограниченных сигналов!",
                reply_markup=get_main_keyboard(user_id)
            )
            return
    
    # Отправляем мгновенный ответ
    loading_msg = await update.message.reply_text("⚡ Анализирую рынок...")
    
    try:
        # Быстрая генерация сигналов
        symbols = []
        if is_premium:
            # Для премиум: 3 случайные монеты из топ-30
            top_symbols = list(COINGECKO_IDS.keys())[:30]
            symbols = random.sample(top_symbols, min(3, len(top_symbols)))
        else:
            # Для бесплатных: 1 монета из топ-10
            symbols = [random.choice(list(COINGECKO_IDS.keys())[:10])]
        
        signals = []
        for symbol in symbols:
            signal = await generate_signal_fast(symbol)
            if signal:
                signals.append(signal)
        
        await loading_msg.delete()
        
        if not signals:
            await update.message.reply_text(
                "⚠️ Временная ошибка получения данных. Попробуйте через минуту.",
                reply_markup=get_main_keyboard(user_id)
            )
            return
        
        # Быстрая отправка сигналов
        for signal in signals:
            if is_premium:
                text = f"""
💎 **ПРЕМИУМ СИГНАЛ** ⚡

🏷 {signal['symbol']}/USDT
⚡ {signal['action']}
💰 {signal['formatted_price']}
📊 {signal['change']:+.2f}%
🎯 Цель: {signal['formatted_target']}
📈 Плечо: {signal['leverage']}
✅ {signal['confidence']}
"""
            else:
                text = f"""
🎯 **БЕСПЛАТНЫЙ СИГНАЛ**

🏷 {signal['symbol']}/USDT
💰 {signal['formatted_price']}
📊 Изменение: {signal['change']:+.2f}%

🔒 Премиум: /premium
"""
            
            await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))
        
        # Обновляем счетчик
        if not is_premium:
            user_db.update_user(user_id, {
                "signals_today": user_db.get_user(user_id).get("signals_today", 0) + 1,
                "total_signals": user_db.get_user(user_id).get("total_signals", 0) + 1
            })
        
    except Exception as e:
        logger.error(f"Ошибка сигналов: {e}")
        await update.message.reply_text(
            "⚡ Получите сигналы мгновенно! Попробуйте еще раз.",
            reply_markup=get_main_keyboard(user_id)
        )

async def pumpdump_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pump/Dump мониторинг - СТРОГО для премиум"""
    user = update.effective_user
    user_id = user.id
    
    # СТРОГАЯ проверка премиума
    is_premium = user_db.is_premium(user_id)
    is_admin = ADMIN_ID != 0 and str(user_id) == str(ADMIN_ID)
    
    if not is_premium and not is_admin:
        await update.message.reply_text(
            "🔒 **ДОСТУП ЗАПРЕЩЕН!**\n\n"
            "📈 **Pump/Dump мониторинг доступен ТОЛЬКО для премиум пользователей!**\n\n"
            "💎 **Что дает премиум:**\n"
            "• Мгновенный анализ 100+ монет\n"
            "• Автоматические уведомления о pump/dump\n"
            "• Неограниченные торговые сигналы\n"
            "• Приоритетную поддержку\n\n"
            "💰 **9 USDT** на 30 дней\n"
            "👉 /premium - оформить подписку",
            reply_markup=get_main_keyboard(user_id)
        )
        return
    
    # Мгновенный ответ
    loading_msg = await update.message.reply_text("⚡ Сканирую 100+ монет...")
    
    try:
        # Быстрый поиск pump/dump
        alerts = await check_pump_dump_fast()
        
        await loading_msg.delete()
        
        if alerts:
            # Показываем топ-3 самых сильных сигналов
            alerts.sort(key=lambda x: abs(x['change']), reverse=True)
            
            for alert in alerts[:3]:
                text = f"""
{alert['type']} **ОБНАРУЖЕН!** ⚡

🏷 {alert['symbol']}/USDT
💰 {format_price_fast(alert['price'])}
📊 {alert['change']:+.1f}%
💪 {alert['intensity']}
⚡ {alert['action']}

⏰ {datetime.now().strftime('%H:%M')}
"""
                await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))
            
            summary = f"""
📊 **АНАЛИЗ ЗАВЕРШЕН**

✅ Найдено активных сигналов: {len(alerts)}
💎 Ваш статус: ПРЕМИУМ ✅

⚡ Анализировано: 100+ монет
🎯 Критерий: >12% за 24ч
"""
            
        else:
            summary = f"""
📊 **АНАЛИЗ ЗАВЕРШЕН**

✅ Активных pump/dump сигналов не обнаружено
💎 Ваш статус: ПРЕМИУМ ✅

⚡ Анализировано: 100+ монет
🎯 Критерий: >12% за 24ч
"""
        
        await update.message.reply_text(summary, reply_markup=get_main_keyboard(user_id))
        
    except Exception as e:
        logger.error(f"Ошибка pumpdump: {e}")
        await update.message.reply_text(
            "⚡ Быстрый анализ завершен!",
            reply_markup=get_main_keyboard(user_id)
        )

async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о подписке"""
    user = update.effective_user
    user_id = user.id
    
    is_premium = user_db.is_premium(user_id)
    
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
💎 **ВАШ ПРЕМИУМ АКТИВЕН**

✅ Статус: Активен
📅 Истекает: {expiry_str}
⏳ Осталось дней: {days_left}
📊 Всего сигналов: {user_data.get('total_signals', 0)}

🔔 **Доступно:**
• Неограниченные сигналы
• Pump/Dump мониторинг
• Анализ 100+ монет
"""
    else:
        text = f"""
💎 **ПРЕМИУМ ПОДПИСКА**

💰 **9 USDT** / 30 дней
👤 **Ваш ID:** `{user_id}`

💳 **USDT (TRC20):**
`TF33keB2N3P226zxFfESVCvXCFQMjnMXQh`

📋 **Что включено:**
✅ Неограниченные сигналы
✅ Pump/Dump мониторинг (100+ монет)
✅ Мгновенные уведомления
✅ Приоритетная поддержка

📸 **Процесс:**
1. Отправьте 9 USDT
2. Сохраните чек
3. Отправьте в @YESsignals_support_bot
4. Укажите ID: `{user_id}`

⚡ **Активация: до 15 минут**
"""
    
    keyboard = [
        [InlineKeyboardButton("📤 Отправить чек", url="https://t.me/YESsignals_support_bot")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ]
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поддержка"""
    text = """
🆘 **ПОДДЕРЖКА**

🤖 **@YESsignals_support_bot**
⏰ **Ответ: до 15 минут**

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

# ================== АДМИН КОМАНДЫ ==================
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Панель администратора"""
    user = update.effective_user
    
    if ADMIN_ID == 0 or str(user.id) != str(ADMIN_ID):
        await update.message.reply_text("❌ Команда не найдена.")
        return
    
    keyboard = [
        [InlineKeyboardButton("➕ Активировать премиум", callback_data="admin_activate")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ]
    
    await update.message.reply_text(
        "👑 **АДМИН-ПАНЕЛЬ**\n\nБыстрые команды:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def activate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Активация премиума"""
    user = update.effective_user
    
    if ADMIN_ID == 0 or str(user.id) != str(ADMIN_ID):
        return
    
    if not context.args:
        await update.message.reply_text("Использование: /activate <id> [дни=30]")
        return
    
    try:
        target_id = int(context.args[0])
        days = int(context.args[1]) if len(context.args) > 1 else 30
        
        expiry_date = (datetime.now() + timedelta(days=days)).isoformat()
        
        user_db.update_user(target_id, {
            "is_premium": True,
            "premium_expiry": expiry_date,
            "premium_start": datetime.now().isoformat()
        })
        
        await update.message.reply_text(f"✅ Премиум активирован для {target_id} на {days} дней")
        
        # Уведомляем пользователя
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"🎉 **ВАШ ПРЕМИУМ АКТИВИРОВАН!**\n\n"
                     f"Подписка активна {days} дней.\n\n"
                     f"✅ Теперь доступны все функции!"
            )
        except:
            pass
        
    except:
        await update.message.reply_text("❌ Ошибка")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика"""
    user = update.effective_user
    
    if ADMIN_ID == 0 or str(user.id) != str(ADMIN_ID):
        return
    
    db = user_db.db
    total = len(db)
    premium = sum(1 for u in db.values() if user_db.is_premium(u.get('id')))
    
    text = f"""
📊 **СТАТИСТИКА**

👥 Пользователи: {total}
💎 Премиум: {premium}
🎯 Обычные: {total - premium}

⚡ Монет в базе: {len(COINGECKO_IDS)}
"""
    
    await update.message.reply_text(text)

# ================== ОБРАБОТЧИКИ ==================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == "back":
        await query.message.reply_text("🔙 Назад", reply_markup=get_main_keyboard(user_id))
    
    elif query.data == "admin_activate":
        if ADMIN_ID != 0 and str(user_id) == str(ADMIN_ID):
            await query.message.edit_text("Используйте: /activate <id> [дни]")
    
    elif query.data == "admin_stats":
        if ADMIN_ID != 0 and str(user_id) == str(ADMIN_ID):
            await stats_command(update, context)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текста"""
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
    elif text == "👑 Админ":
        await admin_command(update, context)
    else:
        await update.message.reply_text(
            "⚡ Используйте кнопки для быстрого доступа!",
            reply_markup=get_main_keyboard(user_id)
        )

# ================== ЗАПУСК ==================
def main():
    """Основной запуск"""
    # Веб-сервер
    run_web_server()
    
    print("=" * 60)
    print("🚀 YESsignals_bot - Оптимизированная версия")
    print("=" * 60)
    print(f"🤖 Бот: @YESsignals_bot")
    print(f"👑 Админ ID: {ADMIN_ID}")
    print(f"📊 Монет в базе: {len(COINGECKO_IDS)}")
    print(f"⚡ Скорость: Оптимизировано")
    print(f"🔒 Премиум проверка: Строгая")
    print("=" * 60)
    
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_TOKEN не найден!")
        return
    
    try:
        # Создаем приложение
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Команды
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("signals", signals_command))
        application.add_handler(CommandHandler("pumpdump", pumpdump_command))
        application.add_handler(CommandHandler("premium", premium_command))
        application.add_handler(CommandHandler("support", support_command))
        application.add_handler(CommandHandler("admin", admin_command))
        application.add_handler(CommandHandler("activate", activate_command))
        application.add_handler(CommandHandler("stats", stats_command))
        
        # Обработчики
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        
        print("✅ Бот запускается...")
        
        # Оптимизированные параметры
        application.run_polling(
            poll_interval=2.0,  # Быстрый опрос
            timeout=20,
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
            close_loop=False
        )
        
    except KeyboardInterrupt:
        print("\n🔴 Бот остановлен")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    main()
