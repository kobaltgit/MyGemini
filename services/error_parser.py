# File: services/error_parser.py
"""
Модуль для анализа ошибок Gemini API и преобразования их в понятные для пользователя ключи локализации.
"""
import json
from typing import Dict, Any

# Карта ключевых слов из ошибок API на ключи для файла локализации
ERROR_MAP = {
    # Ошибки, связанные с ключом и доступом
    "API_KEY_INVALID": "gemini_error_api_key_invalid",
    "API_KEY_NOT_FOUND": "gemini_error_api_key_invalid",
    "permission_denied": "gemini_error_permission_denied",
    "PERMISSION_DENIED": "gemini_error_permission_denied",

    # Ошибки, связанные с квотами и ресурсами
    "resource_exhausted": "gemini_error_quota_exceeded",
    "RESOURCE_EXHAUSTED": "gemini_error_quota_exceeded",
    "429": "gemini_error_quota_exceeded", # HTTP status code for too many requests

    # Ошибки безопасности (контент-фильтры)
    "finish_reason: SAFETY": "gemini_error_safety",
    "SAFETY": "gemini_error_safety",

    # Ошибки, связанные с недоступностью сервиса
    "service_unavailable": "gemini_error_unavailable",
    "model is overloaded": "gemini_error_unavailable",

    # Другие распространенные ошибки
    "Invalid argument": "gemini_error_invalid_argument",
    "invalid_argument": "gemini_error_invalid_argument",
}

DEFAULT_ERROR_KEY = "gemini_error_unknown"

def get_user_friendly_error_key(error_detail: Dict[str, Any]) -> str:
    """
    Анализирует JSON-объект ошибки от API и возвращает ключ для локализации.

    Args:
        error_detail: Словарь с деталями ошибки, полученный от API.

    Returns:
        Ключ строки из файла локализации.
    """
    if not isinstance(error_detail, dict):
        return DEFAULT_ERROR_KEY

    # Преобразуем весь словарь в строку для простого поиска ключевых слов
    error_str = json.dumps(error_detail).lower()

    for keyword, loc_key in ERROR_MAP.items():
        if keyword.lower() in error_str:
            return loc_key

    return DEFAULT_ERROR_KEY
