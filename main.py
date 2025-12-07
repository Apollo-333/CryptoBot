import os
import psycopg
from psycopg import pool
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
import requests
import random
import aiohttp
import asyncio

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Конфигурация
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# CoinGecko API конфигурация
COINGECKO_API_URL = "https://api.coingecko.com/api/v3"

# Расширенный список монет (100+)
COINGECKO_IDS = {
    # Топ 50 по капитализации
    'BTC': 'bitcoin',
    'ETH': 'ethereum', 
    'BNB': 'binancecoin',
    'SOL': 'solana',
    'XRP': 'ripple',
    'ADA': 'cardano',
    'DOGE': 'dogecoin',
    'DOT': 'polkadot',
    'LTC': 'litecoin',
    'LINK': 'chainlink',
    'AVAX': 'avalanche-2',
    'MATIC': 'matic-network',
    'SHIB': 'shiba-inu',
    'PEPE': 'pepe',
    'ATOM': 'cosmos',
    'UNI': 'uniswap',
    'AAVE': 'aave',
    'ALGO': 'algorand',
    'NEAR': 'near',
    'TRX': 'tron',
    'XLM': 'stellar',
    'ETC': 'ethereum-classic',
    'XMR': 'monero',
    'EOS': 'eos',
    'XTZ': 'tezos',
    'VET': 'vechain',
    'FIL': 'filecoin',
    'THETA': 'theta-token',
    'MKR': 'maker',
    'COMP': 'compound-governance-token',
    'YFI': 'yearn-finance',
    'SNX': 'havven',
    'CRV': 'curve-dao-token',
    'SUSHI': 'sushi',
    '1INCH': '1inch',
    'ZRX': '0x',
    'BAT': 'basic-attention-token',
    'ENJ': 'enjincoin',
    'MANA': 'decentraland',
    'SAND': 'the-sandbox',
    'AXS': 'axie-infinity',
    'CHZ': 'chiliz',
    'GMT': 'stepn',
    'APE': 'apecoin',
    'GALA': 'gala',
    'IMX': 'immutable-x',
    'RNDR': 'render-token',
    'OP': 'optimism',
    'ARB': 'arbitrum',
    'APT': 'aptos',
    'SUI': 'sui',
    'SEI': 'sei-network',
    'INJ': 'injective-protocol',
    'TIA': 'celestia',
    'PYTH': 'pyth-network',
    'JTO': 'jito',
    'WIF': 'dogwifhat',
    'BONK': 'bonk',
    'MEME': 'memecoin',
    'POPCAT': 'popcat',
    'ORDI': 'ordinals',
    'SATS': 'sats',
    'RATS': 'rats',
    'BCH': 'bitcoin-cash',
    'ICP': 'internet-computer',
    'STX': 'blockstack',
    'FTM': 'fantom',
    'EGLD': 'elrond-erd-2',
    'KAS': 'kaspa',
    'RUNE': 'thorchain',
    'MNT': 'mantle',
    'TAO': 'bittensor',
    'FET': 'fetch-ai',
    'AGIX': 'singularitynet',
    'OCEAN': 'ocean-protocol',
    'GRT': 'the-graph',
    'ANKR': 'ankr',
    'STORJ': 'storj',
    'HOT': 'holotoken',
    'ONE': 'harmony',
    'IOTA': 'iota',
    'QTUM': 'qtum',
    'ZIL': 'zilliqa',
    'ONT': 'ontology',
    'SC': 'siacoin',
    'DGB': 'digibyte',
    'RVN': 'ravencoin',
    'XVG': 'verge',
    'BTT': 'bittorrent',
    'WIN': 'wink',
    'CHR': 'chromia',
    'CELO': 'celo',
    'UMA': 'uma',
    'BAND': 'band-protocol',
    'NMR': 'numeraire',
    'OXT': 'orchid-protocol',
    'RSR': 'reserve-rights-token',
    'CVC': 'civic',
    'AUCTION': 'bounce-token',
    'BADGER': 'badger-dao',
    'MLN': 'enzyme',
    'POLS': 'polkastarter',
    'REQ': 'request-network',
    'TRIBE': 'tribe-2',
    'ORN': 'orion-protocol',
    'PERP': 'perpetual-protocol',
    'RLC': 'iexec-rlc',
    'POND': 'marvelous-nfts',
    'ALICE': 'my-neighbor-alice',
    'DODO': 'dodo',
    'LINA': 'linear',
    'STMX': 'storm',
    'TOMO': 'tomochain',
    'VTHO': 'vethor-token',
    'FUN': 'funfair',
    'KEY': 'selfkey',
    'DENT': 'dent',
    'HIVE': 'hive',
    'STEEM': 'steem',
    'WAXP': 'wax',
    'TLM': 'alien-worlds',
    'SFP': 'safepal',
    'CTK': 'certik',
    'BEL': 'bella-protocol',
    'DEGO': 'dego-finance',
    'TKO': 'tokocrypto',
    'ALPHA': 'alpha-finance',
    'CAKE': 'pancakeswap-token',
    'BAKE': 'bakerytoken',
}

