import pickle
import logging
from constants import SUBJECTS, DATA_FILE

# Включаем логирование
logger = logging.getLogger(__name__)

# --- Хранилище данных ---
# Словарь для хранения имён пользователей (ID -> имя)
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
        user_names.update(loaded_data.get('user_names', {}))
        queues.update(loaded_data.get('queues', {subject: [] for subject in SUBJECTS}))
        logger.info(f"Данные успешно загружены из {DATA_FILE}")
    except FileNotFoundError:
        logger.info(f"Файл {DATA_FILE} не найден. Используем начальные значения.")
        # Если файл не существует, создадим его с начальными значениями
        save_data_to_file()
    except Exception as e:
        logger.error(f"Неизвестная ошибка при загрузке данных из файла {DATA_FILE}: {e}")
        # В случае любой ошибки, создадим файл заново
        save_data_to_file()

# Загружаем данные при импорте модуля
load_data_from_file() # <-- Эта строка важна!

# --- Функции для работы с данными ---
def add_user_to_queue(user_id, subject, position=None):
    """
    Добавляет пользователя в очередь на определённую позицию.
    user_id: ID пользователя (int)
    subject: Предмет (str)
    position: Позиция в очереди (int), если None - в конец
    """
    name = user_names.get(user_id)
    if not name or subject not in queues:
        logger.warning(f"add_user_to_queue: Пользователь {user_id} ({name}) или предмет '{subject}' не найдены.")
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

    save_data_to_file() # Сохраняем изменения
    return True

def remove_user_from_queue(user_id, subject):
    """
    Удаляет пользователя из очереди по определённому предмету.
    user_id: ID пользователя (int)
    subject: Предмет (str)
    """
    name = user_names.get(user_id)
    if name and name in queues[subject]:
        queues[subject].remove(name)
        save_data_to_file() # Сохраняем изменения
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
    name = user_names.get(user_id)
    if not name or subject not in queues or name not in queues[subject]:
        logger.warning(f"move_user_in_queue: Пользователь {user_id} ({name}), предмет '{subject}' или пользователь не в очереди.")
        return False

    if not (0 <= new_position < len(queues[subject])):
        logger.warning(f"move_user_in_queue: Некорректная позиция {new_position} для очереди '{subject}'.")
        return False

    old_position = queues[subject].index(name)
    queues[subject].remove(name)
    queues[subject].insert(new_position, name)
    save_data_to_file() # Сохраняем изменения
    logger.info(f"move_user_in_queue: Пользователь '{name}' (ID {user_id}) перемещен в очереди '{subject}' с позиции {old_position} на позицию {new_position}.")
    return True