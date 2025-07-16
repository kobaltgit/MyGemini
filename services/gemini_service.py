# File: services/gemini_service.py
import aiohttp
import PIL.Image
from typing import List, Union, Dict, Optional, Any
from io import BytesIO
import base64

from config.settings import GEMINI_MODEL_NAME, GENERATION_CONFIG, SAFETY_SETTINGS
from logger_config import get_logger
from database import db_manager
from .error_parser import get_user_friendly_error_key # Импортируем наш новый парсер

gemini_logger = get_logger('gemini_api')

# Словарь для хранения истории чатов в памяти
user_chats: Dict[int, List[Dict[str, Any]]] = {}

# Базовый URL для Gemini API v1beta
GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiAPIError(Exception):
    """Кастомное исключение для ошибок Gemini API."""
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message)
        self.details = details or {}
        self.error_key = get_user_friendly_error_key(self.details)

async def _make_gemini_request_async(api_key: str, url: str, payload: Optional[Dict] = None,
                                     method: str = 'POST') -> Dict[str, Any]:
    """
    Выполняет универсальный асинхронный HTTP-запрос к Gemini API.
    В случае ошибки выбрасывает GeminiAPIError.
    """
    headers = {'Content-Type': 'application/json'}
    params = {'key': api_key}

    try:
        async with aiohttp.ClientSession() as session:
            request_args = {'params': params, 'headers': headers}
            if payload:
                request_args['json'] = payload

            async with session.request(method, url, **request_args) as response:
                response_json = await response.json()
                if response.status != 200:
                    error_details = response_json.get('error', {})
                    error_message = error_details.get('message', 'Неизвестная ошибка API')
                    gemini_logger.error(f"Ошибка API Gemini (HTTP {response.status}): {error_message}", extra={'user_id': 'System'})
                    raise GeminiAPIError(error_message, details=error_details)
                return response_json
    except aiohttp.ClientError as e:
        gemini_logger.exception(f"Сетевая ошибка при запросе к Gemini API: {e}", extra={'user_id': 'System'})
        raise GeminiAPIError("Сетевая ошибка при подключении к сервису.", details={"error": {"message": "service_unavailable"}})
    except GeminiAPIError:
        # Просто пробрасываем ошибку дальше
        raise
    except Exception as e:
        gemini_logger.exception(f"Неожиданная ошибка при выполнении запроса к Gemini API: {e}", extra={'user_id': 'System'})
        raise GeminiAPIError(f"Неожиданная ошибка: {e}", details={"error": {"message": "unknown_error"}})


def _get_user_chat_history(user_id: int) -> List[Dict[str, Any]]:
    """
    Возвращает или создает историю чата для пользователя из кэша или БД.
    """
    global user_chats
    if user_id not in user_chats:
        gemini_logger.debug(f"Кэш истории для user_id: {user_id} не найден. Загрузка из БД.", extra={'user_id': str(user_id)})
        history_from_db = db_manager.get_conversation_history(user_id, limit=20)
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