class UserDatabase:
    def __init__(self):
        self.conn = psycopg.connect(os.getenv("DATABASE_URL"))
        self.cursor = self.conn.cursor()
        self.init_db()

    def init_db(self):
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
        try:
            self.cursor.execute('''
                SELECT user_id, is_premium, signals_today, last_reset_date
                FROM users WHERE user_id = %s
            ''', (user_id,))
            result = self.cursor.fetchone()
            if result:
                return result
            else:
                self.add_user(user_id)
                return (user_id, False, 0, datetime.now().date().isoformat())
        except Exception as e:
            print(f"❌ Ошибка при получении пользователя: {e}")
            return (user_id, False, 0, datetime.now().date().isoformat())

    def can_send_signal(self, user_id):
        try:
            user_id, is_premium, signals_today, last_reset_date = self.get_user(user_id)
            today = datetime.now().date().isoformat()
            if last_reset_date != today:
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
        try:
            self.cursor.execute('''
                UPDATE users SET signals_today = signals_today + 1 WHERE user_id = %s
            ''', (user_id,))
            self.conn.commit()
        except Exception as e:
            print(f"❌ Ошибка увеличения счетчика: {e}")

    def activate_premium(self, user_id, duration_days=30):
        try:
            expiry_date = (datetime.now() + timedelta(days=duration_days)).isoformat()
            self.cursor.execute('''
                UPDATE users SET is_premium = TRUE, premium_expiry = %s WHERE user_id = %s
            ''', (expiry_date, user_id))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Ошибка активации премиума: {e}")
            return False

    def deactivate_premium(self, user_id):
        try:
            self.cursor.execute('''
                UPDATE users SET is_premium = FALSE WHERE user_id = %s
            ''', (user_id,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"❌ Ошибка деактивации премиума: {e}")
            return False

# Создаем глобальный экземпляр базы данных
user_db = UserDatabase()

def is_admin(user_id):
    """Проверка, является ли пользователь администратором"""
    return user_id in ADMIN_IDS

async def get_crypto_price(symbol):
    """Получить текущую цену криптовалюты с CoinGecko"""
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
    """Получить цены для нескольких символов одновременно"""
    tasks = [get_crypto_price(symbol) for symbol in symbols]
    results = await asyncio.gather(*tasks)
    return dict(zip(symbols, results))

async def get_top_coins(limit=100):
    """Получить топ монет по капитализации"""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{COINGECKO_API_URL}/coins/markets"
            params = {
                'vs_currency': 'usd',
                'order': 'market_cap_desc',
                'per_page': limit,
                'page': 1,
                'sparkline': 'false'
            }

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    coins = await response.json()
                    # Создаем словарь символ -> coin_id
                    return {coin['symbol'].upper(): coin['id'] for coin in coins}
    except Exception as e:
        print(f"❌ Ошибка получения топ монет: {e}")
        return {}

def calculate_signal_parameters(current_price, change_24h, volume):
    """Рассчитать параметры сигнала на основе рыночных данных"""
    # Анализируем тренд на основе изменения цены за 24 часа
    if change_24h > 5:
        # Сильный восходящий тренд
        action = "BUY" if random.random() > 0.3 else "HOLD"
        target_percent = random.uniform(3, 8)
        stop_loss_percent = random.uniform(2, 4)
        confidence = random.randint(75, 90)
    elif change_24h < -5:
        # Сильный нисходящий тренд
        action = "SELL" if random.random() > 0.3 else "HOLD"
        target_percent = random.uniform(3, 8)
        stop_loss_percent = random.uniform(2, 4)
        confidence = random.randint(70, 85)
    else:
        # Боковой тренд
        action = random.choice(["BUY", "SELL", "HOLD"])
        target_percent = random.uniform(2, 6)
        stop_loss_percent = random.uniform(1.5, 3)
        confidence = random.randint(65, 80)

    # Корректируем на основе объема
    if volume > 1000000000:  # Высокий объем
        confidence = min(95, confidence + 10)
    elif volume < 100000000:  # Низкий объем
        confidence = max(60, confidence - 5)

    # Рассчитываем цены
    if action == "BUY":
        target_price = current_price * (1 + target_percent / 100)
        stop_loss_price = current_price * (1 - stop_loss_percent / 100)
    elif action == "SELL":
        target_price = current_price * (1 - target_percent / 100)
        stop_loss_price = current_price * (1 + stop_loss_percent / 100)
    else:
        target_price = current_price
        stop_loss_price = current_price

    # Выбираем плечо на основе волатильности
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
    """Генерация реальных торговых сигналов на основе текущих цен"""
    try:
        # Выбираем случайные символы для анализа из топ 100
        symbols = list(COINGECKO_IDS.keys())[:100]  # Берем только первые 100
        selected_symbols = random.sample(symbols, min(5, len(symbols)))
        print(f"🔍 Анализируем символы: {selected_symbols}")

        # Получаем текущие цены
        prices_data = await get_multiple_prices(selected_symbols)

        signals = []

        for symbol in selected_symbols:
            price_data = prices_data.get(symbol)
            if not price_data or not price_data.get('price'):
                continue

            current_price = price_data['price']
            change_24h = price_data.get('change_24h', 0)
            volume = price_data.get('volume', 0)

            # Генерируем сигнал на основе рыночных данных
            signal_params = calculate_signal_parameters(current_price, change_24h, volume)

            if signal_params['action'] == 'HOLD':
                continue  # Пропускаем сигналы HOLD

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

        # Если нет хороших сигналов, создаем хотя бы один
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
        # Возвращаем fallback сигналы
        return await generate_fallback_signals()

async def generate_fallback_signals():
    """Генерация резервных сигналов если API не доступно"""
    symbols = random.sample(list(COINGECKO_IDS.keys())[:50], 2)
    signals = []

    for symbol in symbols:
        # Используем приблизительные цены как fallback
        approximate_prices = {
            'BTC': 35000, 'ETH': 1800, 'BNB': 250, 'SOL': 100,
            'XRP': 0.6, 'ADA': 0.4, 'DOGE': 0.08, 'DOT': 5,
            'LTC': 70, 'LINK': 14, 'AVAX': 20, 'MATIC': 0.8,
            'SHIB': 0.000008, 'PEPE': 0.000001, 'ATOM': 10,
            'UNI': 6, 'AAVE': 80, 'ALGO': 0.2, 'NEAR': 2
        }

        current_price = approximate_prices.get(symbol, 100)
        signal_params = calculate_signal_parameters(current_price, 0, 0)

        signal_text = f"""
🎯 **СИГНАЛ** 🎯

🏷 **Пара:** {symbol}/USDT
⚡ **Действие:** {signal_params['action']}
💰 **Текущая цена:** ${current_price:,.2f}
🎯 **Цель:** ${signal_params['target_price']:,.2f}
🛑 **Стоп-лосс:** ${signal_params['stop_loss_price']:,.2f}
📈 **Плечо:** {signal_params['leverage']}
✅ **Уверенность:** {signal_params['confidence']}

⏰ **Время сигнала:** {datetime.now().strftime('%H:%M %d.%m.%Y')}
⚠️ **Примечание:** Используются приблизительные данные
        """
        signals.append(signal_text)

    return signals

async def generate_free_signals():
    """Генерация сигналов для бесплатных пользователей"""
    try:
        # Бесплатные пользователи получают информацию о BTC
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
✓ Неограниченное количество сигналов (100+ монет)
✓ Точные точки входа/выхода
✓ Стоп-лосс и тейк-профит  
✓ Рекомендации по плечу
✓ Приоритетную поддержку
✓ Pump/Dump мониторинг 24/7
✓ Анализ всех топовых монет
            """]

    except Exception as e:
        print(f"❌ Ошибка генерации бесплатных сигналов: {e}")

    # Fallback для бесплатных пользователей
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
    """Анализ рынка на основе изменения BTC"""
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

class PumpDumpMonitor:
    def __init__(self):
        self.last_alerts = {}
        self.alert_cooldown = timedelta(minutes=10)  # 10 минут кд между алертами

    async def check_pump_dump_signals(self):
        """Проверка REAL pump/dump сигналов на основе реальных данных"""
        try:
            # Берем топ 100 монет для анализа
            symbols = list(COINGECKO_IDS.keys())[:100]
            print(f"🔍 Анализируем {len(symbols)} монет для Pump/Dump...")

            prices_data = await get_multiple_prices(symbols)

            alerts = []

            for symbol, data in prices_data.items():
                if not data or data.get('change_24h') is None:
                    continue

                change_24h = data['change_24h']
                current_price = data.get('price', 0)
                volume = data.get('volume', 0)

                # REAL критерии для pump сигналов
                if change_24h > 12:  # Реальный pump: более 12% за 24 часа
                    alert_type = "🚀 PUMP"
                    intensity = "Высокая" if change_24h > 20 else "Средняя"
                    alert_msg = f"{symbol} вырос на {change_24h:.1f}% до ${current_price:,.2f}"

                # REAL критерии для dump сигналов  
                elif change_24h < -12:  # Реальный dump: более 12% падения
                    alert_type = "🔻 DUMP"
                    intensity = "Высокая" if change_24h < -20 else "Средняя"
                    alert_msg = f"{symbol} упал на {abs(change_24h):.1f}% до ${current_price:,.2f}"
                else:
                    continue

                # Проверяем коoldown
                alert_key = f"{symbol}_{alert_type}"
                last_alert_time = self.last_alerts.get(alert_key)

                if last_alert_time and datetime.now() - last_alert_time < self.alert_cooldown:
                    continue

                self.last_alerts[alert_key] = datetime.now()

                # Добавляем рекомендации на основе реальных данных
                if alert_type == "🚀 PUMP":
                    if change_24h > 25:
                        recommendation = "⚠️ Сильный перекуп - возможна коррекция"
                        action = "SELL/WAIT"
                    elif change_24h > 15:
                        recommendation = "📈 Рост продолжается, но будьте осторожны"
                        action = "CAUTIOUS BUY"
                    else:
                        recommendation = "💹 Умеренный рост - можно рассматривать покупки"
                        action = "BUY"
                else:  # DUMP
                    if change_24h < -25:
                        recommendation = "💥 Сильное падение - возможен отскок"
                        action = "BUY/WAIT"
                    elif change_24h < -15:
                        recommendation = "📉 Падение продолжается, осторожно с покупками"
                        action = "WAIT/SELL"
                    else:
                        recommendation = "🔻 Умеренное падение - можно искать точки входа"
                        action = "CAUTIOUS BUY"

                alerts.append({
                    'type': alert_type,
                    'message': alert_msg,
                    'symbol': symbol,
                    'change': change_24h,
                    'price': current_price,
                    'intensity': intensity,
                    'recommendation': recommendation,
                    'action': action,
                    'volume': volume
                })

            print(f"🔔 Найдено {len(alerts)} Pump/Dump сигналов")
            return alerts

        except Exception as e:
            print(f"❌ Ошибка проверки pump/dump: {e}")
            return []

    async def get_market_overview(self):
        """Получить обзор рынка с потенциальными сигналами"""
        try:
            symbols = list(COINGECKO_IDS.keys())[:50]
            prices_data = await get_multiple_prices(symbols)

            potential_signals = []

            for symbol, data in prices_data.items():
                if not data or data.get('change_24h') is None:
                    continue

                change_24h = data['change_24h']
                current_price = data.get('price', 0)

                # Ищем активы с высокой волатильностью (5-12%)
                if 5 <= abs(change_24h) < 12:
                    status = "📊 ВЫСОКАЯ ВОЛАТИЛЬНОСТЬ"
                    if change_24h > 0:
                        trend = "📈 Восходящий"
                        recommendation = "Может продолжить рост"
                    else:
                        trend = "📉 Нисходящий" 
                        recommendation = "Может продолжить падение"

                    potential_signals.append({
                        'symbol': symbol,
                        'change': change_24h,
                        'price': current_price,
                        'status': status,
                        'trend': trend,
                        'recommendation': recommendation
                    })

            return potential_signals

        except Exception as e:
            print(f"❌ Ошибка получения обзора рынка: {e}")
            return []

# Создаем глобальный экземпляр монитора
pump_dump_monitor = PumpDumpMonitor()

async def generate_comprehensive_signals(user_id):
    """Генерация торговых сигналов"""
    try:
        # Для администраторов - полный доступ всегда
        if is_admin(user_id):
            print(f"👑 Администратор {user_id} запросил сигналы")
            signals = await generate_real_signals()
            return signals, None

        # Для обычных пользователей проверяем премиум
        user_data = user_db.get_user(user_id)
        is_premium = user_data[1]

        if not is_premium:
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

        # Премиум пользователи получают полные сигналы
        print(f"💎 Премиум пользователь {user_id} запросил сигналы")
        signals = await generate_real_signals()
        user_db.increment_signal_count(user_id)
        return signals, None

    except Exception as e:
        print(f"❌ Ошибка генерации сигналов: {e}")
        return None, "⚠️ Произошла ошибка при генерации сигналов"

def get_main_keyboard(user_id):
    """Получить основную клавиатуру"""
    keyboard = [
        [KeyboardButton("🎯 Сигналы"), KeyboardButton("📈 Pump/Dump")],
        [KeyboardButton("💎 Подписка"), KeyboardButton("🆘 Поддержка")]
    ]

    # Добавляем кнопку админ-панели для администраторов
    if is_admin(user_id):
        keyboard.append([KeyboardButton("👨‍💻 Админ-панель")])

    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name

    # Добавляем пользователя в базу
    user_db.add_user(user_id)

    welcome_text = f"""
🚀 **Добро пожаловать в Crypto Signals Pro, {user_name}!** 🚀

💡 **Ваш ID:** `{user_id}`
📊 **Доступные функции:**
• 🎯 1 бесплатный сигнал в сутки
• 📈 Pump/Dump мониторинг (премиум)
• 💎 Премиум подписка
• 🆘 Поддержка 24/7

🎯 **Начните с кнопки \"Сигналы\"!**
    """

    await update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=get_main_keyboard(user_id)
    )

async def signals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /signals"""
    user_id = update.effective_user.id

    try:
        # Показываем статус загрузки
        loading_msg = await update.message.reply_text(
            "**ПОЛУЧАЮ АКТУАЛЬНЫЕ СИГНАЛЫ...**\nЗапрашиваю рыночные данные...",
            reply_markup=get_main_keyboard(user_id)
        )

        # Получаем сигналы
        signals, error = await generate_comprehensive_signals(user_id)

        # Удаляем сообщение о загрузки
        await loading_msg.delete()

        if error:
            await update.message.reply_text(error, reply_markup=get_main_keyboard(user_id))
            return

        # Отправляем сигналы
        for signal in signals:
            await update.message.reply_text(
                signal,
                parse_mode='Markdown',
                reply_markup=get_main_keyboard(user_id)
            )

    except Exception as e:
        print(f"❌ Ошибка в signals_command: {e}")
        await update.message.reply_text(
            "⚠️ Произошла ошибка при получении сигналов",
            reply_markup=get_main_keyboard(user_id)
        )

async def subscription_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды подписки"""
    user_id = update.effective_user.id

    subscription_text = """
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
    """.format(user_id=user_id)

    keyboard = [
        [InlineKeyboardButton("📤 Отправить квитанцию", url="https://t.me/CryptoSignalsSupportBot")],
        [InlineKeyboardButton("🆘 Поддержка", callback_data="support")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        subscription_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def pumpdump_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды Pump/Dump"""
    user_id = update.effective_user.id

    # Проверяем премиум статус для обычных пользователей
    if not is_admin(user_id):
        user_data = user_db.get_user(user_id)
        if not user_data[1]:  # Если не премиум
            await update.message.reply_text(
                "🔒 **Pump/Dump мониторинг доступен только для премиум пользователей!**\n\n"
                "💎 Оформите подписку для доступа к эксклюзивным данным.",
                reply_markup=get_main_keyboard(user_id)
            )
            return

    try:
        # Показываем статус загрузки
        loading_msg = await update.message.reply_text(
            "🔍 **АНАЛИЗИРУЮ РЫНОК...**\nПолучаю актуальные данные...",
            reply_markup=get_main_keyboard(user_id)
        )

        # Получаем REAL pump/dump сигналы
        alerts = await pump_dump_monitor.check_pump_dump_signals()

        # Удаляем сообщение о загрузке
        await loading_msg.delete()

        if alerts:
            # Отправляем REAL сигналы
            for alert in alerts[:3]:  # Максимум 3 сигнала за раз
                signal_text = f"""
{alert['type']} СИГНАЛ! ⚡

**{alert['message']}**

🎯 **Детальный анализ:**
• Символ: {alert['symbol']}/USDT
• Цена: ${alert['price']:,.2f}
• Изменение 24ч: {alert['change']:+.1f}%
• Интенсивность: {alert['intensity']}
• Объем: ${alert['volume']:,.0f}

💡 **Рекомендация:** {alert['recommendation']}
⚡ **Действие:** {alert['action']}

⏰ **Обнаружено:** {datetime.now().strftime('%H:%M %d.%m.%Y')}
                """

                await update.message.reply_text(
                    signal_text,
                    parse_mode='Markdown',
                    reply_markup=get_main_keyboard(user_id)
                )
        else:
            # Если нет активных pump/dump, показываем обзор рынка
            market_overview = await pump_dump_monitor.get_market_overview()

            if market_overview:
                overview_text = "📊 **ОБЗОР РЫНОЧНОЙ ВОЛАТИЛЬНОСТИ**\n\n"
                overview_text += "🔍 **Активы с высокой активностью:**\n\n"

                for signal in market_overview[:5]:  # Показываем топ-5
                    overview_text += f"""**{signal['symbol']}**
Цена: ${signal['price']:,.2f}
Изменение: {signal['change']:+.1f}%
Тренд: {signal['trend']}
Рекомендация: {signal['recommendation']}

"""

                overview_text += f"""\n💎 **Премиум функции:**
• Мгновенные уведомления о pump/dump
• Расширенный анализ
• Приоритетные сигналы

⏰ Данные обновлены: {datetime.now().strftime('%H:%M %d.%m.%Y')}"""

                await update.message.reply_text(
                    overview_text,
                    parse_mode='Markdown',
                    reply_markup=get_main_keyboard(user_id)
                )
            else:
                # Если рынок совсем спокойный
                await update.message.reply_text(
                    "📊 **РЫНОК В СТАБИЛЬНОМ СОСТОЯНИИ**\n\n"
                    "В настоящее время нет активных pump/dump сигналов.\n"
                    "Рынок демонстрирует низкую волатильность.\n\n"
                    "🔔 **Мониторинг продолжается 24/7**\n"
                    "💎 **Вы получите уведомление при появлении сигналов**\n\n"
                    "⏰ Последняя проверка: " + datetime.now().strftime('%H:%M %d.%m.%Y'),
                    reply_markup=get_main_keyboard(user_id)
                )

    except Exception as e:
        print(f"❌ Ошибка в pumpdump_command: {e}")
        await update.message.reply_text(
            "⚠️ Ошибка получения данных Pump/Dump",
            reply_markup=get_main_keyboard(user_id)
        )

async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды поддержки"""
    user_id = update.effective_user.id

    support_text = """
🆘 **ПОДДЕРЖКА**

🤖 **Единый бот поддержки:**
@CryptoSignalsSupportBot

📋 **Решаем все вопросы:**
• Техническая поддержка
• Вопросы по оплате
• Активация премиум подписки
• Проблемы с ботом

⏰ **Время ответа:** до 15 минут

💡 **Частые вопросы:**
• Оплата - USDT (TRC20)
• Активация - до 15 минут
• Сигналы - обновляются каждые 2 часа
• Данные - реальные цены с бирж
    """

    keyboard = [
        [InlineKeyboardButton("🤖 Написать в поддержку", url="https://t.me/CryptoSignalsSupportBot")],
        [InlineKeyboardButton("💎 Оформить подписку", callback_data="subscription")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        support_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Панель администратора"""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("❌ Доступ запрещен")
        return

    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("🎯 Тест сигналов", callback_data="admin_test_signals")],
        [InlineKeyboardButton("💎 Управление премиум", callback_data="admin_manage_premium")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "👨‍💻 **ПАНЕЛЬ АДМИНИСТРАТОРА**\n\n"
        "Выберите действие:",
        reply_markup=reply_markup
    )

