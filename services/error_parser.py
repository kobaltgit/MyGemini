# services/error_parser.py
"""
Модуль для анализа ошибок Gemini API и преобразования их в понятные для пользователя ключи локализации.
"""
import json
from typing import Dict, Any

# Карта ключевых слов из ошибок API на ключи для файла локализации
# Порядок важен: более специфичные ошибки должны идти раньше.
ERROR_MAP = {
    # --- Специфичная ошибка для поиска ---
    "tool is not supported": "gemini_error_search_not_supported",

    # --- Ошибки перегрузки модели и высокой нагрузки (503 / High demand) ---
    "high demand": "gemini_error_overloaded",
    "experiencing high demand": "gemini_error_overloaded",
    "model is overloaded": "gemini_error_overloaded",
    "overloaded": "gemini_error_overloaded",
    "unavailable": "gemini_error_overloaded",
    "service_unavailable": "gemini_error_overloaded",
    "503": "gemini_error_overloaded",

    # --- Модель устарела / удалена / не поддерживается ---
    "is not found": "gemini_error_model_deprecated",
    "was not found": "gemini_error_model_deprecated",
    "not supported for generatecontent": "gemini_error_model_deprecated",
    "call listmodels": "gemini_error_model_deprecated",
    "not found for api version": "gemini_error_model_deprecated",
    "model_not_found": "gemini_error_model_deprecated",
    "deprecated": "gemini_error_model_deprecated",

    # --- Блокировка фильтрами безопасности и авторских прав ---
    "recitation": "gemini_error_recitation",
    "finish_reason: safety": "gemini_error_safety",
    "safety": "gemini_error_safety",
    "blocklist": "gemini_error_safety",
    "prohibited_content": "gemini_error_safety",
    "spii": "gemini_error_safety",

    # --- Пустой ответ ---
    "empty_response": "gemini_error_empty_response",
    "no_parts": "gemini_error_empty_response",

    # --- Ошибка таймаута ---
    "service_timeout": "gemini_error_timeout",
    "deadline exceeded": "gemini_error_timeout",

    # --- Неверный API-ключ ---
    "api_key_invalid": "gemini_error_api_key_invalid",
    "api_key_not_found": "gemini_error_api_key_invalid",
    "api_key_not_valid": "gemini_error_api_key_invalid",
    "invalid api key": "gemini_error_api_key_invalid",

    # --- Квота (429) ---
    "resource_exhausted": "gemini_error_quota_exceeded",
    "quota exceeded": "gemini_error_quota_exceeded",
    "rate limit": "gemini_error_quota_exceeded",
    "429": "gemini_error_quota_exceeded",

    # --- Доступ запрещен ---
    "permission_denied": "gemini_error_permission_denied",

    # --- Некорректный запрос ---
    "invalid argument": "gemini_error_invalid_argument",
    "invalid_argument": "gemini_error_invalid_argument",
    "bad request": "gemini_error_invalid_argument",
}

# Ключ по умолчанию
DEFAULT_ERROR_KEY = "gemini_error_unknown"

def get_user_friendly_error_key(error_detail: Dict[str, Any]) -> str:
    """
    Анализирует JSON-объект ошибки от API и возвращает ключ для локализации.
    """
    if not isinstance(error_detail, dict):
        return DEFAULT_ERROR_KEY

    error_str = json.dumps(error_detail).lower()

    for keyword, loc_key in ERROR_MAP.items():
        if keyword.lower() in error_str:
            return loc_key

    return DEFAULT_ERROR_KEY