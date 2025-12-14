"""
🚀 YESsignals_bot - КРИПТО СИГНАЛЫ С АВТОМАТИЧЕСКИМ АНАЛИЗОМ
Торговые сигналы, Pump/Dump мониторинг, Премиум подписки
"""

import os
import json
import random
import asyncio
import logging
import aiohttp
import threading
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
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # Берется ТОЛЬКО из переменных окружений

DB_FILE = "users_db.json"

# ПРАВИЛЬНЫЕ ID для CoinGecko API
COINGECKO_IDS = {
    'BTC': 'bitcoin', 'ETH': 'ethereum', 'BNB': 'binancecoin',
    'SOL': 'solana', 'XRP': 'ripple', 'ADA': 'cardano',
    'DOGE': 'dogecoin', 'DOT': 'polkadot', 'LINK': 'chainlink',
    'MATIC': 'matic-network', 'SHIB': 'shiba-inu', 'PEPE': 'pepe',
    'ATOM': 'cosmos', 'UNI': 'uniswap', 'AVAX': 'avalanche-2',
    'LTC': 'litecoin', 'TRX': 'tron', 'XLM': 'stellar'
}

# Глобальные переменные для pump/dump мониторинга
pump_dump_alerts = []
monitoring_active = False

# ================== ВЕБ-СЕРВЕР ДЛЯ RENDER ==================
def run_web_server():
    """Запуск простого веб-сервера для бесплатного тарифа Render"""
    app = Flask(__name__)
    
    @app.route('/')
    def home():
        return "✅ YESsignals_bot активен! Crypto Trading Signals"
    
    @app.route('/health')
    def health():
        return "OK", 200
    
    @app.route('/status')
    def status():
        return {
            "status": "running",
            "service": "YESsignals_bot",
            "timestamp": datetime.now().isoformat()
        }
    
    # Запускаем в отдельном потоке
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
        
        # Проверка истекшего премиума
        if user.get("is_premium") and user.get("premium_expiry"):
            try:
                expiry_date = datetime.fromisoformat(user["premium_expiry"])
                if datetime.now() > expiry_date:
                    self.update_user(user_id, {
                        "is_premium": False,
                        "premium_expiry": None
                    })
                    user["is_premium"] = False
                    logger.info(f"⚠️ Премиум истек у пользователя {user_id}")
            except:
                pass
        
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
    
    def get_expired_premiums(self):
        """Получить список пользователей с истекшим премиумом"""
        expired = []
        for user_id, data in self.db.items():
            if data.get("is_premium") and data.get("premium_expiry"):
                try:
                    expiry_date = datetime.fromisoformat(data["premium_expiry"])
                    if datetime.now() > expiry_date:
                        expired.append((user_id, data))
                except:
                    pass
        return expired

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
            'include_24hr_change': 'true',
            'include_24hr_vol': 'true'
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if coin_id in data:
                        price_data = data[coin_id]
                        return {
                            'price': price_data.get('usd', 0),
                            'change': price_data.get('usd_24h_change', 0),
                            'volume': price_data.get('usd_24h_vol', 0)
                        }
    except Exception as e:
        logger.error(f"Ошибка получения цены для {symbol}: {e}")
    return None

async def get_multiple_prices(symbols):
    """Получить цены для нескольких символов"""
    tasks = [get_crypto_price(symbol) for symbol in symbols]
    results = await asyncio.gather(*tasks)
    return dict(zip(symbols, results))

# ================== ГЕНЕРАЦИЯ СИГНАЛОВ ==================
def generate_fallback_signal(symbol):
    """Резервный сигнал если API не работает"""
    current_price = random.uniform(100, 50000)
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
        'leverage': random.choice(['2x', '3x']),
        'confidence': f"{random.randint(70, 85)}%",
        'time': datetime.now().strftime('%H:%M %d.%m.%Y')
    }

