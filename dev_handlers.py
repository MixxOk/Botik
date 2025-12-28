# dev_handlers.py

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from constants import SUBJECTS
from data import user_names, queues, remove_user_from_queue, is_user_banned, ban_user, unban_user, get_all_banned_users
from rating import update_rating, format_rating_message

logger = logging.getLogger(__name__)

dev_mode_users = set()
awaiting_subject_selection = set()
awaiting_user_selection = set()
selected_subject_for_removal = {}
awaiting_user_forget_selection = set()
# --- Новые переменные для добавления в очередь ---
awaiting_subject_selection_add = set()
awaiting_user_selection_add = set()
awaiting_position_selection_add = set()
selected_subject_for_add = {}
selected_user_for_add = {}
# --- Переменные для бана ---
awaiting_ban_user_selection = set()
awaiting_unban_user_selection = set()

DEV_CODE = '2411'

async def enter_dev_code(update, context):
    """Функция для обработки ввода кода разработчика."""
    user_id = update.effective_user.id
    text = update.message.text
    logger.info(f"[DEV_CODE] Пользователь {user_id} ввел текст: '{text}'")

    if text == DEV_CODE:
        logger.info(f"[DEV_CODE] Код верен для пользователя {user_id}. Вход в dev-режим.")
        dev_mode_users.add(user_id)
        await show_dev_menu(update, context)
        return True
    else:
        logger.info(f"[DEV_CODE] Неверный код '{text}' от пользователя {user_id}. Ожидаемый код: '{DEV_CODE}'")
    return False

