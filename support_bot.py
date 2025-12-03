from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import logging
import sqlite3
import os
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Токен бота-помощника из переменных окружения
SUPPORT_BOT_TOKEN = '8363521944:AAEzSvJu6NgO6t-kyMIpox6e5UfZFJvm9vI'
# Ваш ID администратора из переменных окружения
ADMIN_ID = 638584949

print(f"🔧 Запуск бота поддержки...")
print(f"👨‍💻 ADMIN_ID: {ADMIN_ID}")

# Словарь для отслеживания активных диалогов
active_conversations = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственное сообщение бота поддержки"""
    user = update.effective_user
    print(f"🎯 Новый пользователь: {user.id} - {user.first_name}")

    # Сохраняем информацию о пользователе
    active_conversations[user.id] = {
        'name': f"{user.first_name} {user.last_name or ''}",
        'username': user.username,
        'active': True
    }

    welcome_text = f"""
🤖 **Crypto Signals Support**

Здравствуйте, {user.first_name}! Я бот технической поддержки.

📋 **Я могу помочь с:**
• Техническими проблемами с ботом
• Вопросами по оплате и подписке
• Активацией премиум доступа
• Любыми другими вопросами

💡 **Для быстрого решения:**
1. Опишите вашу проблему подробно
2. Укажите ваш ID: `{user.id}`
3. Приложите скриншот если есть

⏰ **Время ответа:** до 15 минут
    """

    keyboard = [
        [InlineKeyboardButton("💳 Оплата подписки", callback_data="payment_info")],
        [InlineKeyboardButton("📋 Частые вопросы", callback_data="faq")],
        [InlineKeyboardButton("🔧 Технические проблемы", callback_data="tech_issues")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome_text, parse_mode='Markdown', reply_markup=reply_markup)

    # Уведомляем администратора о новом обращении
    admin_notification = f"""
🔔 **НОВОЕ ОБРАЩЕНИЕ В ПОДДЕРЖКУ**

👤 **Пользователь начал диалог:**
Имя: {user.first_name} {user.last_name or ''}
ID: `{user.id}`
Username: @{user.username or 'нет'}

🕒 Время: {update.message.date.strftime('%H:%M %d.%m.%Y')}

