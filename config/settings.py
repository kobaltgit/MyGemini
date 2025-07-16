# File: config/settings.py
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()

# --- Telegram Bot Settings ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Необходимо установить переменную окружения BOT_TOKEN")

ADMIN_USER_ID_STR = os.getenv("ADMIN_USER_ID")
ADMIN_USER_ID = int(ADMIN_USER_ID_STR) if ADMIN_USER_ID_STR and ADMIN_USER_ID_STR.isdigit() else None

# --- Gemini API Settings ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-1.5-flash-latest")

# --- Database Settings ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_NAME = os.path.join(BASE_DIR, 'database', 'bot_database.db')

# --- Gemini Model Configuration ---
GENERATION_CONFIG = {
    "temperature": 0.8,
    "top_p": 1,
    "max_output_tokens": 8192,
}

SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

# НОВОЕ: --- Token Cost-Tracking Settings ---
# Цены указаны в USD за 1 миллион токенов.
# Источник: https://ai.google.dev/pricing
# Модель Flash: $0.35 за 1M входных, $1.05 за 1M выходных.
TOKEN_PRICING = {
    "default": { # Используется для gemini-1.5-flash-latest
        "input_usd_per_million": 0.35,
        "output_usd_per_million": 1.05
    },
    "gemini-1.5-pro-latest": {
        "input_usd_per_million": 3.50,
        "output_usd_per_million": 10.50
    }
}

# --- Bot Styles ---
BOT_STYLES = {
    'default': '🤖 По умолчанию / Default',
    'formal': '💼 Официальный / Formal',
    'informal': '☕️ Неформальный / Informal',
    'concise': '⚡️ Краткий / Concise',
    'detailed': '🔍 Подробный / Detailed'
}

# --- Language Selection (for translation feature) ---
TRANSLATE_LANGUAGES = {
    'ru': '🇷🇺 Русский', 'en': '🇺🇸 Английский', 'de': '🇩🇪 Немецкий',
    'fr': '🇫🇷 Французский', 'es': '🇪🇸 Испанский', 'it': '🇮🇹 Итальянский',
}

# --- Callback Data Prefixes ---
CALLBACK_IGNORE = 'ignore'
CALLBACK_REPORT_ERROR = 'report_error'
# Settings
CALLBACK_SETTINGS_STYLE_PREFIX = 'settings_style:'
CALLBACK_SETTINGS_LANG_PREFIX = 'settings_lang:'
CALLBACK_SETTINGS_SET_API_KEY = 'settings_set_api_key'
CALLBACK_SETTINGS_CHOOSE_MODEL_MENU = 'settings_choose_model_menu' # <-- НОВЫЙ ПРЕФИКС (открыть меню)
CALLBACK_SETTINGS_MODEL_PREFIX = 'settings_model:'          # <-- НОВЫЙ ПРЕФИКС (выбрать модель)
CALLBACK_SETTINGS_BACK_TO_MAIN = 'settings_back_to_main'      # <-- НОВЫЙ ПРЕФИКС (вернуться в осн. настройки)
# Language (for translation)
CALLBACK_LANG_PREFIX = 'lang:'
# Calendar (for history)
CALLBACK_CALENDAR_DATE_PREFIX = 'calendar_date:'
CALLBACK_CALENDAR_MONTH_PREFIX = 'calendar_month:'

# --- User States ---
STATE_WAITING_FOR_TRANSLATE_TEXT = 'waiting_for_translate_text'
STATE_WAITING_FOR_HISTORY_DATE = 'waiting_for_history_date'
STATE_WAITING_FOR_API_KEY = 'waiting_for_api_key'

print(f"Конфигурация MyGemini/settings.py загружена. Модель Gemini: {GEMINI_MODEL_NAME}")
