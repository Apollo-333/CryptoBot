"""
🤖 CRYPTO SIGNALS SUPPORT BOT
Принимает чеки об оплате и вопросы от пользователей
"""

import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# ================== НАСТРОЙКА ==================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен из переменных окружения Render
SUPPORT_BOT_TOKEN = os.getenv("SUPPORT_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "638584949"))  # Ваш ID из основного бота

print("=" * 60)
print("🤖 ЗАПУСК CRYPTO SIGNALS SUPPORT BOT")
print("=" * 60)

# ================== КОМАНДЫ ==================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственное сообщение"""
    user = update.effective_user
    
    # Логируем обращение
    logger.info(f"🆘 Новое обращение: {user.id} - {user.username}")
    
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
        [InlineKeyboardButton("🔧 Тех. проблемы", callback_data="tech_issues")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    
    # Уведомляем администратора
    try:
        admin_text = f"""
🔔 **НОВОЕ ОБРАЩЕНИЕ В ПОДДЕРЖКУ**

👤 **Пользователь начал диалог:**
Имя: {user.first_name} {user.last_name or ''}
ID: `{user.id}`
Username: @{user.username or 'нет'}

🕒 Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}

💬 **Для ответа используйте:**
`/reply {user.id} ваш ответ`
        """
        
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_text
        )
        
        logger.info(f"✅ Уведомление отправлено администратору {ADMIN_ID}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка уведомления админа: {e}")

async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пересылка сообщения администратору"""
    user = update.effective_user
    message = update.message
    
    logger.info(f"📨 Сообщение от {user.id}: {message.text}")
    
    try:
        # Подтверждение пользователю
        await message.reply_text(
            "✅ Ваше сообщение получено! Администратор свяжется с вами в течение 15 минут."
        )
        
        # Пересылаем сообщение администратору
        await message.forward(chat_id=ADMIN_ID)
        
        # Дополнительная информация админу
        admin_info = f"""
👤 **Сообщение от пользователя:**
Имя: {user.first_name} {user.last_name or ''}
ID: `{user.id}`
Username: @{user.username or 'нет'}

🕒 Время: {message.date.strftime('%H:%M %d.%m.%Y')}

💬 **Для ответа:**
`/reply {user.id} ваш текст`
        """
        
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_info
        )
        
        logger.info(f"✅ Сообщение переслано администратору")
        
    except Exception as e:
        logger.error(f"❌ Ошибка пересылки: {e}")
        await message.reply_text("❌ Произошла ошибка при отправке сообщения.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка фотографий (скриншоты оплаты)"""
    user = update.effective_user
    message = update.message
    
    logger.info(f"📸 Фото от {user.id}")
    
    try:
        # Подтверждение пользователю
        await message.reply_text(
            "✅ Скриншот получен! Администратор проверит его в течение 15 минут."
        )
        
        # Пересылаем фото администратору
        await message.forward(chat_id=ADMIN_ID)
        
        # Если есть подпись - пересылаем и её
        if message.caption:
            caption_msg = f"📝 **Подпись к скриншоту:**\n{message.caption}\n\n👤 От: {user.first_name} (ID: {user.id})"
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=caption_msg
            )
        
        # Уведомление администратора
        admin_notification = f"""
📸 **ПОЛУЧЕН СКРИНШОТ ОПЛАТЫ**

👤 **От пользователя:**
Имя: {user.first_name} {user.last_name or ''}
ID: `{user.id}`
Username: @{user.username or 'нет'}

🕒 Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}

💬 **Для ответа:**
`/reply {user.id} ваш текст`
        """
        
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_notification
        )
        
        logger.info(f"✅ Фото переслано администратору")
        
    except Exception as e:
        logger.error(f"❌ Ошибка пересылки фото: {e}")