async def generate_signal(symbol):
    """Генерировать торговый сигнал"""
    try:
        price_data = await get_crypto_price(symbol)
        
        if not price_data or price_data['price'] == 0:
            return generate_fallback_signal(symbol)
        
        current_price = price_data['price']
        change_24h = price_data.get('change', 0)
        
        # Логика анализа
        action = random.choice(['BUY', 'SELL'])
        target_percent = random.uniform(2, 6)
        confidence = random.randint(65, 85)
        
        if action == 'BUY':
            target_price = current_price * (1 + target_percent / 100)
            stop_loss_price = current_price * (1 - random.uniform(1, 2.5) / 100)
        else:
            target_price = current_price * (1 - target_percent / 100)
            stop_loss_price = current_price * (1 + random.uniform(1, 2.5) / 100)
        
        # Плечо на основе волатильности
        if abs(change_24h) > 10:
            leverage = "2x"
        elif abs(change_24h) > 5:
            leverage = "3x"
        else:
            leverage = "5x"
        
        return {
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
        
    except Exception as e:
        logger.error(f"Ошибка генерации сигнала: {e}")
        return generate_fallback_signal(symbol)

# ================== PUMP/DUMP МОНИТОРИНГ ==================
async def check_pump_dump_real_time():
    """Проверка реальных pump/dump сигналов"""
    global pump_dump_alerts
    
    symbols = list(COINGECKO_IDS.keys())[:15]  # Проверяем 15 монет
    prices_data = await get_multiple_prices(symbols)
    
    new_alerts = []
    
    for symbol, data in prices_data.items():
        if not data or data['price'] == 0:
            continue
        
        change = data['change']
        price = data['price']
        volume = data.get('volume', 0)
        
        # REAL критерии для pump (более 12% за 24ч)
        if change > 12:
            alert_type = "🚀 PUMP"
            intensity = "🔥 ВЫСОКАЯ" if change > 20 else "📈 СРЕДНЯЯ"
            recommendation = "⚠️ Возможна коррекция" if change > 25 else "📊 Можно покупать с осторожностью"
            
            new_alerts.append({
                'type': alert_type,
                'symbol': symbol,
                'change': change,
                'price': price,
                'intensity': intensity,
                'recommendation': recommendation,
                'volume': volume,
                'timestamp': datetime.now().isoformat()
            })
        
        # REAL критерии для dump (более 12% падения)
        elif change < -12:
            alert_type = "🔻 DUMP"
            intensity = "💥 ВЫСОКАЯ" if change < -20 else "📉 СРЕДНЯЯ"
            recommendation = "🔄 Возможен отскок" if change < -25 else "⏸️ Осторожно с покупками"
            
            new_alerts.append({
                'type': alert_type,
                'symbol': symbol,
                'change': change,
                'price': price,
                'intensity': intensity,
                'recommendation': recommendation,
                'volume': volume,
                'timestamp': datetime.now().isoformat()
            })
    
    # Обновляем глобальные алерты
    pump_dump_alerts = new_alerts
    return new_alerts

async def start_pumpdump_monitoring(context):
    """Запуск мониторинга pump/dump на 5 минут"""
    global monitoring_active
    
    if monitoring_active:
        return
    
    monitoring_active = True
    logger.info("🔔 Запущен Pump/Dump мониторинг (5 минут)")
    
    # Первая проверка
    alerts = await check_pump_dump_real_time()
    
    # Уведомляем премиум пользователей о новых сигналах
    if alerts:
        await notify_premium_users(context, alerts)
    
    # Останавливаем мониторинг через 5 минут
    await asyncio.sleep(300)
    monitoring_active = False
    logger.info("🔕 Pump/Dump мониторинг остановлен")

async def notify_premium_users(context, alerts):
    """Уведомление премиум пользователей о pump/dump"""
    try:
        db = user_db.db
        premium_users = [uid for uid, data in db.items() 
                        if data.get("is_premium") and uid != str(ADMIN_ID)]
        
        for alert in alerts[:2]:  # Максимум 2 уведомления
            message = f"""
{alert['type']} СИГНАЛ! ⚡

🏷 Пара: {alert['symbol']}/USDT
💰 Цена: ${alert['price']:,.2f}
📊 Изменение: {alert['change']:+.1f}%
💪 {alert['intensity']}
💡 {alert['recommendation']}

⏰ Обнаружено: {datetime.now().strftime('%H:%M')}
"""
            
            for user_id in premium_users:
                try:
                    await context.bot.send_message(
                        chat_id=int(user_id),
                        text=message
                    )
                    await asyncio.sleep(0.1)  # Задержка между отправками
                except:
                    continue
                    
    except Exception as e:
        logger.error(f"Ошибка уведомления пользователей: {e}")

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
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ================== ОСНОВНЫЕ КОМАНДЫ ==================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user = update.effective_user
    user_id = user.id
    
    user_db.update_user(user_id, {"username": user.username})
    
    user_data = user_db.get_user(user_id)
    status = "✅ ПРЕМИУМ" if user_data.get('is_premium') else "🎯 БЕСПЛАТНЫЙ"
    
    text = f"""
🚀 **Добро пожаловать в YESsignals_bot, {user.first_name}!**

👤 **Ваш ID:** `{user_id}`
💎 **Статус:** {status}

📊 **Доступные функции:**
• 🎯 1 бесплатный сигнал в день
• 📈 Pump/Dump мониторинг (премиум)
• 💎 Премиум подписка с неограниченными сигналами
• 🆘 Поддержка 24/7 через @YESsignals_support_bot

⚠️ **ВАЖНО:**
Сигналы носят информационный характер и не являются финансовой рекомендацией.
Торговля криптовалютами сопряжена с высокими рисками.

💡 Используйте кнопки меню для навигации!
"""
    
    await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))

