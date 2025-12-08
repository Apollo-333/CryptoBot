try:
    import imghdr
except ImportError:
    # Импортируем наш фикс
    try:
        from imghdr_fix import ImghdrMock
        import sys
        sys.modules['imghdr'] = ImghdrMock()
        import imghdr
    except ImportError:
        # Создаем простой фикс на месте
        import sys
        
        class SimpleImghdr:
            @staticmethod
            def what(file, h=None):
                return 'jpeg'  # Всегда возвращаем jpeg как fallback
                
        sys.modules['imghdr'] = SimpleImghdr()
        import imghdr
        from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
import logging
import os
from datetime import datetime
import time

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Токен бота-помощника из переменных окружения
SUPPORT_BOT_TOKEN = os.getenv("SUPPORT_BOT_TOKEN")
# Ваш ID администратора из переменных окружения
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

print(f"🔧 Запуск бота поддержки...")
print(f"👨‍💻 ADMIN_ID: {ADMIN_ID}")

# Словарь для отслеживания активных диалогов
active_conversations = {}

def start_command(update, context):
    """Приветственное сообщение бота поддержки"""
    user = update.effective_user
    print(f"🎯 Новый пользователь: {user.id} - {user.first_name}")

    active_conversations[user.id] = {
        'name': f"{user.first_name} {user.last_name or ''}",
        'username': user.username,
        'active': True
    }

    welcome_text = f"""
🤖 Crypto Signals Support

Здравствуйте, {user.first_name}! Я бот технической поддержки.

📋 Я могу помочь с:
• Техническими проблемами с ботом
• Вопросами по оплате и подписке
• Активацией премиум доступа
• Любыми другими вопросами

💡 Для быстрого решения:
1. Опишите вашу проблему подробно
2. Укажите ваш ID: {user.id}
3. Приложите скриншот если есть

⏰ Время ответа: до 15 минут
    """

    keyboard = [
        [InlineKeyboardButton("💳 Оплата подписки", callback_data="payment_info")],
        [InlineKeyboardButton("📋 Частые вопросы", callback_data="faq")],
        [InlineKeyboardButton("🔧 Технические проблемы", callback_data="tech_issues")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(welcome_text, parse_mode='Markdown', reply_markup=reply_markup)

    admin_notification = f"""
🔔 НОВОЕ ОБРАЩЕНИЕ В ПОДДЕРЖКУ

👤 Пользователь начал диалог:
Имя: {user.first_name} {user.last_name or ''}
ID: {user.id}
Username: @{user.username or 'нет'}

🕒 Время: {update.message.date.strftime('%H:%M %d.%m.%Y')}

💬 Для ответа отправьте:
/reply {user.id} ваш ответ
    """

    try:
        context.bot.send_message(chat_id=ADMIN_ID, text=admin_notification, parse_mode='Markdown')
        print("✅ Уведомление отправлено администратору")
    except Exception as e:
        print(f"❌ Ошибка отправки уведомления: {e}")

def forward_to_admin(update, context):
    """Пересылка сообщения пользователя администратору"""
    user = update.effective_user
    message = update.message

    print(f"📨 Сообщение от {user.id}: {message.text}")

    try:
        message.reply_text("✅ Ваше сообщение получено! Администратор свяжется с вами в течение 15 минут.", parse_mode='Markdown')
        message.forward(chat_id=ADMIN_ID)

        user_info = f"""
👤 Сообщение от пользователя:
Имя: {user.first_name} {user.last_name or ''}
ID: {user.id}
Username: @{user.username or 'нет'}

🕒 Время: {message.date.strftime('%H:%M %d.%m.%Y')}

💬 Для ответа:
/reply {user.id} ваш текст ответа
        """
        context.bot.send_message(chat_id=ADMIN_ID, text=user_info, parse_mode='Markdown')
        print("✅ Сообщение переслано администратору")

    except Exception as e:
        print(f"❌ Ошибка пересылки: {e}")
        message.reply_text("❌ Произошла ошибка при отправке сообщения.")

def handle_photo(update, context):
    """Обработка фотографий"""
    user = update.effective_user
    message = update.message

    print(f"📸 Фото от {user.id}")

    try:
        message.reply_text("✅ Скриншот получен! Администратор проверит его в течение 15 минут.", parse_mode='Markdown')
        message.forward(chat_id=ADMIN_ID)

        admin_notification = f"""
📸 ПОЛУЧЕН СКРИНШОТ ОПЛАТЫ

👤 От пользователя:
Имя: {user.first_name} {user.last_name or ''}
ID: {user.id}
Username: @{user.username or 'нет'}

🕒 Время: {message.date.strftime('%H:%M %d.%m.%Y')}

💬 Для ответа:
/reply {user.id} ваш текст ответа
        """
        context.bot.send_message(chat_id=ADMIN_ID, text=admin_notification, parse_mode='Markdown')
        print("✅ Фото переслано администратору")

    except Exception as e:
        print(f"❌ Ошибка пересылки фото: {e}")

def admin_reply_command(update, context):
    """Ответ пользователю (только для админа)"""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        update.message.reply_text("❌ Доступ запрещен")
        return

    if not context.args or len(context.args) < 2:
        update.message.reply_text("❌ Использование: /reply <user_id> <сообщение>")
        return

    try:
        target_user_id = int(context.args[0])
        message_text = ' '.join(context.args[1:])
        context.bot.send_message(chat_id=target_user_id, text=f"💬 Ответ от поддержки:\n\n{message_text}", parse_mode='Markdown')
        update.message.reply_text(f"✅ Ответ отправлен пользователю {target_user_id}")
        print(f"📤 Админ отправил ответ пользователю {target_user_id}")
    except Exception as e:
        update.message.reply_text(f"❌ Не удалось отправить сообщение: {e}")
        print(f"❌ Ошибка: {e}")

def handle_payment_info(update, context):
    query = update.callback_query
    query.answer()
    payment_text = """
💳 Информация об оплате:

USDT (TRC20): `TF33keB2N3P226zxFfESVCvXCFQMjnMXQh`
Стоимость подписки: 1 месяц = 9 USDT
    """
    query.message.reply_text(payment_text, parse_mode='Markdown')

def handle_faq(update, context):
    query = update.callback_query
    query.answer()
    faq_text = """
❓ Частые вопросы:

🔧 Бот не отвечает:
• Перезапустите командой /start
• Проверьте интернет

💎 Не приходят сигналы:
• Лимит бесплатных сигналов (1 в день)
• Активируйте премиум

⏰ Подписка не активирована:
• Отправьте скриншот оплаты
• Ожидайте до 15 минут
    """
    query.message.reply_text(faq_text, parse_mode='Markdown')

def handle_message(update, context):
    if update.message.text and not update.message.text.startswith('/'):
        forward_to_admin(update, context)

def main():
    """Запуск бота поддержки"""
    print("🚀 Запуск бота поддержки...")
    
    if not SUPPORT_BOT_TOKEN:
        print("⚠️ SUPPORT_BOT_TOKEN не найден")
        return
    
    from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
    
    updater = Updater(SUPPORT_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start_command))
    dp.add_handler(CommandHandler("reply", admin_reply_command))
    dp.add_handler(CallbackQueryHandler(handle_payment_info, pattern="payment_info"))
    dp.add_handler(CallbackQueryHandler(handle_faq, pattern="faq"))
    dp.add_handler(CallbackQueryHandler(handle_faq, pattern="tech_issues"))
    dp.add_handler(MessageHandler(Filters.photo, handle_photo))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    
    print("✅ Бот поддержки запущен...")
    print(f"👨‍💻 ADMIN_ID: {ADMIN_ID}")
    print("👨‍💻 Для ответа: /reply <user_id> <сообщение>")
    
    # ЗАПУСКАЕМ БЕЗ idle()!
    updater.start_polling()
    
    # Вместо idle() делаем бесконечный цикл
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Остановка бота поддержки...")
        updater.stop()

if __name__ == "__main__":
    main()
