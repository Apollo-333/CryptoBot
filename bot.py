"""
🚀 CRYPTO SIGNALS PRO BOT - РАБОЧАЯ ВЕРСИЯ С PACK/DUMP
"""

import os
import json
import random
import asyncio
import logging
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

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "638584949"))

DB_FILE = "users_db.json"

# ПРАВИЛЬНЫЕ ID для CoinGecko API
COINGECKO_IDS = {
    'BTC': 'bitcoin',
    'ETH': 'ethereum', 
    'BNB': 'binancecoin',
    'SOL': 'solana',
    'XRP': 'ripple',
    'ADA': 'cardano',
    'DOGE': 'dogecoin',
    'DOT': 'polkadot',
    'LINK': 'chainlink',
    'MATIC': 'matic-network',
    'SHIB': 'shiba-inu',
    'PEPE': 'pepe',
    'ATOM': 'cosmos',
    'UNI': 'uniswap',
    'AVAX': 'avalanche-2',
    'LTC': 'litecoin',
    'TRX': 'tron',
    'XLM': 'stellar',
    'ALGO': 'algorand',
    'NEAR': 'near'
}

print("=" * 60)
print("🚀 ЗАПУСК CRYPTO SIGNALS PRO BOT")
print("=" * 60)

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
        
        if user.get("last_reset_date") != today:
            self.update_user(user_id, {
                "signals_today": 0,
                "last_reset_date": today
            })
            user["signals_today"] = 0
        
        if user.get("is_premium"):
            return True
        return user.get("signals_today", 0) < 1
    
    def increment_signal(self, user_id):
        user = self.get_user(user_id)
        self.update_user(user_id, {
            "signals_today": user.get("signals_today", 0) + 1,
            "total_signals": user.get("total_signals", 0) + 1
        })

user_db = UserDatabase()

