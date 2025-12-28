# rating.py

import logging
import requests
import tempfile
import os
from pathlib import Path
import pickle

from odf.opendocument import load
from odf.table import Table, TableCell
from odf.text import P

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

YANDEX_DISK_LINK = 'https://disk.yandex.ru/d/2CxHh12B72bOcg  '
TARGET_FILE_NAME = '2025-2026 ЛР.ods'
SHEET_NAME = '25КБ-1 ЯП'
RATING_FILE = 'rating_cache.db'  # Кеш рейтинга

# Словарь для хранения рейтинга в памяти
# Структура: {предмет: {имя: баллы}}
ratings = {}

def get_cell_text(cell):
    """Извлекает текст из ячейки ODS."""
    text = []
    for paragraph in cell.getElementsByType(P):
        # Извлекаем текст из каждого параграфа
        for node in paragraph.childNodes:
            if hasattr(node, 'data'):
                text.append(node.data)
    return ''.join(text).strip()

def download_file_from_yandex(public_link):
    """Скачивает файл с Яндекс.Диска по публичной ссылке на папку."""
    logger.info(f"[RATING] Попытка скачать файл {TARGET_FILE_NAME} из папки: {public_link}")
    
    try:
        # URL для получения содержимого публичной папки
        resource_url = 'https://cloud-api.yandex.net/v1/disk/public/resources'
        headers = {'Accept': 'application/json'}
        params = {'public_key': public_link.strip()}

        response = requests.get(resource_url, headers=headers, params=params)
        response.raise_for_status()
        folder_contents = response.json()

        # Логируем содержимое папки для отладки
        logger.info(f"[RATING] Содержимое папки: {list(item['name'] for item in folder_contents.get('_embedded', {}).get('items', []))}")

        # Поиск целевого файла в содержимом папки
        download_url = None
        if '_embedded' in folder_contents and 'items' in folder_contents['_embedded']:
            for item in folder_contents['_embedded']['items']:
                logger.debug(f"[RATING] Проверяем файл: {item['name']}")
                if item['name'] == TARGET_FILE_NAME:
                    download_url = item['file']  # Прямая ссылка на файл
                    logger.info(f"[RATING] Найден файл '{TARGET_FILE_NAME}', ссылка: {download_url}")
                    break

        if not download_url:
            logger.error(f"[RATING] Файл '{TARGET_FILE_NAME}' не найден в папке. Доступные файлы: {list(item['name'] for item in folder_contents.get('_embedded', {}).get('items', []))}")
            return None

        # Скачивание файла по прямой ссылке
        response = requests.get(download_url)
        response.raise_for_status()

        # Сохраняем во временный файл
        temp_dir = tempfile.gettempdir()
        temp_file = os.path.join(temp_dir, TARGET_FILE_NAME)
        
        with open(temp_file, 'wb') as f:
            f.write(response.content)
        
        logger.info(f"[RATING] Файл успешно скачан: {temp_file}")
        return temp_file
    
    except requests.exceptions.RequestException as e:
        logger.error(f"[RATING] Ошибка при обращении к API Яндекс.Диска: {e}")
        return None
    except KeyError:
        logger.error(f"[RATING] Ошибка: Неожиданный формат ответа от API.")
        return None
    except Exception as e:
        logger.error(f"[RATING] Ошибка при скачивании файла: {e}")
        return None

def parse_ods_file(file_path, sheet_name, start_row=35):
    """
    Парсит ODS файл и извлекает данные.
    start_row: строка, с которой начинаются данные (по умолчанию 35 в изображении)
    
    Возвращает словарь: {имя: баллы}
    """
    logger.info(f"[RATING] Парсинг файла {file_path}, лист '{sheet_name}'")
    
    try:
        doc = load(file_path)
        
        # Находим нужный лист
        sheet = None
        available_sheets = []
        for table_elem in doc.spreadsheet.getElementsByType(Table):
            sheet_name_attr = table_elem.getAttribute('name')
            available_sheets.append(sheet_name_attr)
            if sheet_name_attr == sheet_name:
                sheet = table_elem
                break
        
        if not sheet:
            logger.error(f"[RATING] Лист '{sheet_name}' не найден в файле. Доступные листы: {available_sheets}")
            return {}
        
        # Извлекаем строки из листа (не через getElementsByType(Table))
        rows = sheet.childNodes  # Строки находятся как дочерние элементы листа
        
        # Логируем количество строк для отладки
        logger.info(f"[RATING] Найдено {len(rows)} элементов в листе '{sheet_name}'")
        
        rating_data = {}
        
        for row_idx, row in enumerate(rows[start_row - 1:], start=start_row):
            # Проверяем, что элемент - это строка таблицы
            if row.qname[1] != 'table-row':  # qname[1] содержит имя тега
                continue
            
            cells = row.getElementsByType(TableCell)
            
            # Логируем количество ячеек в строке
            logger.debug(f"[RATING] Строка {row_idx}: {len(cells)} ячеек")
            
            if len(cells) < 3:  # Нужны минимум колонки A, B, C
                continue
            
            # Извлекаем текст из ячеек
            a_text = get_cell_text(cells[0])
            b_text = get_cell_text(cells[1])
            c_text = get_cell_text(cells[2]) if len(cells) > 2 else ''
            
            logger.debug(f"[RATING] A={a_text}, B={b_text}, C={c_text}")
            
            # Пропускаем пустые строки и строку заголовка
            if not a_text or a_text.strip() == 'итого':
                continue
            
            # Пропускаем строку заголовка
            if not b_text or b_text == 'ФИО':
                continue
            
            try:
                if c_text:
                    score = float(c_text.replace(',', '.'))
                    rating_data[b_text] = score
                    logger.debug(f"[RATING] Найден: {b_text} = {score}")
            except (ValueError, AttributeError):
                logger.warning(f"[RATING] Не удалось распарсить оценку для {b_text}: {c_text}")
                continue
        
        logger.info(f"[RATING] Загружено {len(rating_data)} студентов из '{sheet_name}'")
        return rating_data
    
    except Exception as e:
        logger.error(f"[RATING] Ошибка при парсинге ODS: {e}")
        return {}

