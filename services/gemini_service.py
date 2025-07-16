# --- START OF FILE services/gemini_service.py ---
import google.generativeai as genai
from typing import List, Union, Dict, Optional, Tuple
import PIL.Image # Для работы с изображениями
from io import BytesIO

# Импортируем настройки и логгер
from config.settings import GEMINI_API_KEY, GEMINI_MODEL_NAME, GENERATION_CONFIG, SAFETY_SETTINGS
from logger_config import get_logger
from database import db_manager # Для сохранения истории

gemini_logger = get_logger('gemini_api')

# --- Инициализация модели ---
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL_NAME,
        generation_config=GENERATION_CONFIG,
        safety_settings=SAFETY_SETTINGS
    )
    gemini_logger.info(f"Модель Gemini '{GEMINI_MODEL_NAME}' успешно инициализирована.", extra={'user_id': 'System'})
except Exception as e:
    gemini_logger.exception(f"Критическая ошибка: Не удалось инициализировать модель Gemini: {e}", extra={'user_id': 'System'})
    # В реальном приложении здесь может быть логика аварийного завершения или оповещения
    raise  # Поднимаем исключение, чтобы бот не запустился без модели

# Словарь для хранения активных чатов (контекста) пользователей
# Ключ - user_id, значение - объект ChatSession
user_chats: Dict[int, genai.ChatSession] = {}

def _get_user_chat(user_id: int, reload_history: bool = False) -> genai.ChatSession:
    """
    Возвращает или создает сессию чата для пользователя.
    При reload_history=True загружает историю из БД.
    """
    global user_chats
    if user_id not in user_chats or reload_history:
        gemini_logger.debug(f"Создание/перезагрузка сессии чата для user_id: {user_id}", extra={'user_id': user_id})
        history_from_db = db_manager.get_conversation_history(user_id, limit=20) # Загружаем последние N сообщений
        # Преобразуем историю в формат, понятный Gemini
        gemini_history = []
        for role, text in history_from_db:
             # Gemini ожидает 'user' и 'model'
             gemini_role = 'user' if role == 'user' else 'model'
             gemini_history.append({'role': gemini_role, 'parts': [{'text': text}]})

        user_chats[user_id] = model.start_chat(history=gemini_history)
        gemini_logger.info(f"Сессия чата для user_id: {user_id} создана/перезагружена. Загружено {len(gemini_history)} сообщений.", extra={'user_id': user_id})
    return user_chats[user_id]

def reset_user_chat(user_id: int):
    """Сбрасывает историю чата для пользователя."""
    global user_chats
    if user_id in user_chats:
        del user_chats[user_id]
        gemini_logger.info(f"История чата для user_id: {user_id} сброшена.", extra={'user_id': user_id})
        # Опционально: можно также очистить историю в БД или пометить как сброшенную
    else:
        gemini_logger.debug(f"Попытка сброса несуществующей сессии чата для user_id: {user_id}", extra={'user_id': user_id})

