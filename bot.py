"""
🚀 FINAL WORKING BOT - NO CONFLICTS
Только один бот, никаких параллельных запусков!
"""
import os
import sys
import time
import logging
from datetime import datetime

# ================== НАСТРОЙКА ==================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID", "0")

print("=" * 60)
print("🤖 CRYPTO SIGNALS BOT v2.0")
print("=" * 60)
print(f"Token: {'✅' if TELEGRAM_TOKEN else '❌'}")
print(f"Admin ID: {ADMIN_ID}")
print("=" * 60)

# Простая база данных в памяти
users_db = {}
premium_users = set()

def is_admin(user_id):
    return str(user_id) == ADMIN_ID

# ================== БОТ ==================
def run_bot():
    """Основная функция бота"""
    if not TELEGRAM_TOKEN:
        logger.error("❌ No TELEGRAM_TOKEN!")
        return
    
    try:
        from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
        from telegram import ParseMode
        
        logger.info("🚀 Starting bot...")
        
        # ВАЖНО: Создаем ТОЛЬКО ОДИН экземпляр
        updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
        dispatcher = updater.dispatcher
        
        # ================== КОМАНДЫ ==================
        def start(update, context):
            user = update.effective_user
            user_id = user.id
            
            if user_id not in users_db:
                users_db[user_id] = {
                    'name': user.first_name,
                    'is_premium': False,
                    'signals': 0
                }
            
            text = f"""
🚀 **Welcome, {user.first_name}!**

Your ID: `{user_id}`
Status: {'💎 PREMIUM' if users_db[user_id]['is_premium'] else '🎯 FREE'}

**Commands:**
/signals - Get trading signals
/premium - Premium subscription
/status - My status
/help - Help
            """
            
            update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        
        def signals(update, context):
            user_id = update.effective_user.id
            
            if user_id not in users_db:
                users_db[user_id] = {'is_premium': False, 'signals': 0}
            
            user_data = users_db[user_id]
            
            if user_data['is_premium']:
                # Премиум сигнал
                text = """
💎 **PREMIUM SIGNAL** 💎

🏷 Pair: BTC/USDT
⚡ Action: BUY
💰 Price: $42,500
🎯 Target: $44,000
🛑 Stop-loss: $41,800
📈 Leverage: 3x
✅ Confidence: 85%

⏰ Time: Immediate
💡 Analysis: Strong bullish trend
                """
            else:
                # Бесплатный сигнал (лимит 1 в день)
                user_data['signals'] += 1
                text = f"""
🎯 **FREE SIGNAL** 🎯

🏷 Pair: BTC/USDT
💰 Current: Market analysis...
📊 Trend: Mixed signals

⚠️ **Free signals used: {user_data['signals']}/1 today**

💎 **Upgrade to premium for:**
• Unlimited signals
• Exact entry/exit points
• Stop-loss recommendations
                """
            
            update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        
        def premium(update, context):
            user_id = update.effective_user.id
            user_data = users_db.get(user_id, {'is_premium': False})
            
            if user_data['is_premium']:
                text = """
💎 **YOUR PREMIUM IS ACTIVE**

✅ All premium features unlocked
📊 Enjoy unlimited signals!
                """
            else:
                text = f"""
💎 **PREMIUM SUBSCRIPTION**

💰 1 month: 9 USDT
🎯 Your ID: `{user_id}`

💳 **Payment:**
USDT (TRC20): `TF33keB2N3P226zxFfESVCvXCFQMjnMXQh`

📋 **After payment:**
1. Send screenshot to admin
2. Wait for activation (15 min)

⚡ **Features:**
• Unlimited trading signals
• Exact entry/exit points
• Priority support
                """
            
            update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        
        def status(update, context):
            user_id = update.effective_user.id
            user_data = users_db.get(user_id, {'is_premium': False, 'signals': 0})
            
            text = f"""
📊 **YOUR STATUS**

👤 ID: `{user_id}`
💎 Premium: {'✅ ACTIVE' if user_data['is_premium'] else '❌ INACTIVE'}
📈 Signals today: {user_data['signals']}

{'🎯 Upgrade with /premium' if not user_data['is_premium'] else '✅ Enjoy premium features!'}
            """
            
            update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        
        # ================== АДМИН КОМАНДЫ ==================
        def activate_premium(update, context):
            user_id = update.effective_user.id
            
            if not is_admin(user_id):
                update.message.reply_text("❌ Access denied")
                return
            
            if not context.args:
                update.message.reply_text("❌ Usage: /activate <user_id> [days=30]")
                return
            
            try:
                target_id = int(context.args[0])
                days = int(context.args[1]) if len(context.args) > 1 else 30
                
                # Активируем премиум
                if target_id not in users_db:
                    users_db[target_id] = {'is_premium': True, 'signals': 0}
                else:
                    users_db[target_id]['is_premium'] = True
                
                premium_users.add(target_id)
                
                update.message.reply_text(
                    f"✅ Premium activated for user {target_id} ({days} days)\n"
                    f"Total premium users: {len(premium_users)}"
                )
                
                # Уведомляем пользователя
                try:
                    context.bot.send_message(
                        chat_id=target_id,
                        text="🎉 **YOUR PREMIUM IS ACTIVATED!**\n\n"
                             "Thank you! All premium features are now unlocked.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except:
                    pass
                    
            except ValueError:
                update.message.reply_text("❌ Invalid user ID")
        
        def list_users(update, context):
            user_id = update.effective_user.id
            
            if not is_admin(user_id):
                update.message.reply_text("❌ Access denied")
                return
            
            if not users_db:
                update.message.reply_text("📊 No users yet")
                return
            
            text = "📊 **USERS:**\n\n"
            for uid, data in users_db.items():
                status = "💎" if data['is_premium'] else "🎯"
                text += f"{status} ID: `{uid}` - {data.get('name', 'Unknown')}\n"
            
            text += f"\n📈 Total: {len(users_db)} users"
            text += f"\n💎 Premium: {len(premium_users)} users"
            
            update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        
        # ================== РЕГИСТРАЦИЯ КОМАНД ==================
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("signals", signals))
        dispatcher.add_handler(CommandHandler("premium", premium))
        dispatcher.add_handler(CommandHandler("status", status))
        dispatcher.add_handler(CommandHandler("help", start))
        
        # Админ команды
        dispatcher.add_handler(CommandHandler("activate", activate_premium))
        dispatcher.add_handler(CommandHandler("list", list_users))
        dispatcher.add_handler(CommandHandler("users", list_users))
        
        # ================== ЗАПУСК ==================
        logger.info("✅ Bot initialized successfully")
        
        # КРИТИЧЕСКИ ВАЖНО: Сбрасываем offset
        try:
            logger.info("🔄 Resetting offset...")
            updater.bot.get_updates(offset=-1)
            time.sleep(1)
        except Exception as e:
            logger.warning(f"Offset reset warning: {e}")
        
        # Запускаем polling
        updater.start_polling(
            poll_interval=2.0,
            timeout=20,
            drop_pending_updates=True,
            allowed_updates=['message', 'callback_query']
        )
        
        logger.info("🤖 Bot is now listening for messages...")
        logger.info(f"👑 Admin ID: {ADMIN_ID}")
        logger.info(f"👥 Users in DB: {len(users_db)}")
        
        # Бесконечный цикл
        try:
            while True:
                time.sleep(10)
        except KeyboardInterrupt:
            logger.info("\n🛑 Bot stopped by user")
        except Exception as e:
            logger.error(f"❌ Bot error: {e}")
        
        updater.stop()
        
    except Exception as e:
        logger.error(f"❌ Failed to start bot: {e}")
        import traceback
        traceback.print_exc()