async def admin_reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для ответа от администратора"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "❌ **Использование:** `/reply <user_id> <сообщение>`\n\n"
            "**Пример:**\n"
            "`/reply 123456789 Ваша подписка активирована!`"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        message_text = ' '.join(context.args[1:])
        
        # Отправляем сообщение пользователю
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"💬 **Ответ от поддержки:**\n\n{message_text}\n\n_Вы можете продолжить диалог в этом чате_"
        )
        
        # Подтверждение администратору
        await update.message.reply_text(f"✅ Ответ отправлен пользователю {target_user_id}")
        
        # Логируем в файл (для истории)
        with open("support_log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now()}] Админ {user_id} -> Пользователь {target_user_id}: {message_text}\n")
        
        logger.info(f"📤 Админ {user_id} отправил ответ пользователю {target_user_id}")
        
    except Exception as e:
        error_msg = f"❌ Не удалось отправить сообщение: {e}"
        await update.message.reply_text(error_msg)
        logger.error(error_msg)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка документов (чеки, PDF и т.д.)"""
    user = update.effective_user
    message = update.message
    
    logger.info(f"📄 Документ от {user.id}: {message.document.file_name}")
    
    try:
        # Подтверждение пользователю
        await message.reply_text(
            "✅ Документ получен! Администратор проверит его в течение 15 минут."
        )
        
        # Пересылаем документ администратору
        await message.forward(chat_id=ADMIN_ID)
        
        # Уведомление администратора
        admin_notification = f"""
📄 **ПОЛУЧЕН ДОКУМЕНТ**

👤 **От пользователя:**
Имя: {user.first_name} {user.last_name or ''}
ID: `{user.id}`
Username: @{user.username or 'нет'}

📋 **Файл:** {message.document.file_name}
📏 **Размер:** {message.document.file_size} байт

🕒 Время: {datetime.now().strftime('%H:%M %d.%m.%Y')}

💬 **Для ответа:**
`/reply {user.id} ваш текст`
        """
        
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_notification
        )
        
        logger.info(f"✅ Документ переслан администратору")
        
    except Exception as e:
        logger.error(f"❌ Ошибка пересылки документа: {e}")

# ================== ИНФОРМАЦИОННЫЕ КНОПКИ ==================
async def handle_payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация об оплате"""
    query = update.callback_query
    await query.answer()
    
    payment_text = """
💳 **Информация об оплате:**

💰 **Реквизиты:**
USDT (TRC20): `TF33keB2N3P226zxFfESVCvXCFQMjnMXQh`

💎 **Стоимость подписки:**
1 месяц - 9 USDT

📋 **Процесс оплаты:**
1. Отправьте 9 USDT на указанный адрес
2. Сохраните скриншот/чек транзакции
3. Отправьте его мне с указанием вашего ID
4. Ожидайте активации (до 15 минут)

❓ **Отправьте скриншот чека для активации подписки**
    """
    
    await query.message.reply_text(payment_text)

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
    
    await query.message.reply_text(faq_text)