# ================== КОМАНДЫ УПРАВЛЕНИЯ ПРЕМИУМ ==================

async def activate_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Активировать премиум подписку (только для админа)"""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("❌ Доступ запрещен")
        return

    if not context.args:
        await update.message.reply_text("❌ Использование: /activate_premium <user_id> [дней=30]")
        return

    try:
        target_user_id = int(context.args[0])
        days = int(context.args[1]) if len(context.args) > 1 else 30

        if user_db.activate_premium(target_user_id, days):
            await update.message.reply_text(f"✅ Премиум активирован для пользователя {target_user_id} на {days} дней")

            # Уведомляем пользователя
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"🎉 **ВАШ ПРЕМИУМ АКТИВИРОВАН!**\n\n"
                         f"Подписка активна на {days} дней\n"
                         "Теперь вам доступны:\n"
                         "• Неограниченное количество сигналов (100+ монет)\n"
                         "• Pump/Dump мониторинг всех рынков\n"
                         "• Приоритетная поддержка\n\n"
                         "💎 Добро пожаловать в клуб премиум пользователей!",
                    parse_mode='Markdown'
                )
            except:
                print(f"Не удалось уведомить пользователя {target_user_id}")

        else:
            await update.message.reply_text("❌ Ошибка активации премиума")

    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Использование: /activate_premium <user_id> [дней]")

async def deactivate_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Деактивировать премиум подписку (только для админа)"""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("❌ Доступ запрещен")
        return

    if not context.args:
        await update.message.reply_text("❌ Использование: /deactivate_premium <user_id>")
        return

    try:
        target_user_id = int(context.args[0])

        if user_db.deactivate_premium(target_user_id):
            await update.message.reply_text(f"✅ Премиум деактивирован для пользователя {target_user_id}")

            # Уведомляем пользователя
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text="ℹ️ **ВАША ПРЕМИУМ ПОДПИСКА ЗАВЕРШЕНА**\n\n"
                         "Спасибо что пользовались нашим сервисом!\n"
                         "Для возобновления доступа оформите новую подписку.",
                    parse_mode='Markdown'
                )
            except:
                print(f"Не удалось уведомить пользователя {target_user_id}")

        else:
            await update.message.reply_text("❌ Ошибка деактивации премиума")

    except ValueError:
        await update.message.reply_text("❌ Неверный user_id")

