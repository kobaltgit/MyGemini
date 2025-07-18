# File: services/gemini_service.py
import asyncio
import aiohttp
import PIL.Image
from typing import List, Union, Dict, Optional, Any
from io import BytesIO
import base64
import re
from cachetools import LRUCache

from config.settings import DEFAULT_MODEL_ID, GENERATION_CONFIG, SAFETY_SETTINGS, BOT_PERSONAS, BOT_STYLES
from utils import guide_manager
from logger_config import get_logger
from database import db_manager
from .error_parser import get_user_friendly_error_key

gemini_logger = get_logger('gemini_api')

# Кэш для хранения истории диалогов. Ограничен по размеру для предотвращения утечек памяти.
# maxsize=100 означает, что в памяти будет храниться история 100 последних используемых диалогов.
dialog_chats_cache: LRUCache = LRUCache(maxsize=100)

GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Конфигурация инструмента для поиска Google
GOOGLE_SEARCH_TOOL = {
    "tools": [{"google_search": {}}]
}


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
    Реализует механизм повторных попыток для временных ошибок.
    """
    headers = {'Content-Type': 'application/json'}
    params = {'key': api_key}

    # --- НОВЫЙ БЛОК: Настройки для повторных попыток ---
    max_retries = 3
    retry_delay = 2  # задержка в секундах

    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                request_args = {'params': params, 'headers': headers, 'timeout': aiohttp.ClientTimeout(total=60)}
                if payload:
                    request_args['json'] = payload

                async with session.request(method, url, **request_args) as response:
                    response_json = await response.json()
                    if response.status != 200:
                        error_details = response_json.get('error', {})
                        error_message = error_details.get('message', 'Неизвестная ошибка API')

                        # --- НОВЫЙ БЛОК: Логика повторных попыток ---
                        # Повторяем только для ошибок 5xx (проблемы на сервере) и 429 (превышение квот)
                        if response.status >= 500 or response.status == 429:
                            if attempt < max_retries - 1:
                                gemini_logger.warning(
                                    f"Попытка {attempt + 1}/{max_retries}: "
                                    f"Получена временная ошибка (HTTP {response.status}). "
                                    f"Повтор через {retry_delay} сек. Ошибка: {error_message}",
                                    extra={'user_id': 'System'}
                                )
                                await asyncio.sleep(retry_delay)
                                continue # Переходим к следующей попытке

                        # Если ошибка не временная или попытки закончились, выбрасываем исключение
                        gemini_logger.error(f"Ошибка API Gemini (HTTP {response.status}): {response_json}", extra={'user_id': 'System'})
                        raise GeminiAPIError(error_message, details=error_details)

                    return response_json # Успешный ответ

        except aiohttp.ClientError as e:
            gemini_logger.exception(f"Сетевая ошибка при запросе к Gemini API: {e}", extra={'user_id': 'System'})
            # Для сетевых ошибок тоже можно попробовать повторить
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                continue
            raise GeminiAPIError("Сетевая ошибка при подключении к сервису.", details={"error": {"message": "service_unavailable"}})
        except GeminiAPIError:
            # Пробрасываем "фатальные" ошибки API без повторных попыток
            raise
        except Exception as e:
            gemini_logger.exception(f"Неожиданная ошибка при выполнении запроса к Gemini API: {e}", extra={'user_id': 'System'})
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                continue
            raise GeminiAPIError(f"Неожиданная ошибка: {e}", details={"error": {"message": "unknown_error"}})

    # Этот код выполнится, только если все попытки провалились
    raise GeminiAPIError("Не удалось получить ответ от API после нескольких попыток.", details={"error": {"message": "service_unavailable"}})


async def _get_dialog_chat_history(dialog_id: int) -> List[Dict[str, Any]]:
    """
    Возвращает или создает историю чата для диалога из кэша или БД.
    """
    if dialog_id not in dialog_chats_cache:
        gemini_logger.debug(f"Кэш истории для dialog_id: {dialog_id} не найден. Загрузка из БД.")
        history_from_db = await db_manager.get_conversation_history(dialog_id, limit=20)
        gemini_history = []
        for item in history_from_db:
            role = 'user' if item.get('role') == 'user' else 'model'
            gemini_history.append({"role": role, "parts": [{"text": item.get('message_text', '')}]})
        dialog_chats_cache[dialog_id] = gemini_history
        gemini_logger.info(f"История для dialog_id: {dialog_id} загружена в кэш ({len(gemini_history)} сообщений).")
    return dialog_chats_cache[dialog_id]

def reset_dialog_chat(dialog_id: int):
    """Сбрасывает историю чата для конкретного диалога в кэше."""
    if dialog_id in dialog_chats_cache:
        del dialog_chats_cache[dialog_id]
        gemini_logger.info(f"История чата в кэше для dialog_id: {dialog_id} сброшена.")

async def _get_system_instruction_text(user_id: int) -> Optional[str]:
    """
    Формирует полный текст системной инструкции, включая персону/стиль
    и полное руководство по функциям бота на языке пользователя.
    """
    lang_code = await db_manager.get_user_language(user_id)
    
    # --- Часть 1: Инструкция по поведению (персона или стиль) ---
    persona_prompt = ""
    persona_id = await db_manager.get_user_persona(user_id)

    if persona_id != 'default':
        persona_info = BOT_PERSONAS.get(persona_id, BOT_PERSONAS['default'])
        prompt_key = f"prompt_{lang_code}"
        # Фоллбэк на русский, если для выбранного языка нет промпта
        persona_prompt = persona_info.get(prompt_key, persona_info.get('prompt_ru', ''))
    else:
        style_id = await db_manager.get_user_bot_style(user_id)
        if style_id != 'default':
            # Стили не локализованы, они всегда на английском
            style_prompts = {
                'formal': "You must answer in a strictly formal and business-like manner.",
                'informal': "You should communicate in a friendly and informal way.",
                'concise': "Your answers must be as short and to the point as possible.",
                'detailed': "Provide detailed and comprehensive answers, explaining all aspects."
            }
            persona_prompt = style_prompts.get(style_id, "")

    # --- Часть 2: Справка по боту для ответов на вопросы о себе ---
    full_guide_text = guide_manager.get_full_guide(lang_code)
    
    # Удаляем Markdown ссылки с картинками, чтобы не загромождать контекст
    full_guide_text = re.sub(r'!\[.*?\]\(.*?\)', '', full_guide_text)

    # --- Шаблоны промптов для разных языков ---
    prompt_templates = {
        'ru': f"""
