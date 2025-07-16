# --- START OF FILE utils/file_helpers.py ---
import os
import re # <-- Импортируем re
import docx # python-docx
import PyPDF2 # pypdf2
from typing import Optional
# Импортируем AsyncTeleBot для аннотации типа
from telebot.async_telebot import AsyncTeleBot

# Импортируем логгер
from logger_config import get_logger

file_logger = get_logger('file_utils') # Логгер для файловых операций

# Директория для временного хранения скачанных файлов
DOWNLOAD_DIR = "downloads"

def get_text_from_docx(file_path: str) -> Optional[str]:
    """Извлекает текст из DOCX файла."""
    try:
        if not os.path.exists(file_path):
             file_logger.error(f"Файл DOCX не найден по пути: {file_path}", extra={'user_id': 'System'})
             return None
        doc = docx.Document(file_path)
        full_text = [paragraph.text for paragraph in doc.paragraphs if paragraph.text] # Собираем только непустые параграфы
        extracted_text = "\n\n".join(full_text).strip() # Соединяем двойным переносом для сохранения абзацев
        if not extracted_text:
             file_logger.warning(f"Не удалось извлечь текст из DOCX (возможно, пустой): {file_path}", extra={'user_id': 'System'})
             return None
        file_logger.debug(f"Извлечено ~{len(extracted_text)} символов из DOCX: {os.path.basename(file_path)}", extra={'user_id': 'System'})
        return extracted_text
    except Exception as e:
        # Логируем ошибку, включая тип файла, так как docx может вызвать разные ошибки
        file_logger.exception(f"Ошибка при обработке DOCX файла {os.path.basename(file_path)}: {e}", extra={'user_id': 'System'})
        return None

def get_text_from_pdf(file_path: str) -> Optional[str]:
    """Извлекает текст из PDF файла."""
    text = ""
    try:
        if not os.path.exists(file_path):
            file_logger.error(f"Файл PDF не найден по пути: {file_path}", extra={'user_id': 'System'})
            return None

        with open(file_path, 'rb') as pdf_file:
            # Используем strict=False для большей устойчивости к поврежденным файлам
            pdf_reader = PyPDF2.PdfReader(pdf_file, strict=False)

            # Проверка на шифрование
            if pdf_reader.is_encrypted:
                try:
                    # Пытаемся снять шифрование без пароля (иногда работает для простых случаев)
                    if pdf_reader.decrypt('') == PyPDF2.PasswordType.NOT_DECRYPTED: # Проверяем результат дешифровки
                       file_logger.warning(f"PDF файл '{os.path.basename(file_path)}' зашифрован и не может быть расшифрован без пароля.", extra={'user_id': 'System'})
                       return None
                except Exception as decrypt_err:
                    file_logger.warning(f"Ошибка при попытке дешифровки PDF файла '{os.path.basename(file_path)}': {decrypt_err}", extra={'user_id': 'System'})
                    return None # Не можем извлечь текст из зашифрованного файла

            num_pages = len(pdf_reader.pages)
            file_logger.debug(f"Найдено {num_pages} страниц в PDF: {os.path.basename(file_path)}", extra={'user_id': 'System'})

            extracted_pages = 0
            for page_num in range(num_pages):
                try:
                    page = pdf_reader.pages[page_num]
                    page_text = page.extract_text()
                    if page_text: # Добавляем текст, только если он извлечен
                         text += page_text + "\n\n" # Добавляем двойной перенос строки между страницами
                         extracted_pages += 1
                except Exception as page_e:
                     # Ошибки могут быть разными, включая проблемы с конкретной страницей
                     file_logger.warning(f"Ошибка при извлечении текста со страницы {page_num + 1} PDF файла {os.path.basename(file_path)}: {page_e}", extra={'user_id': 'System'})
                     continue # Переходим к следующей странице

        extracted_text = text.strip()
        if not extracted_text:
             file_logger.warning(f"Не удалось извлечь текст из PDF (возможно, только изображения или пустой): {os.path.basename(file_path)}", extra={'user_id': 'System'})
             return None

        file_logger.debug(f"Извлечено ~{len(extracted_text)} символов с {extracted_pages}/{num_pages} страниц PDF: {os.path.basename(file_path)}", extra={'user_id': 'System'})
        return extracted_text
    except PyPDF2.errors.PdfReadError as read_err:
        file_logger.error(f"Ошибка чтения PDF (возможно, поврежден или не PDF): {os.path.basename(file_path)} - {read_err}", extra={'user_id': 'System'})
        return None
    except Exception as e:
        file_logger.exception(f"Неожиданная ошибка при обработке PDF файла {os.path.basename(file_path)}: {e}", extra={'user_id': 'System'})
        return None