def generate_response(user_id: int, prompt: Union[str, List[Union[str, PIL.Image.Image]]], store_in_db: bool = True) -> Optional[str]:
    """
    Генерирует ответ от Gemini, обрабатывает историю и ошибки.

    Args:
        user_id: ID пользователя Telegram.
        prompt: Текст запроса или список [текст, изображение].
        store_in_db: Сохранять ли запрос и ответ в БД.

    Returns:
        Текстовый ответ от модели или None в случае ошибки.
    """
    chat = _get_user_chat(user_id)
    prompt_for_log = prompt if isinstance(prompt, str) else "[Image + Text]" if isinstance(prompt, list) else "[Unknown Prompt Type]"

    try:
        gemini_logger.debug(f"Отправка запроса к Gemini для user_id: {user_id}. Prompt: '{prompt_for_log[:100]}...'", extra={'user_id': user_id})

        # --- Обработка разных типов prompt ---
        gemini_prompt_parts = []
        user_message_for_db = ""

        if isinstance(prompt, str):
            plain_text_instruction = "Пожалуйста, предоставь ответ в формате plain text, без какого-либо Markdown форматирования."
            gemini_prompt_parts.append(prompt + "\n\n" + plain_text_instruction) # Добавляем инструкцию к промпту
            user_message_for_db = prompt
        elif isinstance(prompt, list):
            # Предполагаем формат [text, image] или [image, text] или [image]
            img = None
            txt = ""
            for item in prompt:
                if isinstance(item, PIL.Image.Image):
                    img = item
                    gemini_prompt_parts.append(img) # Добавляем изображение
                elif isinstance(item, str):
                    txt = item
                    if not img and not txt:
                       gemini_logger.error(f"Некорректный prompt для user_id {user_id}: в списке нет ни текста, ни изображения", extra={'user_id': user_id})
                       return None

                    gemini_prompt_parts.append(txt) # Добавляем текст
            user_message_for_db = f"[Изображение] {txt}".strip() if img else txt # Формируем сообщение для БД
        else:
             gemini_logger.error(f"Неподдерживаемый тип prompt для user_id {user_id}: {type(prompt)}", extra={'user_id': user_id})
             return None

        # Сохраняем сообщение пользователя перед отправкой запроса
        if store_in_db and user_message_for_db: # Проверяем, что есть что сохранять
             db_manager.store_message(user_id, 'user', user_message_for_db)

        # Отправляем запрос в Gemini
        response = chat.send_message(gemini_prompt_parts) # Отправляем подготовленные части

        # Обработка ответа
        if response and response.text:
            response_text = response.text.strip()
            gemini_logger.debug(f"Получен ответ от Gemini для user_id: {user_id}. Response: '{response_text[:100]}...'", extra={'user_id': user_id})
            # Сохраняем ответ бота в БД
            if store_in_db:
                db_manager.store_message(user_id, 'bot', response_text)
            return response_text
        else:
            # Обработка случаев, когда ответ пустой или заблокирован
            block_reason = response.prompt_feedback.block_reason if response.prompt_feedback is not None else "Неизвестно (возможно, пустой ответ)"
            safety_ratings = response.prompt_feedback.safety_ratings if response.prompt_feedback is not None else "Нет данных"
            gemini_logger.warning(f"Получен пустой или заблокированный ответ от Gemini для user_id: {user_id}. Причина: {block_reason}. Рейтинги: {safety_ratings}", extra={'user_id': user_id})
            # Можно вернуть кастомное сообщение об ошибке или None
            # return f"Извините, я не могу ответить на этот запрос. Причина: {block_reason}."
            return None # Возвращаем None, чтобы обработчик в боте мог выдать стандартную ошибку

    except Exception as e:
        gemini_logger.exception(f"Ошибка при взаимодействии с Gemini API для user_id: {user_id}: {e}", extra={'user_id': user_id})
        return None # Возвращаем None при любой ошибке

# Дополнительные функции сервиса Gemini (если нужны):
# - Функция для генерации контента без сохранения истории (для специфичных задач)
# - Функция для анализа изображений без текстового запроса и т.д.

def generate_content_simple(prompt: Union[str, List[Union[str, PIL.Image.Image]]]) -> Optional[str]:
    """
    Генерирует ответ от Gemini без использования истории чата.
    Подходит для одноразовых запросов (например, анализ тем).
    """
    try:
        gemini_logger.debug(f"Отправка одноразового запроса к Gemini. Prompt: '{str(prompt)[:100]}...'", extra={'user_id': 'System'})
        response = model.generate_content(prompt) # Используем generate_content вместо chat.send_message

        if response and response.text:
            response_text = response.text.strip()
            gemini_logger.debug(f"Получен ответ на одноразовый запрос: '{response_text[:100]}...'", extra={'user_id': 'System'})
            return response_text
        else:
            block_reason = response.prompt_feedback.block_reason if response.prompt_feedback is not None else "Неизвестно (пустой ответ)"
            safety_ratings = response.prompt_feedback.safety_ratings if response.prompt_feedback is not None else "Нет данных"
            gemini_logger.warning(f"Получен пустой или заблокированный ответ на одноразовый запрос. Причина: {block_reason}. Рейтинги: {safety_ratings}", extra={'user_id': 'System'})
            return None

    except Exception as e:
        gemini_logger.exception(f"Ошибка при выполнении одноразового запроса к Gemini: {e}", extra={'user_id': 'System'})
        return None

# --- END OF FILE services/gemini_service.py ---