def save_rating_to_cache(rating_data, subject):
    """Сохраняет рейтинг в кеш."""
    try:
        global ratings
        ratings[subject] = rating_data
        
        with open(RATING_FILE, 'wb') as f:
            pickle.dump(ratings, f)
        
        logger.info(f"[RATING] Рейтинг для '{subject}' сохранен в кеш")
    except Exception as e:
        logger.error(f"[RATING] Ошибка при сохранении кеша: {e}")

def load_rating_from_cache():
    """Загружает рейтинг из кеша."""
    global ratings
    try:
        if os.path.exists(RATING_FILE):
            with open(RATING_FILE, 'rb') as f:
                ratings = pickle.load(f)
            logger.info(f"[RATING] Рейтинг загружен из кеша")
        else:
            logger.info(f"[RATING] Файл кеша не найден")
    except Exception as e:
        logger.error(f"[RATING] Ошибка при загрузке кеша: {e}")

def update_rating(subject='ЯП'):
    """
    Обновляет рейтинг из Яндекс.Диска.
    subject: предмет (по умолчанию 'ЯП')
    
    Возвращает словарь с обновленным рейтингом или None если ошибка
    """
    logger.info(f"[RATING] Начало обновления рейтинга для '{subject}'")
    
    # Скачиваем файл
    file_path = download_file_from_yandex(YANDEX_DISK_LINK)
    if not file_path:
        logger.error(f"[RATING] Не удалось скачать файл с Яндекс.Диска")
        return None
    
    # Парсим файл
    rating_data = parse_ods_file(file_path, f'25КБ-1 {subject}')
    
    # Очищаем временный файл ВСЕГДА после обработки
    try:
        os.remove(file_path)
        logger.info(f"[RATING] Временный файл удален после обработки")
    except Exception as e:
        logger.warning(f"[RATING] Не удалось удалить временный файл {file_path}: {e}")
    
    if rating_data:  # <-- ИСПРАВЛЕНО: rating_data, а не rating_
        # Сохраняем в кеш
        save_rating_to_cache(rating_data, subject)
        logger.info(f"[RATING] Рейтинг успешно обновлен для '{subject}': {len(rating_data)} студентов")
        return rating_data
    else:
        logger.error(f"[RATING] Не удалось загрузить рейтинг для '{subject}'")
        return None

def get_cached_rating(subject='ЯП'):
    """Возвращает текущий рейтинг из кеша."""
    return ratings.get(subject, {})

def get_user_rating(user_name, subject='ЯП'):
    """Получает оценку конкретного пользователя."""
    if subject not in ratings:
        logger.warning(f"[RATING] Рейтинг для '{subject}' не загружен. Используйте update_rating()")
        return None
    
    return ratings[subject].get(user_name)

def get_top_rating(subject='ЯП', limit=10):
    """Возвращает топ студентов по оценкам."""
    if subject not in ratings:
        logger.warning(f"[RATING] Рейтинг для '{subject}' не загружен")
        return []
    
    # Сортируем по баллам в убывающем порядке
    sorted_rating = sorted(ratings[subject].items(), key=lambda x: x[1], reverse=True)
    return sorted_rating[:limit]

def get_user_rank(user_name, subject='ЯП'):
    """Получает место студента в рейтинге."""
    if subject not in ratings:
        logger.warning(f"[RATING] Рейтинг для '{subject}' не загружен")
        return None
    
    sorted_rating = sorted(ratings[subject].items(), key=lambda x: x[1], reverse=True)
    
    for rank, (name, score) in enumerate(sorted_rating, start=1):
        if name == user_name:
            return rank
    
    return None

def format_rating_message(subject='ЯП'):
    """Форматирует рейтинг в красивое сообщение."""
    top = get_top_rating(subject, limit=10)
    
    if not top:
        return f"📊 Рейтинг по '{subject}' не загружен"
    
    message = f"📊 <b>Топ рейтинга по {subject}:</b>\n\n"
    
    for rank, (name, score) in enumerate(top, start=1):
        medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}."
        message += f"{medal} <b>{name}</b> — {score:.2f} лаб\n"
    
    return message

# Загружаем рейтинг при импорте модуля
load_rating_from_cache()