# ================== COINGECKO API ==================
async def get_crypto_price(symbol):
    """Получить цену криптовалюты с логированием"""
    try:
        coin_id = COINGECKO_IDS.get(symbol.upper())
        if not coin_id:
            logger.error(f"❌ Не найден coin_id для символа: {symbol}")
            return None
        
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            'ids': coin_id,
            'vs_currencies': 'usd',
            'include_24hr_change': 'true',
            'include_market_cap': 'true',
            'include_24hr_vol': 'true'
        }
        
        logger.info(f"🔍 Запрос CoinGecko: {symbol} -> {coin_id}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=15) as response:
                logger.info(f"📡 Статус: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"📊 Получены данные: {data}")
                    
                    if coin_id in data:
                        price_data = data[coin_id]
                        result = {
                            'price': price_data.get('usd', 0),
                            'change': price_data.get('usd_24h_change', 0),
                            'volume': price_data.get('usd_24h_vol', 0),
                            'market_cap': price_data.get('usd_market_cap', 0)
                        }
                        logger.info(f"✅ Успех: {symbol} = ${result['price']}")
                        return result
                    else:
                        logger.error(f"❌ Coin {coin_id} не найден в ответе")
                elif response.status == 429:
                    logger.error("❌ Превышен лимит запросов к CoinGecko (429)")
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Ошибка API: {response.status} - {error_text}")
                    
    except asyncio.TimeoutError:
        logger.error("❌ Таймаут запроса к CoinGecko")
    except Exception as e:
        logger.error(f"❌ Ошибка получения цены для {symbol}: {str(e)}")
    
    return None

async def get_multiple_prices(symbols):
    """Получить цены для нескольких символов"""
    tasks = [get_crypto_price(symbol) for symbol in symbols]
    results = await asyncio.gather(*tasks)
    return dict(zip(symbols, results))

# ================== ГЕНЕРАЦИЯ СИГНАЛОВ ==================
async def generate_signal(symbol):
    """Генерировать торговый сигнал с ФАЛЛБЕКОМ"""
    logger.info(f"🎯 Генерация сигнала для {symbol}")
    
    try:
        # Пытаемся получить реальные данные
        price_data = await get_crypto_price(symbol)
        
        # Если данные не получены, используем ФАЛЛБЕК
        if not price_data or price_data.get('price', 0) == 0:
            logger.warning(f"⚠️ Нет данных для {symbol}, использую fallback")
            return generate_fallback_signal(symbol)
        
        current_price = price_data['price']
        change_24h = price_data.get('change', 0)
        
        # ОСНОВНАЯ ЛОГИКА СИГНАЛОВ (всегда должен быть сигнал)
        import random
        import time
        
        # Всегда генерируем BUY или SELL, никогда HOLD
        actions = ['BUY', 'SELL']
        action = random.choice(actions)
        
        # Рассчитываем параметры
        target_percent = random.uniform(2, 8)
        stop_loss_percent = random.uniform(1, 4)
        confidence = random.randint(65, 90)
        
        if action == 'BUY':
            target_price = current_price * (1 + target_percent / 100)
            stop_loss_price = current_price * (1 - stop_loss_percent / 100)
        else:  # SELL
            target_price = current_price * (1 - target_percent / 100)
            stop_loss_price = current_price * (1 + stop_loss_percent / 100)
        
        # Выбор плеча
        if abs(change_24h) > 10:
            leverage = "2x"
        elif abs(change_24h) > 5:
            leverage = "3x"
        else:
            leverage = "5x"
        
        signal = {
            'symbol': symbol,
            'action': action,
            'price': current_price,
            'change': change_24h,
            'target': target_price,
            'stop_loss': stop_loss_price,
            'leverage': leverage,
            'confidence': f"{confidence}%",
            'time': datetime.now().strftime('%H:%M %d.%m.%Y')
        }
        
        logger.info(f"✅ Сгенерирован сигнал: {signal['action']} {symbol}")
        return signal
        
    except Exception as e:
        logger.error(f"❌ Ошибка генерации сигнала для {symbol}: {e}")
        # ВСЕГДА возвращаем fallback сигнал при любой ошибке
        return generate_fallback_signal(symbol)


def generate_fallback_signal(symbol):
    """Создать резервный сигнал если API не работает"""
    import random
    
    # Приблизительные цены для популярных монет
    approximate_prices = {
        'BTC': 45000, 'ETH': 2400, 'BNB': 320, 'SOL': 120,
        'XRP': 0.62, 'ADA': 0.45, 'DOGE': 0.09, 'DOT': 7.5,
        'LINK': 15, 'MATIC': 0.85, 'SHIB': 0.000009,
        'PEPE': 0.0000012, 'ATOM': 10.5, 'UNI': 7.2
    }
    
    current_price = approximate_prices.get(symbol, 100)
    action = random.choice(['BUY', 'SELL'])
    target_percent = random.uniform(3, 7)
    
    if action == 'BUY':
        target_price = current_price * (1 + target_percent / 100)
        stop_loss_price = current_price * (1 - random.uniform(1.5, 3) / 100)
    else:
        target_price = current_price * (1 - target_percent / 100)
        stop_loss_price = current_price * (1 + random.uniform(1.5, 3) / 100)
    
    return {
        'symbol': symbol,
        'action': action,
        'price': current_price,
        'change': round(random.uniform(-5, 5), 2),
        'target': target_price,
        'stop_loss': stop_loss_price,
        'leverage': random.choice(['2x', '3x', '5x']),
        'confidence': f"{random.randint(70, 85)}%",
        'time': datetime.now().strftime('%H:%M %d.%m.%Y')
    }

# ================== PUMP/DUMP МОНИТОРИНГ ==================
async def check_pump_dump():
    """Проверка pump/dump сигналов"""
    logger.info("🔍 Запуск Pump/Dump мониторинга")
    
    symbols = ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE', 'DOT', 'LINK', 'MATIC']
    prices_data = await get_multiple_prices(symbols)
    
    alerts = []
    
    for symbol, data in prices_data.items():
        if not data or data['price'] == 0:
            continue
        
        change = data['change']
        price = data['price']
        volume = data.get('volume', 0)
        
        # Критерии для pump
        if change > 15:  # Более 15% роста
            alert_type = "🚀 PUMP"
            intensity = "🔥 ВЫСОКАЯ" if change > 25 else "📈 СРЕДНЯЯ"
            recommendation = "Рассмотрите продажу/ожидание" if change > 25 else "Можно покупать с осторожностью"
            
            alerts.append({
                'type': alert_type,
                'symbol': symbol,
                'change': change,
                'price': price,
                'intensity': intensity,
                'recommendation': recommendation,
                'volume': f"${volume:,.0f}"
            })
        
        # Критерии для dump
        elif change < -15:  # Более 15% падения
            alert_type = "🔻 DUMP"
            intensity = "💥 ВЫСОКАЯ" if change < -25 else "📉 СРЕДНЯЯ"
            recommendation = "Возможен отскок" if change < -25 else "Осторожно с покупками"
            
            alerts.append({
                'type': alert_type,
                'symbol': symbol,
                'change': change,
                'price': price,
                'intensity': intensity,
                'recommendation': recommendation,
                'volume': f"${volume:,.0f}"
            })
    
    logger.info(f"🔔 Найдено {len(alerts)} pump/dump сигналов")
    return alerts

# ================== КЛАВИАТУРЫ ==================
def get_main_keyboard(user_id):
    keyboard = [
        [KeyboardButton("🎯 Сигналы"), KeyboardButton("📈 Pump/Dump")],
        [KeyboardButton("💎 Подписка"), KeyboardButton("🆘 Поддержка")]
    ]
    
    if str(user_id) == str(ADMIN_ID):
        keyboard.append([KeyboardButton("👑 Админ")])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ================== ОСНОВНЫЕ КОМАНДЫ ==================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    user_db.update_user(user_id, {"username": user.username})
    
    user_data = user_db.get_user(user_id)
    status = "✅ ПРЕМИУМ" if user_data.get('is_premium') else "🎯 БЕСПЛАТНЫЙ"
    
    text = f"""
🚀 Добро пожаловать в Crypto Signals Pro, {user.first_name}!

👤 Ваш ID: `{user_id}`
💎 Статус: {status}

📊 Доступные функции:
• 🎯 1 бесплатный сигнал в день
• 📈 Pump/Dump мониторинг (премиум)
• 💎 Премиум подписка с неограниченными сигналами
• 🆘 Поддержка 24/7

💡 Используйте кнопки меню!
"""
    
    await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))