async def generate_response(user_id: int, api_key: str, prompt: Union[str, List[Union[str, PIL.Image.Image]]], store_in_db: bool = True) -> str:
    """
    Генерирует ответ от Gemini.
    Выбрасывает GeminiAPIError в случае сбоя.
    """
    model_name = db_manager.get_user_gemini_model(user_id) or GEMINI_MODEL_NAME
    gemini_logger.info(f"Используется модель '{model_name}' для user_id: {user_id}", extra={'user_id': str(user_id)})
    history = _get_user_chat_history(user_id)
    request_contents = list(history)
    user_message_for_db = ""
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
                buffered = BytesIO()
                if item.mode == 'RGBA': item = item.convert('RGB')
                item.save(buffered, format="JPEG")
                img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
                user_parts.append({"inline_data": {"mime_type": "image/jpeg", "data": img_str}})
        user_parts.append({"text": text_part})
        user_message_for_db = f"[Изображение] {text_part}".strip()
    request_contents.append({"role": "user", "parts": user_parts})

    # ИЗМЕНЕНО: Сообщение пользователя сохраняется без токенов, так как токены относятся ко всему обмену
    if store_in_db and user_message_for_db:
        db_manager.store_message(user_id, 'user', user_message_for_db)

    url = f"{GEMINI_API_BASE_URL}/models/{model_name}:generateContent"
    payload = {"contents": request_contents, "generationConfig": GENERATION_CONFIG, "safetySettings": SAFETY_SETTINGS}

    try:
        response_json = await _make_gemini_request_async(api_key, url, payload, 'POST')
        if not response_json or "candidates" not in response_json:
            raise GeminiAPIError("Ответ API не содержит 'candidates'.", details=response_json)

        # Проверка на safety settings
        if response_json["candidates"][0].get("finishReason") == "SAFETY":
             raise GeminiAPIError("Ответ заблокирован настройками безопасности.", details={"finish_reason": "SAFETY"})

        response_text = response_json["candidates"][0]["content"]["parts"][0]["text"].strip()
        history.append({"role": "user", "parts": user_parts})
        history.append({"role": "model", "parts": [{"text": response_text}]})

        # НОВОЕ: Извлекаем информацию о токенах
        usage_metadata = response_json.get('usageMetadata', {})
        prompt_tokens = usage_metadata.get('promptTokenCount', 0)
        completion_tokens = usage_metadata.get('candidatesTokenCount', 0)
        total_tokens = usage_metadata.get('totalTokenCount', 0)
        gemini_logger.info(
            f"Использование токенов для user_id: {user_id} - "
            f"Prompt: {prompt_tokens}, Completion: {completion_tokens}, Total: {total_tokens}",
            extra={'user_id': str(user_id)}
        )

        if store_in_db:
            # ИЗМЕНЕНО: Сохраняем сообщение бота вместе с информацией о токенах
            db_manager.store_message(
                user_id=user_id,
                role='bot',
                message_text=response_text,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
            )
        return response_text
    except (KeyError, IndexError) as e:
        gemini_logger.error(f"Ошибка парсинга ответа от Gemini: {e}", extra={'user_id': str(user_id)})
        raise GeminiAPIError(f"Ошибка чтения ответа от API: {e}", details={"error": {"message": "parsing_error"}})
    except GeminiAPIError as e:
        # Если произошла ошибка, удаляем последнее сообщение пользователя из истории в кэше, чтобы не засорять контекст
        if history: history.pop()
        raise e


async def generate_content_simple(api_key: str, prompt: str) -> str:
    """Генерирует ответ от Gemini без истории. Выбрасывает GeminiAPIError."""
    url = f"{GEMINI_API_BASE_URL}/models/{GEMINI_MODEL_NAME}:generateContent"
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    response_json = await _make_gemini_request_async(api_key, url, payload, 'POST')
    try:
        # Примечание: простой запрос тоже возвращает токены, но мы их здесь не отслеживаем,
        # так как это используется для внутренних нужд (анализ тем, перевод), а не для основного чата.
        return response_json["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError) as e:
        raise GeminiAPIError(f"Ошибка чтения ответа от API: {e}", details={"error": {"message": "parsing_error"}})

async def validate_api_key(api_key: str) -> bool:
    """Проверяет валидность API-ключа."""
    url = f"{GEMINI_API_BASE_URL}/models/{GEMINI_MODEL_NAME}:countTokens"
    payload = {"contents": [{"parts": [{"text": "hello"}]}]}
    try:
        response = await _make_gemini_request_async(api_key, url, payload, 'POST')
        return response is not None and "totalTokens" in response
    except GeminiAPIError:
        return False


async def get_available_models(api_key: str) -> List[Dict[str, str]]:
    """Получает список доступных моделей Gemini с API. Выбрасывает GeminiAPIError."""
    url = f"{GEMINI_API_BASE_URL}/models"
    response_json = await _make_gemini_request_async(api_key, url, method='GET')
    available_models = []
    if not response_json or 'models' not in response_json:
        return []

    for model in response_json['models']:
        model_name = model.get('name', '').replace('models/', '')
        if 'generateContent' in model.get('supportedGenerationMethods', []) and \
           'embedding' not in model_name and 'aqa' not in model_name and 'text-embedding' not in model_name:
            available_models.append({
                "name": model_name,
                "display_name": model.get('displayName', model_name)
            })

    available_models.sort(key=lambda x: ('flash' not in x['name'], 'pro' not in x['name'], x['name']))
    return available_models