💬 **Отправьте ответ командой:**
`/reply {user.id} ваш ответ`
    """

    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_notification, parse_mode='Markdown')
        print(f"✅ Уведомление отправлено администратору")
    except Exception as e:
        print(f"❌ Ошибка отправки уведомления: {e}")

async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пересылка сообщения пользователя администратору"""
    user = update.effective_user
    message = update.message

    print(f"📨 Сообщение от {user.id}: {message.text}")

    try:
        # Сначала отправляем подтверждение пользователю
        await message.reply_text(
            "✅ Ваше сообщение получено! Администратор свяжется с вами в течение 15 минут.",
            parse_mode='Markdown'
        )

        # Пересылаем оригинальное сообщение администратору
        await message.forward(chat_id=ADMIN_ID)

        # Отправляем информацию о пользователе
        user_info = f"""
👤 **Сообщение от пользователя:**
Имя: {user.first_name} {user.last_name or ''}
ID: `{user.id}`
Username: @{user.username or 'нет'}

🕒 Время: {message.date.strftime('%H:%M %d.%m.%Y')}

💬 **Для ответа отправьте:**
`/reply {user.id} ваш текст ответа`
        """

        await context.bot.send_message(
            chat_id=ADMIN_ID, 
            text=user_info, 
            parse_mode='Markdown'
        )

        print(f"✅ Сообщение переслано администратору")

    except Exception as e:
        print(f"❌ Ошибка пересылки: {e}")
        await message.reply_text("❌ Произошла ошибка при отправке сообщения.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка фотографий (скриншотов оплаты)"""
    user = update.effective_user
    message = update.message

    print(f"📸 Фото от {user.id}")

    try:
        # Сначала подтверждаем пользователю
        await message.reply_text(
            "✅ Скриншот получен! Администратор проверит его в течение 15 минут.",
            parse_mode='Markdown'
        )

        # Пересылаем фото администратору
        await message.forward(chat_id=ADMIN_ID)

        # Уведомление администратора
        admin_notification = f"""
📸 **ПОЛУЧЕН СКРИНШОТ ОПЛАТЫ**

👤 **От пользователя:**
Имя: {user.first_name} {user.last_name or ''}
ID: `{user.id}`
Username: @{user.username or 'нет'}

🕒 Время: {message.date.strftime('%H:%M %d.%m.%Y')}

💬 **Для ответа отправьте:**
`/reply {user.id} ваш текст ответа`
        """

        await context.bot.send_message(
            chat_id=ADMIN_ID, 
            text=admin_notification, 
            parse_mode='Markdown'
        )

        print(f"✅ Фото переслано администратору")

    except Exception as e:
        print(f"❌ Ошибка пересылки фото: {e}")

async def admin_reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для ответа пользователю (только для админа)"""
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Доступ запрещен")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text("❌ Использование: /reply <user_id> <сообщение>")
        return

    try:
        target_user_id = int(context.args[0])
        message_text = ' '.join(context.args[1:])

        # Отправляем сообщение пользователю
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"💬 **Ответ от поддержки:**\n\n{message_text}\n\n_Вы можете продолжить диалог в этом чате_",
            parse_mode='Markdown'
        )

        # Подтверждаем администратору
        await update.message.reply_text(f"✅ Ответ отправлен пользователю {target_user_id}")

        # Логируем действие
        print(f"📤 Админ отправил ответ пользователю {target_user_id}")

    except Exception as e:
        error_msg = f"❌ Не удалось отправить сообщение: {e}"
        await update.message.reply_text(error_msg)
        print(error_msg)

async def handle_payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация об оплате"""
    query = update.callback_query
    await query.answer()

    payment_text = """
💳 **Информация об оплате:**

💰 **Реквизиты:**
USDT (TRC20): `TF33keB2N3P226zxFfESVCvXCFQMjnMXQh`

💎 **Стоимость подписки:**
1 месяц - 2,499 ₽

📋 **Процесс оплаты:**
1. Отправьте USDT на указанный адрес
2. Сохраните скриншот/чек транзакции
3. Отправьте его мне с указанием вашего ID
4. Ожидайте активации (до 15 минут)

❓ **Отправьте скриншот чека для активации подписки**
    """

    await query.message.reply_text(payment_text, parse_mode='Markdown')

async def handle_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Частые вопросы"""
    query = update.callback_query
    await query.answer()

    faq_text = """
❓ **Частые вопросы:**

🔧 **Бот не отвечает:**
• Перезапустите бота командой /start
• Проверьте подключение к интернету

💎 **Не приходят сигналы:**
• Проверьте лимит бесплатных сигналов (1 в день)
• Убедитесь что активирована премиум подписка

⏰ **Подписка не активирована:**
• Отправьте скриншот оплаты
• Ожидайте до 15 минут
• Напишите нам если прошло больше времени

📱 **Другие проблемы:**
Опишите подробно вашу проблему ниже и я передам администратору.
    """

    await query.message.reply_text(faq_text, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    if update.message.text and not update.message.text.startswith('/'):
        await forward_to_admin(update, context)

def main():
    """Запуск бота поддержки"""
    print("🚀 Запуск бота поддержки...")

    if not SUPPORT_BOT_TOKEN:
        print("⚠️ SUPPORT_BOT_TOKEN не найден в переменных окружения")
        print("💡 Добавьте SUPPORT_BOT_TOKEN в секреты для запуска бота поддержки")
        return

    try:
        application = Application.builder().token(SUPPORT_BOT_TOKEN).build()

        # Добавляем обработчики
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("reply", admin_reply_command))
        application.add_handler(CallbackQueryHandler(handle_payment_info, pattern="payment_info"))
        application.add_handler(CallbackQueryHandler(handle_faq, pattern="faq"))
        application.add_handler(CallbackQueryHandler(handle_faq, pattern="tech_issues"))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        print("✅ Бот поддержки запущен и слушает сообщения...")
        print("💡 Напишите в @CryptoSignalsSupportBot для теста")
        print("👨‍💻 Для ответа пользователям используйте: /reply <user_id> <сообщение>")

        application.run_polling()

    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        print("🔧 Проверьте токен бота")

if __name__ == '__main__':
    main()