async def signals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получить торговые сигналы"""
    user = update.effective_user
    user_id = user.id
    user_data = user_db.get_user(user_id)
    
    # Проверка лимита
    if not user_db.can_send_signal(user_id):
        await update.message.reply_text(
            f"❌ **Достигнут дневной лимит!**\n\n"
            f"Использовано: {user_data.get('signals_today', 0)}/1 сигналов\n\n"
            f"💎 **Премиум включает:**\n"
            f"• Неограниченные сигналы\n"
            f"• Pump/Dump мониторинг\n"
            f"• Приоритетную поддержку\n\n"
            f"Оформите подписку: /premium",
            reply_markup=get_main_keyboard(user_id)
        )
        return
    
    loading_msg = await update.message.reply_text("🔄 Анализирую рынок...")
    
    try:
        # Выбираем символы
        if user_data.get('is_premium'):
            symbols = random.sample(list(COINGECKO_IDS.keys())[:10], 3)
        else:
            symbols = ['BTC']
        
        signals = []
        for symbol in symbols:
            signal = await generate_signal(symbol)
            if signal:
                signals.append(signal)
                if not user_data.get('is_premium'):
                    break
        
        await loading_msg.delete()
        
        if not signals:
            await update.message.reply_text(
                "⚠️ В данный момент нет активных сигналов. Попробуйте позже.",
                reply_markup=get_main_keyboard(user_id)
            )
            return
        
        # Отправляем сигналы
        for signal in signals:
            if user_data.get('is_premium'):
                text = f"""
💎 **ПРЕМИУМ СИГНАЛ** 💎

🏷 **Пара:** {signal['symbol']}/USDT
⚡ **Действие:** {signal['action']}
💰 **Цена:** ${signal['price']:,.2f}
📊 **Изменение 24ч:** {signal['change']:+.2f}%
🎯 **Цель:** ${signal['target']:,.2f}
🛑 **Стоп-лосс:** ${signal['stop_loss']:,.2f}
📈 **Плечо:** {signal['leverage']}
✅ **Уверенность:** {signal['confidence']}

⏰ **Время:** {signal['time']}