def get_text_from_txt(file_path: str) -> Optional[str]:
    """Извлекает текст из TXT файла, пытаясь определить кодировку."""
    try:
        if not os.path.exists(file_path):
            file_logger.error(f"Файл TXT не найден по пути: {file_path}", extra={'user_id': 'System'})
            return None
        # Пробуем стандартные кодировки
        encodings_to_try = ['utf-8', 'cp1251', 'latin-1']
        extracted_text = None
        detected_encoding = None

        for enc in encodings_to_try:
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    extracted_text = f.read().strip()
                detected_encoding = enc
                file_logger.debug(f"Файл TXT '{os.path.basename(file_path)}' успешно прочитан с кодировкой {enc}.", extra={'user_id': 'System'})
                break # Выходим, если успешно прочитали
            except UnicodeDecodeError:
                file_logger.debug(f"Не удалось прочитать TXT '{os.path.basename(file_path)}' с кодировкой {enc}.", extra={'user_id': 'System'})
                continue # Пробуем следующую кодировку
            except Exception as inner_e:
                 file_logger.warning(f"Неожиданная ошибка при чтении TXT '{os.path.basename(file_path)}' с кодировкой {enc}: {inner_e}", extra={'user_id': 'System'})
                 continue

        if extracted_text is None:
             file_logger.error(f"Не удалось определить кодировку или прочитать TXT файл: {os.path.basename(file_path)}", extra={'user_id': 'System'})
             return None
        if not extracted_text:
             file_logger.warning(f"Файл TXT '{os.path.basename(file_path)}' пустой.", extra={'user_id': 'System'})
             return None

        file_logger.debug(f"Извлечено ~{len(extracted_text)} символов из TXT ({detected_encoding}): {os.path.basename(file_path)}", extra={'user_id': 'System'})
        return extracted_text
    except Exception as e:
        file_logger.exception(f"Ошибка при обработке TXT файла {os.path.basename(file_path)}: {e}", extra={'user_id': 'System'})
        return None

# --- ИЗМЕНЕНИЕ: Добавляем async ---
async def save_downloaded_file(bot: AsyncTeleBot, file_id: str, file_name: str) -> Optional[str]:
    """Скачивает файл из Telegram и сохраняет его локально во временную папку."""
    file_path_local = None # Используем другое имя переменной
    try:
        # Создаем директорию для скачивания, если ее нет
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

        file_logger.debug(f"Запрос информации о файле file_id: {file_id}")
        # --- ИЗМЕНЕНИЕ: Используем await ---
        file_info = await bot.get_file(file_id)
        if not file_info or not file_info.file_path:
            file_logger.error(f"Не удалось получить информацию о файле (или file_path) с file_id: {file_id}", extra={'user_id': 'System'})
            return None
        file_logger.debug(f"Информация о файле получена. file_path на сервере Telegram: {file_info.file_path}")

        file_logger.debug(f"Начало скачивания файла: {file_info.file_path}")
        # --- ИЗМЕНЕНИЕ: Используем await ---
        downloaded_file_content = await bot.download_file(file_info.file_path)
        if not downloaded_file_content:
             file_logger.error(f"Не удалось скачать файл с file_id: {file_id} (путь: {file_info.file_path}). bot.download_file вернул None.", extra={'user_id': 'System'})
             return None
        file_logger.debug(f"Файл скачан, размер: {len(downloaded_file_content)} байт.")

        # Создаем безопасное имя файла (убираем путь, заменяем опасные символы)
        safe_file_name = os.path.basename(file_name or f"file_{file_id}") # Если имя пустое, генерируем из ID
        safe_file_name = re.sub(r'[\\/*?:"<>|]', "_", safe_file_name) # Заменяем недопустимые символы
        # Добавляем уникальный префикс, чтобы избежать коллизий имен
        unique_prefix = f"{file_id[:8]}_"
        safe_file_name = unique_prefix + safe_file_name

        file_path_local = os.path.join(DOWNLOAD_DIR, safe_file_name)

        # Записываем скачанное содержимое в файл
        # Запись в файл - синхронная операция, выполняем как есть
        with open(file_path_local, 'wb') as new_file:
            new_file.write(downloaded_file_content)

        file_logger.info(f"Файл '{os.path.basename(file_name)}' (ID: {file_id}) успешно скачан и сохранен как '{file_path_local}'", extra={'user_id': 'System'})
        return file_path_local

    except Exception as e:
        file_logger.exception(f"Ошибка при скачивании или сохранении файла ID {file_id} ({file_name}): {e}", extra={'user_id': 'System'})
        # Удаляем частично скачанный файл, если он есть и произошла ошибка
        if file_path_local and os.path.exists(file_path_local):
            cleanup_file(file_path_local) # Используем cleanup_file
        return None

# --- cleanup_file остается синхронной ---
def cleanup_file(file_path: Optional[str]):
    """Удаляет указанный файл, если он существует."""
    if not file_path:
        return
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            file_logger.info(f"Временный файл '{file_path}' удален.", extra={'user_id': 'System'})
        else:
            file_logger.debug(f"Попытка удаления несуществующего файла: {file_path}", extra={'user_id': 'System'})
    except OSError as e:
        file_logger.error(f"Ошибка при удалении временного файла '{file_path}': {e}", extra={'user_id': 'System'})

# --- END OF FILE utils/file_helpers.py ---