async def show_dev_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает главное меню для разработчика."""
    user_id = update.effective_user.id
    logger.info(f"[DEV_MENU] Показываем меню разработчика пользователю {user_id}")
    keyboard = [
        [InlineKeyboardButton("База данных", callback_data='dev_show_db')],
        [InlineKeyboardButton("📊 Обновить рейтинг", callback_data='dev_update_rating')],
        [InlineKeyboardButton("Убрать из очереди", callback_data='dev_remove_user_start')],
        [InlineKeyboardButton("Забыть пользователя", callback_data='dev_forget_user_start')],
        [InlineKeyboardButton("Добавить в очередь", callback_data='dev_add_user_start')],
        [InlineKeyboardButton("Очистить очереди от неизвестных", callback_data='dev_clean_unknown')],
        [InlineKeyboardButton("🚫 Забанить", callback_data='dev_ban_user_start')],
        [InlineKeyboardButton("✅ Разбанить", callback_data='dev_unban_user_start')],
        [InlineKeyboardButton("Банлист", callback_data='dev_show_ban_list')],
        [InlineKeyboardButton("← Назад", callback_data='dev_back_to_user_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if hasattr(update, 'callback_query') and update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("Меню разработчика:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Меню разработчика:", reply_markup=reply_markup)

async def show_database_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет содержимое базы данных (user_names и queues)."""
    user_id = update.effective_user.id
    logger.info(f"[DEV_SHOW_DB] Пользователь {user_id} запросил содержимое базы данных через кнопку.")

    message = "Содержимое базы данных:\n\n"
    message += "<b>Пользователи:</b>\n"
    if user_names:
        for uid, data in user_names.items():
            ban_status = "🚫 ЗАБАНЕН" if data.get("banned", False) else "✅"
            message += f"  {ban_status} ID: {uid}, Имя: {data['name']}\n"
    else:
        message += "  Нет зарегистрированных пользователей.\n"

    message += "\n<b>Очереди:</b>\n"
    for subject, queue_list in queues.items():
        message += f"  <u>{subject}</u>:\n"
        if queue_list:
            for i, name in enumerate(queue_list):
                message += f"    {i+1}. {name}\n"
        else:
            message += "    Очередь пуста\n"
        message += "\n"

    keyboard = [
        [InlineKeyboardButton("← Назад", callback_data='dev_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await update.callback_query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
        logger.info(f"[DEV_SHOW_DB] Содержимое базы данных отправлено пользователю {user_id} через callback_query с кнопкой назад.")
    except Exception as e:
        logger.error(f"[DEV_SHOW_DB] Ошибка при отправке содержимого базы данных пользователю {user_id}: {e}")
        await update.callback_query.edit_message_text("Произошла ошибка при отправке содержимого базы данных.")
        await show_dev_menu(update, context)

async def start_remove_user_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс удаления пользователя: запрашивает выбор предмета."""
    user_id = update.effective_user.id
    logger.info(f"[DEV_REMOVE_START] Пользователь {user_id} начал процесс удаления пользователя из очереди.")
    query = update.callback_query
    await query.answer()

    awaiting_subject_selection.discard(user_id)
    awaiting_user_selection.discard(user_id)
    selected_subject_for_removal.pop(user_id, None)
    awaiting_user_forget_selection.discard(user_id)
    awaiting_subject_selection_add.discard(user_id)
    awaiting_user_selection_add.discard(user_id)
    selected_subject_for_add.pop(user_id, None)
    selected_user_for_add.pop(user_id, None)
    awaiting_position_selection_add.discard(user_id)
    awaiting_subject_selection.add(user_id)

    keyboard = [
        [InlineKeyboardButton(subject, callback_data=f'dev_select_subject_{subject}')] for subject in SUBJECTS
    ]
    keyboard.append([InlineKeyboardButton("← Назад", callback_data='dev_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text("Выберите предмет, из очереди которого нужно удалить пользователя:", reply_markup=reply_markup)

async def select_subject_for_removal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор предмета и запрашивает выбор пользователя."""
    user_id = update.effective_user.id
    logger.info(f"[DEV_SELECT_SUBJECT_REMOVE] Пользователь {user_id} выбрал предмет для удаления.")
    query = update.callback_query
    await query.answer()

    if user_id not in awaiting_subject_selection:
        logger.warning(f"[DEV_SELECT_SUBJECT_REMOVE] Пользователь {user_id} не в состоянии ожидания выбора предмета.")
        await query.edit_message_text("Ошибка состояния. Пожалуйста, начните снова.")
        await show_dev_menu(update, context)
        return

    subject = query.data.split('dev_select_subject_')[1]
    selected_subject_for_removal[user_id] = subject
    awaiting_subject_selection.discard(user_id)
    awaiting_user_selection.add(user_id)

    queue_users = queues[subject]
    if not queue_users:
        await query.edit_message_text(f"Очередь по '{subject}' пуста.")
        await start_remove_user_process(update, context)
        return

    keyboard = []
    for name in queue_users:
        # Найдем ID пользователя по имени
        user_id_to_remove = None
        for id, data in user_names.items():
            if data["name"] == name:
                user_id_to_remove = id
                break
        # Используем ID в callback_data
        if user_id_to_remove is not None:
            keyboard.append([InlineKeyboardButton(name, callback_data=f'dev_confirm_remove_user_{user_id_to_remove}')])
        else:
            logger.warning(f"[DEV_SELECT_SUBJECT_REMOVE] Имя '{name}' из очереди '{subject}' не найдено в user_names.")
            continue

    keyboard.append([InlineKeyboardButton("← Назад", callback_data='dev_remove_user_start')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"Выберите пользователя для удаления из очереди '{subject}':", reply_markup=reply_markup)

async def confirm_remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждает удаление выбранного пользователя из очереди по выбранному предмету."""
    user_id = update.effective_user.id
    logger.info(f"[DEV_CONFIRM_REMOVE] Пользователь {user_id} подтверждает удаление пользователя.")
    query = update.callback_query
    await query.answer()

    if user_id not in awaiting_user_selection:
        logger.warning(f"[DEV_CONFIRM_REMOVE] Пользователь {user_id} не в состоянии ожидания выбора пользователя для удаления.")
        await query.edit_message_text("Ошибка состояния. Пожалуйста, начните снова.")
        await show_dev_menu(update, context)
        return

    selected_user_id_str = query.data.split('dev_confirm_remove_user_')[1]
    try:
        selected_user_id = int(selected_user_id_str)
    except ValueError:
        logger.error(f"[DEV_CONFIRM_REMOVE] Неверный формат ID пользователя '{selected_user_id_str}' от {user_id}.")
        await query.edit_message_text("Ошибка: некорректный ID пользователя.")
        await show_dev_menu(update, context)
        return

    subject = selected_subject_for_removal.get(user_id)

    if not subject:
        logger.error(f"[DEV_CONFIRM_REMOVE] Не найден выбранный предмет для пользователя {user_id}.")
        await query.edit_message_text("Ошибка: предмет не выбран. Пожалуйста, начните снова.")
        await show_dev_menu(update, context)
        return

    # Проверим, существует ли пользователь
    if selected_user_id not in user_names:
        logger.warning(f"[DEV_CONFIRM_REMOVE] Пользователь с ID {selected_user_id} не найден в user_names при попытке удалить из очереди '{subject}' от {user_id}.")
        await query.edit_message_text(f"Пользователь с ID {selected_user_id} не найден в базе данных.")
        await start_remove_user_process(update, context)
        return

    selected_user_name = user_names[selected_user_id]["name"]

    success = remove_user_from_queue(selected_user_id, subject)
    if success:
        await query.edit_message_text(f"Пользователь '{selected_user_name}' успешно удален из очереди '{subject}'.")
        logger.info(f"[DEV_CONFIRM_REMOVE] Пользователь {user_id} удалил '{selected_user_name}' (ID {selected_user_id}) из очереди '{subject}'.")
    else:
        await query.edit_message_text(f"Не удалось удалить '{selected_user_name}' из очереди '{subject}'. Возможно, пользователь уже был удален.")
        logger.warning(f"[DEV_CONFIRM_REMOVE] Функция remove_user_from_queue вернула False при удалении '{selected_user_name}' (ID {selected_user_id}) из очереди '{subject}' пользователем {user_id}.")

    awaiting_user_selection.discard(user_id)
    selected_subject_for_removal.pop(user_id, None)
    await show_dev_menu(update, context)

async def start_forget_user_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс "забывания" пользователя: запрашивает выбор пользователя."""
    user_id = update.effective_user.id
    logger.info(f"[DEV_FORGET_START] Пользователь {user_id} начал процесс 'забывания' пользователя.")
    query = update.callback_query
    await query.answer()

    awaiting_subject_selection.discard(user_id)
    awaiting_user_selection.discard(user_id)
    selected_subject_for_removal.pop(user_id, None)
    awaiting_user_forget_selection.discard(user_id)
    awaiting_subject_selection_add.discard(user_id)
    awaiting_user_selection_add.discard(user_id)
    selected_subject_for_add.pop(user_id, None)
    selected_user_for_add.pop(user_id, None)
    awaiting_position_selection_add.discard(user_id)
    awaiting_user_forget_selection.add(user_id)

    if not user_names:
        await query.edit_message_text("Нет зарегистрированных пользователей для удаления.")
        await show_dev_menu(update, context)
        return

    keyboard = []
    for uid, data in user_names.items():
        keyboard.append([InlineKeyboardButton(f"{data['name']} (ID: {uid})", callback_data=f'dev_confirm_forget_user_{uid}')])

    keyboard.append([InlineKeyboardButton("← Назад", callback_data='dev_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text("Выберите пользователя, которого нужно 'забыть' (удалить из базы данных):", reply_markup=reply_markup)

async def confirm_forget_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждает "забывание" выбранного пользователя."""
    user_id = update.effective_user.id
    logger.info(f"[DEV_CONFIRM_FORGET] Пользователь {user_id} подтверждает 'забывание' пользователя.")
    query = update.callback_query
    await query.answer()

    if user_id not in awaiting_user_forget_selection:
        logger.warning(f"[DEV_CONFIRM_FORGET] Пользователь {user_id} не в состоянии ожидания выбора пользователя для 'забывания'.")
        await query.edit_message_text("Ошибка состояния. Пожалуйста, начните снова.")
        await show_dev_menu(update, context)
        return

    selected_user_id_str = query.data.split('dev_confirm_forget_user_')[1]
    try:
        selected_user_id = int(selected_user_id_str)
    except ValueError:
        logger.error(f"[DEV_CONFIRM_FORGET] Неверный формат ID пользователя '{selected_user_id_str}' от {user_id}.")
        await query.edit_message_text("Ошибка: некорректный ID пользователя.")
        await show_dev_menu(update, context)
        return

    if selected_user_id not in user_names:
        logger.warning(f"[DEV_CONFIRM_FORGET] Пользователь с ID {selected_user_id} не найден в user_names при попытке 'забыть' от {user_id}.")
        await query.edit_message_text(f"Пользователь с ID {selected_user_id} не найден в базе данных.")
        await start_forget_user_process(update, context)
        return

    selected_user_name = user_names[selected_user_id]["name"]

    del user_names[selected_user_id]
    logger.info(f"[DEV_CONFIRM_FORGET] Пользователь '{selected_user_name}' (ID {selected_user_id}) удалён из user_names пользователем {user_id}.")

    queues_changed = False
    for subject in queues:
        if selected_user_name in queues[subject]:
            queues[subject].remove(selected_user_name)
            queues_changed = True
            logger.info(f"[DEV_CONFIRM_FORGET] Пользователь '{selected_user_name}' (ID {selected_user_id}) удалён из очереди '{subject}'.")

    from data import save_data_to_file
    save_data_to_file()
    logger.info(f"[DEV_CONFIRM_FORGET] Данные сохранены после 'забывания' пользователя {selected_user_id} ({selected_user_name}) пользователем {user_id}.")

    await query.edit_message_text(f"Пользователь '{selected_user_name}' (ID {selected_user_id}) успешно 'забыт' (удалён из базы данных).")
    await show_dev_menu(update, context)

# --- Новые функции для добавления в очередь ---

async def start_add_user_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс добавления пользователя: запрашивает выбор предмета."""
    user_id = update.effective_user.id
    logger.info(f"[DEV_ADD_START] Пользователь {user_id} начал процесс добавления пользователя в очередь.")
    query = update.callback_query
    await query.answer()

    # Очищаем предыдущие состояния для этого пользователя
    awaiting_subject_selection.discard(user_id)
    awaiting_user_selection.discard(user_id)
    selected_subject_for_removal.pop(user_id, None)
    awaiting_user_forget_selection.discard(user_id)
    awaiting_subject_selection_add.discard(user_id)
    awaiting_user_selection_add.discard(user_id)
    selected_subject_for_add.pop(user_id, None)
    selected_user_for_add.pop(user_id, None)
    awaiting_position_selection_add.discard(user_id)
    # Устанавливаем состояние ожидания выбора предмета
    awaiting_subject_selection_add.add(user_id)

    keyboard = [
        [InlineKeyboardButton(subject, callback_data=f'dev_select_subject_add_{subject}')] for subject in SUBJECTS
    ]
    keyboard.append([InlineKeyboardButton("← Назад", callback_data='dev_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text("Выберите предмет, в очередь которого нужно добавить пользователя:", reply_markup=reply_markup)

async def select_subject_for_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор предмета и запрашивает выбор пользователя."""
    user_id = update.effective_user.id
    logger.info(f"[DEV_SELECT_SUBJECT_ADD] Пользователь {user_id} выбрал предмет для добавления.")
    query = update.callback_query
    await query.answer()

    if user_id not in awaiting_subject_selection_add:
        logger.warning(f"[DEV_SELECT_SUBJECT_ADD] Пользователь {user_id} не в состоянии ожидания выбора предмета для добавления.")
        await query.edit_message_text("Ошибка состояния. Пожалуйста, начните снова.")
        await show_dev_menu(update, context)
        return

    subject = query.data.split('dev_select_subject_add_')[1]
    # Сохраняем выбранный предмет
    selected_subject_for_add[user_id] = subject
    # Меняем состояние: теперь ожидаем выбора пользователя
    awaiting_subject_selection_add.discard(user_id)
    awaiting_user_selection_add.add(user_id)

    if not user_names:
        await query.edit_message_text("Нет зарегистрированных пользователей для добавления.")
        # Возвращаем в меню выбора предмета
        await start_add_user_process(update, context)
        return

    keyboard = []
    for uid, data in user_names.items():
        keyboard.append([InlineKeyboardButton(f"{data['name']} (ID: {uid})", callback_data=f'dev_select_user_add_{uid}')])

    keyboard.append([InlineKeyboardButton("← Назад", callback_data='dev_add_user_start')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"Выберите пользователя для добавления в очередь '{subject}':", reply_markup=reply_markup)

async def select_user_for_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор пользователя и запрашивает выбор позиции."""
    user_id = update.effective_user.id
    logger.info(f"[DEV_SELECT_USER_ADD] Пользователь {user_id} выбрал пользователя для добавления.")
    query = update.callback_query
    await query.answer()

    if user_id not in awaiting_user_selection_add:
        logger.warning(f"[DEV_SELECT_USER_ADD] Пользователь {user_id} не в состоянии ожидания выбора пользователя для добавления.")
        await query.edit_message_text("Ошибка состояния. Пожалуйста, начните снова.")
        await show_dev_menu(update, context)
        return

    selected_user_id_str = query.data.split('dev_select_user_add_')[1]
    try:
        selected_user_id = int(selected_user_id_str)
    except ValueError:
        logger.error(f"[DEV_SELECT_USER_ADD] Неверный формат ID пользователя '{selected_user_id_str}' от {user_id}.")
        await query.edit_message_text("Ошибка: некорректный ID пользователя.")
        await show_dev_menu(update, context)
        return

    # Проверим, существует ли пользователь
    if selected_user_id not in user_names:
        logger.warning(f"[DEV_SELECT_USER_ADD] Пользователь с ID {selected_user_id} не найден в user_names при попытке добавить от {user_id}.")
        await query.edit_message_text(f"Пользователь с ID {selected_user_id} не найден в базе данных.")
        # Возвращаем в меню выбора пользователя
        await select_subject_for_add(update, context)
        return

    subject = selected_subject_for_add.get(user_id)
    if not subject:
        logger.error(f"[DEV_SELECT_USER_ADD] Не найден выбранный предмет для пользователя {user_id} при выборе пользователя.")
        await query.edit_message_text("Ошибка: предмет не выбран. Пожалуйста, начните снова.")
        await show_dev_menu(update, context)
        return

    selected_user_name = user_names[selected_user_id]["name"]
    # Сохраняем выбранного пользователя
    selected_user_for_add[user_id] = selected_user_id
    # Меняем состояние: теперь ожидаем выбора позиции
    awaiting_user_selection_add.discard(user_id)
    awaiting_position_selection_add.add(user_id)

    queue_length = len(queues[subject])
    keyboard = []
    # Позиции от 1 до длины очереди (вставка в середину/начало) и +1 (вставка в конец)
    for pos in range(1, queue_length + 2):
        keyboard.append([InlineKeyboardButton(f"Позиция {pos}", callback_data=f'dev_select_position_add_{pos}')])

    keyboard.append([InlineKeyboardButton("← Назад", callback_data=f'dev_select_subject_add_{subject}')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"Выбран пользователь '{selected_user_name}' для добавления в очередь '{subject}'.\nТекущая длина очереди: {queue_length}.\nВыберите позицию (1 - в начало, {queue_length + 1} - в конец):", reply_markup=reply_markup)

async def select_position_for_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор позиции и добавляет пользователя."""
    user_id = update.effective_user.id
    logger.info(f"[DEV_SELECT_POSITION_ADD] Пользователь {user_id} выбрал позицию для добавления.")
    query = update.callback_query
    await query.answer()

    if user_id not in awaiting_position_selection_add:
        logger.warning(f"[DEV_SELECT_POSITION_ADD] Пользователь {user_id} не в состоянии ожидания выбора позиции для добавления.")
        await query.edit_message_text("Ошибка состояния. Пожалуйста, начните снова.")
        await show_dev_menu(update, context)
        return

    selected_position_str = query.data.split('dev_select_position_add_')[1]
    try:
        selected_position = int(selected_position_str)
    except ValueError:
        logger.error(f"[DEV_SELECT_POSITION_ADD] Неверный формат позиции '{selected_position_str}' от {user_id}.")
        await query.edit_message_text("Ошибка: некорректная позиция.")
        await show_dev_menu(update, context)
        return

    subject = selected_subject_for_add.get(user_id)
    selected_user_id = selected_user_for_add.get(user_id)

    if not subject or selected_user_id is None:
        logger.error(f"[DEV_SELECT_POSITION_ADD] Не найдены предмет или пользователь для {user_id} при выборе позиции.")
        await query.edit_message_text("Ошибка: данные пользователя или предмета не найдены. Пожалуйста, начните снова.")
        await show_dev_menu(update, context)
        return

    selected_user_name = user_names[selected_user_id]["name"]

    # Проверим, что позиция в допустимом диапазоне (1 до len+1)
    queue_length = len(queues[subject])
    if selected_position < 1 or selected_position > queue_length + 1:
        logger.warning(f"[DEV_SELECT_POSITION_ADD] Пользователь {user_id} выбрал недопустимую позицию {selected_position} для очереди '{subject}' (длина {queue_length}).")
        await query.edit_message_text(f"Недопустимая позиция. Выберите от 1 до {queue_length + 1}.")
        # Возвращаем к выбору позиции
        await select_user_for_add(update, context)
        return

    # Удаляем пользователя из очереди, если он уже там (чтобы не дублировать)
    if selected_user_name in queues[subject]:
        queues[subject].remove(selected_user_name)
        logger.info(f"[DEV_SELECT_POSITION_ADD] Пользователь '{selected_user_name}' (ID {selected_user_id}) удален из очереди '{subject}' перед добавлением на новую позицию.")

    # Вставляем на выбранную позицию (преобразуем 1-нумерацию в 0-нумерацию индекса)
    queues[subject].insert(selected_position - 1, selected_user_name)
    logger.info(f"[DEV_SELECT_POSITION_ADD] Пользователь '{selected_user_name}' (ID {selected_user_id}) добавлен в очередь '{subject}' на позицию {selected_position} пользователем {user_id}.")

    # Сохраняем изменения
    from data import save_data_to_file
    save_data_to_file()
    logger.info(f"[DEV_SELECT_POSITION_ADD] Данные сохранены после добавления пользователя {selected_user_id} ({selected_user_name}) в очередь '{subject}' на позицию {selected_position} пользователем {user_id}.")

    await query.edit_message_text(f"Пользователь '{selected_user_name}' успешно добавлен в очередь '{subject}' на позицию {selected_position}.")
    # Очищаем состояния
    awaiting_position_selection_add.discard(user_id)
    selected_subject_for_add.pop(user_id, None)
    selected_user_for_add.pop(user_id, None)
    # Возвращаем в главное меню разработчика
    await show_dev_menu(update, context)

# --- Новая функция для очистки очередей от неизвестных пользователей ---

async def clean_queues_from_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очищает все очереди от пользователей, чьи имена не находятся в user_names."""
    user_id = update.effective_user.id
    logger.info(f"[DEV_CLEAN_UNKNOWN] Пользователь {user_id} запустил очистку очередей от неизвестных пользователей.")
    query = update.callback_query
    await query.answer()

    total_removed = 0
    user_names_list = [data["name"] for data in user_names.values()]
    
    for subject, queue_list in queues.items():
        original_length = len(queue_list)
        # Фильтруем очередь, оставляя только имена, которые есть в user_names
        cleaned_queue = [name for name in queue_list if name in user_names_list]
        removed_count = original_length - len(cleaned_queue)
        total_removed += removed_count
        if removed_count > 0:
            queues[subject] = cleaned_queue
            logger.info(f"[DEV_CLEAN_UNKNOWN] Из очереди '{subject}' удалено {removed_count} неизвестных пользователей.")

    if total_removed > 0:
        # Сохраняем изменения
        from data import save_data_to_file
        save_data_to_file()
        logger.info(f"[DEV_CLEAN_UNKNOWN] Данные сохранены после удаления {total_removed} неизвестных пользователей.")
        await query.edit_message_text(f"Очистка завершена. Удалено {total_removed} неизвестных пользователей из всех очередей.")
    else:
        await query.edit_message_text("Очистка завершена. Неизвестных пользователей не найдено.")
    # Возвращаем в главное меню разработчика
    await show_dev_menu(update, context)

# --- Функции для управления баном ---

async def start_ban_user_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс бана пользователя."""
    user_id = update.effective_user.id
    logger.info(f"[DEV_BAN_START] Пользователь {user_id} начал процесс бана.")
    query = update.callback_query
    await query.answer()
    
    awaiting_ban_user_selection.discard(user_id)
    
    if not user_names:
        await query.edit_message_text("Нет зарегистрированных пользователей для бана.")
        await show_dev_menu(update, context)
        return
    
    awaiting_ban_user_selection.add(user_id)
    keyboard = []
    for uid, data in user_names.items():
        if not data.get("banned", False):
            keyboard.append([InlineKeyboardButton(f"{data['name']} (ID: {uid})", callback_data=f'dev_select_ban_user_{uid}')])
    
    keyboard.append([InlineKeyboardButton("← Назад", callback_data='dev_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text("Выберите пользователя для бана:", reply_markup=reply_markup)

async def confirm_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выполняет бан пользователя и отправляет ему уведомление."""
    user_id = update.effective_user.id
    logger.info(f"[DEV_BAN_CONFIRM] Пользователь {user_id} подтверждает бан.")
    query = update.callback_query
    await query.answer()
    if user_id not in awaiting_ban_user_selection:
        logger.warning(f"[DEV_BAN_CONFIRM] Пользователь {user_id} не в состоянии ожидания.")
        await query.edit_message_text("Ошибка состояния. Начните снова.")
        await show_dev_menu(update, context)
        return

    selected_user_id_str = query.data.split('dev_select_ban_user_')[1]
    try:
        selected_user_id = int(selected_user_id_str)
    except ValueError:
        logger.error(f"[DEV_BAN_CONFIRM] Неверный ID {selected_user_id_str}.")
        await query.edit_message_text("Ошибка: некорректный ID пользователя.")
        await show_dev_menu(update, context)
        return

    if selected_user_id not in user_names:
        await query.edit_message_text("Пользователь не найден в базе данных.")
        await start_ban_user_process(update, context)
        return

    selected_user_name = user_names[selected_user_id]["name"]
    # success = ban_user(selected_user_id) # <-- БЫЛО
    success = await ban_user(selected_user_id, app_instance=context.application) # <-- СТАЛО
    if success:
        await query.edit_message_text(f"✅ Пользователь '{selected_user_name}' (ID: {selected_user_id}) успешно забанен.")
        logger.info(f"[DEV_BAN_CONFIRM] Пользователь {user_id} забанил '{selected_user_name}' (ID {selected_user_id}).")
        # УВЕДОМЛЕНИЕ отправляется внутри ban_user
    else:
        await query.edit_message_text(f"❌ Не удалось забанить пользователя. Возможно, он уже забанен.")
        logger.warning(f"[DEV_BAN_CONFIRM] Не удалось забанить {selected_user_id}.")

    awaiting_ban_user_selection.discard(user_id)
    await show_dev_menu(update, context)



async def start_unban_user_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает процесс разбана пользователя."""
    user_id = update.effective_user.id
    logger.info(f"[DEV_UNBAN_START] Пользователь {user_id} начал процесс разбана.")
    query = update.callback_query
    await query.answer()
    
    awaiting_unban_user_selection.discard(user_id)
    
    banned_list = get_all_banned_users()
    
    if not banned_list:
        await query.edit_message_text("Список забаненных пользователей пуст.")
        await show_dev_menu(update, context)
        return
    
    awaiting_unban_user_selection.add(user_id)
    keyboard = []
    for uid, data in banned_list.items():
        keyboard.append([InlineKeyboardButton(f"{data['name']} (ID: {uid})", callback_data=f'dev_confirm_unban_user_{uid}')])
    
    keyboard.append([InlineKeyboardButton("← Назад", callback_data='dev_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text("Выберите пользователя для разбана:", reply_markup=reply_markup)

async def confirm_unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выполняет разбан пользователя."""
    user_id = update.effective_user.id
    logger.info(f"[DEV_UNBAN_CONFIRM] Пользователь {user_id} подтверждает разбан.")
    query = update.callback_query
    await query.answer()
    if user_id not in awaiting_unban_user_selection:
        logger.warning(f"[DEV_UNBAN_CONFIRM] Пользователь {user_id} не в состоянии ожидания.")
        await query.edit_message_text("Ошибка состояния. Начните снова.")
        await show_dev_menu(update, context)
        return

    selected_user_id_str = query.data.split('dev_confirm_unban_user_')[1]
    try:
        selected_user_id = int(selected_user_id_str)
    except ValueError:
        logger.error(f"[DEV_UNBAN_CONFIRM] Неверный ID {selected_user_id_str}.")
        await query.edit_message_text("Ошибка: некорректный ID пользователя.")
        await show_dev_menu(update, context)
        return

    success = await unban_user(selected_user_id, app_instance=context.application)
    if success:
        await query.edit_message_text(f"✅ Пользователь {selected_user_id} успешно разбанен.")
        logger.info(f"[DEV_UNBAN_CONFIRM] Пользователь {user_id} разбанил {selected_user_id}.")
        
        # --- ОТПРАВКА УВЕДОМЛЕНИЯ РАЗБАНЕННОМУ ПОЛЬЗОВАТЕЛЮ (опционально) ---
        try:
            await context.bot.send_message(
                chat_id=selected_user_id,
                text="✅ Вы разбанены и можете снова использовать бота."
            )
            logger.info(f"[DEV_UNBAN_CONFIRM] Уведомление о разбане отправлено пользователю {selected_user_id}.")
        except Exception as e:
            logger.warning(f"[DEV_UNBAN_CONFIRM] Не удалось отправить уведомление о разбане пользователю {selected_user_id}: {e}")
        # ---
    else:
        await query.edit_message_text(f"❌ Не удалось разбанить пользователя.")
        logger.warning(f"[DEV_UNBAN_CONFIRM] Не удалось разбанить {selected_user_id}.")

    awaiting_unban_user_selection.discard(user_id)
    await show_dev_menu(update, context)


async def show_ban_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список забаненных пользователей."""
    user_id = update.effective_user.id
    logger.info(f"[DEV_SHOW_BAN_LIST] Пользователь {user_id} запросил банлист.")
    query = update.callback_query
    await query.answer()
    
    message = "📋 <b>Список забаненных пользователей:</b>\n\n"
    
    banned_list = get_all_banned_users()
    
    if not banned_list:
        message += "Забаненные пользователи отсутствуют."
    else:
        for uid, data in banned_list.items():
            message += f"🚫 {data['name']} (ID: <code>{uid}</code>)\n"
    
    keyboard = [[InlineKeyboardButton("← Назад", callback_data='dev_menu')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
    logger.info(f"[DEV_SHOW_BAN_LIST] Банлист показан пользователю {user_id}.")

async def update_rating_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обновляет рейтинг из Яндекс.Диска и показывает топ."""
    user_id = update.effective_user.id
    logger.info(f"[DEV_RATING] Пользователь {user_id} обновляет рейтинг")
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("⏳ Обновляю рейтинг из Яндекс.Диска...")

    # Обновляем рейтинг
    result = update_rating('ЯП')
    if result:
        logger.info(f"[DEV_RATING] Рейтинг успешно обновлен ({len(result)} студентов)")

        # Извлекаем только фамилии и сортируем
        surname_scores = {}
        for full_name, score in result.items():
            surname = full_name.split()[0]  # Берём первую часть (фамилию)
            surname_scores[surname] = score

        sorted_data = sorted(surname_scores.items(), key=lambda x: x[1], reverse=True)

        # Разбиваем на части по 27 студентов (чтобы уложиться в лимиты сообщения с форматированием)
        chunk_size = 27
        chunks = [sorted_data[i:i + chunk_size] for i in range(0, len(sorted_data), chunk_size)]

        # Отправляем каждую часть отдельным сообщением
        for chunk_idx, chunk in enumerate(chunks, start=1):
            message = f"<b>Рейтинг по ЯП :</b>\n\n"
            for rank, (surname, score) in enumerate(chunk, start=(chunk_idx - 1) * chunk_size + 1):
                medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}."
                message += f"{medal} <b>{surname}</b> — {score:.2f} лаб\n"
            
            if chunk_idx == len(chunks):
                keyboard = [[InlineKeyboardButton("← Назад", callback_data='dev_menu')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
            else:
                reply_markup = None
            
            await context.bot.send_message(
                chat_id=query.from_user.id,
                text=message,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        logger.info(f"[DEV_RATING] Отправлено {len(chunks)} сообщений с рейтингом")
    else:
        message = "❌ Ошибка при обновлении рейтинга"
        keyboard = [[InlineKeyboardButton("← Назад", callback_data='dev_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)
        logger.error(f"[DEV_RATING] Ошибка обновления рейтинга")


async def go_back_to_user_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Возвращает пользователя из dev-меню в обычное меню."""
    user_id = update.effective_user.id
    logger.info(f"[DEV_BACK_TO_USER] Пользователь {user_id} выходит из dev-режима.")
    dev_mode_users.discard(user_id)
    awaiting_subject_selection.discard(user_id)
    awaiting_user_selection.discard(user_id)
    selected_subject_for_removal.pop(user_id, None)
    awaiting_user_forget_selection.discard(user_id)
    # Очищаем и состояния добавления
    awaiting_subject_selection_add.discard(user_id)
    awaiting_user_selection_add.discard(user_id)
    selected_subject_for_add.pop(user_id, None)
    selected_user_for_add.pop(user_id, None)
    awaiting_position_selection_add.discard(user_id)
    # Очищаем состояния бана
    awaiting_ban_user_selection.discard(user_id)
    awaiting_unban_user_selection.discard(user_id)

    from user_handlers import show_subjects
    await show_subjects(update)

async def handle_dev_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Общий обработчик callback_query для разработчика."""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    logger.info(f"[DEV_CALLBACK] Получен callback от пользователя {user_id} с данными: '{data}'")

    if user_id not in dev_mode_users:
        logger.warning(f"[DEV_CALLBACK] Callback '{data}' от пользователя {user_id}, который не в dev-режиме.")
        await query.answer("Эта команда доступна только в режиме разработчика.", show_alert=True)
        return

    logger.info(f"[DEV_CALLBACK] Обработка callback '{data}' от пользователя {user_id} в dev-режиме.")

    if data == 'dev_menu':
        awaiting_subject_selection.discard(user_id)
        awaiting_user_selection.discard(user_id)
        selected_subject_for_removal.pop(user_id, None)
        awaiting_user_forget_selection.discard(user_id)
        awaiting_subject_selection_add.discard(user_id)
        awaiting_user_selection_add.discard(user_id)
        selected_subject_for_add.pop(user_id, None)
        selected_user_for_add.pop(user_id, None)
        awaiting_position_selection_add.discard(user_id)
        awaiting_ban_user_selection.discard(user_id)
        awaiting_unban_user_selection.discard(user_id)
        await show_dev_menu(update, context)
    elif data == 'dev_show_db':
        awaiting_subject_selection.discard(user_id)
        awaiting_user_selection.discard(user_id)
        selected_subject_for_removal.pop(user_id, None)
        awaiting_user_forget_selection.discard(user_id)
        awaiting_subject_selection_add.discard(user_id)
        awaiting_user_selection_add.discard(user_id)
        selected_subject_for_add.pop(user_id, None)
        selected_user_for_add.pop(user_id, None)
        awaiting_position_selection_add.discard(user_id)
        await show_database_content(update, context)
    # --- Новые обработчики для добавления СТОЯТ ПЕРВЫМИ ---
    elif data == 'dev_add_user_start':
        await start_add_user_process(update, context)
    elif data.startswith('dev_select_subject_add_'):
        await select_subject_for_add(update, context)
    elif data.startswith('dev_select_user_add_'):
        await select_user_for_add(update, context)
    elif data.startswith('dev_select_position_add_'):
        await select_position_for_add(update, context)
    # ---
    elif data == 'dev_remove_user_start':
        await start_remove_user_process(update, context)
    elif data.startswith('dev_select_subject_'): # Теперь обрабатывает только удаление
        await select_subject_for_removal(update, context)
    elif data.startswith('dev_confirm_remove_user_'):
        await confirm_remove_user(update, context)
    elif data == 'dev_forget_user_start':
        await start_forget_user_process(update, context)
    elif data.startswith('dev_confirm_forget_user_'):
        await confirm_forget_user(update, context)
    # --- Новый обработчик для очистки ---
    elif data == 'dev_clean_unknown':
        await clean_queues_from_unknown(update, context)
    # --- Обработчики для бана ---
    elif data == 'dev_ban_user_start':
        await start_ban_user_process(update, context)
    elif data.startswith('dev_select_ban_user_'):
        await confirm_ban_user(update, context)
    elif data == 'dev_unban_user_start':
        await start_unban_user_process(update, context)
    elif data.startswith('dev_confirm_unban_user_'):
        await confirm_unban_user(update, context)
    elif data == 'dev_show_ban_list':
        await show_ban_list(update, context)
    # ---
    elif data == 'dev_update_rating':  # <-- НОВЫЙ ОБРАБОТЧИК
        await update_rating_handler(update, context)
        return  # ВАЖНО: не вызываем show_dev_menu снова
    elif data == 'dev_back_to_user_menu':
        await go_back_to_user_menu(update, context)
    else:
        logger.warning(f"[DEV_CALLBACK] Неизвестный callback '{data}' от пользователя {user_id}")
        await query.answer("Неизвестная команда.", show_alert=True)
        awaiting_subject_selection.discard(user_id)
        awaiting_user_selection.discard(user_id)
        selected_subject_for_removal.pop(user_id, None)
        awaiting_user_forget_selection.discard(user_id)
        awaiting_subject_selection_add.discard(user_id)
        awaiting_user_selection_add.discard(user_id)
        selected_subject_for_add.pop(user_id, None)
        selected_user_for_add.pop(user_id, None)
        awaiting_position_selection_add.discard(user_id)
        awaiting_ban_user_selection.discard(user_id)
        awaiting_unban_user_selection.discard(user_id)
        await show_dev_menu(update, context)