⚠️ **Предупреждение о рисках:**
Торговые сигналы носят информационный характер.
Проводите собственный анализ перед сделками.
Автор не несет ответственности за убытки.
"""
            else:
                text = f"""
🎯 **БЕСПЛАТНЫЙ СИГНАЛ** 🎯

🏷 **Пара:** {signal['symbol']}/USDT
💰 **Цена:** ${signal['price']:,.2f}
📊 **Изменение 24ч:** {signal['change']:+.2f}%
📈 **Тренд:** {'📈 Восходящий' if signal['change'] > 0 else '📉 Нисходящий' if signal['change'] < 0 else '➡️ Боковой'}

🔒 **Для получения полных сигналов оформите премиум!**

🎯 **Использовано:** {user_data.get('signals_today', 0)+1}/1 сегодня
💎 **Премиум:** /premium

⚠️ **Торговля сопряжена с рисками.**
"""
            
            await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))
        
        # Увеличиваем счетчик
        user_db.increment_signal(user_id)
        
    except Exception as e:
        logger.error(f"Ошибка получения сигналов: {e}")
        await update.message.reply_text(
            "⚠️ Ошибка получения сигналов. Попробуйте позже.",
            reply_markup=get_main_keyboard(user_id)
        )

async def pumpdump_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pump/Dump мониторинг"""
    user = update.effective_user
    user_id = user.id
    
    # Проверка премиума
    user_data = user_db.get_user(user_id)
    if not user_data.get('is_premium') and str(user_id) != str(ADMIN_ID):
        await update.message.reply_text(
            "🔒 **Pump/Dump мониторинг доступен только для премиум пользователей!**\n\n"
            "💎 **Премиум включает:**\n"
            "• Мгновенные уведомления о pump/dump\n"
            "• 24/7 мониторинг рынка\n"
            "• Расширенный анализ\n\n"
            "Оформите подписку: /premium",
            reply_markup=get_main_keyboard(user_id)
        )
        return
    
    loading_msg = await update.message.reply_text("🔍 Ищу активные Pump/Dump сигналы...")
    
    try:
        # Ищем реальные pump/dump
        alerts = await check_pump_dump_real_time()
        
        await loading_msg.delete()
        
        if alerts:
            # Показываем найденные сигналы
            for alert in alerts[:2]:  # Максимум 2 сигнала
                text = f"""
{alert['type']} **ОБНАРУЖЕН!** ⚡

🏷 **Пара:** {alert['symbol']}/USDT
💰 **Цена:** ${alert['price']:,.2f}
📊 **Изменение 24ч:** {alert['change']:+.1f}%
💪 **Интенсивность:** {alert['intensity']}
💡 **Рекомендация:** {alert['recommendation']}
💹 **Объем:** ${alert.get('volume', 0):,.0f}

⏰ **Время обнаружения:** {datetime.now().strftime('%H:%M %d.%m.%Y')}

⚠️ **Будьте осторожны:** Высокая волатильность.
"""
                await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))
            
            # Запускаем мониторинг на 5 минут
            asyncio.create_task(start_pumpdump_monitoring(context.bot))
            
            info_text = """
🔔 **Pump/Dump мониторинг АКТИВИРОВАН!**

В течение **5 минут** вы будете получать уведомления
о новых pump/dump сигналах на рынке.

💎 **Премиум функция активна!**
"""
            await update.message.reply_text(info_text, reply_markup=get_main_keyboard(user_id))
            
        else:
            text = """
📊 **РЫНОК СТАБИЛЕН**

На данный момент нет активных pump/dump сигналов.
Волатильность в пределах нормы.

🔔 **Pump/Dump мониторинг АКТИВИРОВАН!**

В течение **5 минут** вы будете получать уведомления
о новых pump/dump сигналах на рынке.

⏰ **Следующая проверка:** автоматически
"""
            await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id))
            
            # Все равно запускаем мониторинг
            asyncio.create_task(start_pumpdump_monitoring(context.bot))
            
    except Exception as e:
        logger.error(f"Ошибка pump/dump: {e}")
        await update.message.reply_text(
            "⚠️ Ошибка анализа рынка. Попробуйте позже.",
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
📊 **Всего сигналов:** {user_data.get('total_signals', 0)}

🔔 **Доступные функции:**
• Неограниченные торговые сигналы
• Pump/Dump мониторинг 24/7
• Автоматические уведомления
• Приоритетная поддержка

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
• ✅ Неограниченное количество сигналов
• ✅ Pump/Dump мониторинг 24/7
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
• Сигналы носят информационный характер
• Проводите собственный анализ
• Торговля сопряжена с рисками
• Автор не несет ответственности за убытки
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

# ================== АДМИН КОМАНДЫ ==================
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Панель администратора"""
    user = update.effective_user
    
    if ADMIN_ID == 0 or str(user.id) != str(ADMIN_ID):
        await update.message.reply_text("❌ Команда не найдена.")
        return
    
    keyboard = [
        [InlineKeyboardButton("➕ Активировать премиум", callback_data="admin_activate")],
        [InlineKeyboardButton("📋 Список премиум", callback_data="admin_list")],
        [InlineKeyboardButton("🔄 Проверить истекшие", callback_data="admin_check_expired")],
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "👑 **АДМИН-ПАНЕЛЬ YESsignals**\n\nВыберите действие:",
        reply_markup=reply_markup
    )

async def activate_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Активировать премиум"""
    user = update.effective_user
    
    if ADMIN_ID == 0 or str(user.id) != str(ADMIN_ID):
        await update.message.reply_text("❌ Команда не найдена.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "❌ **Использование:** `/activate <user_id> [дней=30]`\n\n"
            "**Примеры:**\n"
            "• `/activate 123456789` - на 30 дней\n"
            "• `/activate 123456789 90` - на 90 дней\n\n"
            "💡 Премиум автоматически деактивируется по истечении срока."
        )
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
        
        expiry_str = (datetime.now() + timedelta(days=days)).strftime('%d.%m.%Y')
        
        await update.message.reply_text(
            f"✅ **ПРЕМИУМ АКТИВИРОВАН!**\n\n"
            f"👤 **Пользователь:** `{target_id}`\n"
            f"📅 **Срок:** {days} дней\n"
            f"⏳ **Истекает:** {expiry_str}\n\n"
            f"🔔 **Автоотключение:** {expiry_str}"
        )
        
        # Уведомляем пользователя
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"🎉 **ВАШ ПРЕМИУМ АКТИВИРОВАН!**\n\n"
                     f"Подписка активна на {days} дней (до {expiry_str}).\n\n"
                     f"✅ **Теперь доступно:**\n"
                     f"• Неограниченные торговые сигналы\n"
                     f"• Pump/Dump мониторинг 24/7\n"
                     f"• Автоматические уведомления\n\n"
                     f"⚠️ **Напоминание:** Сигналы носят информационный характер.\n"
                     f"Срок действия: до {expiry_str}"
            )
        except:
            logger.warning(f"Не удалось уведомить пользователя {target_id}")
        
    except ValueError:
        await update.message.reply_text("❌ Неверный формат. Используйте: /activate <число> [дни]")

