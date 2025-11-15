import logging
import httpx
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from constants import BOT_TOKEN
import user_handlers
import dev_handlers
from data import user_names

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logging.getLogger("httpx").setLevel(logging.WARNING)

async def combined_message_handler(update, context):
    """Комбинированный обработчик текстовых сообщений."""
    user_id = update.effective_user.id
    text = update.message.text
    current_user_name = user_names.get(user_id, "Неизвестный пользователь")
    user_handlers.logger.info(f"combined_message_handler: Получено сообщение от пользователя {user_id} ({current_user_name}): '{text}'")

    if user_id not in user_names:
        user_handlers.logger.info(f"Сохраняю имя '{text}' для нового пользователя {user_id}.")
        user_names[user_id] = text
        from data import save_data_to_file
        save_data_to_file()
        await update.message.reply_text(f"Привет, {text}!")
        await user_handlers.show_subjects(update)
        user_handlers.logger.info(f"Имя '{text}' успешно сохранено для пользователя {user_id}.")
        return
    else:
        if user_id not in dev_handlers.dev_mode_users:
            if await dev_handlers.enter_dev_code(update, context):
                user_handlers.logger.info(f"Пользователь {user_id} успешно вошёл в dev-режим через код.")
                return
            user_handlers.logger.info(f"Пользователь {user_id} не в dev-режиме и код не подошёл. Игнорируем.")
            return
        user_handlers.logger.info(f"Пользователь {user_id} в dev-режиме, ввёл: '{text}'. Возвращаем в меню.")
        await dev_handlers.show_dev_menu(update, context)
        return

    user_handlers.logger.info(f"Нераспознанное сообщение от пользователя {user_id} ({current_user_name}): '{text}'. Игнорируется.")
    pass

application = Application.builder().token(BOT_TOKEN).build()

application.add_handler(CommandHandler("start", user_handlers.start))
application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, combined_message_handler))
application.add_handler(CallbackQueryHandler(user_handlers.go_back, pattern='^back_to_menu$'))
application.add_handler(CallbackQueryHandler(user_handlers.show_queue, pattern='^show_queue_'))
application.add_handler(CallbackQueryHandler(user_handlers.join_queue, pattern='^join_'))
application.add_handler(CallbackQueryHandler(user_handlers.handle_passed, pattern='^passed_'))
application.add_handler(CallbackQueryHandler(dev_handlers.handle_dev_callback, pattern='^(dev_|back_to_menu)'))

if __name__ == '__main__':
    application.run_polling()