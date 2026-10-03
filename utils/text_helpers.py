# File: utils/text_helpers.py
import re
import html
import string
from urllib.parse import urlparse
from logger_config import get_logger
from typing import List

# Максимальная длина сообщения Telegram (используется новой библиотекой, но оставим для справки)
TELEGRAM_MAX_MESSAGE_LENGTH = 4096

logger = get_logger('text_helpers')


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

def escape_markdown(text: str, version: int = 2) -> str:
    """
    Экранирует специальные символы в тексте для безопасной отправки
    в Telegram с parse_mode='MarkdownV2'.
    """
    if not isinstance(text, str):
        return ""
    if version == 1:
        # Для старого Markdown, если понадобится
        escape_chars = r'_*`['
    elif version == 2:
        # Для MarkdownV2, который мы используем
        escape_chars = r'_*[]()~`>#+-=|{}.!'
    else:
        raise ValueError("Only Markdown versions 1 and 2 are supported.")

    # Экранируем только символы из списка
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)


def split_text_by_chunks(text: str, max_chars: int = 3500) -> list[str]:
    """
    Разбивает длинный текст на удобочитаемые части, не превышающие max_chars.
    Старается делить по границам абзацев (\\n\\n), строк (\\n) или пробелов.
    Гарантирует, что ни один чанк не превысит лимит Telegram (4096 символов).
    """
    if not text:
        return []
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_chars:
            chunks.append(text)
            break

        # Ищем наилучшую точку разделения в пределах max_chars
        split_idx = text.rfind("\n\n", 0, max_chars)
        if split_idx == -1 or split_idx < max_chars // 2:
            split_idx = text.rfind("\n", 0, max_chars)
        if split_idx == -1 or split_idx < max_chars // 2:
            split_idx = text.rfind(" ", 0, max_chars)
        if split_idx == -1:
            split_idx = max_chars

        chunk = text[:split_idx].strip()
        if chunk:
            chunks.append(chunk)
        text = text[split_idx:].strip()

    return chunks


def markdown_to_telegram_html(text: str) -> str:
    """
    Converts standard GitHub-flavored Markdown text (such as full user manuals)
    into clean, valid Telegram HTML.
    - Removes internal section markers: # [НАЧАЛО РАЗДЕЛА: ...] / # [START OF SECTION: ...]
    - Removes horizontal dividers (---)
    - Converts code blocks and inline code safely with HTML escaping
    - Converts headers (###, ####, ##, #) to <b>bold</b>
    - Converts **bold** to <b>bold</b>
    - Converts *italic* and _italic_ to <i>italic</i>
    - Converts bullet lists (*, -) to unicode bullet dots (•)
    - Converts image links ![alt](url) to clickable link 🖼 <a href="url">alt</a>
    - Converts hyperlinks [text](url) to <a href="url">text</a>
    - Safely escapes unhandled HTML entities
    """
    if not text:
        return ""

    # 1. Remove internal section tags and dividers
    text = re.sub(r'# \[(?:НАЧАЛО|КОНЕЦ|START OF|END OF) SECTION:?[^\]]*\]\n*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'# \[(?:НАЧАЛО|КОНЕЦ) РАЗДЕЛА:?[^\]]*\]\n*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^[ \t]*---[ \t]*$', '', text, flags=re.MULTILINE)

    # 2. Extract and protect code blocks
    code_blocks = []
    def _save_code_block(match):
        code_content = match.group(2)
        escaped_code = html.escape(code_content.strip(), quote=False)
        placeholder = f"__CODE_BLOCK_{len(code_blocks)}__"
        code_blocks.append(f"<pre><code>{escaped_code}</code></pre>")
        return placeholder

    text = re.sub(r'```(?:([a-zA-Z0-9_-]+)\n)?([\s\S]*?)```', _save_code_block, text)

    # 3. Extract and protect inline code
    inline_codes = []
    def _save_inline_code(match):
        code_content = match.group(1)
        escaped_code = html.escape(code_content, quote=False)
        placeholder = f"__INLINE_CODE_{len(inline_codes)}__"
        inline_codes.append(f"<code>{escaped_code}</code>")
        return placeholder

    text = re.sub(r'`([^`\n]+)`', _save_inline_code, text)

    # 4. Escape special HTML entities before applying tags
    text = re.sub(r'&(?!(?:amp|lt|gt|quot|#\d+);)', '&amp;', text)
    text = text.replace('<', '&lt;').replace('>', '&gt;')

    # 5. Convert Images: ![alt](url) -> 🖼 <a href="url">alt</a>
    def _convert_image(match):
        alt = match.group(1) or "Image"
        url = match.group(2)
        return f'🖼 <a href="{url}">{alt}</a>'

    text = re.sub(r'!\[(.*?)\]\((https?://[^\s\)]+)\)', _convert_image, text)

    # 6. Convert Links: [text](url) -> <a href="url">text</a>
    def _convert_link(match):
        link_text = match.group(1)
        url = match.group(2)
        return f'<a href="{url}">{link_text}</a>'

    text = re.sub(r'\[(.*?)\]\((https?://[^\s\)]+)\)', _convert_link, text)

    # 7. Convert Headers: # H1, ## H2, ### H3, #### H4 -> <b>Header</b>
    text = re.sub(r'^[ \t]*#{1,6}[ \t]+([^\n]+)$', r'<b>\1</b>', text, flags=re.MULTILINE)

    # 8. Convert Bold: **text** -> <b>text</b>
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text, flags=re.DOTALL)

    # 9. Convert Italic: *text* -> <i>text</i> and _text_ -> <i>text</i>
    text = re.sub(r'(?<![*\w])\*([^*\n]+)\*(?![*\w])', r'<i>\1</i>', text)
    text = re.sub(r'(?<![_\w])_([^_\n]+)_(?![_\w])', r'<i>\1</i>', text)

    # 10. Convert Bullet Lists: * item or - item -> • item
    text = re.sub(r'^[ \t]*[\*\-][ \t]+', '• ', text, flags=re.MULTILINE)

    # 11. Restore inline code and code blocks
    for idx, inc in enumerate(inline_codes):
        text = text.replace(f"__INLINE_CODE_{idx}__", inc)

    for idx, cb in enumerate(code_blocks):
        text = text.replace(f"__CODE_BLOCK_{idx}__", cb)

    # 12. Normalize multiple empty lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()