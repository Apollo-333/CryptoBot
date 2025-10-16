import ccxt
import pandas as pd
import time
from datetime import datetime, timedelta
from ta.trend import EMAIndicator, MACD, ADXIndicator
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import OnBalanceVolumeIndicator, VolumeWeightedAveragePrice
import telebot
from threading import Thread, Lock
import os
from dotenv import load_dotenv
import logging
import numpy as np
from collections import deque
import random

# ========== НАСТРОЙКИ ПРОКСИ ДЛЯ PYTHONANYWHERE ==========
import os
os.environ['HTTP_PROXY'] = 'http://proxy.server:3128'
os.environ['HTTPS_PROXY'] = 'http://proxy.server:3128'

# ========== СИСТЕМА ПОДПИСКИ ==========
import sqlite3
from datetime import datetime, timedelta

# База данных пользователей
def init_database():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, 
                  subscription_end DATE,
                  is_active BOOLEAN DEFAULT TRUE)''')
    conn.commit()
    conn.close()

def check_subscription(user_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT subscription_end FROM users WHERE user_id = ? AND is_active = TRUE", (user_id,))
    result = c.fetchone()
    conn.close()
    
    if result and datetime.now().date() <= datetime.strptime(result[0], '%Y-%m-%d').date():
        return True
    return False

def add_user(user_id, days=30):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    end_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
    c.execute("INSERT OR REPLACE INTO users (user_id, subscription_end, is_active) VALUES (?, ?, TRUE)", 
              (user_id, end_date))
    conn.commit()
    conn.close()

# Инициализируем базу при запуске
init_database()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

# ========== НАСТРОЙКИ ==========

load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')

if not TELEGRAM_TOKEN or not ADMIN_CHAT_ID:
    print("❌ Критическая ошибка: не загружены переменные!")
    exit(1)

try:
    ADMIN_CHAT_ID = int(ADMIN_CHAT_ID)
except ValueError:
    print("❌ ADMIN_CHAT_ID должен быть числом")
    exit(1)

# Параметры стратегии
MAIN_ANALYSIS_TIMEFRAMES = ['1h', '4h']
SHORT_TERM_TIMEFRAMES = ['15m', '30m']
PUMP_DUMP_TIMEFRAMES = ['5m', '15m']

MIN_VOLUME_USDT = 500000
MAX_RISK_PER_TRADE = 0.02
MIN_RISK_REWARD = 1.5

# УЛУЧШЕННЫЕ НАСТРОЙКИ PUMP/DUMP ДЕТЕКТОРА
PUMP_THRESHOLD = 3.0  # Уменьшили для раннего обнаружения
DUMP_THRESHOLD = -2.5
VOLUME_SPIKE_RATIO = 2.0

# Хранилище
price_history = {}
volume_history = {}
last_signals = {}
signal_lock = Lock()

# Инициализация бота
bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)

try:
    print(f"\n🔷 Проверяем доступ к чату {ADMIN_CHAT_ID}...")
    bot.send_message(ADMIN_CHAT_ID, "🟢 УЛУЧШЕННЫЙ БОТ ЗАПУЩЕН!\n• Раннее обнаружение pump/dump\n• Четкие рекомендации\n• Увеличенное кол-во сигналов")
    print("✅ Проверка прошла успешно! Чат найден.")
except Exception as e:
    print(f"\n❌ Ошибка Telegram: {e}")
    ADMIN_CHAT_ID = None

# ========== ИНИЦИАЛИЗАЦИЯ BYBIT ==========
exchange = ccxt.bybit({
    'enableRateLimit': True,
    'options': {'defaultType': 'swap'},
    'timeout': 30000
})

try:
    print("Проверяем подключение к Bybit API...")
    markets = exchange.load_markets()
    print(f"✅ Успешно загружено {len(markets)} торговых пар")
except Exception as e:
    print(f"❌ Ошибка подключения: {e}")
    markets = {}

# ========== БАЗОВЫЕ ФУНКЦИИ ==========
def get_all_perp_symbols():
    """Получение списка бессрочных контрактов"""
    print("\n🔍 Загрузка бессрочных контрактов...")
    
    all_symbols = []
    
    # Популярные пары для гарантированного покрытия
    popular_pairs = [
        'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT',
        'ADA/USDT', 'AVAX/USDT', 'DOGE/USDT', 'DOT/USDT', 'LINK/USDT',
        'MATIC/USDT', 'LTC/USDT', 'ATOM/USDT', 'UNI/USDT', 'XLM/USDT',
        'ETC/USDT', 'BCH/USDT', 'FIL/USDT', 'ALGO/USDT', 'EOS/USDT',
        'AAVE/USDT', 'SUSHI/USDT', 'MKR/USDT', 'COMP/USDT', 'YFI/USDT',
        'THETA/USDT', 'VET/USDT', 'TRX/USDT', 'XTZ/USDT', 'NEAR/USDT',
        'FTM/USDT', 'MANA/USDT', 'SAND/USDT', 'GALA/USDT', 'ENJ/USDT',
        'CHZ/USDT', 'HBAR/USDT', 'EGLD/USDT', 'ZIL/USDT', 'IOTA/USDT',
        'CELO/USDT', 'ONE/USDT', 'HOT/USDT', 'ONT/USDT', 'ICX/USDT',
        'WAVES/USDT', 'RVN/USDT', 'SC/USDT', 'DASH/USDT', 'ZEC/USDT',
        'BAT/USDT', 'ZRX/USDT', 'SNX/USDT', 'CRV/USDT', 'REN/USDT',
        'OMG/USDT', 'KNC/USDT', 'BAND/USDT', 'NMR/USDT', 'OCEAN/USDT'
    ]
    
    # Сначала добавляем популярные пары
    for symbol in popular_pairs:
        try:
            ticker = exchange.fetch_ticker(symbol)
            volume = ticker.get('quoteVolume', 0)
            
            if volume > MIN_VOLUME_USDT:
                all_symbols.append({
                    'symbol': symbol,
                    'volume': volume,
                    'price': ticker['last']
                })
        except Exception as e:
            continue
    
    # Затем добавляем случайные пары из всех доступных для разнообразия
    all_market_symbols = list(markets.keys())
    random.shuffle(all_market_symbols)
    
    for symbol in all_market_symbols[:80]:
        try:
            market = markets[symbol]
            if (market.get('active', False) and 
                market.get('type', '') == 'swap' and
                symbol.endswith('/USDT:USDT') and
                not any(x in symbol.upper() for x in ['BULL', 'BEAR', '3L', '3S', 'UP', 'DOWN', '1000', '10000'])):
                
                ticker = exchange.fetch_ticker(symbol)
                volume = ticker.get('quoteVolume', 0)
                
                if volume > MIN_VOLUME_USDT:
                    clean_symbol = symbol.replace(':USDT', '')
                    if not any(item['symbol'] == clean_symbol for item in all_symbols):
                        all_symbols.append({
                            'symbol': clean_symbol,
                            'volume': volume,
                            'price': ticker['last']
                        })
                
                if len(all_symbols) >= 100:
                    break
                    
        except Exception as e:
            continue
    
    # Сортируем по объему
    all_symbols.sort(key=lambda x: x['volume'], reverse=True)
    
    print(f"\n✅ Итоговый список: {len(all_symbols)} ликвидных пар")
    
    # Выводим топ-10
    print("\n🏆 Топ-10 пар по объему:")
    for i, item in enumerate(all_symbols[:10], 1):
        print(f"{i:2d}. {item['symbol']}: {item['volume']:,.0f} USDT")
    
    return [item['symbol'] for item in all_symbols]

def calculate_advanced_indicators(df):
    """Расширенный расчет индикаторов"""
    try:
        # Трендовые
        df['ema_20'] = EMAIndicator(df['close'], 20).ema_indicator()
        df['ema_50'] = EMAIndicator(df['close'], 50).ema_indicator()
        df['ema_100'] = EMAIndicator(df['close'], 100).ema_indicator()
        
        # MACD
        macd = MACD(df['close'], window_slow=26, window_fast=12, window_sign=9)
        df['macd'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_hist'] = macd.macd_diff()
        
        # RSI
        df['rsi_14'] = RSIIndicator(df['close'], 14).rsi()
        df['rsi_28'] = RSIIndicator(df['close'], 28).rsi()
        
        # Stochastic
        stoch = StochasticOscillator(df['high'], df['low'], df['close'], 14)
        df['stoch_k'] = stoch.stoch()
        df['stoch_d'] = df['stoch_k'].rolling(3).mean()
        
        # Волатильность
        bb = BollingerBands(df['close'], window=20, window_dev=2)
        df['bb_upper'] = bb.bollinger_hband()
        df['bb_lower'] = bb.bollinger_lband()
        df['bb_middle'] = bb.bollinger_mavg()
        
        df['atr'] = AverageTrueRange(df['high'], df['low'], df['close'], 14).average_true_range()
        
        # Volume analysis
        df['obv'] = OnBalanceVolumeIndicator(df['close'], df['volume']).on_balance_volume()
        df['vwap'] = VolumeWeightedAveragePrice(df['high'], df['low'], df['close'], df['volume']).volume_weighted_average_price()
        df['volume_sma'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        
        # ADX
        df['adx'] = ADXIndicator(df['high'], df['low'], df['close'], 14).adx()
        
        return df
    except Exception as e:
        print(f"❌ Ошибка в calculate_advanced_indicators: {e}")
        return df

def calculate_signal_score(df, signal_type):
    """Система оценки силы сигнала"""
    try:
        last = df.iloc[-1]
        
        score = 0
        max_score = 0
        
        # 1. Трендовые индикаторы (макс 25 баллов)
        if signal_type == 'BUY':
            if last['ema_20'] > last['ema_50']: score += 8
            if last['ema_50'] > last['ema_100']: score += 7
            if last['close'] > last['ema_20']: score += 5
            if last['adx'] > 20: score += 5
        else:  # SELL
            if last['ema_20'] < last['ema_50']: score += 8
            if last['ema_50'] < last['ema_100']: score += 7
            if last['close'] < last['ema_20']: score += 5
            if last['adx'] > 20: score += 5
        max_score += 25
        
        # 2. Моментум индикаторы (макс 30 баллов)
        if signal_type == 'BUY':
            if last['rsi_14'] < 40: score += 10
            elif last['rsi_14'] < 45: score += 7
            if last['rsi_28'] < 45: score += 5
            if last['stoch_k'] < 30 and last['stoch_k'] > last['stoch_d']: score += 8
            elif last['stoch_k'] < 35 and last['stoch_k'] > last['stoch_d']: score += 5
        else:  # SELL
            if last['rsi_14'] > 60: score += 10
            elif last['rsi_14'] > 55: score += 7
            if last['rsi_28'] > 55: score += 5
            if last['stoch_k'] > 70 and last['stoch_k'] < last['stoch_d']: score += 8
            elif last['stoch_k'] > 65 and last['stoch_k'] < last['stoch_d']: score += 5
        max_score += 30
        
        # 3. MACD (макс 15 баллов)
        if signal_type == 'BUY':
            if last['macd'] > last['macd_signal']: score += 8
            if last['macd_hist'] > 0: score += 7
        else:  # SELL
            if last['macd'] < last['macd_signal']: score += 8
            if last['macd_hist'] < 0: score += 7
        max_score += 15
        
        # 4. Объем и волатильность (макс 20 баллов)
        if last['obv'] > df['obv'].rolling(20).mean().iloc[-1]: 
            score += 6 if signal_type == 'BUY' else 3
        else:
            score += 3 if signal_type == 'SELL' else 0
            
        if last['close'] > last['vwap']: 
            score += 6 if signal_type == 'BUY' else 3
        else:
            score += 3 if signal_type == 'SELL' else 0
            
        if last['atr'] / last['close'] > 0.008: score += 4
        if last['volume_ratio'] > 1.2: score += 4
        max_score += 20
        
        # 5. Уровни Боллинджера (макс 10 баллов)
        bb_pos = (last['close'] - last['bb_lower']) / (last['bb_upper'] - last['bb_lower'])
        if signal_type == 'BUY':
            if bb_pos < 0.3: score += 10
            elif bb_pos < 0.4: score += 7
            elif bb_pos < 0.5: score += 4
        else:  # SELL
            if bb_pos > 0.7: score += 10
            elif bb_pos > 0.6: score += 7
            elif bb_pos > 0.5: score += 4
        max_score += 10
        
        # Рассчитываем итоговый процент
        final_score = min(100, int((score / max_score) * 100)) if max_score > 0 else 0
        
        return final_score, score, max_score
    except Exception as e:
        return 0, 0, 0

def get_signal_strength(score):
    """Определяем силу сигнала на основе баллов"""
    if score >= 70:
        return 'VERY_STRONG', '🔥🔥🔥'
    elif score >= 60:
        return 'STRONG', '🔥🔥'
    elif score >= 50:
        return 'MEDIUM', '🔥'
    elif score >= 40:
        return 'MODERATE', '⚡'
    else:
        return 'WEAK', '⚠️'

def generate_main_signal(df, symbol, timeframe):
    """Генерация сигналов"""
    try:
        last = df.iloc[-1]
        
        # Проверяем условия для BUY и SELL отдельно
        buy_score, buy_raw, buy_max = calculate_signal_score(df, 'BUY')
        sell_score, sell_raw, sell_max = calculate_signal_score(df, 'SELL')
        
        # Выбираем лучший сигнал
        best_score = max(buy_score, sell_score)
        signal_type = 'BUY' if buy_score > sell_score else 'SELL'
        
        # Фильтр по минимальному качеству
        if best_score < 45:  # Снизили порог
            return None
        
        # Определяем уровни входа/выхода
        if signal_type == 'BUY':
            entry = last['close']
            stop_loss = min(last['bb_lower'] * 0.98, entry * 0.97)
            take_profit_levels = [
                entry + (entry - stop_loss) * 1.5,
                entry + (entry - stop_loss) * 2.5,
                entry + (entry - stop_loss) * 3.5
            ]
        else:  # SELL
            entry = last['close']
            stop_loss = max(last['bb_upper'] * 1.02, entry * 1.03)
            take_profit_levels = [
                entry - (stop_loss - entry) * 1.5,
                entry - (stop_loss - entry) * 2.5,
                entry - (stop_loss - entry) * 3.5
            ]
        
        # Проверяем минимальное R/R
        if signal_type == 'BUY':
            risk_reward = (take_profit_levels[0] - entry) / (entry - stop_loss)
        else:
            risk_reward = (entry - take_profit_levels[0]) / (stop_loss - entry)
        
        if risk_reward < MIN_RISK_REWARD:
            return None
        
        # Расчет процентных изменений
        tp_percentages = [calculate_percentage_change(entry, tp) for tp in take_profit_levels]
        sl_percentage = calculate_percentage_change(entry, stop_loss)
        
        # Определяем силу сигнала
        strength, emoji = get_signal_strength(best_score)
        
        return {
            'type': signal_type,
            'symbol': symbol,
            'timeframe': timeframe,
            'entry': round(entry, 6),
            'take_profit': [round(tp, 6) for tp in take_profit_levels],
            'stop_loss': round(stop_loss, 6),
            'risk_reward': round(risk_reward, 2),
            'position_size': calculate_position_size(entry, stop_loss),
            'score': best_score,
            'strength': strength,
            'strength_emoji': emoji,
            'percentage_changes': {
                'tp1_percent': round(tp_percentages[0], 2),
                'tp2_percent': round(tp_percentages[1], 2),
                'tp3_percent': round(tp_percentages[2], 2),
                'sl_percent': round(sl_percentage, 2)
            },
            'indicators': {
                'rsi_14': round(last['rsi_14'], 1),
                'rsi_28': round(last['rsi_28'], 1),
                'stoch_k': round(last['stoch_k'], 1),
                'macd_hist': round(last['macd_hist'], 4),
                'adx': round(last['adx'], 1),
                'volume_ratio': round(last['volume_ratio'], 1)
            }
        }
    except Exception as e:
        print(f"❌ Ошибка в generate_main_signal для {symbol}: {e}")
        return None

def format_main_signal(signal):
    """Форматирование основного сигнала"""
    emoji = "🟢" if signal['type'] == 'BUY' else "🔴"
    
    tp_lines = []
    for i, (tp, percent) in enumerate(zip(signal['take_profit'], 
                                        [signal['percentage_changes']['tp1_percent'],
                                         signal['percentage_changes']['tp2_percent'],
                                         signal['percentage_changes']['tp3_percent']])):
        tp_lines.append(f"✅ TP{i+1}: {tp} ({percent}%)")
    
    tp_text = "\n".join(tp_lines)
    
    return f"""
{emoji} {signal['type']} {signal['strength_emoji']} {signal['symbol']} ({signal['timeframe']})
{signal['strength_emoji']} Сила: {signal['strength']} | Оценка: {signal['score']}% | R/R: {signal['risk_reward']}:1

💰 Размер позиции: {signal['position_size']} coins
📍 Вход: {signal['entry']}
❌ SL: {signal['stop_loss']} ({signal['percentage_changes']['sl_percent']}%)

{tp_text}

📊 Детальный анализ:
RSI 14/28: {signal['indicators']['rsi_14']}/{signal['indicators']['rsi_28']}
Stoch K: {signal['indicators']['stoch_k']} | ADX: {signal['indicators']['adx']}
MACD Hist: {signal['indicators']['macd_hist']} | Volume: {signal['indicators']['volume_ratio']}x

🎯 Рекомендация: {'ВЫСОКИЙ ПРИОРИТЕТ' if signal['strength'] in ['VERY_STRONG', 'STRONG'] else 'СРЕДНИЙ ПРИОРИТЕТ'}
"""

def calculate_percentage_change(entry, target):
    return ((target - entry) / entry) * 100

def calculate_position_size(entry, stop_loss, account_balance=1000):
    risk_amount = account_balance * MAX_RISK_PER_TRADE
    risk_per_coin = abs(entry - stop_loss)
    
    if risk_per_coin == 0:
        return 0
    
    position_size = risk_amount / risk_per_coin
    return round(position_size, 6)

# ========== УЛУЧШЕННЫЙ PUMP/DUMP ДЕТЕКТОР ==========
def analyze_trend_for_pump_dump(symbol, timeframe='5m'):
    """Анализирует тренд для определения направления сделки"""
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=50)
        if len(ohlcv) < 20:
            return "NEUTRAL"
            
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # Расчет индикаторов тренда
        df['ema_20'] = EMAIndicator(df['close'], 20).ema_indicator()
        df['ema_50'] = EMAIndicator(df['close'], 50).ema_indicator()
        df['rsi'] = RSIIndicator(df['close'], 14).rsi()
        
        last = df.iloc[-1]
        
        # Определение тренда
        if last['ema_20'] > last['ema_50'] and last['rsi'] < 70:
            return "UPTREND"
        elif last['ema_20'] < last['ema_50'] and last['rsi'] > 30:
            return "DOWNTREND"
        else:
            return "NEUTRAL"
            
    except Exception as e:
        return "NEUTRAL"

def detect_pump_dump_with_recommendation(symbol, timeframe='5m'):
    """Улучшенное обнаружение с рекомендациями по сделкам"""
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=20)
        if len(ohlcv) < 10:
            return None
            
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # Расчет изменений
        current_price = df['close'].iloc[-1]
        prev_price_1 = df['close'].iloc[-2]
        prev_price_3 = df['close'].iloc[-4] if len(df) >= 4 else prev_price_1
        
        price_change_1 = ((current_price - prev_price_1) / prev_price_1) * 100
        price_change_3 = ((current_price - prev_price_3) / prev_price_3) * 100
        
        # Расчет объема
        current_volume = df['volume'].iloc[-1]
        avg_volume = df['volume'].rolling(10).mean().iloc[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
        
        # Анализ тренда
        trend = analyze_trend_for_pump_dump(symbol, timeframe)
        
        # ОПРЕДЕЛЕНИЕ СИГНАЛОВ С РЕКОМЕНДАЦИЯМИ
        recommendation = None
        signal_type = None
        
        if price_change_1 > PUMP_THRESHOLD and volume_ratio > VOLUME_SPIKE_RATIO:
            if trend == "UPTREND":
                signal_type = "PUMP_TREND_CONTINUATION"
                recommendation = "LONG"
            elif trend == "DOWNTREND":
                signal_type = "PUMP_TREND_REVERSAL" 
                recommendation = "LONG_CAREFUL"
            else:
                signal_type = "PUMP_NEUTRAL"
                recommendation = "LONG_NEUTRAL"
                
        elif price_change_1 < DUMP_THRESHOLD and volume_ratio > VOLUME_SPIKE_RATIO:
            if trend == "DOWNTREND":
                signal_type = "DUMP_TREND_CONTINUATION"
                recommendation = "SHORT"
            elif trend == "UPTREND":
                signal_type = "DUMP_TREND_REVERSAL"
                recommendation = "SHORT_CAREFUL"
            else:
                signal_type = "DUMP_NEUTRAL"
                recommendation = "SHORT_NEUTRAL"
        
        if signal_type and recommendation:
            return {
                'type': signal_type,
                'recommendation': recommendation,
                'symbol': symbol,
                'price_change_1min': round(price_change_1, 2),
                'price_change_3min': round(price_change_3, 2),
                'volume_ratio': round(volume_ratio, 2),
                'current_price': current_price,
                'trend': trend,
                'timeframe': timeframe,
                'timestamp': datetime.now().strftime('%H:%M:%S')
            }
            
    except Exception as e:
        return None
    
    return None

def get_recommendation_details(recommendation, symbol, current_price):
    """Детализированные рекомендации для сделок"""
    details = {
        'LONG': {
            'action': '🟢 ПОКУПАТЬ (LONG)',
            'reason': 'Pump в восходящем тренде - продолжение движения',
            'entry': f'{current_price * 0.995:.4f}',  # -0.5% от текущей цены
            'sl': f'{current_price * 0.97:.4f}',     # -3%
            'tp1': f'{current_price * 1.02:.4f}',    # +2%
            'tp2': f'{current_price * 1.04:.4f}'     # +4%
        },
        'LONG_CAREFUL': {
            'action': '🟡 ПОКУПАТЬ ОСТОРОЖНО',
            'reason': 'Pump в нисходящем тренде - возможен разворот',
            'entry': f'{current_price * 0.99:.4f}',   # -1%
            'sl': f'{current_price * 0.96:.4f}',      # -4%
            'tp1': f'{current_price * 1.015:.4f}',    # +1.5%
            'tp2': f'{current_price * 1.03:.4f}'      # +3%
        },
        'SHORT': {
            'action': '🔴 ПРОДАВАТЬ (SHORT)',
            'reason': 'Dump в нисходящем тренде - продолжение движения',
            'entry': f'{current_price * 1.005:.4f}',  # +0.5%
            'sl': f'{current_price * 1.03:.4f}',      # +3%
            'tp1': f'{current_price * 0.98:.4f}',     # -2%
            'tp2': f'{current_price * 0.96:.4f}'      # -4%
        },
        'SHORT_CAREFUL': {
            'action': '🟡 ПРОДАВАТЬ ОСТОРОЖНО',
            'reason': 'Dump в восходящем тренде - возможен разворот',
            'entry': f'{current_price * 1.01:.4f}',   # +1%
            'sl': f'{current_price * 1.04:.4f}',      # +4%
            'tp1': f'{current_price * 0.985:.4f}',    # -1.5%
            'tp2': f'{current_price * 0.97:.4f}'      # -3%
        }
    }
    
    return details.get(recommendation, {
        'action': '⚪ НЕТ ЧЕТКОГО СИГНАЛА',
        'reason': 'Требуется дополнительный анализ',
        'entry': 'N/A',
        'sl': 'N/A',
        'tp1': 'N/A',
        'tp2': 'N/A'
    })

def monitor_pump_dump():
    """Улучшенный мониторинг с четкими рекомендациями"""
    print(f"\n🔍 Запуск УЛУЧШЕННОГО pump/dump мониторинга в {datetime.now().strftime('%H:%M:%S')}")
    
    symbols = get_all_perp_symbols()[:60]
    
    detected_events = []
    for symbol in symbols:
        try:
            for timeframe in PUMP_DUMP_TIMEFRAMES:
                if event := detect_pump_dump_with_recommendation(symbol, timeframe):
                    # Защита от дублирования
                    event_key = f"{symbol}_{event['type']}"
                    with signal_lock:
                        if event_key not in last_signals or time.time() - last_signals[event_key] > 600:  # 10 минут
                            
                            detected_events.append(event)
                            last_signals[event_key] = time.time()
                            
                            print(f"🚨 {event['type']} {event['symbol']}: {event['price_change_1min']}%")
                            
                            if ADMIN_CHAT_ID:
                                try:
                                    details = get_recommendation_details(
                                        event['recommendation'], 
                                        event['symbol'], 
                                        event['current_price']
                                    )
                                    
                                    message = f"""
🎯 {details['action']}

📊 Пара: {event['symbol']}
📈 Изменение: {event['price_change_1min']}% (3свечи: {event['price_change_3min']}%)
📊 Объем: {event['volume_ratio']}x от среднего
📉 Тренд: {event['trend']}
💰 Текущая цена: {event['current_price']}

🎯 РЕКОМЕНДАЦИЯ:
{details['reason']}

📍 Вход: {details['entry']}
❌ Стоп-лосс: {details['sl']}
✅ Тейк-профит 1: {details['tp1']}
✅ Тейк-профит 2: {details['tp2']}

⏰ Таймфрейм: {event['timeframe']}
🕒 Время: {event['timestamp']}

💡 Сигнал: {event['type']}
"""
                                    bot.send_message(ADMIN_CHAT_ID, message)
                                    time.sleep(0.3)
                                except Exception as e:
                                    print(f"Ошибка отправки: {e}")
        
        except Exception as e:
            continue
        
        time.sleep(0.05)
    
    if detected_events:
        print(f"✅ Найдено {len(detected_events)} pump/dump событий")
    else:
        print("ℹ️ Pump/dump событий не обнаружено")

# ========== ОСНОВНОЙ АНАЛИЗ ==========
def run_main_analysis():
    """Основной анализ с увеличенным количеством сигналов"""
    print(f"\n🔍 Начало ОСНОВНОГО АНАЛИЗА в {datetime.now().strftime('%H:%M:%S')}")
    
    signals = []
    symbols = get_all_perp_symbols()
    
    if not symbols:
        print("❌ Нет ликвидных пар для анализа!")
        return
    
    analyzed_count = 0
    signal_count = 0
    
    for symbol in symbols:
        try:
            for timeframe in MAIN_ANALYSIS_TIMEFRAMES:
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=100)
                if len(ohlcv) < 50:
                    continue
                    
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df = calculate_advanced_indicators(df)
                
                if signal := generate_main_signal(df, symbol, timeframe):
                    signals.append(signal)
                    signal_count += 1
                    print(f"🎯 {signal['strength_emoji']} {signal['type']} {signal['symbol']} - Оценка: {signal['score']}%")
                
                analyzed_count += 1
                if analyzed_count % 20 == 0:
                    print(f"📊 Проанализировано {analyzed_count} пар... Найдено {signal_count} сигналов")
        
        except Exception as e:
            continue
    
    # УПРОЩЕННАЯ ФИЛЬТРАЦИЯ - больше сигналов
    signals.sort(key=lambda x: x['score'], reverse=True)
    
    if signals:
        print(f"\n✅ Основной анализ завершен. Найдено {len(signals)} сигналов")
        
        # Отправляем ВСЕ сигналы с оценкой выше 45%
        good_signals = [s for s in signals if s['score'] >= 45]
        
        print(f"📈 Качественные сигналы ({len(good_signals)}):")
        for i, signal in enumerate(good_signals[:10], 1):  # До 10 сигналов
            print(f"{i}. {signal['type']} {signal['symbol']} - {signal['score']}% - R/R: {signal['risk_reward']}:1")
            if ADMIN_CHAT_ID:
                try:
                    bot.send_message(ADMIN_CHAT_ID, format_main_signal(signal))
                    time.sleep(0.5)
                except Exception as e:
                    print(f"Ошибка отправки: {e}")
                    
    else:
        print("\nℹ️ Основной анализ: сигналов не найдено")

def run_short_term_analysis():
    """Краткосрочный анализ на 15m/30m таймфреймах"""
    print("📊 Краткосрочный анализ на 15m/30m...")
    
    symbols = get_all_perp_symbols()[:40]  # Меньше пар для скорости
    
    signals = []
    for symbol in symbols:
        try:
            for timeframe in SHORT_TERM_TIMEFRAMES:
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=50)
                if len(ohlcv) < 20:
                    continue
                    
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df = calculate_advanced_indicators(df)
                
                if signal := generate_main_signal(df, symbol, timeframe):
                    signals.append(signal)
                    print(f"⚡ {signal['type']} {signal['symbol']} - {signal['score']}%")
        
        except Exception as e:
            continue
    
    if signals and ADMIN_CHAT_ID:
        summary = "📊 КРАТКОСРОЧНЫЕ СИГНАЛЫ (15m/30m):\n"
        for signal in signals[:5]:  # Топ-5 сигналов
            summary += f"{signal['type']} {signal['symbol']} - {signal['score']}%\n"
        bot.send_message(ADMIN_CHAT_ID, summary)

# ========== УЛУЧШЕННЫЙ ЦИКЛ АНАЛИЗА ==========
def run_analysis_cycle():
    """Четкий цикл анализа с понятным расписанием"""
    analysis_count = 0
    
    while True:
        try:
            analysis_count += 1
            current_time = datetime.now()
            
            print(f"\n{'='*60}")
            print(f"🎯 ЦИКЛ АНАЛИЗА #{analysis_count} - {current_time.strftime('%H:%M:%S')}")
            print(f"{'='*60}")
            
            # ОСНОВНОЙ АНАЛИЗ - каждый час
            if current_time.minute == 0:  # В начале каждого часа
                print("🕐 Запуск ОСНОВНОГО анализа (каждый час)...")
                run_main_analysis()
            
            # КРАТКОСРОЧНЫЙ АНАЛИЗ - каждые 30 минут
            elif current_time.minute % 30 == 0:
                print("🕑 Запуск КРАТКОСРОЧНОГО анализа (каждые 30 минут)...")
                run_short_term_analysis()
            
            # PUMP/DUMP МОНИТОРИНГ - постоянно
            print("🔍 Запуск PUMP/DUMP мониторинга...")
            monitor_pump_dump()
            
            # Ожидание до следующей минуты
            next_minute = (current_time + timedelta(minutes=1)).replace(second=0, microsecond=0)
            sleep_time = (next_minute - current_time).total_seconds()
            time.sleep(max(1, sleep_time))
                
        except Exception as e:
            print(f"❌ Критическая ошибка в цикле анализа: {e}")
            time.sleep(60)

if __name__ == "__main__":
    print("🚀 Запуск УЛУЧШЕННОГО крипто-бота v2.0...")
    print("🎯 Ключевые улучшения:")
    print("• Четкие рекомендации для pump/dump")
    print("• Раннее обнаружение движений") 
    print("• Увеличенное количество сигналов")
    print("• Понятное расписание анализа")
    
    # Тестовый запуск
    print("\n🧪 Тестовый запуск...")
    run_main_analysis()
    
    # Запуск основного цикла
    print("\n🔄 Запуск основного цикла анализа...")
    analysis_thread = Thread(target=run_analysis_cycle, daemon=True)
    analysis_thread.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:

        print("\n⏹️ Остановка бота...")
       

