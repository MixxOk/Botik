import pickle
import logging
from constants import SUBJECTS, DATA_FILE
from telegram.ext import Application

application = None

# Включаем логирование
logger = logging.getLogger(__name__)



# --- Хранилище данных ---
# Словарь для хранения пользователей: ID -> {"name": "Имя", "banned": False}
user_names = {}
# Очередь в виде словаря для каждого предмета
queues = {subject: [] for subject in SUBJECTS}

def save_data_to_file():
    """Сохраняет данные в бинарный .db файл."""
    data_to_save = {
        'user_names': user_names,
        'queues': queues,
    }
    try:
        with open(DATA_FILE, 'wb') as f:
            pickle.dump(data_to_save, f)
        logger.info(f"Данные успешно сохранены в {DATA_FILE}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных в файл {DATA_FILE}: {e}")

def load_data_from_file():
    """Загружает данные из бинарного .db файла."""
    global user_names, queues
    try:
        with open(DATA_FILE, 'rb') as f:
            loaded_data = pickle.load(f)
        # Обновляем словари
        loaded_users = loaded_data.get('user_names', {})
        # Конвертируем старый формат если нужно
        for uid, data in loaded_users.items():
            if isinstance(data, str):
                user_names[uid] = {"name": data, "banned": False}
            else:
                user_names[uid] = data
        
        queues.update(loaded_data.get('queues', {subject: [] for subject in SUBJECTS}))
        logger.info(f"Данные успешно загружены из {DATA_FILE}")
    except FileNotFoundError:
        logger.info(f"Файл {DATA_FILE} не найден. Используем начальные значения.")
        save_data_to_file()
    except Exception as e:
        logger.error(f"Неизвестная ошибка при загрузке данных из файла {DATA_FILE}: {e}")
        save_data_to_file()

# Загружаем данные при импорте модуля
load_data_from_file()

# --- Функции для работы с данными ---
def add_user_to_queue(user_id, subject, position=None):
    """
    Добавляет пользователя в очередь на определённую позицию.
    user_id: ID пользователя (int)
    subject: Предмет (str)
    position: Позиция в очереди (int), если None - в конец
    """
    if user_id not in user_names:
        logger.warning(f"add_user_to_queue: Пользователь {user_id} не найден.")
        return False
    
    name = user_names[user_id]["name"]
    if subject not in queues:
        logger.warning(f"add_user_to_queue: Предмет '{subject}' не найден.")
        return False

    if name in queues[subject]:
        old_position = queues[subject].index(name)
        queues[subject].remove(name)
        logger.info(f"add_user_to_queue: Пользователь '{name}' (ID {user_id}) удален из очереди '{subject}' с позиции {old_position} перед добавлением.")

    if position is not None and 0 <= position <= len(queues[subject]):
        queues[subject].insert(position, name)
        logger.info(f"add_user_to_queue: Пользователь '{name}' (ID {user_id}) добавлен в очередь '{subject}' на позицию {position}.")
    else:
        queues[subject].append(name)
        logger.info(f"add_user_to_queue: Пользователь '{name}' (ID {user_id}) добавлен в конец очереди '{subject}'.")

    save_data_to_file()
    return True

def remove_user_from_queue(user_id, subject):
    """
    Удаляет пользователя из очереди по определённому предмету.
    user_id: ID пользователя (int)
    subject: Предмет (str)
    """
    if user_id not in user_names:
        logger.warning(f"remove_user_from_queue: Пользователь {user_id} не найден.")
        return False
    
    name = user_names[user_id]["name"]
    if name and name in queues[subject]:
        queues[subject].remove(name)
        save_data_to_file()
        logger.info(f"remove_user_from_queue: Пользователь '{name}' (ID {user_id}) удален из очереди '{subject}'.")
        return True
    else:
        logger.info(f"remove_user_from_queue: Пользователь '{name}' (ID {user_id}) не найден в очереди '{subject}', удаление не выполнено.")
        return False

