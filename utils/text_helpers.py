# --- START OF FILE utils/text_helpers.py ---
import re
import string
from urllib.parse import urlparse
from logger_config import get_logger
from typing import List # <-- Добавили List для типизации

# Максимальная длина сообщения Telegram
TELEGRAM_MAX_MESSAGE_LENGTH = 4096

logger = get_logger('text_helpers') # Используем имя модуля для логгера

# def escape_markdown_v2(text: str) -> str:
#     """
#     Экранирует специальные символы для Telegram MarkdownV2.
#     Символы: '_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!'
#     """
#     if not isinstance(text, str): # Добавим проверку типа на всякий случай
#         return ""
#     # Символы, которые нужно экранировать
#     escape_chars = r'_*[]()~`>#+-=|{}.!'
#     # Создаем регулярное выражение для поиска этих символов
#     # Нужно экранировать сам символ '-', поэтому он в конце или начале [...]
#     # Также экранируем ']'
#     regex = r'([' + re.escape(escape_chars) + r'])'
#     # Заменяем найденные символы на их экранированную версию (\символ)
#     return re.sub(regex, r'\\\1', text)

# >>>>> НАЧАЛО ФУНКЦИИ sanitize_text_for_telegram <<<<<
def sanitize_text_for_telegram(text: str) -> str:
    """
    Очищает текст для безопасной отправки через Telegram (даже с parse_mode='None').
    Удаляет Markdown, символ '@', опасные символы и непечатаемые символы.
    """
    if not isinstance(text, str):
        return ""

    # 1. Удаляем Markdown
    text = remove_markdown(text)

    # 2. Заменяем символ '@'
    text = text.replace('@', '(at)')

    # 3. Удаляем опасные символы, которые Telegram может попытаться распарсить
    dangerous_symbols = ['`', '*', '_', '[', ']', '(', ')', '~', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for symbol in dangerous_symbols:
        text = text.replace(symbol, '')

    # 4. Удаляем всё кроме допустимых символов
    allowed_chars = string.ascii_letters + string.digits + ' \t\n\r' + 'абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ'
    text = ''.join(c for c in text if c in allowed_chars)

    # 5. Убираем повторяющиеся пробелы и переносы
    text = re.sub(r'\s{2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()
# >>>>> КОНЕЦ ФУНКЦИИ sanitize_text_for_telegram <<<<<

def split_message(text: str, max_length: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> List[str]:
    """
    Разбивает длинный текст на части, не превышающие max_length.
    Старается разбивать по двойным переносам строк, затем по одинарным, затем по пробелам.
    Подходит для простого текста без сложного Markdown.
    """
    parts: List[str] = []
    if not text:
        return parts

    logger.debug(f"Разбиваем текст длиной {len(text)} символов на части по {max_length}")
    current_pos = 0
    while current_pos < len(text):
        end_pos = current_pos + max_length
        split_pos = -1

        # Если оставшаяся часть помещается, добавляем ее и выходим
        if end_pos >= len(text):
            parts.append(text[current_pos:])
            break

        # Ищем наилучшее место для разрыва (в обратном порядке от end_pos)
        # 1. Двойной перенос строки
        double_newline_pos = text.rfind('\n\n', current_pos, end_pos)
        if double_newline_pos != -1 and double_newline_pos > current_pos: # Убедимся, что не в самом начале
             split_pos = double_newline_pos + 2 # Включаем двойной перенос в предыдущую часть
        else:
            # 2. Одинарный перенос строки
            single_newline_pos = text.rfind('\n', current_pos, end_pos)
            if single_newline_pos != -1 and single_newline_pos > current_pos:
                 split_pos = single_newline_pos + 1
            else:
                # 3. Пробел
                space_pos = text.rfind(' ', current_pos, end_pos)
                if space_pos != -1 and space_pos > current_pos:
                    split_pos = space_pos + 1
                else:
                    # 4. Если ничего не нашли, режем по max_length
                    split_pos = end_pos

        # Добавляем найденную часть
        part_to_add = text[current_pos:split_pos].strip()
        if part_to_add: # Не добавляем пустые части
             parts.append(part_to_add)

        # Обновляем текущую позицию
        current_pos = split_pos

    logger.debug(f"Текст разбит на {len(parts)} частей.")
    return parts

def remove_markdown(text: str) -> str:
    """Удаляет основные Markdown v2 символы из текста."""
    if not text:
        return ""
    # Порядок важен: сначала удаляем экранирование, потом сами символы
    text = re.sub(r'\\([_*\[\]()~`>#+-=|{}.!])', r'\1', text) # Удаляем экранирование \
    # Удаление жирного (**text** или __text__)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)  # *курсив/жирный*
    text = re.sub(r'_([^_]+)_', r'\1', text)  # _курсив/подчеркнутый_
    # Удаление зачеркнутого (~text~)
    text = re.sub(r'~([^~]+)~', r'\1', text)
    # Удаление спойлера (||text||)
    text = re.sub(r'\|\|([^|]+)\|\|', r'\1', text)
    # Удаление ссылок ([text](url)) -> text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Удаление блоков кода (```lang\ncode``` или ```code```)
    text = re.sub(r'```(?:[a-zA-Z]+\n)?([\s\S]*?)```', r'\1', text) # Оставляем содержимое блока кода
    # Удаление встроенного кода (`code`) -> code
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Удаление заголовков (# Header) -> Header (не поддерживается в TG Markdown V2)
    # text = re.sub(r'^#+\s*(.*)', r'\1', text, flags=re.MULTILINE)
    # Удаление горизонтальных линий (---, ***, ___) (не поддерживается)
    # text = re.sub(r'^\s*[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    # Удаление элементов списка (* item, - item, + item, 1. item)
    text = re.sub(r'^[*\-]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\d+[\.\)]\s+', '', text, flags=re.MULTILINE)
    # Удаление цитат (> quote)
    text = re.sub(r'^>\s?', '', text, flags=re.MULTILINE)
    # Замена множественных пробелов и очистка
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()

def is_url(text: str) -> bool:
    """Проверяет, является ли строка валидным URL (простая проверка)."""
    if not text:
        return False
    # Упрощенная проверка: начинается с http:// или https:// и содержит точку после схемы
    if not (text.startswith('http://') or text.startswith('https://')):
        return False
    try:
        # Используем urlparse для базовой проверки структуры
        result = urlparse(text)
        # Проверяем наличие схемы и сетевой локации (домена)
        return bool(result.scheme and result.netloc and '.' in result.netloc)
    except ValueError: # urlparse может вызвать ValueError на очень странных строках
        return False

# --- END OF FILE utils/text_helpers.py ---