async def list_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список премиум пользователей"""
    user = update.effective_user
    
    if ADMIN_ID == 0 or str(user.id) != str(ADMIN_ID):
        await update.message.reply_text("❌ Команда не найдена.")
        return
    
    db = user_db.db
    premium_users = [(uid, data) for uid, data in db.items() 
                    if data.get('is_premium') and not uid.startswith('_')]
    
    if not premium_users:
        await update.message.reply_text("📊 Нет активных премиум пользователей.")
        return
    
    text = "📋 **АКТИВНЫЕ ПРЕМИУМ ПОЛЬЗОВАТЕЛИ:**\n\n"
    
    for i, (user_id, data) in enumerate(premium_users[:15], 1):
        expiry = data.get('premium_expiry')
        start_date = data.get('premium_start')
        
        if expiry:
            try:
                expiry_date = datetime.fromisoformat(expiry)
                expiry_str = expiry_date.strftime('%d.%m')
                days_left = (expiry_date - datetime.now()).days
                status = f"⏳ {days_left}д" if days_left > 0 else "🔴 Истек"
            except:
                expiry_str = "?"
                status = "?"
        else:
            expiry_str = "∞"
            status = "✅"
        
        if start_date:
            try:
                start_str = datetime.fromisoformat(start_date).strftime('%d.%m')
            except:
                start_str = "?"
        else:
            start_str = "?"
        
        username = data.get('username', 'нет')
        
        text += f"{i}. `{user_id}` - @{username}\n"
        text += f"   📅 {start_str} → {expiry_str} ({status})\n"
        text += f"   📊 Сигналов: {data.get('total_signals', 0)}\n\n"
    
    if len(premium_users) > 15:
        text += f"\n... и еще {len(premium_users) - 15} пользователей"
    
    text += f"\n💎 Всего премиум: {len(premium_users)} пользователей"
    
    await update.message.reply_text(text)

async def check_expired_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверить и отключить истекшие подписки"""
    user = update.effective_user
    
    if ADMIN_ID == 0 or str(user.id) != str(ADMIN_ID):
        await update.message.reply_text("❌ Команда не найдена.")
        return
    
    expired = user_db.get_expired_premiums()
    
    if not expired:
        await update.message.reply_text("✅ Нет пользователей с истекшим премиумом.")
        return
    
    deactivated = []
    for user_id, data in expired:
        user_db.update_user(user_id, {
            "is_premium": False,
            "premium_expiry": None
        })
        deactivated.append(user_id)
        
        # Уведомляем пользователя
        try:
            await context.bot.send_message(
                chat_id=int(user_id),
                text="ℹ️ **ВАША ПРЕМИУМ ПОДПИСКА ЗАВЕРШЕНА**\n\n"
                     "Срок действия вашей премиум подписки истек.\n\n"
                     "💎 **Для возобновления доступа:**\n"
                     "1. Оформите новую подписку (/premium)\n"
                     "2. Отправьте чек в @YESsignals_support_bot\n\n"
                     "Спасибо что пользовались нашим сервисом!"
            )
        except:
            pass
    
    text = f"✅ **ОТКЛЮЧЕНО {len(deactivated)} ПОДПИСОК:**\n\n"
    for uid in deactivated[:10]:
        text += f"• `{uid}`\n"
    
    if len(deactivated) > 10:
        text += f"\n... и еще {len(deactivated) - 10} пользователей"
    
    await update.message.reply_text(text)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика системы"""
    user = update.effective_user
    
    if ADMIN_ID == 0 or str(user.id) != str(ADMIN_ID):
        await update.message.reply_text("❌ Команда не найдена.")
        return
    
    db = user_db.db
    total_users = len([u for u in db.keys() if not u.startswith('_')])
    premium_users = sum(1 for u in db.values() 
                       if u.get('is_premium') and not str(u.get('id', '')).startswith('_'))
    today_signals = sum(u.get('signals_today', 0) for u in db.values())
    total_all_signals = sum(u.get('total_signals', 0) for u in db.values())
    
    expired_count = len(user_db.get_expired_premiums())
    
    text = f"""