---
Дополнительный контекст: Ты — Telegram-бот, и у тебя есть встроенные функции, описанные ниже. Используй эту информацию, чтобы отвечать на вопросы пользователя о твоих возможностях, командах или процессе получения API-ключа. Всегда отвечай от первого лица ("Я могу...", "Используй команду /settings...").

{full_guide_text}
---
""",
        'en': f"""
---
Additional context: You are a Telegram bot, and you have built-in features described below. Use this information to answer user questions about your capabilities, commands, or the process of obtaining an API key. Always answer in the first person ("I can...", "Use the /settings command...").

{full_guide_text}
---
"""
    }
    
    # Выбираем шаблон по языку пользователя, с фоллбэком на русский
    guide_prompt = prompt_templates.get(lang_code, prompt_templates['ru']).strip()

    # --- Сборка финального промпта ---
    final_prompt = ""
    if persona_prompt:
        final_prompt += persona_prompt.strip() + "\n\n"
    
    final_prompt += guide_prompt
    
    return final_prompt.strip() if final_prompt else None

async def generate_response(user_id: int, prompt: Union[str, List[Union[str, PIL.Image.Image]]]) -> str:
    """
    Генерирует ответ от Gemini, учитывая активный диалог и персону.
    Всегда пытается использовать поиск в интернете.
    """
    api_key = await db_manager.get_user_api_key(user_id)
    if not api_key:
        raise GeminiAPIError("API-ключ пользователя не найден.", details={"error": {"message": "API_KEY_NOT_FOUND"}})

    active_dialog_id = await db_manager.get_active_dialog_id(user_id)
    if not active_dialog_id:
        gemini_logger.error(f"У пользователя {user_id} нет активного диалога для генерации ответа.")
        raise GeminiAPIError("Не найден активный диалог. Пожалуйста, перезапустите бота командой /start.", details={})

    history = await _get_dialog_chat_history(active_dialog_id)
    model_name = await db_manager.get_user_gemini_model(user_id) or DEFAULT_MODEL_ID

    gemini_logger.info(f"Генерация ответа для user_id: {user_id}, диалог: {active_dialog_id}, модель: {model_name}, поиск: True", extra={'user_id': str(user_id)})

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
        if text_part:
            user_parts.append({"text": text_part})
        user_message_for_db = f"[Изображение] {text_part}".strip()

    request_contents.append({"role": "user", "parts": user_parts})

    await db_manager.store_message(user_id, active_dialog_id, 'user', user_message_for_db)

    url = f"{GEMINI_API_BASE_URL}/models/{model_name}:generateContent"

    # Собираем payload, по умолчанию включая инструмент поиска
    payload = {
        "contents": request_contents,
        "generationConfig": GENERATION_CONFIG,
        "safetySettings": SAFETY_SETTINGS,
        **GOOGLE_SEARCH_TOOL
    }

    system_instruction_text = await _get_system_instruction_text(user_id)
    if system_instruction_text:
        payload["system_instruction"] = { "parts": [{"text": system_instruction_text}] }

    try:
        response_json = await _make_gemini_request_async(api_key, url, payload)

    except GeminiAPIError as e:
        # Если ошибка связана с тем, что модель не поддерживает поиск,
        # попробуем сделать запрос еще раз, но уже без инструмента поиска.
        if e.error_key == "gemini_error_search_not_supported":
            gemini_logger.warning(f"Модель {model_name} не поддерживает поиск. Повторный запрос без tools.", extra={'user_id': str(user_id)})
            payload.pop("tools", None) # Удаляем ключ tools
            try:
                # Вторая попытка запроса
                response_json = await _make_gemini_request_async(api_key, url, payload)
            except GeminiAPIError as final_e:
                 if history: history.pop() # Удаляем неверный запрос из кеша
                 raise final_e # Пробрасываем ошибку второй попытки
        else:
            # Для всех других ошибок API
            if history: history.pop() # Удаляем неверный запрос из кеша
            raise e # Пробрасываем ошибку

    # Обработка успешного ответа (с первой или второй попытки)
    if not response_json or "candidates" not in response_json:
        raise GeminiAPIError("Ответ API не содержит 'candidates'.", details=response_json)

    if response_json["candidates"][0].get("finishReason") == "SAFETY":
         raise GeminiAPIError("Ответ заблокирован настройками безопасности.", details={"finish_reason": "SAFETY"})

    response_text = response_json["candidates"][0]["content"]["parts"][0]["text"].strip()

    history.append({"role": "user", "parts": user_parts})
    history.append({"role": "model", "parts": [{"text": response_text}]})

    usage_metadata = response_json.get('usageMetadata', {})
    prompt_tokens = usage_metadata.get('promptTokenCount', 0)
    completion_tokens = usage_metadata.get('candidatesTokenCount', 0)
    total_tokens = usage_metadata.get('totalTokenCount', 0)

    await db_manager.store_message(
        user_id=user_id,
        dialog_id=active_dialog_id,
        role='bot',
        message_text=response_text,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens
    )
    return response_text

async def generate_content_simple(api_key: str, prompt: str) -> str:
    """Генерирует ответ от Gemini без истории. Выбрасывает GeminiAPIError."""
    url = f"{GEMINI_API_BASE_URL}/models/{DEFAULT_MODEL_ID}:generateContent"
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    response_json = await _make_gemini_request_async(api_key, url, payload, 'POST')
    try:
        return response_json["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError) as e:
        raise GeminiAPIError(f"Ошибка чтения ответа от API: {e}", details={"error": {"message": "parsing_error"}})

async def validate_api_key(api_key: str) -> bool:
    """Проверяет валидность API-ключа."""
    url = f"{GEMINI_API_BASE_URL}/models/{DEFAULT_MODEL_ID}:countTokens"
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