def move_user_in_queue(user_id, subject, new_position):
    """
    Перемещает пользователя в очереди на новую позицию.
    user_id: ID пользователя (int)
    subject: Предмет (str)
    new_position: Новая позиция (int)
    """
    if user_id not in user_names:
        logger.warning(f"move_user_in_queue: Пользователь {user_id} не найден.")
        return False
    
    name = user_names[user_id]["name"]
    if subject not in queues or name not in queues[subject]:
        logger.warning(f"move_user_in_queue: Пользователь '{name}' не в очереди '{subject}'.")
        return False

    if not (0 <= new_position < len(queues[subject])):
        logger.warning(f"move_user_in_queue: Некорректная позиция {new_position} для очереди '{subject}'.")
        return False

    old_position = queues[subject].index(name)
    queues[subject].remove(name)
    queues[subject].insert(new_position, name)
    save_data_to_file()
    logger.info(f"move_user_in_queue: Пользователь '{name}' (ID {user_id}) перемещен в очереди '{subject}' с позиции {old_position} на позицию {new_position}.")
    return True

def is_user_banned(user_id):
    """Проверяет, забанен ли пользователь."""
    if user_id not in user_names:
        return False
    return user_names[user_id].get("banned", False)

async def ban_user(user_id, app_instance=None): # <-- ДОБАВИТЬ app_instance
    """Добавляет пользователя в бан."""
    global application # <-- ДОБАВИТЬ ЭТУ СТРОКУ
    if app_instance:
        application = app_instance # <-- ОБНОВИТЬ application, если передано
    
    if user_id not in user_names:
        logger.info(f"ban_user: Пользователь {user_id} не найден в user_names.")
        return False
    
    if user_names[user_id]["banned"]:
        logger.info(f"ban_user: Пользователь {user_id} уже забанен.")
        return False
    
    user_names[user_id]["banned"] = True
    user_name = user_names[user_id]["name"]
    
    # Удаляем пользователя из всех очередей
    for subject in queues:
        if user_name in queues[subject]:
            queues[subject].remove(user_name)
    
    save_data_to_file()
    logger.info(f"ban_user: Пользователь {user_id} ({user_name}) забанен.")
    
    # --- ОТПРАВКА УВЕДОМЛЕНИЯ ЗАБАНЕННОМУ ПОЛЬЗОВАТЕЛЮ ---
    if application:
        try:
            await application.bot.send_message(
                chat_id=user_id,
                text="❌ Вы забанены и не можете больше использовать этого бота."
            )
            logger.info(f"ban_user: Уведомление о бане отправлено пользователю {user_id}.")
        except Exception as e:
            logger.warning(f"ban_user: Не удалось отправить уведомление о бане пользователю {user_id}: {e}")
    # ---
    return True

async def unban_user(user_id, app_instance=None):
    """Удаляет пользователя из бана."""
    global application
    if app_instance:
        application = app_instance

    if user_id not in user_names:
        logger.info(f"unban_user: Пользователь {user_id} не найден в user_names.")
        return False

    user_names[user_id]["banned"] = False
    save_data_to_file()
    logger.info(f"unban_user: Пользователь {user_id} разбанен.")

    # --- ОТПРАВКА УВЕДОМЛЕНИЯ РАЗБАНЕННОМУ ПОЛЬЗОВАТЕЛЮ (опционально) ---
    if application:
        try:
            await application.bot.send_message(
                chat_id=user_id,
                text="✅ Вы разбанены и можете снова использовать бота."
            )
            logger.info(f"unban_user: Уведомление о разбане отправлено пользователю {user_id}.")
        except Exception as e:
            logger.warning(f"unban_user: Не удалось отправить уведомление о разбане пользователю {user_id}: {e}")
    # ---
    return True


def get_all_banned_users():
    """Возвращает словарь всех забаненных пользователей."""
    return {uid: data for uid, data in user_names.items() if data.get("banned", False)}
