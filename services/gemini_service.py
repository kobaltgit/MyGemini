import aiohttp
import PIL.Image
from typing import List, Union, Dict, Optional, Any
from io import BytesIO
import base64

from config.settings import GEMINI_MODEL_NAME, GENERATION_CONFIG, SAFETY_SETTINGS
from logger_config import get_logger
from database import db_manager

gemini_logger = get_logger('gemini_api')

# Словарь для хранения истории чатов в памяти
user_chats: Dict[int, List[Dict[str, Any]]] = {}

# Базовый URL для Gemini API v1beta
GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


async def _make_gemini_request_async(api_key: str, model_name: str, contents: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Выполняет асинхронный HTTP-запрос к Gemini API.
    """
    url = f"{GEMINI_API_BASE_URL}/{model_name}:generateContent?key={api_key}"

    payload = {
        "contents": contents,
        "generationConfig": GENERATION_CONFIG,
        "safetySettings": SAFETY_SETTINGS
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                response_json = await response.json()
                if response.status != 200:
                    error_details = response_json.get('error', {})
                    gemini_logger.error(
                        f"Ошибка API Gemini (HTTP {response.status}): {error_details.get('message', 'Нет деталей')}",
                        extra={'user_id': 'System'}
                    )
                    return None
                return response_json
    except aiohttp.ClientError as e:
        gemini_logger.exception(f"Сетевая ошибка при запросе к Gemini API: {e}", extra={'user_id': 'System'})
        return None
    except Exception as e:
        gemini_logger.exception(f"Неожиданная ошибка при выполнении запроса к Gemini API: {e}", extra={'user_id': 'System'})
        return None

def _get_user_chat_history(user_id: int) -> List[Dict[str, Any]]:
    """
    Возвращает или создает историю чата для пользователя из кэша или БД.
    """
    global user_chats
    if user_id not in user_chats:
        gemini_logger.debug(f"Кэш истории для user_id: {user_id} не найден. Загрузка из БД.", extra={'user_id': str(user_id)})
        history_from_db = db_manager.get_conversation_history(user_id, limit=20)

        # Конвертируем формат из БД в формат Gemini API
        gemini_history = []
        for item in history_from_db:
            role = 'user' if item.get('role') == 'user' else 'model'
            gemini_history.append({"role": role, "parts": [{"text": item.get('message_text', '')}]})

        user_chats[user_id] = gemini_history
        gemini_logger.info(f"История для user_id: {user_id} загружена в кэш ({len(gemini_history)} сообщений).", extra={'user_id': str(user_id)})

    return user_chats[user_id]

def reset_user_chat(user_id: int):
    """Сбрасывает историю чата для пользователя в кэше."""
    global user_chats
    if user_id in user_chats:
        del user_chats[user_id]
        gemini_logger.info(f"История чата в кэше для user_id: {user_id} сброшена.", extra={'user_id': str(user_id)})

async def generate_response(user_id: int, api_key: str, prompt: Union[str, List[Union[str, PIL.Image.Image]]], store_in_db: bool = True) -> Optional[str]:
    """
    Генерирует ответ от Gemini, используя прямой HTTP-запрос.
    """
    history = _get_user_chat_history(user_id)

    # Формируем 'contents' для запроса
    request_contents = list(history) # Копируем историю
    user_message_for_db = ""

    # Обрабатываем промпт пользователя
    user_parts = []
    if isinstance(prompt, str):
        user_parts.append({"text": prompt})
        user_message_for_db = prompt
    elif isinstance(prompt, list):
        text_part = ""
        for item in prompt:
            if isinstance(item, str):
                text_part = item
            elif isinstance(item, PIL.Image.Image):
                # Конвертируем изображение в base64
                buffered = BytesIO()
                item.save(buffered, format="JPEG")
                img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
                user_parts.append({"inline_data": {"mime_type": "image/jpeg", "data": img_str}})
        user_parts.append({"text": text_part})
        user_message_for_db = f"[Изображение] {text_part}".strip()

    request_contents.append({"role": "user", "parts": user_parts})

    # Сохраняем сообщение пользователя в БД
    if store_in_db and user_message_for_db:
        db_manager.store_message(user_id, 'user', user_message_for_db)

    # Делаем запрос к API
    response_json = await _make_gemini_request_async(api_key, GEMINI_MODEL_NAME, request_contents)

    if not response_json or "candidates" not in response_json:
        # Если ответ неудачный, удаляем последнее сообщение пользователя из истории в кэше
        if history:
            history.pop()
        return None

    try:
        response_text = response_json["candidates"][0]["content"]["parts"][0]["text"].strip()

        # Обновляем историю в кэше
        history.append({"role": "user", "parts": user_parts})
        history.append({"role": "model", "parts": [{"text": response_text}]})

        # Сохраняем ответ бота в БД
        if store_in_db:
            db_manager.store_message(user_id, 'bot', response_text)

        return response_text
    except (KeyError, IndexError) as e:
        gemini_logger.error(f"Ошибка парсинга ответа от Gemini: {e}. Ответ: {response_json}", extra={'user_id': str(user_id)})
        return None

async def generate_content_simple(api_key: str, prompt: str) -> Optional[str]:
    """
    Генерирует ответ от Gemini без использования истории чата.
    """
    contents = [{"role": "user", "parts": [{"text": prompt}]}]
    response_json = await _make_gemini_request_async(api_key, GEMINI_MODEL_NAME, contents)

    if not response_json or "candidates" not in response_json:
        return None
    try:
        return response_json["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError):
        return None

async def validate_api_key(api_key: str) -> bool:
    """
    Проверяет валидность API-ключа, делая дешевый запрос (countTokens).
    """
    url = f"{GEMINI_API_BASE_URL}/{GEMINI_MODEL_NAME}:countTokens?key={api_key}"
    payload = {"contents": [{"parts": [{"text": "hello"}]}]}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                return response.status == 200
    except Exception:
        return False