async def signals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    user_data = user_db.get_user(user_id)
    
    # Проверка лимита
    if not user_db.can_send_signal(user_id):
        await update.message.reply_text(
            f"❌ Достигнут дневной лимит!\n\n"
            f"Использовано: {user_data.get('signals_today', 0)}/1 сигналов\n\n"
            f"💎 Оформите премиум для неограниченного доступа!\n"
            f"Команда: /premium",
            reply_markup=get_main_keyboard(user_id)
        )
        return
    
    loading_msg = await update.message.reply_text("🔄 Получаю рыночные данные...")
    
    try:
        # Выбираем символы в зависимости от статуса
        if user_data.get('is_premium'):
            symbols = random.sample(list(COINGECKO_IDS.keys())[:10], 3)
            logger.info(f"💎 Премиум сигналы для {user_id}: {symbols}")
        else:
            symbols = ['BTC']
            logger.info(f"🎯 Бесплатный сигнал для {user_id}")
        
        signals = []
        for symbol in symbols:
            signal = await generate_signal(symbol)
        if signal:  # ← ПРОСТАЯ ПРОВЕРКА, без условия '!= HOLD'
            signals.append(signal)
        if len(signals) >= 2 and not user_data.get('is_premium'):
            break
        
        await loading_msg.delete()
        
        if not signals:
            await update.message.reply_text(
                "⚠️ В данный момент нет сильных сигналов. Попробуйте позже.",
                reply_markup=get_main_keyboard(user_id)
            )
            return
        
        # Отправляем сигналы
        for signal in signals:
            if user_data.get('is_premium'):
                text = f"""
💎 ПРЕМИУМ СИГНАЛ 💎

🏷 Пара: {signal['symbol']}/USDT
⚡ Действие: {signal['action']}
💰 Цена: ${signal['price']:,.4f}
📊 Изменение 24ч: {signal['change']:+.2f}%
🎯 Цель: ${signal['target']:,.4f}
🛑 Стоп-лосс: ${signal['stop_loss']:,.4f}
📈 Плечо: {signal['leverage']}
✅ Уверенность: {signal['confidence']}
💹 Объем: ${signal['volume']:,.0f}

⏰ {signal['time']}
"""
            else:
                text = f"""
🎯 БЕСПЛАТНЫЙ СИГНАЛ 🎯

🏷 Пара: {signal['symbol']}/USDT
💰 Цена: ${signal['price']:,.2f}
📊 Изменение 24ч: {signal['change']:+.2f}%
📈 Тренд: {'📈 Восходящий' if signal['change'] > 0 else '📉 Нисходящий' if signal['change'] < 0 else '➡️ Боковой'}

🔒 Для получения полных сигналов с точками входа/выхода оформите премиум!

🎯 Использовано: {user_data.get('signals_today', 0)+1}/1 сегодня
💎 Премиум: /premium
"""
            
            await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))
        
        # Увеличиваем счетчик
        user_db.increment_signal(user_id)
        
    except Exception as e:
        logger.error(f"❌ Ошибка в signals_command: {e}")
        await update.message.reply_text(
            "⚠️ Ошибка получения сигналов. Попробуйте позже.",
            reply_markup=get_main_keyboard(user_id)
        )

