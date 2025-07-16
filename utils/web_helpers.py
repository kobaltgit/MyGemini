# --- START OF FILE utils/web_helpers.py ---
import requests
from bs4 import BeautifulSoup
from typing import Optional

# Импортируем логгер
from logger_config import get_logger

web_logger = get_logger('web_utils') # Логгер для веб-операций

DEFAULT_TIMEOUT = 15 # Таймаут для веб-запросов (в секундах)
# Оставляем стандартный User-Agent
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def get_text_from_url(url: str, timeout: int = DEFAULT_TIMEOUT) -> Optional[str]:
    """Извлекает основной текстовый контент со страницы по URL."""
    web_logger.info(f"Запрос на извлечение текста из URL: {url}", extra={'user_id':'System'})
    try:
        response = requests.get(url, timeout=timeout, headers=DEFAULT_HEADERS, allow_redirects=True, stream=True) # stream=True для проверки content-type до скачивания всего
        response.raise_for_status() # Проверяем на HTTP ошибки (4xx, 5xx)

        # Проверяем тип контента ДО скачивания всего тела ответа
        content_type = response.headers.get('content-type', '').lower()
        if 'html' not in content_type:
             web_logger.warning(f"Контент по URL {url} не является HTML ({content_type}). Извлечение текста невозможно.", extra={'user_id':'System'})
             response.close() # Закрываем соединение
             return None

        # Если это HTML, читаем контент
        try:
             # Указываем кодировку из ответа, если есть, иначе requests попытается угадать
             response_content = response.content # content читает все тело
        except Exception as read_err:
             web_logger.error(f"Ошибка чтения контента из URL {url}: {read_err}", extra={'user_id':'System'})
             return None
        finally:
             response.close() # Закрываем соединение в любом случае

        # Используем lxml для более быстрого парсинга, если доступен
        try:
            soup = BeautifulSoup(response_content, 'lxml')
            parser_used = 'lxml'
        except ImportError:
            web_logger.warning("Библиотека 'lxml' не установлена. Используется медленный 'html.parser'. Рекомендуется установить 'lxml' (`pip install lxml`).", extra={'user_id':'System'})
            soup = BeautifulSoup(response_content, 'html.parser')
            parser_used = 'html.parser'
        web_logger.debug(f"Используется парсер: {parser_used} для URL: {url}", extra={'user_id':'System'})


        # Удаляем ненужные теги (скрипты, стили, навигацию, футеры и т.д.)
        tags_to_remove = ["script", "style", "nav", "footer", "header", "aside", "form", "button", "select", "img", "svg", "iframe", "video", "audio", "figure"]
        for element in soup(tags_to_remove): # Более короткий способ найти все теги из списка
            element.decompose()

        # Извлекаем текст из основных тегов
        # Ищем основной контентный блок
        main_content = soup.find('main') or soup.find('article') or soup.find('div', role='main') or soup.find('div', id='content') or soup.find('div', class_='content') or soup.body

        if main_content:
            # Получаем текст, используя get_text с разделителем и strip=True
            # separator='\n' добавляет переносы между блочными элементами
            raw_text = main_content.get_text(separator='\n', strip=True)
        else:
            # Если не нашли основной контент, берем текст из body (менее надежно)
            web_logger.warning(f"Не удалось найти основной блок контента на {url}. Используем весь body.", extra={'user_id':'System'})
            raw_text = soup.get_text(separator='\n', strip=True) # Берем весь текст страницы

        # Постобработка: убираем лишние пустые строки
        lines = [line.strip() for line in raw_text.splitlines()]
        cleaned_text = "\n".join(line for line in lines if line) # Собираем только непустые строки

        if not cleaned_text:
             web_logger.warning(f"Не удалось извлечь значимый текст из URL: {url} после очистки.", extra={'user_id':'System'})
             return None

        web_logger.info(f"Успешно извлечено ~{len(cleaned_text)} символов из URL: {url}", extra={'user_id':'System'})
        return cleaned_text

    except requests.exceptions.Timeout:
        web_logger.error(f"Таймаут ({timeout}s) при запросе URL: {url}", extra={'user_id':'System'})
        return None
    except requests.exceptions.RequestException as e:
        web_logger.exception(f"Ошибка сети при запросе URL {url}: {e}", extra={'user_id':'System'})
        return None
    except Exception as e:
        # Ловим другие ошибки (например, при парсинге BeautifulSoup)
        web_logger.exception(f"Неожиданная ошибка при обработке контента URL {url}: {e}", extra={'user_id':'System'})
        return None

# --- END OF FILE utils/web_helpers.py ---