async def handle_tech_issues(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Технические проблемы"""
    query = update.callback_query
    await query.answer()
    
    tech_text = """
🔧 **Технические проблемы:**

🤖 **Бот не работает:**
1. Перезапустите бота командой /start
2. Очистите кэш приложения Telegram
3. Обновите Telegram до последней версии

📱 **Не приходят уведомления:**
• Проверьте настройки уведомлений в Telegram
• Убедитесь что бот не заблокирован

💾 **Ошибка базы данных:**
• Сообщите администратору ваш ID
• Скриншот ошибки поможет быстрее решить проблему

📨 **Пишите подробное описание проблемы для быстрого решения.**
    """
    
    await query.message.reply_text(tech_text)

async def handle_active_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация о текущих подписках"""
    query = update.callback_query
    await query.answer()
    
    subs_text = """
💎 **Информация о подписках:**

⏳ **Срок подписки:** 30 дней
🔄 **Автопродление:** Нет (только ручное)
📊 **Доступ после оплаты:** До конца оплаченного периода

🔔 **Уведомления:**
• За 3 дня до окончания подписки
• После окончания подписки

💰 **Стоимость всегда:** 9 USDT (скидок нет)
🎁 **Бонусы:** При оплате 3 месяцев - 1 неделя в подарок

📞 **По всем вопросам:** Пишите в этом чате
    """
    
    await query.message.reply_text(subs_text)

# ================== СЛУЖЕБНЫЕ КОМАНДЫ ==================
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статистика поддержки (только для админа)"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Доступ запрещен")
        return
    
    try:
        # Пытаемся прочитать лог файл
        try:
            with open("support_log.txt", "r", encoding="utf-8") as f:
                lines = f.readlines()
                total_messages = len(lines)
                today_messages = len([l for l in lines if datetime.now().strftime('%Y-%m-%d') in l])
        except:
            total_messages = 0
            today_messages = 0
        
        stats_text = f"""
📊 **СТАТИСТИКА ПОДДЕРЖКИ**

📅 **Сегодня:**
• Сообщений: {today_messages}

📈 **Всего:**
• Сообщений в логе: {total_messages}

👨‍💻 **Админ ID:** {ADMIN_ID}
🤖 **Статус:** ✅ Активен

💡 **Команды:**
• `/reply <id> <текст>` - ответить пользователю
• `/broadcast <текст>` - рассылка (в разработке)
• `/help` - помощь по командам
        """
        
        await update.message.reply_text(stats_text)
        
    except Exception as e:
        logger.error(f"Ошибка stats: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Помощь по командам"""
    user_id = update.effective_user.id
    
    if user_id == ADMIN_ID:
        text = """
🆘 **ПОМОЩЬ ДЛЯ АДМИНИСТРАТОРА:**

👑 **Админ команды:**
• `/reply <user_id> <текст>` - ответить пользователю
• `/stats` - статистика поддержки
• `/help` - эта справка

📋 **Обычные команды:**
• `/start` - начать диалог
• Любой текст - пересылается админу
• Фото/документы - пересылаются админу

💡 **Советы:**
• Все сообщения пользователей пересылаются вам
• Используйте /reply для ответов
• Сохраняйте скриншоты оплаты
        """
    else:
        text = """
🆘 **ПОМОЩЬ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ:**

💬 **Как получить помощь:**
1. Напишите ваш вопрос в чат
2. Приложите скриншот если нужно
3. Укажите ваш ID если спрашиваете о подписке

📞 **Что мы решаем:**
• Проблемы с ботом Crypto Signals
• Вопросы по оплате подписки
• Активацию премиум доступа
• Технические неполадки

⏰ **Время ответа:** до 15 минут
        """
    
    await update.message.reply_text(text)

# ================== ОСНОВНОЙ ОБРАБОТЧИК ==================
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    if update.message.text and not update.message.text.startswith('/'):
        await forward_to_admin(update, context)

# ================== ЗАПУСК ==================
def main():
    """Запуск бота поддержки"""
    print("🚀 Бот поддержки запускается...")
    
    if not SUPPORT_BOT_TOKEN:
        logger.error("❌ SUPPORT_BOT_TOKEN не найден!")
        print("⚠️ Добавьте SUPPORT_BOT_TOKEN в переменные окружения Render")
        return
    
    try:
        # Создаем приложение
        application = Application.builder().token(SUPPORT_BOT_TOKEN).build()
        
        # Команды
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("reply", admin_reply_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CommandHandler("help", help_command))
        
        # Callback кнопки
        application.add_handler(CallbackQueryHandler(handle_payment_info, pattern="payment_info"))
        application.add_handler(CallbackQueryHandler(handle_faq, pattern="faq"))
        application.add_handler(CallbackQueryHandler(handle_tech_issues, pattern="tech_issues"))
        application.add_handler(CallbackQueryHandler(handle_active_subscriptions, pattern="subscriptions"))
        
        # Сообщения
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
        
        print("✅ Бот поддержки готов к работе!")
        print(f"🤖 Бот: @CryptoSignalsSupportBot")
        print(f"👨‍💻 Админ ID: {ADMIN_ID}")
        print(f"💬 Для ответа: /reply <user_id> <сообщение>")
        print("=" * 60)
        
        # Запускаем polling
        application.run_polling(
            poll_interval=3.0,
            timeout=30,
            drop_pending_updates=True
        )
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        print(f"🔧 Проверьте токен бота и настройки")

if __name__ == "__main__":
    main()