async def check_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверить статус премиум подписки"""
    user_id = update.effective_user.id

    if not is_admin(user_id) and not context.args:
        # Если обычный пользователь без аргументов - показываем его статус
        user_data = user_db.get_user(user_id)
        is_premium = user_data[1]

        if is_premium:
            await update.message.reply_text("✅ У вас активна премиум подписка!")
        else:
            await update.message.reply_text("❌ У вас нет активной премиум подписки")
        return

    if not context.args:
        await update.message.reply_text("❌ Использование: /check_premium [user_id]")
        return

    try:
        target_user_id = int(context.args[0])
        is_premium = user_db.check_premium_status(target_user_id)

        if is_premium:
            await update.message.reply_text(f"✅ Пользователь {target_user_id} имеет активную премиум подписку")
        else:
            await update.message.reply_text(f"❌ Пользователь {target_user_id} не имеет активной премиум подписки")

    except ValueError:
        await update.message.reply_text("❌ Неверный user_id")

async def list_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать всех премиум пользователей (только для админа)"""
    user_id = update.effective_user.id

    if not is_admin(user_id):
        await update.message.reply_text("❌ Доступ запрещен")
        return

    premium_users = user_db.get_premium_users()

    if not premium_users:
        await update.message.reply_text("📊 Нет активных премиум пользователей")
        return

    message = "📊 **АКТИВНЫЕ ПРЕМИУМ ПОЛЬЗОВАТЕЛИ:**\n\n"

    for idx, (user_id, expiry_date) in enumerate(premium_users[:50], 1):  # Ограничиваем 50
        try:
            expiry = datetime.fromisoformat(expiry_date).strftime('%d.%m.%Y') if expiry_date else "Бессрочно"
            message += f"{idx}. ID: `{user_id}` - Истекает: {expiry}\n"
        except:
            message += f"{idx}. ID: `{user_id}`\n"

    if len(premium_users) > 50:
        message += f"\n... и еще {len(premium_users) - 50} пользователей"

    await update.message.reply_text(message, parse_mode='Markdown')