# ================== ВЕБ-СЕРВЕР ==================
def run_web():
    """Простой веб-сервер для Render"""
    from flask import Flask
    from waitress import serve
    
    app = Flask(__name__)
    
    @app.route('/')
    def home():
        return f"""
        <html>
            <head><title>Crypto Signals Bot</title></head>
            <body>
                <h1>🤖 Crypto Signals Bot</h1>
                <p>Status: <span style="color:green">✅ ACTIVE</span></p>
                <p>Time: {datetime.now().strftime('%H:%M:%S')}</p>
                <p>Users: {len(users_db)}</p>
                <p>Premium users: {len(premium_users)}</p>
                <p><a href="/health">Health check</a></p>
            </body>
        </html>
        """
    
    @app.route('/health')
    def health():
        return "OK", 200
    
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🌐 Web server starting on port {port}")
    
    # Блокирующий запуск
    serve(app, host="0.0.0.0", port=port)

# ================== ГЛАВНАЯ ФУНКЦИЯ ==================
def main():
    """Запуск всей системы"""
    import threading
    
    # Проверяем токен
    if not TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN is required!")
        return
    
    # Запускаем веб-сервер в отдельном потоке
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    
    # Ждем немного
    time.sleep(3)
    
    # Запускаем бота в основном потоке
    run_bot()

# ================== ЗАПУСК ==================
if __name__ == "__main__":
    print("🚀 Starting Crypto Signals System...")
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Shutdown requested")
    except Exception as e:
        print(f"❌ Critical error: {e}")
        sys.exit(1)
