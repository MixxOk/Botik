import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from constants import SUBJECTS
from data import user_names, queues, is_user_banned
from rating import get_cached_rating  # Импортируем функцию для получения кеша

logger = logging.getLogger(__name__)

def get_user_queue_keyboard(subject, is_in_queue):
    """Создает клавиатуру для меню очереди в зависимости от того, находится ли пользователь в очереди."""
    if is_in_queue:
        keyboard = [
            [InlineKeyboardButton("Сдал", callback_data=f'passed_{subject}'),
             InlineKeyboardButton("← Назад", callback_data='back_to_menu')]
        ]
        logger.debug(f"Создана клавиатура для пользователя В очереди по '{subject}'.")
    else:
        keyboard = [
            [InlineKeyboardButton("Записаться", callback_data=f'join_{subject}'),
             InlineKeyboardButton("← Назад", callback_data='back_to_menu')]
        ]
        logger.debug(f"Создана клавиатура для пользователя НЕ в очереди по '{subject}'.")
    return keyboard

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    
    # Проверка бана ПЕРВЫМ ДЕЛОМ
    if is_user_banned(user_id):
        await update.message.reply_text("❌ Вы забанены и не можете использовать бот.")
        logger.warning(f"Забаненный пользователь {user_id} попытался использовать /start")
        return
    
    user_data = user_names.get(user_id)
    user_name = user_data["name"] if user_data else "Неизвестный пользователь"
    logger.info(f"Пользователь {user_id} ({user_name}) вызвал команду /start.")
    
    if user_id not in user_names:
        await update.message.reply_text("Как тебя зовут?")
        logger.info(f"Запрошено имя у пользователя {user_id}.")
    else:
        await show_subjects(update)
        logger.info(f"Пользователю {user_id} ({user_name}) показано меню выбора предметов.")

async def show_subjects(update: Update) -> None:
    user_id = update.effective_user.id
    user_data = user_names.get(user_id)
    user_name = user_data["name"] if user_data else "Miha"
    
    logger.info(f"Формирование меню выбора предметов для пользователя {user_id} ({user_name}).")
    keyboard = [
        [InlineKeyboardButton(subject, callback_data=f'show_queue_{subject}')] for subject in SUBJECTS
    ]
    # Добавляем кнопку "Рейтинг"
    keyboard.append([InlineKeyboardButton("📊 Рейтинг", callback_data='show_rating')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text("Выбери предмет:", reply_markup=reply_markup)
        logger.info(f"Меню выбора предметов отправлено пользователю {user_id} ({user_name}) через callback_query.")
    else:
        await update.message.reply_text("Выбери предмет:", reply_markup=reply_markup)
        logger.info(f"Меню выбора предметов отправлено пользователю {user_id} ({user_name}) через обычное сообщение.")

async def show_queue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Проверка бана
    if is_user_banned(user_id):
        await query.edit_message_text("❌ Вы забанены и не можете использовать бот.")
        logger.warning(f"Забаненный пользователь {user_id} попытался нажать show_queue")
        return
    
    if not query.data.startswith('show_queue_'):
        logger.warning(f"Получен неожиданный callback_ '{query.data}' от пользователя {query.from_user.id}.")
        return
    
    user_data = user_names.get(user_id)
    user_name = user_data["name"] if user_data else "Неизвестный пользователь"
    subject = query.data.split('show_queue_')[1]
    logger.info(f"Пользователь {user_id} ({user_name}) запросил очередь по предмету '{subject}'.")

    queue_list = "\n".join([f"{i+1}. {name}" for i, name in enumerate(queues[subject])])
    if not queue_list:
        queue_list = "Очередь пуста"
    is_in_queue = user_name and user_name in queues[subject]

    if is_in_queue:
        logger.info(f"Пользователь {user_id} ({user_name}) находится в очереди по '{subject}'. Предложено действие 'Сдал'.")
    else:
        logger.info(f"Пользователь {user_id} ({user_name}) НЕ находится в очереди по '{subject}'. Предложено действие 'Записаться'.")

    keyboard = get_user_queue_keyboard(subject, is_in_queue)
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=f"Очередь по '{subject}':\n{queue_list}",
        reply_markup=reply_markup
    )
    logger.info(f"Отправлена очередь по '{subject}' пользователю {user_id} ({user_name}).")

async def join_queue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Проверка бана
    if is_user_banned(user_id):
        await query.edit_message_text("❌ Вы забанены и не можете использовать бот.")
        logger.warning(f"Забаненный пользователь {user_id} попытался нажать join_queue")
        return
    
    user_data = user_names.get(user_id)
    user_name = user_data["name"] if user_data else "Неизвестный пользователь"
    subject = query.data.split('join_')[1]
    logger.info(f"Пользователь {user_id} ({user_name}) нажал 'Записаться' в очередь '{subject}'.")

    if not user_name:
        logger.error(f"Пользователь {user_id} не найден в user_names при попытке записи в очередь '{subject}'.")
        await query.edit_message_text(text="Произошла ошибка. Пожалуйста, начните с /start.")
        return

    if user_name in queues[subject]:
        logger.info(f"Пользователь {user_id} ({user_name}) уже находится в очереди '{subject}'. Показана обновлённая очередь.")
        await show_queue_direct(update, context, subject)
        return

    queues[subject].append(user_name)
    from data import save_data_to_file
    save_data_to_file()
    logger.info(f"Пользователь {user_id} ({user_name}) добавлен в очередь '{subject}'. Данные сохранены.")
    await show_queue_direct(update, context, subject)

async def show_queue_direct(update: Update, context: ContextTypes.DEFAULT_TYPE, subject: str) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    
    # Проверка бана
    if is_user_banned(user_id):
        await query.edit_message_text("❌ Вы забанены и не можете использовать бот.")
        logger.warning(f"Забаненный пользователь {user_id} попытался нажать show_queue_direct")
        return
    
    user_data = user_names.get(user_id)
    user_name = user_data["name"] if user_data else "Неизвестный пользователь"
    logger.info(f"Повторный показ очереди '{subject}' пользователю {user_id} ({user_name}).")

    queue_list = "\n".join([f"{i+1}. {name}" for i, name in enumerate(queues[subject])])
    if not queue_list:
        queue_list = "Очередь пуста"

    is_in_queue = user_name and user_name in queues[subject]
    if is_in_queue:
        logger.info(f"Пользователь {user_id} ({user_name}) в очереди '{subject}'. Предложено действие 'Сдал'.")
    else:
        logger.info(f"Пользователь {user_id} ({user_name}) не в очереди '{subject}'. Предложено действие 'Записаться'.")

    keyboard = get_user_queue_keyboard(subject, is_in_queue)
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=f"Очередь по '{subject}':\n{queue_list}",
        reply_markup=reply_markup
    )
    logger.info(f"Отправлена обновлённая очередь по '{subject}' пользователю {user_id} ({user_name}).")