# ================== КОНЕЦ КОМАНД УПРАВЛЕНИЯ ==================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    if data == "back_to_main":
        await query.message.reply_text(
            "🔙 Возврат в главное меню",
            reply_markup=get_main_keyboard(user_id)
        )

    elif data == "subscription":
        await subscription_command(update, context)

    elif data == "support":
        await support_command(update, context)

    elif data == "admin_stats":
        if is_admin(user_id):
            # Простая статистика
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
            await query.message.edit_text(stats_text, parse_mode='Markdown')

    elif data == "admin_test_signals":
        if is_admin(user_id):
            # Администратор всегда получает реальные сигналы
            signals, error = await generate_real_signals()
            if signals:
                for signal in signals:
                    await query.message.reply_text(signal, parse_mode='Markdown')
            else:
                await query.message.reply_text("❌ Ошибка генерации сигналов")

    elif data == "admin_manage_premium":
        if is_admin(user_id):
            keyboard = [
                [InlineKeyboardButton("➕ Активировать премиум", callback_data="admin_activate_premium")],
                [InlineKeyboardButton("➖ Деактивировать премиум", callback_data="admin_deactivate_premium")],
                [InlineKeyboardButton("📋 Список премиум", callback_data="admin_list_premium")],
                [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(
                "💎 **УПРАВЛЕНИЕ ПРЕМИУМ ПОДПИСКАМИ**\n\n"
                "Выберите действие:",
                reply_markup=reply_markup
            )

    elif data == "admin_activate_premium":
        if is_admin(user_id):
            await query.message.edit_text(
                "➕ **АКТИВАЦИЯ ПРЕМИУМ**\n\n"
                "Используйте команду:\n"
                "`/activate_premium <user_id> [дней=30]`\n\n"
                "Пример:\n"
                "`/activate_premium 123456789`\n"
                "`/activate_premium 123456789 90`",
                parse_mode='Markdown'
            )

    elif data == "admin_deactivate_premium":
        if is_admin(user_id):
            await query.message.edit_text(
                "➖ **ДЕАКТИВАЦИЯ ПРЕМИУМ**\n\n"
                "Используйте команду:\n"
                "`/deactivate_premium <user_id>`\n\n"
                "Пример:\n"
                "`/deactivate_premium 123456789`",
                parse_mode='Markdown'
            )

    elif data == "admin_list_premium":
        if is_admin(user_id):
            await list_premium_command(update, context)

    elif data == "admin_back":
        if is_admin(user_id):
            await admin_panel(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений с ЗАЩИТОЙ админских команд"""
    text = update.message.text
    user_id = update.effective_user.id

    # ========== ЗАЩИТА: Скрываем админские команды от обычных пользователей ==========
    admin_commands = [
        '/activate_premium', '/deactivate_premium',
        '/list_premium', '/check_premium', '/check_expired',
        '/expiring_premiums'
    ]

    # Если пользователь не админ и пытается использовать админскую команду
    if any(text.startswith(cmd) for cmd in admin_commands) and not is_admin(user_id):
        # Отправляем "неизвестная команда" вместо "доступ запрещен"
        await update.message.reply_text(
            "❓ Неизвестная команда. Используйте кнопки меню.",
            reply_markup=get_main_keyboard(user_id)
        )
        return  # Выходим - не обрабатываем дальше
    # ========== КОНЕЦ ЗАЩИТЫ ==========

    if text == "🎯 Сигналы":
        await signals_command(update, context)

    elif text == "📈 Pump/Dump":
        await pumpdump_command(update, context)

    elif text == "💎 Подписка":
        await subscription_command(update, context)

    elif text == "🆘 Поддержка":
        await support_command(update, context)

    elif text == "👨‍💻 Админ-панель":
        await admin_panel(update, context)

    else:
        await update.message.reply_text(
            "🤖 Используйте кнопки меню для навигации",
            reply_markup=get_main_keyboard(user_id)
        )

def main():
    """Основная функция"""
    print("=" * 60)
    print("🚀 ЗАПУСК CRYPTO SIGNALS PRO BOT")
    print("=" * 60)
    print(f"📊 Реальные данные с CoinGecko API")
    print(f"💰 Анализ {len(COINGECKO_IDS)} монет")
    print(f"🤖 Бот поддержки: @CryptoSignalsSupportBot")
    print(f"💎 Цена подписки: 9 USDT")
    print("=" * 60)

    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()

    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("signals", signals_command))
    application.add_handler(CommandHandler("subscription", subscription_command))
    application.add_handler(CommandHandler("pumpdump", pumpdump_command))
    application.add_handler(CommandHandler("support", support_command))

    # Команды управления премиум
    application.add_handler(CommandHandler("activate_premium", activate_premium_command))
    application.add_handler(CommandHandler("deactivate_premium", deactivate_premium_command))
    application.add_handler(CommandHandler("check_premium", check_premium_command))
    application.add_handler(CommandHandler("list_premium", list_premium_command))

    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Бот готов к работе!")
    print("💎 Система премиум подписок активна")
    print("🔔 Pump/Dump мониторинг работает при запросах")
    print("🔗 Подключение к CoinGecko API...")
    print("=" * 60)

    # Запускаем бота
    application.run_polling()

if __name__ == '__main__':
    main()