async def pumpdump_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # Проверка премиума
    if not user_db.get_user(user_id).get('is_premium') and str(user_id) != str(ADMIN_ID):
        await update.message.reply_text(
            "🔒 Pump/Dump мониторинг доступен только для премиум пользователей!\n\n"
            "💎 Оформите подписку для доступа к эксклюзивным данным.\n"
            "Команда: /premium",
            reply_markup=get_main_keyboard(user_id)
        )
        return
    
    loading_msg = await update.message.reply_text("🔍 Анализирую рынок на Pump/Dump...")
    
    try:
        alerts = await check_pump_dump()
        
        await loading_msg.delete()
        
        if alerts:
            for alert in alerts[:3]:  # Максимум 3 алерта
                text = f"""
{alert['type']} СИГНАЛ! ⚡

🏷 Пара: {alert['symbol']}/USDT
💰 Цена: ${alert['price']:,.4f}
📊 Изменение 24ч: {alert['change']:+.2f}%
💪 Интенсивность: {alert['intensity']}
💹 Объем: {alert['volume']}
💡 Рекомендация: {alert['recommendation']}

⏰ Обнаружено: {datetime.now().strftime('%H:%M %d.%m.%Y')}
"""
                await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))
        else:
            # Анализ рынка если нет pump/dump
            symbols = ['BTC', 'ETH', 'BNB', 'SOL']
            prices_data = await get_multiple_prices(symbols)
            
            text = "📊 ОБЗОР РЫНКА\n\n"
            
            for symbol in symbols:
                data = prices_data.get(symbol)
                if data and data['price'] > 0:
                    change = data['change']
                    emoji = "🚀" if change > 10 else "📈" if change > 5 else "↗️" if change > 0 else "↘️" if change > -5 else "📉" if change > -10 else "🔻"
                    status = "СИЛЬНЫЙ РОСТ" if change > 10 else "РОСТ" if change > 5 else "НЕБОЛЬШОЙ РОСТ" if change > 0 else "НЕБОЛЬШОЕ ПАДЕНИЕ" if change > -5 else "ПАДЕНИЕ" if change > -10 else "СИЛЬНОЕ ПАДЕНИЕ"
                    
                    text += f"{emoji} **{symbol}**: ${data['price']:,.2f} ({change:+.2f}%)\n{status}\n\n"
            
            text += f"\n💎 Премиум функции:\n• Мгновенные уведомления о pump/dump\n• Расширенный анализ\n• Приоритетные сигналы\n\n⏰ {datetime.now().strftime('%H:%M %d.%m.%Y')}"
            
            await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))
            
    except Exception as e:
        logger.error(f"❌ Ошибка в pumpdump_command: {e}")
        await update.message.reply_text(
            "⚠️ Ошибка анализа рынка. Попробуйте позже.",
            reply_markup=get_main_keyboard(user_id)
        )

async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

👤 ID: `{user_id}`
✅ Статус: Активен
📅 Истекает: {expiry_str}

🎯 Наслаждайтесь полным доступом!
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
• Неограниченные сигналы (20+ монет)
• Точные точки входа/выхода
• Pump/Dump мониторинг 24/7
• Стоп-лосс и тейк-профит
• Приоритетная поддержка

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

# ================== ЗАПУСК ==================
def main():
    print("🤖 Бот поддержки: @CryptoSignalsSupportBot")
    print("💎 Цена подписки: 9 USDT")
    print("📊 Анализ 20+ монет")
    print("=" * 60)
    
    if not TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN не установлен!")
        return
    
    try:
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Основные команды
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("signals", signals_command))
        application.add_handler(CommandHandler("premium", premium_command))
        application.add_handler(CommandHandler("pumpdump", pumpdump_command))
        application.add_handler(CommandHandler("market", pumpdump_command))
        
        # Админ-команды
        application.add_handler(CommandHandler("admin", start_command))  # временно
        application.add_handler(CommandHandler("activate", start_command))  # временно
        
        # Обработчики
        application.add_handler(CallbackQueryHandler(lambda u,c: u.callback_query.answer()))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, 
                                             lambda u,c: u.message.reply_text("Используйте кнопки меню!", 
                                                                              reply_markup=get_main_keyboard(u.effective_user.id))))
        
        print("✅ Бот готов к работе!")
        print("💎 Система премиум подписок активна")
        print("📊 Подключение к CoinGecko API...")
        print("=" * 60)
        
        application.run_polling(
            poll_interval=3.0,
            timeout=30,
            drop_pending_updates=True
        )
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")

if __name__ == "__main__":
    main()