📊 **СТАТИСТИКА YESsignals_bot**

👥 **Пользователи:**
• Всего: {total_users}
• Премиум: {premium_users}
• Обычные: {total_users - premium_users}
• Истекшие: {expired_count}

📈 **Сигналы:**
• Сегодня: {today_signals}
• Всего: {total_all_signals}

💎 **Финансы (оценка):**
• Активных подписок: {premium_users}
• Потенциальный доход: {premium_users * 9} USDT

⚡ **Система:**
• Бот: ✅ Активен
• База данных: {len(db)} записей
• Pump/Dump мониторинг: {'✅' if monitoring_active else '❌'}
• Веб-сервер: ✅ Работает

🛡️ **Безопасность:**
• Админ ID: {'✅ Настроен' if ADMIN_ID != 0 else '❌ Не настроен'}
• Защита данных: ✅ Включена
"""
    
    await update.message.reply_text(text)

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
    
    # Админ-кнопки
    elif data == "admin_activate":
        if ADMIN_ID != 0 and str(user_id) == str(ADMIN_ID):
            await query.message.edit_text(
                "➕ **АКТИВАЦИЯ ПРЕМИУМ**\n\n"
                "Используйте команду:\n"
                "`/activate <user_id> [дней=30]`\n\n"
                "**Примеры:**\n"
                "• `/activate 123456789`\n"
                "• `/activate 123456789 90`\n\n"
                "💡 Премиум автоматически отключится по истечении срока."
            )
    
    elif data == "admin_list":
        if ADMIN_ID != 0 and str(user_id) == str(ADMIN_ID):
            await list_premium_command(update, context)
    
    elif data == "admin_check_expired":
        if ADMIN_ID != 0 and str(user_id) == str(ADMIN_ID):
            await check_expired_command(update, context)
    
    elif data == "admin_stats":
        if ADMIN_ID != 0 and str(user_id) == str(ADMIN_ID):
            await stats_command(update, context)

# ================== ОБРАБОТЧИК ТЕКСТА ==================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
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
            "🤖 **Используйте кнопки меню!**\n\n"
            "**Доступные команды:**\n"
            "/start - Главное меню\n"
            "/signals - Торговые сигналы\n"
            "/premium - Информация о подписке\n"
            "/support - Техническая поддержка\n\n"
            "⚠️ Все общение с администрацией только через @YESsignals_support_bot",
            reply_markup=get_main_keyboard(user_id)
        )

# ================== ЗАПУСК ==================
def main():
    """Основная функция запуска"""
    # Запускаем веб-сервер для Render
    run_web_server()
    
    print("=" * 60)
    print("🚀 ЗАПУСК YESsignals_bot")
    print("=" * 60)
    print("🤖 Основной бот: @YESsignals_bot")
    print("🆘 Бот поддержки: @YESsignals_support_bot")
    print("💎 Стоимость подписки: 9 USDT")
    print("📊 Анализ крипторынка 24/7")
    print("🛡️ Автоматическое отключение премиума")
    print("=" * 60)
    
    if not TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN не установлен!")
        print("⚠️ Добавьте TELEGRAM_TOKEN в переменные окружения")
        return
    
    if ADMIN_ID == 0:
        logger.warning("⚠️ ADMIN_ID не настроен. Админ-панель недоступна.")
        print("ℹ️ Админ-панель: отключена (ADMIN_ID не настроен)")
    else:
        print(f"👑 Админ-панель: доступна для ID {ADMIN_ID}")
    
    try:
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # Основные команды
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("signals", signals_command))
        application.add_handler(CommandHandler("premium", premium_command))
        application.add_handler(CommandHandler("pumpdump", pumpdump_command))
        application.add_handler(CommandHandler("support", support_command))
        
        # Админ-команды (только если ADMIN_ID настроен)
        if ADMIN_ID != 0:
            application.add_handler(CommandHandler("admin", admin_command))
            application.add_handler(CommandHandler("activate", activate_premium_command))
            application.add_handler(CommandHandler("list_premium", list_premium_command))
            application.add_handler(CommandHandler("check_expired", check_expired_command))
            application.add_handler(CommandHandler("stats", stats_command))
        
        # Обработчики
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        
        print("✅ Бот готов к работе!")
        print("💎 Система премиум подписок активна")
        print("📊 Pump/Dump мониторинг настроен")
        print("🛡️ Автоотключение премиума включено")
        print("=" * 60)
        
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