async def handle_passed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Проверка бана
    if is_user_banned(user_id):
        await query.edit_message_text("❌ Вы забанены и не можете использовать бот.")
        logger.warning(f"Забаненный пользователь {user_id} попытался нажать handle_passed")
        return
    
    user_data = user_names.get(user_id)
    user_name = user_data["name"] if user_data else "Неизвестный пользователь"
    subject = query.data.split('passed_')[1]
    logger.info(f"Пользователь {user_id} ({user_name}) нажал 'Сдал' по предмету '{subject}'.")

    if user_name and user_name in queues[subject]:
        queues[subject].remove(user_name)
        from data import save_data_to_file
        save_data_to_file()
        logger.info(f"Пользователь {user_id} ({user_name}) удален из очереди '{subject}' после сдачи. Данные сохранены.")
    else:
        logger.info(f"Пользователь {user_id} ({user_name}) не найден в очереди '{subject}' при попытке сдать.")

    await show_subjects(update)
    logger.info(f"Пользователю {user_id} ({user_name}) показано главное меню после сдачи.")

async def go_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Проверка бана
    if is_user_banned(user_id):
        await query.edit_message_text("❌ Вы забанены и не можете использовать бот.")
        logger.warning(f"Забаненный пользователь {user_id} попытался нажать go_back")
        return
    
    user_data = user_names.get(user_id)
    user_name = user_data["name"] if user_data else "Неизвестный пользователь"
    logger.info(f"Пользователь {user_id} ({user_name}) нажал '← Назад'.")
    await show_subjects(update)
    logger.info(f"Пользователю {user_id} ({user_name}) показано главное меню после нажатия 'Назад'.")

async def show_rating(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает текущий рейтинг."""
    query = update.callback_query
    if query:
        await query.answer()
        user_id = query.from_user.id
        message = query.message
    else:
        user_id = update.effective_user.id
        message = update.message
    
    user_data = user_names.get(user_id)
    user_name = user_data["name"] if user_data else "Miha"
    logger.info(f"Пользователь {user_id} ({user_name}) запрашивает рейтинг")
    
    # Получаем текущий рейтинг из кеша
    rating_data = get_cached_rating('ЯП')
    if not rating_data:
        text = "📊 Рейтинг не загружен"
        keyboard = [[InlineKeyboardButton("← Назад", callback_data='back_to_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if query:
            await query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await message.reply_text(text, reply_markup=reply_markup)
        return
    
    # Извлекаем фамилии и сортируем
    surname_scores = {}
    for full_name, score in rating_data.items():
        surname = full_name.split()[0]
        surname_scores[surname] = score
    
    sorted_data = sorted(surname_scores.items(), key=lambda x: x[1], reverse=True)
    
    # Формируем сообщение 
    text = f"📊 <b>Рейтинг по ЯП:</b>\n\n"
    for rank, (surname, score) in enumerate(sorted_data, start=1):
        medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}."
        text += f"{medal} <b>{surname}</b> — {score:.2f} лаб\n"
    
    keyboard = [[InlineKeyboardButton("← Назад", callback_data='back_to_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
    else:
        await message.reply_text(text, parse_mode='HTML', reply_markup=reply_markup)